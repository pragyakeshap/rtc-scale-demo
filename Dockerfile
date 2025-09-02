ARG CUDA_VERSION=12.1.0
FROM nvidia/cuda:${CUDA_VERSION}-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/requirements.txt .

# Install CUDA-enabled PyTorch matching CUDA 12.1
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cu121 \
      torch==2.3.1+cu121 torchvision==0.18.1+cu121 torchaudio==2.3.1+cu121 && \
    pip3 install --no-cache-dir -r requirements.txt

COPY app/ ./
RUN useradd -u 10001 -m appuser
USER 10001

EXPOSE 8080
HEALTHCHECK CMD curl -f http://localhost:8080/healthz || exit 1
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
