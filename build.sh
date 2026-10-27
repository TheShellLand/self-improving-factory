#!/bin/bash
# Build the SASIAS subagent runtime image
echo "Building SASIAS subagent image..."
docker build -t sasias_runtime .
if [ $? -eq 0 ]; then
    echo "Build Successful."
else
    echo "Build Failed."
    exit 1
fi
