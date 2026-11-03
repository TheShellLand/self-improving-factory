#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Opens an interactive bash shell in the sifh_runtime container
IMAGE="${SIFH_IMAGE:-sifh_runtime}"

echo "Entering test shell... Type 'exit' to leave."
docker run -it --rm \
    --network host \
    -e SIFH_VIEWPORT="1920x1080" \
    -v "$PROJECT_DIR:/app" \
    -w /app \
    "$IMAGE" /bin/bash
