#!/usr/bin/env python3
"""
Simple smoke test for CI - tests basic imports without heavy dependencies
"""
import sys

def test_basic_imports():
    """Test basic Python and PyTorch imports"""
    try:
        import torch
        print(f"✅ Python: {sys.version.split()[0]}")
        print(f"✅ PyTorch: {torch.__version__}")
        print(f"✅ CUDA available: {torch.cuda.is_available()}")
        
        # Test FastAPI import
        import fastapi
        print(f"✅ FastAPI: {fastapi.__version__}")
        
        # Test prometheus client
        import prometheus_client
        print("✅ Prometheus client imported")
        
        print("✅ All basic imports successful")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

if __name__ == "__main__":
    success = test_basic_imports()
    sys.exit(0 if success else 1)
