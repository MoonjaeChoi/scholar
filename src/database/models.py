from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class WebCaptureData:
    url: str  # Changed from source_url to match schema
    image_path: str  # Changed from image_file_path to match schema
    image_size: Optional[int] = None  # Changed from file_size_bytes to match schema
    image_format: Optional[str] = 'PNG'
    http_status_code: Optional[int] = 200
    processing_status: str = 'pending'  # Changed from status to match schema
    capture_id: Optional[int] = None
    crawl_timestamp: Optional[datetime] = None  # Changed from capture_timestamp
    metadata: Optional[str] = None  # JSON string for additional data

@dataclass
class TextBoundingBox:
    capture_id: int
    text_content: str
    x_coordinate: float
    y_coordinate: float
    width: float  # Changed from width_size to match schema
    height: float  # Changed from height_size to match schema
    confidence_score: float = 0.0
    font_size: Optional[float] = None
    box_id: Optional[int] = None  # Added to match schema

@dataclass
class ProcessingLog:
    capture_id: Optional[int]
    process_type: str
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    additional_info: Optional[str] = None
