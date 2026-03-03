import os
import json
import random
from typing import List, Dict, Tuple, Optional
from loguru import logger
from PIL import Image
from dataclasses import dataclass
from datetime import datetime

try:
    from ..database.connection import DatabaseConnection
    DATABASE_AVAILABLE = True
except ImportError:
    logger.warning('Database modules not available, running in mock mode')
    DATABASE_AVAILABLE = False

@dataclass
class ValidationResult:
    capture_id: int
    total_boxes: int
    valid_boxes: int
    invalid_boxes: int
    issues: List[str]
    quality_score: float

class BoundingBoxValidator:
    def __init__(self, data_root_path: str = '/opt/ocr_system/crawling/data'):
        self.data_root_path = data_root_path
        if DATABASE_AVAILABLE:
            self.db_connection = DatabaseConnection()
        else:
            self.db_connection = None
            
        self.min_text_length = 2
        self.min_box_width = 10
        self.min_box_height = 8
        self.max_box_width = 2000
        self.max_box_height = 200

    def validate_single_capture_from_files(self, capture_file: str) -> ValidationResult:
        """파일 기반 캡처 데이터 검증"""
        try:
            # 캡처 메타데이터 로드
            with open(capture_file, 'r') as f:
                capture_data = json.load(f)
            
            capture_id = capture_data.get('capture_id', 0)
            image_path = capture_data.get('image_file_path', '')
            
            # 바운딩 박스 파일 찾기
            bbox_file = capture_file.replace('capture_', 'bounding_boxes_')
            if not os.path.exists(bbox_file):
                return ValidationResult(capture_id, 0, 0, 0, ['No bounding boxes file found'], 0.0)
            
            with open(bbox_file, 'r') as f:
                bounding_boxes = json.load(f)
            
            if not bounding_boxes:
                return ValidationResult(capture_id, 0, 0, 0, ['No bounding boxes found'], 0.0)
            
            issues = []
            valid_boxes = 0
            total_boxes = len(bounding_boxes)
            
            # 이미지 크기 확인
            try:
                if os.path.exists(image_path):
                    img = Image.open(image_path)
                    img_width, img_height = img.size
                else:
                    # 기본 뷰포트 크기 사용
                    img_width, img_height = capture_data.get('viewport_width', 1920), capture_data.get('viewport_height', 1080)
            except Exception as e:
                issues.append(f'Cannot load image: {e}')
                img_width, img_height = 1920, 1080
            
            # 각 바운딩 박스 검증
            for i, box in enumerate(bounding_boxes):
                box_issues = self._validate_bounding_box_dict(
                    i, box, img_width, img_height
                )
                
                if not box_issues:
                    valid_boxes += 1
                else:
                    issues.extend(box_issues)
            
            # 품질 점수 계산
            quality_score = valid_boxes / total_boxes if total_boxes > 0 else 0.0
            
            return ValidationResult(
                capture_id, total_boxes, valid_boxes,
                total_boxes - valid_boxes, issues, quality_score
            )
            
        except Exception as e:
            logger.error(f'Error validating capture file {capture_file}: {e}')
            return ValidationResult(0, 0, 0, 0, [f'Validation error: {e}'], 0.0)

    def _validate_bounding_box_dict(self, box_id: int, box: Dict,
                                   img_width: int, img_height: int) -> List[str]:
        """딕셔너리 형태의 바운딩 박스 검증"""
        issues = []
        
        text_content = box.get('text', '')
        x = box.get('x', 0)
        y = box.get('y', 0) 
        width = box.get('width', 0)
        height = box.get('height', 0)
        
        # 텍스트 길이 검증
        if len(text_content.strip()) < self.min_text_length:
            issues.append(f'Box {box_id}: Text too short ({len(text_content)} chars)')
        
        # 박스 크기 검증
        if width < self.min_box_width or height < self.min_box_height:
            issues.append(f'Box {box_id}: Box too small ({width}x{height})')
        
        if width > self.max_box_width or height > self.max_box_height:
            issues.append(f'Box {box_id}: Box too large ({width}x{height})')
        
        # 좌표 경계 검증
        if x < 0 or y < 0:
            issues.append(f'Box {box_id}: Negative coordinates ({x}, {y})')
        
        if x + width > img_width or y + height > img_height:
            issues.append(f'Box {box_id}: Box exceeds image boundaries')
        
        # 텍스트 품질 검증
        if self._is_low_quality_text(text_content):
            issues.append(f'Box {box_id}: Low quality text content')
        
        return issues

    def _is_low_quality_text(self, text: str) -> bool:
        """텍스트 품질 검사"""
        text = text.strip()
        
        # 너무 짧은 텍스트
        if len(text) < 2:
            return True
        
        # 특수문자만으로 구성된 텍스트
        if len(text.replace(' ', '').replace('\n', '').replace('\t', '')) == 0:
            return True
        
        # 반복되는 문자 (예: "aaaa", "----")
        if len(set(text.replace(' ', ''))) <= 2 and len(text) > 5:
            return True
        
        return False

    def validate_all_captures(self) -> List[ValidationResult]:
        """모든 캡처 데이터 검증"""
        results = []
        metadata_dir = os.path.join(self.data_root_path, 'metadata')
        
        if not os.path.exists(metadata_dir):
            logger.error(f'Metadata directory not found: {metadata_dir}')
            return results
        
        # 캡처 메타데이터 파일들 찾기
        capture_files = [f for f in os.listdir(metadata_dir) if f.startswith('capture_') and f.endswith('.json')]
        
        logger.info(f'Found {len(capture_files)} capture files to validate')
        
        for capture_file in capture_files:
            file_path = os.path.join(metadata_dir, capture_file)
            result = self.validate_single_capture_from_files(file_path)
            results.append(result)
            logger.info(f'Validated {capture_file}: {result.quality_score:.2f} quality score')
        
        return results

    def generate_validation_report(self, results: List[ValidationResult]) -> Dict:
        """검증 결과 리포트 생성"""
        if not results:
            return {}
        
        total_captures = len(results)
        high_quality_captures = len([r for r in results if r.quality_score >= 0.8])
        medium_quality_captures = len([r for r in results if 0.5 <= r.quality_score < 0.8])
        low_quality_captures = len([r for r in results if r.quality_score < 0.5])
        
        avg_quality = sum(r.quality_score for r in results) / total_captures
        total_boxes = sum(r.total_boxes for r in results)
        total_valid_boxes = sum(r.valid_boxes for r in results)
        
        # 공통 이슈 분석
        issue_counts = {}
        for result in results:
            for issue in result.issues:
                issue_type = issue.split(':')[0] if ':' in issue else issue
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        return {
            'total_captures': total_captures,
            'high_quality_captures': high_quality_captures,
            'medium_quality_captures': medium_quality_captures,
            'low_quality_captures': low_quality_captures,
            'average_quality_score': avg_quality,
            'total_bounding_boxes': total_boxes,
            'total_valid_boxes': total_valid_boxes,
            'overall_validity_rate': total_valid_boxes / total_boxes if total_boxes > 0 else 0,
            'common_issues': dict(sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        }
