# edge-compiler TODO

## Overview

A Go service that runs as a **K8s Job** — triggered when a user creates a release on a project. It clones the project repo, validates the config files, packages them, uploads to MinIO, and notifies the orchestrator. The job terminates after completion.

It does NOT run as a persistent service. It's a short-lived worker.

---

## How It Gets Triggered

1. User clicks "Create Release" in the dashboard
2. service-app creates a Git tag on the Gitea repo
3. service-app calls orchestrator: `POST /internal/releases` with `{project_id, tag, name, description, commit_hash}`
4. Orchestrator creates a K8s Job: `edge-compiler-{project_id}-{tag}`
5. The job runs, compiles, uploads, notifies, and terminates

## What It Does (Step by Step)

```
1. Read environment variables:
   - PROJECT_ID (namespace UUID)
   - REPO_NAME (project UUID)
   - RELEASE_TAG (e.g., "v1.0")
   - COMMIT_HASH
   - GITEA_URL (internal: http://gitea-web.scadable-core.svc.cluster.local:3000)
   - GITEA_TOKEN
   - MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
   - ORCHESTRATOR_URL (internal: http://service-orchestrator.scadable-core.svc.cluster.local:8085)
   - ORCHESTRATOR_INTERNAL_KEY (for callback)

2. Clone the repo at the specific tag:
   git clone --branch {RELEASE_TAG} --depth 1 https://{GITEA_TOKEN}@{GITEA_URL}/{PROJECT_ID}/{REPO_NAME}.git

3. Scan for device configs:
   - Walk the repo looking for config.yaml files
   - Expected structure:
     devices/
       modbus-sim/
         config.yaml
       temperature-sensor/
         config.yaml
     .scadable.yaml (optional manifest)

4. Validate each config.yaml:
   - Parse as YAML
   - Verify required fields: device_id, protocol, connection
   - Verify connection has required fields for the protocol:
     - modbus-tcp: host, port
     - modbus-rtu: serial_port
   - Verify frequency is > 0
   - If .scadable.yaml exists, validate it too

5. Generate manifest.json:
   {
     "project_id": "...",
     "release_tag": "v1.0",
     "commit_hash": "abc123",
     "compiled_at": "2026-03-21T...",
     "devices": [
       {
         "device_id": "modbus-sim",
         "protocol": "modbus-tcp",
         "config_path": "devices/modbus-sim/config.yaml",
         "config_hash": "sha256:..."
       }
     ],
     "drivers_needed": ["driver-modbus"]
   }

6. Upload to MinIO:
   Bucket: configs
   Path structure:
     configs/{project_id}/releases/{tag}/manifest.json
     configs/{project_id}/releases/{tag}/devices/modbus-sim/config.yaml
     configs/{project_id}/releases/{tag}/devices/temperature-sensor/config.yaml
   Also copy to "latest":
     configs/{project_id}/latest/manifest.json
     configs/{project_id}/latest/devices/...

7. Notify orchestrator (callback):
   POST {ORCHESTRATOR_URL}/internal/releases/compiled
   {
     "project_id": "...",
     "release_tag": "v1.0",
     "commit_hash": "abc123",
     "status": "success",
     "manifest_url": "https://get.scadable.com/configs/{project_id}/releases/{tag}/manifest.json",
     "devices_count": 2,
     "drivers_needed": ["driver-modbus"],
     "error": ""  // or error message if failed
   }

8. Exit 0 on success, exit 1 on failure
```

## Project Structure

```
edge-compiler/
├── cmd/
│   └── compiler/
│       └── main.go          # Entry point
├── internal/
│   ├── config/
│   │   └── config.go        # Load env vars
│   ├── git/
│   │   └── clone.go         # Clone repo at tag
│   ├── validator/
│   │   └── validate.go      # Validate config.yaml files
│   ├── packager/
│   │   └── package.go       # Generate manifest, upload to MinIO
│   └── notifier/
│       └── notify.go        # Callback to orchestrator
├── go.mod
├── go.sum
├── Dockerfile
└── .github/
    └── workflows/
        └── cd-build.yaml    # Build and push to DOCR
```

## Dockerfile

```dockerfile
FROM golang:1.25.7-alpine AS builder
RUN apk add --no-cache git
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o compiler ./cmd/compiler

FROM alpine:latest
RUN apk add --no-cache ca-certificates git
COPY --from=builder /app/compiler /usr/local/bin/compiler
ENTRYPOINT ["compiler"]
```

Note: needs `git` in the runtime image for cloning.

## Dependencies

```
github.com/minio/minio-go/v7   # MinIO client
gopkg.in/yaml.v3                # YAML parsing/validation
```

No gRPC, no database, no HTTP server. Just a CLI tool that reads env vars, does work, and exits.

## Error Handling

- If clone fails → exit 1, notify orchestrator with error
- If validation fails → exit 1, notify with error (include which file and why)
- If MinIO upload fails → exit 1, notify with error
- If orchestrator callback fails → log error but still exit 0 (the artifacts are uploaded)
- Always try to notify orchestrator, even on failure

## K8s Job Template (created by orchestrator)

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: compile-{project_id_short}-{tag}
  namespace: scadable-core
  labels:
    app: edge-compiler
    project: {project_id}
    release: {tag}
spec:
  ttlSecondsAfterFinished: 300  # clean up after 5 minutes
  backoffLimit: 1                # retry once on failure
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: compiler
        image: registry.digitalocean.com/scadable/edge-compiler:latest
        env:
        - name: PROJECT_ID
          value: "{project_id}"
        - name: REPO_NAME
          value: "{repo_name}"
        - name: RELEASE_TAG
          value: "{tag}"
        - name: COMMIT_HASH
          value: "{commit_hash}"
        - name: GITEA_URL
          value: "http://gitea-web.scadable-core.svc.cluster.local:3000"
        - name: GITEA_TOKEN
          value: "{gitea_token}"
        - name: MINIO_ENDPOINT
          value: "minio.scadable-edge.svc.cluster.local:9000"
        - name: MINIO_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: minio
              key: rootUser
        - name: MINIO_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: minio
              key: rootPassword
        - name: MINIO_BUCKET
          value: "configs"
        - name: ORCHESTRATOR_URL
          value: "http://service-orchestrator.scadable-core.svc.cluster.local:8085"
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
```

## Test: `go build ./cmd/compiler`
