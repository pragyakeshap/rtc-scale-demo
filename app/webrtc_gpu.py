"""
WebRTC Media Processing Module for GPU acceleration
Handles real-time video stream processing with GPU optimization
"""
import asyncio
import logging
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from typing import Optional, Tuple, Any
from dataclasses import dataclass

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
    from aiortc.contrib.media import MediaPlayer, MediaRelay
    from av import VideoFrame
    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    RTCPeerConnection = None
    VideoStreamTrack = None
    VideoFrame = None

logger = logging.getLogger(__name__)

@dataclass
class ProcessingStats:
    """Statistics for GPU processing performance"""
    frame_count: int = 0
    total_processing_time: float = 0.0
    gpu_memory_used: int = 0
    average_fps: float = 0.0

class GPUVideoProcessor:
    """GPU-accelerated video processing for WebRTC streams"""
    
    def __init__(self, device: str = "cuda", enable_face_detection: bool = True):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.enable_face_detection = enable_face_detection
        self.stats = ProcessingStats()
        
        # Initialize GPU models for video processing
        self._init_models()
        
    def _init_models(self):
        """Initialize GPU models for real-time processing"""
        if self.device.type == "cuda":
            # Initialize face detection model on GPU
            if self.enable_face_detection:
                try:
                    # Use a lightweight face detection model
                    self.face_cascade = cv2.CascadeClassifier(
                        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                    )
                except Exception as e:
                    logger.warning(f"Face detection unavailable: {e}")
                    self.enable_face_detection = False
            
            # Initialize GPU-based image processing kernels
            self.gpu_kernels = {
                'blur': torch.tensor([
                    [1, 2, 1],
                    [2, 4, 2], 
                    [1, 2, 1]
                ], dtype=torch.float32, device=self.device) / 16.0,
                
                'sharpen': torch.tensor([
                    [0, -1, 0],
                    [-1, 5, -1],
                    [0, -1, 0]
                ], dtype=torch.float32, device=self.device),
                
                'edge': torch.tensor([
                    [-1, -1, -1],
                    [-1, 8, -1],
                    [-1, -1, -1]
                ], dtype=torch.float32, device=self.device)
            }
            
            logger.info(f"GPU video processor initialized on {self.device}")
        else:
            logger.info("Using CPU fallback for video processing")

    def process_frame_gpu(self, frame: np.ndarray, effect: str = "enhance") -> np.ndarray:
        """
        Process a single frame using GPU acceleration
        
        Args:
            frame: Input frame as numpy array (H, W, C)
            effect: Processing effect to apply
            
        Returns:
            Processed frame as numpy array
        """
        start_time = torch.cuda.Event(enable_timing=True) if self.device.type == "cuda" else None
        end_time = torch.cuda.Event(enable_timing=True) if self.device.type == "cuda" else None
        
        if start_time:
            start_time.record()
        
        try:
            # Convert frame to tensor and move to GPU
            if len(frame.shape) == 3:
                # Convert BGR to RGB and normalize
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                tensor = torch.from_numpy(frame_rgb.transpose(2, 0, 1)).float() / 255.0
            else:
                tensor = torch.from_numpy(frame).float() / 255.0
                
            tensor = tensor.unsqueeze(0).to(self.device)  # Add batch dimension
            
            # Apply GPU processing based on effect
            if effect == "enhance":
                processed = self._enhance_frame(tensor)
            elif effect == "blur":
                processed = self._apply_convolution(tensor, self.gpu_kernels['blur'])
            elif effect == "sharpen":
                processed = self._apply_convolution(tensor, self.gpu_kernels['sharpen'])
            elif effect == "edge":
                processed = self._apply_convolution(tensor, self.gpu_kernels['edge'])
            else:
                processed = tensor
            
            # Convert back to numpy
            processed = processed.squeeze(0).cpu().numpy()
            processed = (processed.transpose(1, 2, 0) * 255).astype(np.uint8)
            
            # Convert back to BGR for OpenCV
            if len(processed.shape) == 3:
                processed = cv2.cvtColor(processed, cv2.COLOR_RGB2BGR)
            
            if start_time and end_time:
                end_time.record()
                torch.cuda.synchronize()
                processing_time = start_time.elapsed_time(end_time) / 1000.0  # Convert to seconds
                self._update_stats(processing_time)
            
            return processed
            
        except Exception as e:
            logger.error(f"GPU processing failed: {e}")
            return frame  # Return original frame on error

    def _enhance_frame(self, tensor: torch.Tensor) -> torch.Tensor:
        """Apply enhancement operations using GPU"""
        # Brightness and contrast adjustment
        enhanced = tensor * 1.1 + 0.05  # Slight brightness/contrast boost
        
        # Apply slight sharpening
        enhanced = self._apply_convolution(enhanced, self.gpu_kernels['sharpen'], strength=0.3)
        
        # Clamp values to valid range
        enhanced = torch.clamp(enhanced, 0.0, 1.0)
        
        return enhanced

    def _apply_convolution(self, tensor: torch.Tensor, kernel: torch.Tensor, strength: float = 1.0) -> torch.Tensor:
        """Apply convolution with given kernel"""
        # Expand kernel for 3-channel processing
        kernel = kernel.unsqueeze(0).unsqueeze(0).repeat(3, 1, 1, 1)
        
        # Apply convolution
        result = F.conv2d(tensor, kernel, padding=1, groups=3)
        
        # Blend with original if strength < 1.0
        if strength < 1.0:
            result = tensor * (1 - strength) + result * strength
            
        return result

    def _update_stats(self, processing_time: float):
        """Update processing statistics"""
        self.stats.frame_count += 1
        self.stats.total_processing_time += processing_time
        
        # Calculate average FPS
        if self.stats.total_processing_time > 0:
            self.stats.average_fps = self.stats.frame_count / self.stats.total_processing_time
        
        # Update GPU memory usage
        if self.device.type == "cuda":
            self.stats.gpu_memory_used = torch.cuda.memory_allocated(self.device)

    def get_stats(self) -> dict:
        """Get current processing statistics"""
        return {
            "frame_count": self.stats.frame_count,
            "total_processing_time": self.stats.total_processing_time,
            "average_fps": self.stats.average_fps,
            "gpu_memory_used_mb": self.stats.gpu_memory_used / (1024 * 1024),
            "device": str(self.device)
        }

class GPUVideoStreamTrack(VideoStreamTrack):
    """WebRTC video track with GPU processing"""
    
    def __init__(self, track: VideoStreamTrack, processor: GPUVideoProcessor, effect: str = "enhance"):
        super().__init__()
        self.track = track
        self.processor = processor
        self.effect = effect
        
    async def recv(self) -> VideoFrame:
        """Receive and process video frame"""
        frame = await self.track.recv()
        
        # Convert to numpy array
        img = frame.to_ndarray(format="bgr24")
        
        # Process with GPU
        processed_img = self.processor.process_frame_gpu(img, self.effect)
        
        # Convert back to VideoFrame
        new_frame = VideoFrame.from_ndarray(processed_img, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base
        
        return new_frame

class WebRTCGPUManager:
    """Manager for WebRTC connections with GPU processing"""
    
    def __init__(self):
        self.connections = {}
        self.processor = GPUVideoProcessor() if torch.cuda.is_available() else None
        self.relay = MediaRelay() if AIORTC_AVAILABLE else None
        
    async def create_peer_connection(self, session_id: str) -> Optional[RTCPeerConnection]:
        """Create a new WebRTC peer connection"""
        if not AIORTC_AVAILABLE:
            logger.error("aiortc not available for WebRTC processing")
            return None
            
        pc = RTCPeerConnection()
        self.connections[session_id] = pc
        
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection {session_id} state: {pc.connectionState}")
            if pc.connectionState == "failed":
                await self.cleanup_connection(session_id)
        
        return pc
    
    async def add_gpu_processing_track(self, pc: RTCPeerConnection, track: VideoStreamTrack, effect: str = "enhance") -> None:
        """Add GPU processing to a video track"""
        if self.processor and self.relay:
            # Relay the track and add GPU processing
            relayed_track = self.relay.subscribe(track)
            gpu_track = GPUVideoStreamTrack(relayed_track, self.processor, effect)
            pc.addTrack(gpu_track)
        else:
            # Fallback: add track without GPU processing
            pc.addTrack(track)
    
    async def cleanup_connection(self, session_id: str):
        """Clean up WebRTC connection"""
        if session_id in self.connections:
            pc = self.connections[session_id]
            await pc.close()
            del self.connections[session_id]
            logger.info(f"Cleaned up connection {session_id}")
    
    def get_processing_stats(self) -> dict:
        """Get GPU processing statistics"""
        if self.processor:
            return self.processor.get_stats()
        return {"status": "GPU processing not available"}

# Global instance
webrtc_gpu_manager = WebRTCGPUManager()
