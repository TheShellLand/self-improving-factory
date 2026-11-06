#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
docker build -f "$PROJECT_DIR/Dockerfile.agent" -t "${SIFH_AGENT_IMAGE:-sifh_agent}" "$PROJECT_DIR"
