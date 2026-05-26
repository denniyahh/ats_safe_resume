#!/usr/bin/env bash
# ATS Safe Resume — Docker convenience wrapper
#
# Builds your resume using the official Docker image. No LaTeX install required.
#
# Usage:
#   ./build_docker.sh                  # builds resume.md in current dir
#   ./build_docker.sh path/to/file.md  # custom input
#
# First run pulls the image from ghcr.io. Subsequent runs are instant.

set -euo pipefail

INPUT_MD="${1:-resume.md}"
INPUT_DIR="$(cd "$(dirname "$INPUT_MD")" && pwd)"
INPUT_FILE="$(basename "$INPUT_MD")"

echo "Building resume via Docker..."
echo "  Input:    $INPUT_MD"
echo "  Image:    ghcr.io/denniyahh/ats_safe_resume:latest"
echo ""

exec docker run --rm \
  -v "$INPUT_DIR":/data \
  -v "$(pwd)/dist":/data/dist \
  ghcr.io/denniyahh/ats_safe_resume:latest \
  "/data/$INPUT_FILE"
