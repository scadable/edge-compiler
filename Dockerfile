FROM golang:1.25.7-alpine AS builder
RUN apk add --no-cache git
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o compiler ./cmd/compiler

FROM python:3.12-slim
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/compiler /usr/local/bin/compiler
COPY scripts/convert.py /usr/local/bin/convert.py
COPY sdk/ /opt/scadable-sdk/
RUN pip install --no-cache-dir /opt/scadable-sdk/ && rm -rf /opt/scadable-sdk/
RUN chmod +x /usr/local/bin/convert.py
ENTRYPOINT ["compiler"]
