#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Opens an interactive bash shell in the sif_runtime container
IMAGE="${SIF_IMAGE:-sif_runtime}"

echo "Entering test shell... Type 'exit' to leave."
docker run -it --rm \
    --network host \
    -e SIF_VIEWPORT="1920x1080" \
    -v "$PROJECT_DIR:/app" \
    -w /app \
    "$IMAGE" /bin/bash
