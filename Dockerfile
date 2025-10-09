ARG CUDA_VERSION=12.1.0
FROM nvidia/cuda:${CUDA_VERSION}-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CUDA_HOME=/usr/local/cuda \
    PATH=/usr/local/cuda/bin:$PATH \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# Install system dependencies including OpenCV requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev \
    curl ca-certificates wget \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    libgstreamer1.0-0 gstreamer1.0-plugins-base gstreamer1.0-libav \
    libopencv-dev python3-opencv \
    libjpeg-dev libpng-dev libtiff-dev \
    libavcodec-dev libavformat-dev libswscale-dev \
    libv4l-dev libxvidcore-dev libx264-dev \
    build-essential cmake pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/requirements.txt .

# Install PyTorch with CUDA support first
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cu121 \
      torch==2.3.1+cu121 torchvision==0.18.1+cu121 torchaudio==2.3.1+cu121

# Install other requirements
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./

# Create non-root user with write access for PyTorch compilation cache
RUN useradd -u 1000 -m -s /bin/bash appuser && \
    mkdir -p /home/appuser/.cache/torch && \
    chown -R appuser:appuser /home/appuser /app

USER appuser

# Set environment for optimal GPU performance
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
ENV OMP_NUM_THREADS=4
ENV CUDA_LAUNCH_BLOCKING=0

EXPOSE 8080

# Enhanced healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
