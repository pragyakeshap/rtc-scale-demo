#!/usr/bin/env bash
# Quick concurrent user test for application
set -euo pipefail

echo "🎯 WebRTC GPU Application - Concurrent User Testing"
echo "=============================================="

# Check if server is running
if ! curl -s http://localhost:8080/healthz > /dev/null 2>&1; then
    echo "❌ Server not running. Please start with:"
    echo "   uvicorn app.server:app --host 0.0.0.0 --port 8080"
    exit 1
fi

echo "✅ Server is running, starting concurrent user tests..."
echo ""

# Test 1: Light concurrent load (simulating 5 concurrent users)
echo "Test 1: Light Load - 5 Concurrent Users"
echo "========================================"
python3 tests/test_load.py --url http://localhost:8080 \
  --requests 25 --concurrency 5 \
  --pixels "640x480" --iterations 3

echo ""

# Test 2: Medium concurrent load (simulating 15 concurrent users)
echo "Test 2: Medium Load - 15 Concurrent Users"
echo "=========================================="
python3 tests/test_load.py --url http://localhost:8080 \
  --requests 60 --concurrency 15 \
  --pixels "1280x720" --iterations 5

echo ""

# Test 3: Performance comparison with concurrent users
echo "Test 3: Performance Comparison with Concurrent Users"
echo "==================================================="
python3 tests/test_load.py --url http://localhost:8080 --comparison

echo ""
echo "🎉 Concurrent user testing completed!"
echo "Check the results above for:"
echo "- Response time percentiles under concurrent load"
echo "- Success rates with multiple users"
echo "- Device utilization (CPU vs GPU)"
echo "- Requests per second (RPS) achieved"
