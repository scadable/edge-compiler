package main

import (
	"context"
	"fmt"
	"os"
	"time"

	"edge-compiler/internal/config"
	"edge-compiler/internal/converter"
	"edge-compiler/internal/git"
	"edge-compiler/internal/notifier"
	"edge-compiler/internal/packager"
)

func main() {
	fmt.Println("=== Scadable Edge Compiler ===")
	start := time.Now()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	// Step 1: Load configuration
	fmt.Println("[1/5] Loading configuration...")
	cfg, err := config.Load()
	if err != nil {
		fail(cfg, fmt.Sprintf("configuration error: %v", err))
	}
	fmt.Printf("  Project: %s\n  Repo: %s\n  Tag: %s\n", cfg.ProjectID, cfg.RepoName, cfg.ReleaseTag)

	// Step 2: Clone repository
	fmt.Println("[2/5] Cloning repository...")
	repoDir, err := os.MkdirTemp("", "compiler-repo-*")
	if err != nil {
		fail(cfg, fmt.Sprintf("failed to create temp dir: %v", err))
	}
	defer os.RemoveAll(repoDir)

	commitHash, err := git.Clone(cfg.GiteaURL, cfg.GiteaToken, cfg.ProjectID, cfg.RepoName, cfg.ReleaseTag, repoDir)
	if err != nil {
		fail(cfg, fmt.Sprintf("clone failed: %v", err))
	}
	if cfg.CommitHash == "" {
		cfg.CommitHash = commitHash
	}
	fmt.Printf("  Cloned at commit: %s\n", commitHash[:8])

	// Step 3: Convert Python to device configs
	fmt.Println("[3/5] Converting Python device definitions...")
	devices, err := converter.ConvertPythonToDevices(repoDir)
	if err != nil {
		fail(cfg, fmt.Sprintf("conversion failed: %v", err))
	}
	fmt.Printf("  Found %d device(s)\n", len(devices))
	for _, d := range devices {
		fmt.Printf("    - %s (%s)\n", d.DeviceID, d.Protocol)
	}

	if len(devices) == 0 {
		fail(cfg, "no device definitions found in repository")
	}

	// Step 4: Package and upload to MinIO
	fmt.Println("[4/5] Packaging and uploading to MinIO...")
	result, err := packager.Package(
		ctx,
		cfg.ProjectID, cfg.ReleaseTag, cfg.CommitHash,
		devices,
		cfg.MinioEndpoint, cfg.MinioAccessKey, cfg.MinioSecretKey, cfg.MinioBucket,
		cfg.MinioUseSSL,
	)
	if err != nil {
		fail(cfg, fmt.Sprintf("packaging failed: %v", err))
	}
	fmt.Printf("  Manifest: %s\n", result.ManifestURL)
	fmt.Printf("  Drivers: %v\n", result.DriversNeeded)

	// Step 5: Notify orchestrator
	fmt.Println("[5/5] Notifying orchestrator...")
	notifyResult := &notifier.CompileResult{
		ProjectID:     cfg.ProjectID,
		ReleaseTag:    cfg.ReleaseTag,
		CommitHash:    cfg.CommitHash,
		Status:        "success",
		ManifestURL:   result.ManifestURL,
		DevicesCount:  result.DevicesCount,
		DriversNeeded: result.DriversNeeded,
	}
	if err := notifier.Notify(cfg.CallbackURL, cfg.CallbackPath, notifyResult); err != nil {
		// Non-fatal — artifacts are uploaded even if notification fails
		fmt.Fprintf(os.Stderr, "WARNING: orchestrator notification failed: %v\n", err)
	}

	elapsed := time.Since(start)
	fmt.Printf("\n✅ Compilation complete in %s\n", elapsed.Round(time.Millisecond))
	fmt.Printf("   %d devices, %d drivers\n", result.DevicesCount, len(result.DriversNeeded))
}

// fail notifies the orchestrator of failure and exits.
func fail(cfg *config.Config, message string) {
	fmt.Fprintf(os.Stderr, "❌ ERROR: %s\n", message)

	// Try to notify orchestrator of failure
	if cfg != nil && cfg.OrchestratorURL != "" {
		result := &notifier.CompileResult{
			ProjectID:  cfg.ProjectID,
			ReleaseTag: cfg.ReleaseTag,
			CommitHash: cfg.CommitHash,
			Status:     "failed",
			Error:      message,
		}
		_ = notifier.Notify(cfg.CallbackURL, cfg.CallbackPath, result)
	}

	os.Exit(1)
}
