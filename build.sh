#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Build the SASIAS subagent runtime image
echo "Building SASIAS subagent image..."
docker build -t "${SASIAS_IMAGE:-sasias_runtime}" "$PROJECT_DIR"
if [ $? -eq 0 ]; then
    echo "Build Successful."
else
    echo "Build Failed."
    exit 1
fi
