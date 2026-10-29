#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Execute an agent-specific command (or keep alive) within a sandbox
IMAGE="${SIF_IMAGE:-sif_runtime}"
CONTAINER_NAME="subagent_$(date +%s)"

echo "Starting subagent $CONTAINER_NAME..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --network host \
    -e SIF_VIEWPORT="1920x1080" \
    -v "$PROJECT_DIR:/app" \
    -w /app \
    "$IMAGE" tail -f /dev/null

if [ $? -eq 0 ]; then
    echo "Subagent started successfully. Container ID: $CONTAINER_NAME."
else
    echo "Failed to start container."
fi
