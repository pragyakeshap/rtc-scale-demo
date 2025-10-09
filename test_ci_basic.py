#!/usr/bin/env python3
"""
Simplified unit tests for CI environment
Tests core functionality without heavy dependencies
"""
import unittest
import sys
import os

# Add project root to path
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

class TestBasicFunctionality(unittest.TestCase):
    """Test basic functionality without server dependencies"""
    
    def test_python_version(self):
        """Test Python version compatibility"""
        version = sys.version_info
        self.assertGreaterEqual(version.major, 3)
        self.assertGreaterEqual(version.minor, 8)
        print(f"✅ Python version: {version.major}.{version.minor}")
    
    def test_basic_imports(self):
        """Test that basic imports work"""
        try:
            import torch
            import fastapi
            import prometheus_client
            print("✅ Basic imports successful")
        except ImportError as e:
            self.fail(f"Basic import failed: {e}")
    
    def test_torch_functionality(self):
        """Test basic PyTorch functionality"""
        import torch
        
        # Create a simple tensor
        x = torch.tensor([1.0, 2.0, 3.0])
        y = torch.tensor([4.0, 5.0, 6.0])
        z = x + y
        
        expected = torch.tensor([5.0, 7.0, 9.0])
        self.assertTrue(torch.allclose(z, expected))
        print("✅ PyTorch basic operations work")
    
    def test_environment_variables(self):
        """Test environment variable handling"""
        # Test GPU simulation flag
        gpu_sim = os.environ.get('GPU_SIMULATION', 'false').lower() == 'true'
        cuda_wanted = os.environ.get('CUDA_WANTED', 'true').lower() == 'true'
        
        print(f"✅ GPU_SIMULATION: {gpu_sim}")
        print(f"✅ CUDA_WANTED: {cuda_wanted}")
        
        # In CI, these should be set for testing
        if 'CI' in os.environ:
            self.assertTrue(gpu_sim, "GPU_SIMULATION should be true in CI")
            self.assertFalse(cuda_wanted, "CUDA_WANTED should be false in CI")

def run_tests():
    """Run the test suite"""
    print("Running simplified CI tests...")
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestBasicFunctionality)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n✅ All CI tests passed!")
        return True
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed")
        print(f"❌ {len(result.errors)} test(s) had errors")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
