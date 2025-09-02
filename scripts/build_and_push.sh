#!/usr/bin/env bash
set -euo pipefail

REG="${REGISTRY:-gcr.io/YOUR_PROJECT}"
IMG="${IMAGE:-gpu-media}"
TAG="${TAG:-v1}"

echo "Building ${REG}/${IMG}:${TAG}"
docker build -t "${REG}/${IMG}:${TAG}" .
docker push "${REG}/${IMG}:${TAG}"

echo "Done: ${REG}/${IMG}:${TAG}"
