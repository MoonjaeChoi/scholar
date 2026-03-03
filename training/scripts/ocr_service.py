#!/usr/bin/env python3
"""
OCR Service for WebSocket C++ Server Communication
Handles Base64 image processing using PaddleOCR with Named Pipe communication
"""

import sys
import json
import base64
import io
import os
import time
import logging
import stat
import select
import struct
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from PIL import Image
import cv2

# PaddleOCR imports
try:
    import paddleocr
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError as e:
    print(f"PaddleOCR not available: {e}")
    PADDLEOCR_AVAILABLE = False

class OCRServiceServer:
    def __init__(self, pipe_name: str):
        self.pipe_name = pipe_name
        self.ocr_engine = None
        self.logger = self._setup_logger()
        self.running = False
        self.pipe_fd = None

        # Configuration
        self.max_message_size = 1024 * 1024  # 1MB

    def _setup_logger(self) -> logging.Logger:
        """Set up logging configuration"""
        logger = logging.getLogger('OCRService')
        logger.setLevel(logging.INFO)

        # Console handler
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # File handler for debugging
        try:
            file_handler = logging.FileHandler('/tmp/ocr_service.log')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Failed to create log file: {e}")

        return logger

    def initialize(self) -> bool:
        """Initialize OCR engine"""
        if not PADDLEOCR_AVAILABLE:
            self.logger.error("PaddleOCR is not available")
            return False

        try:
            self.logger.info("Initializing PaddleOCR engine...")

            # Check for custom trained models
            model_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/models/latest/"
            use_custom_models = os.path.exists(model_path)

            if use_custom_models:
                self.logger.info(f"Using custom models from: {model_path}")
                self.ocr_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang='en',
                    det_model_dir=os.path.join(model_path, "det"),
                    rec_model_dir=os.path.join(model_path, "rec"),
                    cls_model_dir=os.path.join(model_path, "cls"),
                    use_gpu=True,
                    gpu_mem=4000,
                    show_log=False
                )
            else:
                self.logger.info("Using default PaddleOCR models")
                self.ocr_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang='en',
                    use_gpu=True,
                    gpu_mem=4000,
                    show_log=False
                )

            self.logger.info("OCR engine initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize OCR engine: {e}")
            return False

    def create_named_pipe(self) -> bool:
        """Create named pipe for communication"""
        try:
            # Remove existing pipe if it exists
            if os.path.exists(self.pipe_name):
                os.unlink(self.pipe_name)

            # Create new named pipe
            os.mkfifo(self.pipe_name, 0o666)
            self.logger.info(f"Created named pipe: {self.pipe_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create named pipe: {e}")
            return False

    def connect_to_pipe(self) -> bool:
        """Connect to the named pipe"""
        try:
            self.logger.info(f"Connecting to pipe: {self.pipe_name}")
            # Open pipe for read/write
            self.pipe_fd = os.open(self.pipe_name, os.O_RDWR)
            self.logger.info("Connected to named pipe successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to pipe: {e}")
            return False

    def read_message(self, timeout_sec: int = 30) -> Optional[Dict]:
        """Read message from named pipe with timeout"""
        try:
            if self.pipe_fd is None:
                return None

            # Use select for timeout
            ready, _, _ = select.select([self.pipe_fd], [], [], timeout_sec)
            if not ready:
                self.logger.warning(f"Read timeout after {timeout_sec} seconds")
                return None

            # Read message length (4 bytes)
            length_bytes = os.read(self.pipe_fd, 4)
            if len(length_bytes) != 4:
                self.logger.error("Failed to read message length")
                return None

            message_length = struct.unpack('I', length_bytes)[0]

            if message_length > self.max_message_size:
                self.logger.error(f"Message too large: {message_length} bytes")
                return None

            # Read message content
            message_bytes = b''
            bytes_read = 0

            while bytes_read < message_length:
                chunk = os.read(self.pipe_fd, message_length - bytes_read)
                if not chunk:
                    self.logger.error("Unexpected end of stream")
                    return None
                message_bytes += chunk
                bytes_read += len(chunk)

            # Parse JSON
            message_str = message_bytes.decode('utf-8')
            return json.loads(message_str)

        except Exception as e:
            self.logger.error(f"Failed to read message: {e}")
            return None

    def write_message(self, message: Dict) -> bool:
        """Write message to named pipe"""
        try:
            if self.pipe_fd is None:
                return False

            # Serialize message
            message_str = json.dumps(message)
            message_bytes = message_str.encode('utf-8')

            if len(message_bytes) > self.max_message_size:
                self.logger.error(f"Message too large: {len(message_bytes)} bytes")
                return False

            # Write message length first
            length_bytes = struct.pack('I', len(message_bytes))
            os.write(self.pipe_fd, length_bytes)

            # Write message content
            bytes_written = 0
            while bytes_written < len(message_bytes):
                written = os.write(self.pipe_fd, message_bytes[bytes_written:])
                bytes_written += written

            self.logger.debug(f"Wrote message: {len(message_bytes)} bytes")
            return True

        except Exception as e:
            self.logger.error(f"Failed to write message: {e}")
            return False

    def decode_base64_image(self, base64_data: str) -> Optional[np.ndarray]:
        """Decode Base64 image to numpy array"""
        try:
            # Remove data URL prefix if present
            if base64_data.startswith('data:image'):
                base64_data = base64_data.split(',')[1]

            # Decode Base64
            image_bytes = base64.b64decode(base64_data)

            # Convert to PIL Image
            pil_image = Image.open(io.BytesIO(image_bytes))

            # Convert to numpy array (OpenCV format)
            image_array = np.array(pil_image)

            # Convert RGB to BGR if needed (PaddleOCR expects BGR)
            if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)

            return image_array

        except Exception as e:
            self.logger.error(f"Failed to decode Base64 image: {e}")
            return None

    def process_ocr_request(self, request: Dict) -> Dict:
        """Process OCR request"""
        start_time = time.time()

        try:
            request_id = request.get('requestId', '')
            session_id = request.get('sessionId', '')
            image_data = request.get('imageData', '')
            image_format = request.get('format', 'unknown')

            self.logger.info(f"Processing OCR request {request_id} from session {session_id}")

            if not image_data:
                return self._create_error_response(request_id, "Missing image data")

            # Decode image
            image_array = self.decode_base64_image(image_data)
            if image_array is None:
                return self._create_error_response(request_id, "Failed to decode image")

            # Validate image
            if image_array.size == 0:
                return self._create_error_response(request_id, "Invalid image data")

            self.logger.debug(f"Image decoded: {image_array.shape}, dtype: {image_array.dtype}")

            # Run OCR
            ocr_results = self.ocr_engine.ocr(image_array, cls=True)

            # Parse results
            text_boxes = []
            if ocr_results and ocr_results[0]:
                for line_result in ocr_results[0]:
                    if len(line_result) != 2:
                        continue

                    bbox_coords, (text, confidence) = line_result

                    # Create text box
                    text_box = {
                        'text': text,
                        'confidence': float(confidence),
                        'bbox': self._normalize_bounding_box(bbox_coords)
                    }

                    text_boxes.append(text_box)

            processing_time = int((time.time() - start_time) * 1000)

            # Create success response
            response = {
                'requestId': request_id,
                'success': True,
                'errorMessage': '',
                'textBoxes': text_boxes,
                'metrics': {
                    'processingTimeMs': processing_time,
                    'detectedTextCount': len(text_boxes),
                    'averageConfidence': np.mean([tb['confidence'] for tb in text_boxes]) if text_boxes else 0.0
                },
                'timestamp': int(time.time() * 1000)
            }

            self.logger.info(f"OCR completed for request {request_id}: {len(text_boxes)} text boxes in {processing_time}ms")
            return response

        except Exception as e:
            self.logger.error(f"OCR processing failed: {e}")
            return self._create_error_response(request_id, f"OCR processing error: {str(e)}")

    def _normalize_bounding_box(self, coords: List[List[int]]) -> Dict:
        """Convert PaddleOCR coordinates to normalized bounding box"""
        if not coords or len(coords) != 4:
            return {'x': 0, 'y': 0, 'width': 0, 'height': 0, 'polygon': []}

        x_coords = [point[0] for point in coords]
        y_coords = [point[1] for point in coords]

        return {
            'x': int(min(x_coords)),
            'y': int(min(y_coords)),
            'width': int(max(x_coords) - min(x_coords)),
            'height': int(max(y_coords) - min(y_coords)),
            'polygon': [{'x': int(p[0]), 'y': int(p[1])} for p in coords]
        }

    def _create_error_response(self, request_id: str, error_msg: str) -> Dict:
        """Create error response"""
        return {
            'requestId': request_id,
            'success': False,
            'errorMessage': error_msg,
            'textBoxes': [],
            'metrics': {
                'processingTimeMs': 0,
                'detectedTextCount': 0,
                'averageConfidence': 0.0
            },
            'timestamp': int(time.time() * 1000)
        }

    def start_service(self) -> bool:
        """Start the OCR service"""
        try:
            # Initialize OCR engine
            if not self.initialize():
                return False

            # Create and connect to named pipe
            if not self.create_named_pipe():
                return False

            if not self.connect_to_pipe():
                return False

            self.running = True
            self.logger.info(f"OCR Service started, listening on pipe: {self.pipe_name}")

            # Main service loop
            while self.running:
                try:
                    # Read request
                    request = self.read_message(timeout_sec=30)

                    if not request:
                        continue

                    # Handle different message types
                    message_type = request.get('type', 'ocr_request')

                    if message_type == 'test':
                        # Test connection response
                        response = {
                            'type': 'test_response',
                            'success': True,
                            'timestamp': int(time.time() * 1000)
                        }
                        self.write_message(response)
                        continue

                    elif message_type == 'shutdown':
                        self.logger.info("Shutdown request received")
                        break

                    # Process OCR request
                    response = self.process_ocr_request(request)

                    # Send response
                    if not self.write_message(response):
                        self.logger.error("Failed to send response")

                except KeyboardInterrupt:
                    self.logger.info("Service interrupted by user")
                    break
                except Exception as e:
                    self.logger.error(f"Service error: {e}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            return False
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        self.running = False

        if self.pipe_fd is not None:
            try:
                os.close(self.pipe_fd)
                self.pipe_fd = None
            except Exception as e:
                self.logger.warning(f"Error closing pipe: {e}")

        if os.path.exists(self.pipe_name):
            try:
                os.unlink(self.pipe_name)
            except Exception as e:
                self.logger.warning(f"Error removing pipe: {e}")

        if self.ocr_engine:
            del self.ocr_engine
            self.ocr_engine = None

        self.logger.info("OCR Service cleaned up")

def main():
    if len(sys.argv) != 2:
        print("Usage: python ocr_service.py <pipe_name>")
        sys.exit(1)

    pipe_name = sys.argv[1]

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting OCR service with pipe: {pipe_name}")

    service = OCRServiceServer(pipe_name)

    try:
        success = service.start_service()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()