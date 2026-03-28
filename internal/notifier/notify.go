package notifier

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// CompileResult is the payload sent to the orchestrator callback.
type CompileResult struct {
	ProjectID        string   `json:"project_id"`
	ReleaseTag       string   `json:"release_tag"`
	CommitHash       string   `json:"commit_hash"`
	Status           string   `json:"status"` // "success" or "failed"
	ManifestURL      string   `json:"manifest_url,omitempty"`
	DevicesCount     int      `json:"devices_count"`
	StorageCount     int      `json:"storage_count"`
	OutboundCount    int      `json:"outbound_count"`
	ControllersCount int      `json:"controllers_count"`
	DriversNeeded    []string `json:"drivers_needed,omitempty"`
	Error            string   `json:"error,omitempty"`
}

// Notify sends the compile result to the orchestrator.
func Notify(orchestratorURL, callbackPath string, result *CompileResult) error {
	url := orchestratorURL + callbackPath

	body, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("callback request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("callback returned status %d", resp.StatusCode)
	}

	fmt.Printf("Notified orchestrator: %s (status: %s)\n", url, result.Status)
	return nil
}
