#!/usr/bin/env bash
# Requires: gcloud auth, a project set, and APIs enabled
set -euo pipefail

CLUSTER="${CLUSTER:-rtc-demo}"
ZONE="${ZONE:-us-central1-a}"
POOL="${POOL:-gpu-pool}"
ACCEL="${ACCEL:-nvidia-tesla-t4}"
COUNT="${COUNT:-1}"

gcloud container clusters create "${CLUSTER}" --zone "${ZONE}" --num-nodes "1"
gcloud container node-pools create "${POOL}" \
  --cluster "${CLUSTER}" --zone "${ZONE}" \
  --accelerator "type=${ACCEL},count=1" --machine-type "n1-standard-8" \
  --num-nodes "${COUNT}" --node-labels=nvidia.com/gpu.present=true

gcloud container clusters get-credentials "${CLUSTER}" --zone "${ZONE}"

# Install NVIDIA device plugin
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.15.0/nvidia-device-plugin.yml

echo "GPU pool ready."
