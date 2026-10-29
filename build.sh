#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Build the SIF subagent runtime image
echo "Building SIF subagent image..."
docker build -t "${SIF_IMAGE:-sif_runtime}" "$PROJECT_DIR"
if [ $? -eq 0 ]; then
    echo "Build Successful."
else
    echo "Build Failed."
    exit 1
fi
