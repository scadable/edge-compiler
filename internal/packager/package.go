package packager

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
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
	ProjectID     string             `json:"project_id"`
	ReleaseTag    string             `json:"release_tag"`
	CommitHash    string             `json:"commit_hash"`
	CompiledAt    string             `json:"compiled_at"`
	Devices       []ManifestDevice   `json:"devices"`
	Storage       []ManifestResource `json:"storage"`
	Outbound      []ManifestResource `json:"outbound"`
	Controllers   []ManifestResource `json:"controllers"`
	DriversNeeded []string           `json:"drivers_needed"`
}

// ManifestDevice represents a device entry in the manifest.
type ManifestDevice struct {
	DeviceID   string `json:"device_id"`
	Protocol   string `json:"protocol"`
	ConfigPath string `json:"config_path"`
	ConfigHash string `json:"config_hash"`
}

// ManifestResource represents a storage/outbound/controller entry in the manifest.
type ManifestResource struct {
	ID         string `json:"id"`
	ConfigPath string `json:"config_path"`
	ConfigHash string `json:"config_hash"`
	SourcePath string `json:"source_path,omitempty"`
}

// PackageResult holds the result of packaging.
type PackageResult struct {
	ManifestURL      string
	DevicesCount     int
	StorageCount     int
	OutboundCount    int
	ControllersCount int
	DriversNeeded    []string
}

// Package writes YAML configs, generates manifest, and uploads everything to MinIO.
func Package(
	ctx context.Context,
	projectID, releaseTag, commitHash string,
	result *converter.ConvertResult,
	repoDir string,
	minioEndpoint, accessKey, secretKey, bucket string,
	useSSL bool,
) (*PackageResult, error) {
	client, err := minio.New(minioEndpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(accessKey, secretKey, ""),
		Secure: useSSL,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create MinIO client: %w", err)
	}

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

	tmpDir, err := os.MkdirTemp("", "compiler-*")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp dir: %w", err)
	}
	defer os.RemoveAll(tmpDir)

	driversSet := make(map[string]bool)
	var manifestDevices []ManifestDevice
	var manifestStorage []ManifestResource
	var manifestOutbound []ManifestResource
	var manifestControllers []ManifestResource

	// Package devices
	for _, device := range result.Devices {
		hash, err := writeAndUpload(ctx, client, bucket, tmpDir, projectID, releaseTag,
			fmt.Sprintf("devices/%s", device.DeviceID), "config.yaml", device)
		if err != nil {
			return nil, fmt.Errorf("device %s: %w", device.DeviceID, err)
		}

		driverName := converter.DriverName(device.Protocol)
		driversSet[driverName] = true

		manifestDevices = append(manifestDevices, ManifestDevice{
			DeviceID:   device.DeviceID,
			Protocol:   device.Protocol,
			ConfigPath: fmt.Sprintf("devices/%s/config.yaml", device.DeviceID),
			ConfigHash: hash,
		})
	}

	// Package storage
	for _, storage := range result.Storage {
		hash, err := writeAndUpload(ctx, client, bucket, tmpDir, projectID, releaseTag,
			fmt.Sprintf("storage/%s", storage.ID), "config.yaml", storage)
		if err != nil {
			return nil, fmt.Errorf("storage %s: %w", storage.ID, err)
		}
		manifestStorage = append(manifestStorage, ManifestResource{
			ID:         storage.ID,
			ConfigPath: fmt.Sprintf("storage/%s/config.yaml", storage.ID),
			ConfigHash: hash,
		})
	}

	// Package outbound
	for _, outbound := range result.Outbound {
		hash, err := writeAndUpload(ctx, client, bucket, tmpDir, projectID, releaseTag,
			fmt.Sprintf("outbound/%s", outbound.ID), "config.yaml", outbound)
		if err != nil {
			return nil, fmt.Errorf("outbound %s: %w", outbound.ID, err)
		}
		manifestOutbound = append(manifestOutbound, ManifestResource{
			ID:         outbound.ID,
			ConfigPath: fmt.Sprintf("outbound/%s/config.yaml", outbound.ID),
			ConfigHash: hash,
		})
	}

	// Package controllers (config.yaml + source.py)
	for _, ctrl := range result.Controllers {
		hash, err := writeAndUpload(ctx, client, bucket, tmpDir, projectID, releaseTag,
			fmt.Sprintf("controllers/%s", ctrl.ID), "config.yaml", ctrl)
		if err != nil {
			return nil, fmt.Errorf("controller %s: %w", ctrl.ID, err)
		}

		entry := ManifestResource{
			ID:         ctrl.ID,
			ConfigPath: fmt.Sprintf("controllers/%s/config.yaml", ctrl.ID),
			ConfigHash: hash,
		}

		// Upload the raw Python source file
		if ctrl.SourceFile != "" {
			sourcePath := filepath.Join(repoDir, ctrl.SourceFile)
			if _, err := os.Stat(sourcePath); err == nil {
				sourceObject := fmt.Sprintf("%s/releases/%s/controllers/%s/source.py", projectID, releaseTag, ctrl.ID)
				if _, err := client.FPutObject(ctx, bucket, sourceObject, sourcePath, minio.PutObjectOptions{
					ContentType: "text/x-python",
				}); err != nil {
					return nil, fmt.Errorf("controller %s: failed to upload source: %w", ctrl.ID, err)
				}
				// Also upload to latest
				latestSource := fmt.Sprintf("%s/latest/controllers/%s/source.py", projectID, ctrl.ID)
				client.FPutObject(ctx, bucket, latestSource, sourcePath, minio.PutObjectOptions{
					ContentType: "text/x-python",
				})
				entry.SourcePath = fmt.Sprintf("controllers/%s/source.py", ctrl.ID)
				fmt.Printf("Uploaded: %s/%s\n", bucket, sourceObject)
			}
		}

		manifestControllers = append(manifestControllers, entry)
	}

	// Collect drivers
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
		Storage:       manifestStorage,
		Outbound:      manifestOutbound,
		Controllers:   manifestControllers,
		DriversNeeded: drivers,
	}

	manifestBytes, err := json.Marshal(manifest)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal manifest: %w", err)
	}

	manifestFilePath := filepath.Join(tmpDir, "manifest.json")
	if err := os.WriteFile(manifestFilePath, manifestBytes, 0o644); err != nil {
		return nil, fmt.Errorf("failed to write manifest: %w", err)
	}

	// Upload manifest (versioned + latest)
	manifestObject := fmt.Sprintf("%s/releases/%s/manifest.json", projectID, releaseTag)
	if _, err := client.FPutObject(ctx, bucket, manifestObject, manifestFilePath, minio.PutObjectOptions{
		ContentType: "application/json",
	}); err != nil {
		return nil, fmt.Errorf("failed to upload manifest: %w", err)
	}
	fmt.Printf("Uploaded: %s/%s\n", bucket, manifestObject)

	latestManifest := fmt.Sprintf("%s/latest/manifest.json", projectID)
	client.FPutObject(ctx, bucket, latestManifest, manifestFilePath, minio.PutObjectOptions{
		ContentType: "application/json",
	})

	manifestURL := fmt.Sprintf("https://get.scadable.com/%s/%s", bucket, manifestObject)
	if strings.Contains(minioEndpoint, "svc.cluster.local") {
		manifestURL = fmt.Sprintf("http://%s/%s/%s", minioEndpoint, bucket, manifestObject)
	}

	return &PackageResult{
		ManifestURL:      manifestURL,
		DevicesCount:     len(result.Devices),
		StorageCount:     len(result.Storage),
		OutboundCount:    len(result.Outbound),
		ControllersCount: len(result.Controllers),
		DriversNeeded:    drivers,
	}, nil
}

// writeAndUpload marshals data to YAML, writes to temp dir, uploads to MinIO, returns SHA256 hash.
func writeAndUpload(
	ctx context.Context, client *minio.Client, bucket, tmpDir, projectID, releaseTag, subPath, filename string, data interface{},
) (string, error) {
	yamlBytes, err := yaml.Marshal(data)
	if err != nil {
		return "", fmt.Errorf("failed to marshal YAML: %w", err)
	}

	localDir := filepath.Join(tmpDir, subPath)
	if err := os.MkdirAll(localDir, 0o755); err != nil {
		return "", fmt.Errorf("failed to create dir: %w", err)
	}

	localPath := filepath.Join(localDir, filename)
	if err := os.WriteFile(localPath, yamlBytes, 0o644); err != nil {
		return "", fmt.Errorf("failed to write file: %w", err)
	}

	hash := sha256.Sum256(yamlBytes)
	hashStr := hex.EncodeToString(hash[:])

	// Upload versioned
	objectPath := fmt.Sprintf("%s/releases/%s/%s/%s", projectID, releaseTag, subPath, filename)
	if _, err := client.FPutObject(ctx, bucket, objectPath, localPath, minio.PutObjectOptions{
		ContentType: "text/yaml",
	}); err != nil {
		return "", fmt.Errorf("failed to upload: %w", err)
	}
	fmt.Printf("Uploaded: %s/%s\n", bucket, objectPath)

	// Upload latest
	latestPath := fmt.Sprintf("%s/latest/%s/%s", projectID, subPath, filename)
	client.FPutObject(ctx, bucket, latestPath, localPath, minio.PutObjectOptions{
		ContentType: "text/yaml",
	})

	return hashStr, nil
}
