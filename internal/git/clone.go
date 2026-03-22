package git

import (
	"fmt"
	"net/url"
	"os"
	"os/exec"
	"strings"
)

// Clone clones a Gitea repository at a specific tag into destDir.
// Returns the commit hash at HEAD.
func Clone(giteaURL, token, orgName, repoName, tag, destDir string) (string, error) {
	// Build authenticated clone URL
	u, err := url.Parse(giteaURL)
	if err != nil {
		return "", fmt.Errorf("invalid gitea URL: %w", err)
	}
	u.User = url.UserPassword("oauth2", token)
	u.Path = fmt.Sprintf("/%s/%s.git", orgName, repoName)

	cloneURL := u.String()

	// Clone at specific tag, shallow
	cmd := exec.Command("git", "clone", "--branch", tag, "--depth", "1", cloneURL, destDir)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("git clone failed: %w", err)
	}

	// Get commit hash
	hashCmd := exec.Command("git", "rev-parse", "HEAD")
	hashCmd.Dir = destDir
	out, err := hashCmd.Output()
	if err != nil {
		return "", fmt.Errorf("git rev-parse failed: %w", err)
	}

	return strings.TrimSpace(string(out)), nil
}
