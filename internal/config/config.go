package config

import (
	"fmt"
	"os"
)

type Config struct {
	ProjectID      string
	RepoName       string
	ReleaseTag     string
	CommitHash     string
	GiteaURL       string
	GiteaToken     string
	MinioEndpoint  string
	MinioAccessKey string
	MinioSecretKey string
	MinioBucket    string
	MinioUseSSL    bool
	OrchestratorURL string
	CallbackURL    string
	CallbackPath   string
}

func Load() (*Config, error) {
	cfg := &Config{
		ProjectID:       os.Getenv("PROJECT_ID"),
		RepoName:        os.Getenv("REPO_NAME"),
		ReleaseTag:      os.Getenv("RELEASE_TAG"),
		CommitHash:      os.Getenv("COMMIT_HASH"),
		GiteaURL:        getenv("GITEA_URL", "http://gitea-web.scadable-core.svc.cluster.local:3000"),
		GiteaToken:      os.Getenv("GITEA_TOKEN"),
		MinioEndpoint:   getenv("MINIO_ENDPOINT", "minio.scadable-edge.svc.cluster.local:9000"),
		MinioAccessKey:  os.Getenv("MINIO_ACCESS_KEY"),
		MinioSecretKey:  os.Getenv("MINIO_SECRET_KEY"),
		MinioBucket:     getenv("MINIO_BUCKET", "configs"),
		MinioUseSSL:     os.Getenv("MINIO_USE_SSL") == "true",
		OrchestratorURL: getenv("ORCHESTRATOR_URL", "http://service-orchestrator.scadable-core.svc.cluster.local:8085"),
		CallbackURL:     getenv("CALLBACK_URL", "http://service-app.scadable-app.svc.cluster.local"),
		CallbackPath:    getenv("CALLBACK_PATH", "/api/webhooks/compiler"),
	}

	if cfg.ProjectID == "" {
		return nil, fmt.Errorf("PROJECT_ID is required")
	}
	if cfg.RepoName == "" {
		return nil, fmt.Errorf("REPO_NAME is required")
	}
	if cfg.ReleaseTag == "" {
		return nil, fmt.Errorf("RELEASE_TAG is required")
	}
	if cfg.GiteaToken == "" {
		return nil, fmt.Errorf("GITEA_TOKEN is required")
	}

	return cfg, nil
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
