package packager

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"gopkg.in/yaml.v3"

	"edge-compiler/internal/converter"
)

// Manifest is the release manifest uploaded to MinIO.
type Manifest struct {
	ProjectID    string           `json:"project_id" yaml:"project_id"`
	ReleaseTag   string           `json:"release_tag" yaml:"release_tag"`
	CommitHash   string           `json:"commit_hash" yaml:"commit_hash"`
	CompiledAt   string           `json:"compiled_at" yaml:"compiled_at"`
	Devices      []ManifestDevice `json:"devices" yaml:"devices"`
	DriversNeeded []string        `json:"drivers_needed" yaml:"drivers_needed"`
}

// ManifestDevice represents a device entry in the manifest.
type ManifestDevice struct {
	DeviceID   string `json:"device_id" yaml:"device_id"`
	Protocol   string `json:"protocol" yaml:"protocol"`
	ConfigPath string `json:"config_path" yaml:"config_path"`
	ConfigHash string `json:"config_hash" yaml:"config_hash"`
}

// PackageResult holds the result of packaging.
type PackageResult struct {
	ManifestURL   string
	DevicesCount  int
	DriversNeeded []string
}

// Package writes YAML configs, generates manifest, and uploads everything to MinIO.
func Package(
	ctx context.Context,
	projectID, releaseTag, commitHash string,
	devices []converter.DeviceConfig,
	minioEndpoint, accessKey, secretKey, bucket string,
	useSSL bool,
) (*PackageResult, error) {
	// Create MinIO client
	client, err := minio.New(minioEndpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(accessKey, secretKey, ""),
		Secure: useSSL,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create MinIO client: %w", err)
	}

	// Ensure bucket exists
	exists, err := client.BucketExists(ctx, bucket)
	if err != nil {
		return nil, fmt.Errorf("failed to check bucket: %w", err)
	}
	if !exists {
		if err := client.MakeBucket(ctx, bucket, minio.MakeBucketOptions{}); err != nil {
			return nil, fmt.Errorf("failed to create bucket: %w", err)
		}
		fmt.Printf("Created bucket: %s\n", bucket)
	}

	// Create temp directory for YAML files
	tmpDir, err := os.MkdirTemp("", "compiler-*")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp dir: %w", err)
	}
	defer os.RemoveAll(tmpDir)

	// Write YAML configs and collect manifest entries
	driversSet := make(map[string]bool)
	var manifestDevices []ManifestDevice

	for _, device := range devices {
		// Write config.yaml
		deviceDir := filepath.Join(tmpDir, "devices", device.DeviceID)
		if err := os.MkdirAll(deviceDir, 0o755); err != nil {
			return nil, fmt.Errorf("failed to create device dir: %w", err)
		}

		yamlBytes, err := yaml.Marshal(device)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal device %s: %w", device.DeviceID, err)
		}

		configPath := filepath.Join(deviceDir, "config.yaml")
		if err := os.WriteFile(configPath, yamlBytes, 0o644); err != nil {
			return nil, fmt.Errorf("failed to write config: %w", err)
		}

		// Hash
		hash := sha256.Sum256(yamlBytes)
		hashStr := hex.EncodeToString(hash[:])

		// Track driver
		driverName := converter.DriverName(device.Protocol)
		driversSet[driverName] = true

		manifestDevices = append(manifestDevices, ManifestDevice{
			DeviceID:   device.DeviceID,
			Protocol:   device.Protocol,
			ConfigPath: fmt.Sprintf("devices/%s/config.yaml", device.DeviceID),
			ConfigHash: hashStr,
		})

		// Upload config to MinIO (versioned)
		objectPath := fmt.Sprintf("%s/releases/%s/devices/%s/config.yaml", projectID, releaseTag, device.DeviceID)
		if _, err := client.FPutObject(ctx, bucket, objectPath, configPath, minio.PutObjectOptions{
			ContentType: "text/yaml",
		}); err != nil {
			return nil, fmt.Errorf("failed to upload config for %s: %w", device.DeviceID, err)
		}
		fmt.Printf("Uploaded: %s/%s\n", bucket, objectPath)

		// Also upload to latest
		latestPath := fmt.Sprintf("%s/latest/devices/%s/config.yaml", projectID, device.DeviceID)
		if _, err := client.FPutObject(ctx, bucket, latestPath, configPath, minio.PutObjectOptions{
			ContentType: "text/yaml",
		}); err != nil {
			return nil, fmt.Errorf("failed to upload latest config for %s: %w", device.DeviceID, err)
		}
	}

	// Collect drivers list
	var drivers []string
	for d := range driversSet {
		drivers = append(drivers, d)
	}

	// Generate manifest
	manifest := Manifest{
		ProjectID:     projectID,
		ReleaseTag:    releaseTag,
		CommitHash:    commitHash,
		CompiledAt:    time.Now().UTC().Format(time.RFC3339),
		Devices:       manifestDevices,
		DriversNeeded: drivers,
	}

	manifestBytes, err := yaml.Marshal(manifest)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal manifest: %w", err)
	}

	manifestPath := filepath.Join(tmpDir, "manifest.json")
	if err := os.WriteFile(manifestPath, manifestBytes, 0o644); err != nil {
		return nil, fmt.Errorf("failed to write manifest: %w", err)
	}

	// Upload manifest (versioned)
	manifestObject := fmt.Sprintf("%s/releases/%s/manifest.json", projectID, releaseTag)
	if _, err := client.FPutObject(ctx, bucket, manifestObject, manifestPath, minio.PutObjectOptions{
		ContentType: "application/json",
	}); err != nil {
		return nil, fmt.Errorf("failed to upload manifest: %w", err)
	}
	fmt.Printf("Uploaded: %s/%s\n", bucket, manifestObject)

	// Upload manifest (latest)
	latestManifest := fmt.Sprintf("%s/latest/manifest.json", projectID)
	if _, err := client.FPutObject(ctx, bucket, latestManifest, manifestPath, minio.PutObjectOptions{
		ContentType: "application/json",
	}); err != nil {
		return nil, fmt.Errorf("failed to upload latest manifest: %w", err)
	}

	// Build manifest URL (public)
	manifestURL := fmt.Sprintf("https://get.scadable.com/%s/%s", bucket, manifestObject)
	// If using internal MinIO, use internal URL
	if strings.Contains(minioEndpoint, "svc.cluster.local") {
		manifestURL = fmt.Sprintf("http://%s/%s/%s", minioEndpoint, bucket, manifestObject)
	}

	return &PackageResult{
		ManifestURL:   manifestURL,
		DevicesCount:  len(devices),
		DriversNeeded: drivers,
	}, nil
}
