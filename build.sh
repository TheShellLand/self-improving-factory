#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Build the SIFH subagent runtime image
echo "Building SIFH subagent image..."
docker build -t "${SIFH_IMAGE:-sifh_runtime}" "$PROJECT_DIR"
if [ $? -eq 0 ]; then
    echo "Build Successful."
else
    echo "Build Failed."
    exit 1
fi
