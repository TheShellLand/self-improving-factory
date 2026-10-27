#!/bin/bash
# Opens an interactive bash shell in the SASIAS runtime container
IMAGE="sasias_runtime"

echo "Entering test shell... Type 'exit' to leave."
docker run -it --rm \
    --network host \
    -e SASIAS_VIEWPORT="1920x1080" \
    -v $(pwd):/app \
    -w /app \
    "$IMAGE" /bin/bash
