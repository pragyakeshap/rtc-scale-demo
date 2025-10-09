#!/usr/bin/env bash
# Quick development setup script
set -euo pipefail

echo "🚀 WebRTC GPU Application - Quick Start"
echo "================================="

# Check if we're in the right directory
if [ ! -f "app/server.py" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Setup virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r app/requirements.txt

# Install CPU version of PyTorch for development
echo "🧠 Installing PyTorch (CPU version for development)..."
pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch==2.3.1

echo "✅ Setup complete!"
echo ""
echo "To start the server:"
echo "  source venv/bin/activate"
echo "  uvicorn app.server:app --host 0.0.0.0 --port 8080 --reload"
echo ""
echo "Then open: http://localhost:8080/app"
echo ""
echo "To run tests:"
echo "  python3 test_integration.py"
echo ""
echo "To build Docker image:"
echo "  docker build -t rtc-gpu-app ."
echo "  docker run -p 8080:8080 rtc-gpu-app"
