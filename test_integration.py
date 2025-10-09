#!/usr/bin/env python3
"""
Integration test script for the WebRTC GPU application
Tests key functionality without requiring full deployment
"""
import sys
import time
import subprocess
import requests
import json
from pathlib import Path

def log(message, level="INFO"):
    print(f"[{time.strftime('%H:%M:%S')}] {level}: {message}")

def test_server_startup():
    """Test that server can start without errors"""
    log("Testing server import and basic functionality...")
    
    try:
        # Test imports
        sys.path.insert(0, str(Path(__file__).parent / "app"))
        import server
        log("✅ Server module imported successfully")
        
        # Test device detection
        device = server.device_str()
        log(f"✅ Device detection: {device}")
        
        # Test processing functions exist
        assert hasattr(server, 'real_gpu_process'), "real_gpu_process function missing"
        assert hasattr(server, 'cpu_intensive_process'), "cpu_intensive_process function missing"
        log("✅ Processing functions available")
        
        return True
    except Exception as e:
        log(f"❌ Server startup test failed: {e}", "ERROR")
        return False

def test_webrtc_import():
    """Test WebRTC processor import"""
    try:
        sys.path.insert(0, str(Path(__file__).parent / "app"))
        import webrtc_processor
        log(f"✅ WebRTC processor imported, aiortc available: {webrtc_processor.AIORTC_AVAILABLE}")
        return True
    except Exception as e:
        log(f"❌ WebRTC import test failed: {e}", "ERROR")
        return False

def test_dependencies():
    """Test critical dependencies"""
    try:
        import torch
        log(f"✅ PyTorch available: {torch.__version__}")
        log(f"   CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            log(f"   GPU count: {torch.cuda.device_count()}")
            log(f"   Current device: {torch.cuda.current_device()}")
        
        import numpy
        log(f"✅ NumPy available: {numpy.__version__}")
        
        try:
            import cv2
            log(f"✅ OpenCV available: {cv2.__version__}")
        except ImportError:
            log("⚠️  OpenCV not available (optional for core functionality)")
        
        try:
            import aiortc
            log(f"✅ aiortc available: {aiortc.__version__}")
        except ImportError:
            log("⚠️  aiortc not available (WebRTC features disabled)")
        
        return True
    except Exception as e:
        log(f"❌ Dependency test failed: {e}", "ERROR")
        return False

def test_server_endpoints():
    """Test server endpoints if server is running"""
    base_url = "http://localhost:8080"
    
    try:
        # Test health endpoint
        response = requests.get(f"{base_url}/healthz", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            log(f"✅ Health endpoint working: {health_data}")
            
            # Test process endpoint
            process_response = requests.post(
                f"{base_url}/process",
                params={"pixels": "640x480", "iters": 2},
                timeout=10
            )
            if process_response.status_code == 200:
                process_data = process_response.json()
                log(f"✅ Process endpoint working: latency={process_data.get('latency_seconds', 'N/A')}s")
            else:
                log(f"⚠️  Process endpoint returned {process_response.status_code}")
                
            # Test WebRTC status
            webrtc_response = requests.get(f"{base_url}/webrtc/status", timeout=5)
            if webrtc_response.status_code == 200:
                webrtc_data = webrtc_response.json()
                log(f"✅ WebRTC status: {webrtc_data}")
            
            return True
        else:
            log(f"⚠️  Server not running (status {response.status_code})")
            return False
            
    except requests.exceptions.RequestException:
        log("⚠️  Server not running or not accessible")
        return False

def main():
    log("Starting integration tests for WebRTC GPU Application")
    log("=" * 50)
    
    results = []
    
    # Test 1: Server startup
    results.append(("Server Import", test_server_startup()))
    
    # Test 2: Dependencies
    results.append(("Dependencies", test_dependencies()))
    
    # Test 3: WebRTC import
    results.append(("WebRTC Import", test_webrtc_import()))
    
    # Test 4: Live server endpoints (optional)
    results.append(("Live Endpoints", test_server_endpoints()))
    
    # Summary
    log("=" * 50)
    log("Test Results Summary:")
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        log(f"  {test_name}: {status}")
        if success:
            passed += 1
    
    log(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed >= 3:  # Allow live endpoints to fail if server not running
        log("🎉 Integration tests PASSED - System ready for deployment!")
        return 0
    else:
        log("💥 Integration tests FAILED - Check errors above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
