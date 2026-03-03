import re
import json
import os
from typing import List, Tuple, Dict
from loguru import logger
from datetime import datetime

try:
    from ..database.connection import DatabaseConnection
    DATABASE_AVAILABLE = True
except ImportError:
    logger.warning('Database modules not available, running in file-based mode')
    DATABASE_AVAILABLE = False

class DataOptimizer:
    def __init__(self, data_root_path: str = '/opt/ocr_system/crawling/data'):
        self.data_root_path = data_root_path
        if DATABASE_AVAILABLE:
            self.db_connection = DatabaseConnection()
        else:
            self.db_connection = None

    def clean_text_content(self, text: str) -> str:
        """텍스트 콘텐츠 정제"""
        # 연속된 공백 제거
        text = re.sub(r'\s+', ' ', text)
        
        # 불필요한 특수문자 제거 (더 보수적으로)
        text = re.sub(r'[^\w\s\.,!?;:\-()\'\'"\n\t]+', '', text, flags=re.UNICODE)
        
        # 앞뒤 공백 제거
        text = text.strip()
        
        return text

    def calculate_overlap_ratio(self, box1: Dict, box2: Dict) -> float:
        """두 박스의 겹치는 비율 계산"""
        x1, y1, w1, h1 = box1['x'], box1['y'], box1['width'], box1['height']
        x2, y2, w2, h2 = box2['x'], box2['y'], box2['width'], box2['height']
        
        # 교집합 영역 계산
        intersect_x1 = max(x1, x2)
        intersect_y1 = max(y1, y2)
        intersect_x2 = min(x1 + w1, x2 + w2)
        intersect_y2 = min(y1 + h1, y2 + h2)
        
        if intersect_x2 <= intersect_x1 or intersect_y2 <= intersect_y1:
            return 0.0
        
        intersect_area = (intersect_x2 - intersect_x1) * (intersect_y2 - intersect_y1)
        box1_area = w1 * h1
        box2_area = w2 * h2
        
        # IoU (Intersection over Union) 계산
        union_area = box1_area + box2_area - intersect_area
        return intersect_area / union_area if union_area > 0 else 0.0

    def merge_boxes(self, box1: Dict, box2: Dict) -> Dict:
        """두 박스를 병합"""
        text1, text2 = box1['text'], box2['text']
        x1, y1, w1, h1 = box1['x'], box1['y'], box1['width'], box1['height']
        x2, y2, w2, h2 = box2['x'], box2['y'], box2['width'], box2['height']
        
        # 병합된 텍스트 (중복 제거)
        if text1.strip() in text2.strip() or text2.strip() in text1.strip():
            merged_text = text1 if len(text1) > len(text2) else text2
        else:
            merged_text = f'{text1} {text2}'.strip()
        
        # 병합된 바운딩 박스 좌표
        merged_x = min(x1, x2)
        merged_y = min(y1, y2)
        merged_w = max(x1 + w1, x2 + w2) - merged_x
        merged_h = max(y1 + h1, y2 + h2) - merged_y
        
        # 기타 속성은 첫 번째 박스 기준
        merged_box = box1.copy()
        merged_box.update({
            'text': merged_text,
            'x': merged_x,
            'y': merged_y,
            'width': merged_w,
            'height': merged_h
        })
        
        return merged_box

    def optimize_single_capture(self, capture_file: str, overlap_threshold: float = 0.5) -> Dict:
        """단일 캡처 파일의 바운딩 박스 최적화"""
        results = {
            'original_boxes': 0,
            'merged_boxes': 0,
            'removed_invalid': 0,
            'cleaned_text': 0,
            'final_boxes': 0
        }
        
        try:
            # 바운딩 박스 파일 경로
            bbox_file = capture_file.replace('capture_', 'bounding_boxes_')
            
            if not os.path.exists(bbox_file):
                logger.warning(f'Bounding boxes file not found: {bbox_file}')
                return results
            
            with open(bbox_file, 'r') as f:
                bounding_boxes = json.load(f)
            
            results['original_boxes'] = len(bounding_boxes)
            
            if not bounding_boxes:
                return results
            
            # 1. 유효하지 않은 박스 제거
            valid_boxes = []
            for box in bounding_boxes:
                if (len(box['text'].strip()) >= 2 and 
                    box['width'] >= 10 and box['height'] >= 8 and
                    box['width'] <= 2000 and box['height'] <= 200 and
                    box['x'] >= 0 and box['y'] >= 0):
                    valid_boxes.append(box)
                else:
                    results['removed_invalid'] += 1
            
            # 2. 텍스트 정제
            for box in valid_boxes:
                original_text = box['text']
                cleaned_text = self.clean_text_content(original_text)
                if cleaned_text != original_text:
                    box['text'] = cleaned_text
                    results['cleaned_text'] += 1
            
            # 3. 겹치는 박스 병합
            merged_boxes = []
            used_indices = set()
            
            for i in range(len(valid_boxes)):
                if i in used_indices:
                    continue
                
                current_box = valid_boxes[i]
                merged_with_any = False
                
                for j in range(i + 1, len(valid_boxes)):
                    if j in used_indices:
                        continue
                    
                    other_box = valid_boxes[j]
                    overlap_ratio = self.calculate_overlap_ratio(current_box, other_box)
                    
                    if overlap_ratio > overlap_threshold:
                        # 박스 병합
                        merged_box = self.merge_boxes(current_box, other_box)
                        merged_boxes.append(merged_box)
                        used_indices.add(i)
                        used_indices.add(j)
                        results['merged_boxes'] += 1
                        merged_with_any = True
                        break
                
                if not merged_with_any:
                    merged_boxes.append(current_box)
            
            results['final_boxes'] = len(merged_boxes)
            
            # 최적화된 바운딩 박스 저장
            with open(bbox_file, 'w') as f:
                json.dump(merged_boxes, f, indent=2, ensure_ascii=False)
            
            logger.info(f'Optimized {bbox_file}: {results["original_boxes"]} → {results["final_boxes"]} boxes')
            
            return results
            
        except Exception as e:
            logger.error(f'Error optimizing {capture_file}: {e}')
            return results

    def optimize_all_data(self) -> Dict[str, int]:
        """모든 데이터 최적화"""
        total_results = {
            'files_processed': 0,
            'original_boxes': 0,
            'merged_boxes': 0,
            'removed_invalid': 0,
            'cleaned_text': 0,
            'final_boxes': 0
        }
        
        metadata_dir = os.path.join(self.data_root_path, 'metadata')
        
        if not os.path.exists(metadata_dir):
            logger.error(f'Metadata directory not found: {metadata_dir}')
            return total_results
        
        # 캡처 메타데이터 파일들 찾기
        capture_files = [f for f in os.listdir(metadata_dir) if f.startswith('capture_') and f.endswith('.json')]
        
        logger.info(f'Found {len(capture_files)} capture files to optimize')
        
        for capture_file in capture_files:
            file_path = os.path.join(metadata_dir, capture_file)
            file_results = self.optimize_single_capture(file_path)
            
            total_results['files_processed'] += 1
            for key in ['original_boxes', 'merged_boxes', 'removed_invalid', 'cleaned_text', 'final_boxes']:
                total_results[key] += file_results[key]
        
        # 최적화 비율 계산
        if total_results['original_boxes'] > 0:
            reduction_rate = (total_results['original_boxes'] - total_results['final_boxes']) / total_results['original_boxes']
            total_results['reduction_rate'] = reduction_rate
        else:
            total_results['reduction_rate'] = 0.0
        
        return total_results

    def generate_optimization_report(self, results: Dict) -> str:
        """최적화 결과 리포트 생성"""
        report = f'''
=== 데이터 최적화 리포트 ===
처리된 파일 수: {results['files_processed']}
원본 바운딩 박스 수: {results['original_boxes']}
최종 바운딩 박스 수: {results['final_boxes']}

최적화 상세:
- 제거된 유효하지 않은 박스: {results['removed_invalid']}
- 병합된 박스 쌍: {results['merged_boxes']}
- 정제된 텍스트 항목: {results['cleaned_text']}

감소율: {results.get('reduction_rate', 0) * 100:.1f}%
생성 시간: {datetime.now().isoformat()}
'''
        return report.strip()
