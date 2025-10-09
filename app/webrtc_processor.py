"""
WebRTC Media Processing Module
Handles real-time media processing with GPU acceleration
"""
import asyncio
import logging
import numpy as np
import cv2
from typing import Optional, Tuple
import torch
import torch.nn.functional as F

try:
    from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
    from aiortc.contrib.media import MediaPlayer, MediaRelay
    from av import VideoFrame
    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    MediaStreamTrack = object
    RTCPeerConnection = object
    RTCSessionDescription = object

logger = logging.getLogger(__name__)

class GPUVideoProcessor(MediaStreamTrack):
    """
    GPU-accelerated video processing track for WebRTC
    """
    kind = "video"
    
    def __init__(self, track, use_gpu: bool = True):
        super().__init__()
        self.track = track
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.device = torch.device('cuda' if self.use_gpu else 'cpu')
        
        # Initialize processing pipeline
        self._setup_processing_pipeline()
        
    def _setup_processing_pipeline(self):
        """Setup GPU processing pipeline for video frames"""
        if self.use_gpu:
            # Initialize CUDA kernels and memory pools
            torch.cuda.set_device(0)
            self.memory_pool = torch.cuda.memory.MemoryPool()
            torch.cuda.set_memory_pool(self.memory_pool)
            
    async def recv(self) -> VideoFrame:
        """Process incoming video frame with GPU acceleration"""
        frame = await self.track.recv()
        
        try:
            # Convert frame to tensor for GPU processing
            img = frame.to_ndarray(format="rgb24")
            processed_img = await self._process_frame_gpu(img)
            
            # Convert back to VideoFrame
            new_frame = VideoFrame.from_ndarray(processed_img, format="rgb24")
            new_frame.pts = frame.pts
            new_frame.time_base = frame.time_base
            
            return new_frame
            
        except Exception as e:
            logger.error(f"Frame processing error: {e}")
            return frame  # Return original frame on error
    
    async def _process_frame_gpu(self, img: np.ndarray) -> np.ndarray:
        """GPU-accelerated frame processing"""
        if not self.use_gpu:
            return self._process_frame_cpu(img)
        
        # Convert to tensor and move to GPU
        tensor = torch.from_numpy(img).float().to(self.device)
        tensor = tensor.permute(2, 0, 1).unsqueeze(0) / 255.0  # BCHW format
        
        with torch.cuda.amp.autocast():  # Use mixed precision for performance
            # Apply GPU-accelerated image processing
            processed = await self._apply_gpu_filters(tensor)
        
        # Convert back to CPU numpy array
        processed = processed.squeeze(0).permute(1, 2, 0).cpu().numpy()
        processed = (processed * 255).astype(np.uint8)
        
        return processed
    
    async def _apply_gpu_filters(self, tensor: torch.Tensor) -> torch.Tensor:
        """Apply various GPU-accelerated video filters"""
        # Edge enhancement
        edge_kernel = torch.tensor([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]], 
                                 dtype=torch.float32, device=self.device).unsqueeze(0).unsqueeze(0)
        
        # Apply convolution for each channel
        processed_channels = []
        for i in range(tensor.shape[1]):  # Process each color channel
            channel = tensor[:, i:i+1, :, :]
            edge_enhanced = F.conv2d(channel, edge_kernel, padding=1)
            processed_channels.append(edge_enhanced)
        
        edges = torch.cat(processed_channels, dim=1)
        
        # Combine original with edge enhancement
        enhanced = tensor + 0.1 * edges
        
        # Noise reduction with bilateral filter approximation
        gaussian_kernel = self._get_gaussian_kernel(5, 1.0).to(self.device)
        blurred = F.conv2d(enhanced, gaussian_kernel.unsqueeze(0).unsqueeze(0), 
                          padding=2, groups=enhanced.shape[1])
        
        # Color enhancement
        enhanced = torch.clamp(enhanced * 1.1 + 0.05, 0, 1)
        
        return enhanced
    
    def _get_gaussian_kernel(self, size: int, sigma: float) -> torch.Tensor:
        """Generate Gaussian kernel for GPU processing"""
        coords = torch.arange(size, dtype=torch.float32)
        coords -= (size - 1) / 2
        g = torch.exp(-(coords ** 2) / (2 * sigma ** 2))
        g /= g.sum()
        return g.outer(g)
    
    def _process_frame_cpu(self, img: np.ndarray) -> np.ndarray:
        """CPU fallback processing"""
        # Simple CPU-based processing
        enhanced = cv2.convertScaleAbs(img, alpha=1.1, beta=10)
        return enhanced

class WebRTCManager:
    """Manages WebRTC connections and media processing"""
    
    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu
        self.relay = MediaRelay() if AIORTC_AVAILABLE else None
        self.connections = set()
        
    async def create_peer_connection(self) -> Optional[RTCPeerConnection]:
        """Create a new WebRTC peer connection"""
        if not AIORTC_AVAILABLE:
            logger.warning("aiortc not available, WebRTC functionality disabled")
            return None
            
        pc = RTCPeerConnection()
        self.connections.add(pc)
        
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state: {pc.connectionState}")
            if pc.connectionState == "closed":
                self.connections.discard(pc)
        
        return pc
    
    async def add_gpu_video_track(self, pc: RTCPeerConnection, track: MediaStreamTrack):
        """Add GPU-processed video track to peer connection"""
        if not AIORTC_AVAILABLE:
            return
            
        gpu_track = GPUVideoProcessor(track, use_gpu=self.use_gpu)
        pc.addTrack(gpu_track)
        
    async def process_offer(self, pc: RTCPeerConnection, offer: dict) -> dict:
        """Process WebRTC offer and create answer"""
        if not AIORTC_AVAILABLE:
            return {"error": "WebRTC not available"}
            
        # Set remote description
        await pc.setRemoteDescription(RTCSessionDescription(
            sdp=offer["sdp"], type=offer["type"]
        ))
        
        # Create answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }
    
    async def cleanup(self):
        """Cleanup all connections"""
        if not AIORTC_AVAILABLE:
            return
            
        for pc in list(self.connections):
            await pc.close()
        self.connections.clear()

# Global WebRTC manager instance
webrtc_manager = WebRTCManager()
