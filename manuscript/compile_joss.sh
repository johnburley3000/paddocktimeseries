#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

docker run --rm \
  --platform linux/amd64 \
  --volume "$SCRIPT_DIR:/data" \
  --workdir /data \
  --user "$(id -u):$(id -g)" \
  --env JOURNAL=joss \
  openjournals/inara

echo "Created: $SCRIPT_DIR/paper.pdf"
