#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Opens an interactive bash shell in the SASIAS runtime container
IMAGE="${SASIAS_IMAGE:-sasias_runtime}"

echo "Entering test shell... Type 'exit' to leave."
docker run -it --rm \
    --network host \
    -e SASIAS_VIEWPORT="1920x1080" \
    -v "$PROJECT_DIR:/app" \
    -w /app \
    "$IMAGE" /bin/bash
