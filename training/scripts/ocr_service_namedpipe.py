#!/usr/bin/env python3
# Generated: 2025-01-27 16:25:31 KST
"""
Enhanced OCR Service with Named Pipe Communication
Supports C++ ↔ Python high-performance communication for Phase 1 MVP
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
import signal
import argparse
import threading
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from PIL import Image
import cv2
from pathlib import Path

# PaddleOCR imports
try:
    import paddleocr
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError as e:
    print(f"PaddleOCR not available: {e}")
    PADDLEOCR_AVAILABLE = False

class NamedPipeOCRService:
    def __init__(self, input_pipe: str, output_pipe: str, config: Dict[str, Any] = None):
        self.input_pipe_path = input_pipe
        self.output_pipe_path = output_pipe
        self.config = config or {}

        # 프로세스 관리
        self.running = False
        self.shutdown_requested = False

        # 파이프 핸들
        self.input_pipe_fd = None
        self.output_pipe_fd = None

        # OCR 엔진
        self.ocr_engine = None

        # 로깅 설정
        self.logger = self._setup_logger()

        # 통계
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_processing_time': 0.0,
            'start_time': time.time()
        }

        # 신호 처리
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _setup_logger(self) -> logging.Logger:
        """로깅 시스템 설정"""
        logger = logging.getLogger('NamedPipeOCRService')
        logger.setLevel(logging.INFO)

        # 콘솔 핸들러
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # 파일 핸들러 (옵션)
        if 'log_file' in self.config:
            file_handler = logging.FileHandler(self.config['log_file'])
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _signal_handler(self, signum, frame):
        """신호 처리 핸들러"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown_requested = True

    def initialize_ocr_engine(self) -> bool:
        """PaddleOCR 엔진 초기화"""
        if not PADDLEOCR_AVAILABLE:
            self.logger.error("PaddleOCR is not available")
            return False

        try:
            # OCR 엔진 설정
            ocr_config = {
                'use_angle_cls': True,
                'lang': 'korean',
                'use_gpu': self.config.get('use_gpu', False),
                'show_log': False,
                'use_space_char': True,
            }

            # 커스텀 모델 경로 설정 (있는 경우)
            det_model_dir = self.config.get('det_model_dir')
            rec_model_dir = self.config.get('rec_model_dir')
            cls_model_dir = self.config.get('cls_model_dir')

            if det_model_dir:
                ocr_config['det_model_dir'] = det_model_dir
            if rec_model_dir:
                ocr_config['rec_model_dir'] = rec_model_dir
            if cls_model_dir:
                ocr_config['cls_model_dir'] = cls_model_dir

            self.logger.info("Initializing PaddleOCR engine...")
            self.ocr_engine = PaddleOCR(**ocr_config)
            self.logger.info("PaddleOCR engine initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize OCR engine: {e}")
            return False

    def open_pipes(self) -> bool:
        """Named Pipe 열기"""
        try:
            self.logger.info(f"Opening input pipe: {self.input_pipe_path}")
            self.input_pipe_fd = os.open(self.input_pipe_path, os.O_RDONLY)

            self.logger.info(f"Opening output pipe: {self.output_pipe_path}")
            self.output_pipe_fd = os.open(self.output_pipe_path, os.O_WRONLY)

            self.logger.info("Named pipes opened successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to open pipes: {e}")
            return False

    def close_pipes(self):
        """Named Pipe 닫기"""
        if self.input_pipe_fd is not None:
            os.close(self.input_pipe_fd)
            self.input_pipe_fd = None

        if self.output_pipe_fd is not None:
            os.close(self.output_pipe_fd)
            self.output_pipe_fd = None

        self.logger.info("Named pipes closed")

    def read_request(self, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """파이프에서 요청 읽기"""
        try:
            # select를 사용한 타임아웃 처리
            ready, _, _ = select.select([self.input_pipe_fd], [], [], timeout)
            if not ready:
                return None

            # 데이터 읽기 (최대 1MB)
            data = os.read(self.input_pipe_fd, 1024 * 1024)
            if not data:
                return None

            # JSON 파싱
            json_str = data.decode('utf-8').rstrip('\x00')
            request = json.loads(json_str)

            self.logger.debug(f"Received request: {request.get('request_id', 'unknown')}")
            return request

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error reading request: {e}")
            return None

    def write_response(self, response: Dict[str, Any]) -> bool:
        """파이프에 응답 쓰기"""
        try:
            json_str = json.dumps(response, ensure_ascii=False)
            data = json_str.encode('utf-8') + b'\x00'  # null terminator

            bytes_written = os.write(self.output_pipe_fd, data)
            self.logger.debug(f"Wrote response: {bytes_written} bytes")
            return bytes_written > 0

        except Exception as e:
            self.logger.error(f"Error writing response: {e}")
            return False

    def process_ocr_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """OCR 요청 처리"""
        start_time = time.time()
        request_id = request.get('request_id', 'unknown')

        try:
            # Base64 이미지 디코딩
            image_base64 = request.get('image_base64', '')
            if not image_base64:
                raise ValueError("No image data provided")

            # Base64 디코딩
            image_data = base64.b64decode(image_base64)

            # PIL Image 로 변환
            pil_image = Image.open(io.BytesIO(image_data))

            # OpenCV 형식으로 변환
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            # OCR 수행
            self.logger.info(f"Processing OCR for request: {request_id}")
            ocr_results = self.ocr_engine.ocr(cv_image, cls=True)

            # 결과 정리
            processed_results = []
            total_confidence = 0.0
            text_count = 0

            if ocr_results and ocr_results[0]:
                for line in ocr_results[0]:
                    if len(line) >= 2:
                        bbox = line[0]  # bounding box 좌표
                        text_info = line[1]  # (text, confidence)

                        if isinstance(text_info, tuple) and len(text_info) >= 2:
                            text = text_info[0]
                            confidence = text_info[1]

                            processed_results.append({
                                'text': text,
                                'confidence': float(confidence),
                                'bbox': bbox
                            })

                            total_confidence += confidence
                            text_count += 1

            # 평균 신뢰도 계산
            avg_confidence = total_confidence / text_count if text_count > 0 else 0.0

            processing_time = (time.time() - start_time) * 1000  # ms

            # 응답 생성
            response = {
                'request_id': request_id,
                'success': True,
                'result': json.dumps(processed_results, ensure_ascii=False),
                'processing_time_ms': processing_time,
                'confidence_score': avg_confidence,
                'text_count': text_count
            }

            self.stats['successful_requests'] += 1
            self.logger.info(f"OCR completed for {request_id}: {text_count} texts, {avg_confidence:.3f} confidence, {processing_time:.1f}ms")

            return response

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self.logger.error(f"OCR processing failed for {request_id}: {e}")

            self.stats['failed_requests'] += 1

            return {
                'request_id': request_id,
                'success': False,
                'error_message': str(e),
                'processing_time_ms': processing_time,
                'confidence_score': 0.0
            }

        finally:
            self.stats['total_requests'] += 1
            self.stats['total_processing_time'] += (time.time() - start_time)

    def run_service(self):
        """메인 서비스 루프"""
        self.logger.info("Starting Named Pipe OCR Service")

        # OCR 엔진 초기화
        if not self.initialize_ocr_engine():
            self.logger.error("Failed to initialize OCR engine")
            return False

        # 파이프 열기
        if not self.open_pipes():
            self.logger.error("Failed to open pipes")
            return False

        self.running = True
        self.logger.info("OCR Service is ready and listening...")

        try:
            while self.running and not self.shutdown_requested:
                # 요청 읽기 (30초 타임아웃)
                request = self.read_request(timeout=30.0)

                if request is None:
                    if self.shutdown_requested:
                        break
                    continue

                # OCR 처리
                response = self.process_ocr_request(request)

                # 응답 전송
                if not self.write_response(response):
                    self.logger.error("Failed to write response")
                    break

                # 종료 요청 확인
                if request.get('command') == 'shutdown':
                    self.logger.info("Shutdown command received")
                    break

        except KeyboardInterrupt:
            self.logger.info("Service interrupted by user")
        except Exception as e:
            self.logger.error(f"Service error: {e}")
        finally:
            self.close_pipes()
            self.running = False

            # 최종 통계 출력
            self._print_statistics()

        self.logger.info("OCR Service stopped")
        return True

    def _print_statistics(self):
        """서비스 통계 출력"""
        uptime = time.time() - self.stats['start_time']
        success_rate = (
            self.stats['successful_requests'] / self.stats['total_requests'] * 100
            if self.stats['total_requests'] > 0 else 0
        )
        avg_processing_time = (
            self.stats['total_processing_time'] / self.stats['total_requests'] * 1000
            if self.stats['total_requests'] > 0 else 0
        )

        self.logger.info("=== Service Statistics ===")
        self.logger.info(f"Uptime: {uptime:.1f} seconds")
        self.logger.info(f"Total requests: {self.stats['total_requests']}")
        self.logger.info(f"Successful: {self.stats['successful_requests']}")
        self.logger.info(f"Failed: {self.stats['failed_requests']}")
        self.logger.info(f"Success rate: {success_rate:.1f}%")
        self.logger.info(f"Average processing time: {avg_processing_time:.1f}ms")


def main():
    parser = argparse.ArgumentParser(description='Named Pipe OCR Service')
    parser.add_argument('--input-pipe', required=True,
                        help='Input named pipe path')
    parser.add_argument('--output-pipe', required=True,
                        help='Output named pipe path')
    parser.add_argument('--log-file',
                        help='Log file path')
    parser.add_argument('--use-gpu', action='store_true',
                        help='Use GPU acceleration')
    parser.add_argument('--det-model-dir',
                        help='Custom detection model directory')
    parser.add_argument('--rec-model-dir',
                        help='Custom recognition model directory')
    parser.add_argument('--cls-model-dir',
                        help='Custom classification model directory')

    args = parser.parse_args()

    # 설정 구성
    config = {
        'use_gpu': args.use_gpu,
    }

    if args.log_file:
        config['log_file'] = args.log_file
    if args.det_model_dir:
        config['det_model_dir'] = args.det_model_dir
    if args.rec_model_dir:
        config['rec_model_dir'] = args.rec_model_dir
    if args.cls_model_dir:
        config['cls_model_dir'] = args.cls_model_dir

    # 서비스 시작
    service = NamedPipeOCRService(
        input_pipe=args.input_pipe,
        output_pipe=args.output_pipe,
        config=config
    )

    success = service.run_service()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()