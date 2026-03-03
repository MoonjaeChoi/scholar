# Generated: 2025-10-02 22:51:00 KST
"""
Data Quality Evaluator - 데이터 품질 자동 평가
"""

import cx_Oracle
from typing import Dict, Tuple, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


class DataQualityEvaluator:
    """데이터 품질 자동 평가 시스템"""

    # 품질 평가 임계값
    QUALITY_THRESHOLDS = {
        'bbox_count_min': 1,           # 최소 bbox 개수 (1개만 있으면 학습 가능)
        'bbox_count_max': 99999,       # 최대 bbox 개수 제한 제거 (학습 시 상위 100개 선택)
        'avg_bbox_area_min': 1,        # 최소 bbox 면적 (1px²: bbox 크기 무시)
        'bbox_density_max': 1.0,       # 최대 밀집도 (1.0 = 100%: 밀집도 무시)
        'text_clarity_min': 0.04,      # 최소 OCR 신뢰도 ✅ 유일한 평가 기준
        'image_quality_min': 0.0       # 최소 이미지 품질 (0.0: 이미지 품질 무시)
    }

    # 가중치 (총합 = 1.0)
    WEIGHTS = {
        'text_clarity': 0.40,
        'image_quality': 0.30,
        'bbox_count': 0.15,
        'bbox_area': 0.10,
        'bbox_density': 0.05
    }

    def __init__(self, db_connection: cx_Oracle.Connection):
        """
        Args:
            db_connection: Oracle 데이터베이스 연결
        """
        self.db = db_connection

    def evaluate_capture(self, capture_id: int) -> Dict:
        """
        개별 데이터 품질 평가

        Args:
            capture_id: 평가할 capture ID

        Returns:
            Dict: {
                'is_valid': bool,
                'quality_score': float (0.0~1.0),
                'invalid_reason': str or None,
                'metrics': Dict
            }
        """
        try:
            # 1. BBox 개수 확인
            bbox_count = self._get_bbox_count(capture_id)
            if bbox_count < self.QUALITY_THRESHOLDS['bbox_count_min']:
                return {
                    'is_valid': False,
                    'quality_score': 0.0,
                    'invalid_reason': f'Too few bboxes: {bbox_count}',
                    'metrics': {'bbox_count': bbox_count}
                }

            if bbox_count > self.QUALITY_THRESHOLDS['bbox_count_max']:
                return {
                    'is_valid': False,
                    'quality_score': 0.0,
                    'invalid_reason': f'Too many bboxes (noise): {bbox_count}',
                    'metrics': {'bbox_count': bbox_count}
                }

            # 2. BBox 면적 확인
            avg_area = self._get_avg_bbox_area(capture_id)
            if avg_area < self.QUALITY_THRESHOLDS['avg_bbox_area_min']:
                return {
                    'is_valid': False,
                    'quality_score': 0.0,
                    'invalid_reason': f'Bboxes too small: {avg_area:.1f}px²',
                    'metrics': {'avg_bbox_area': avg_area}
                }

            # 3. BBox 밀집도 확인 (overlap)
            density = self._calculate_bbox_density(capture_id)
            if density > self.QUALITY_THRESHOLDS['bbox_density_max']:
                return {
                    'is_valid': False,
                    'quality_score': 0.0,
                    'invalid_reason': f'High bbox overlap: {density:.2f}',
                    'metrics': {'bbox_density': density}
                }

            # 4. OCR 신뢰도 확인
            text_clarity = self._calculate_text_clarity(capture_id)
            if text_clarity < self.QUALITY_THRESHOLDS['text_clarity_min']:
                return {
                    'is_valid': False,
                    'quality_score': 0.0,
                    'invalid_reason': f'Low OCR confidence: {text_clarity:.2f}',
                    'metrics': {'text_clarity': text_clarity}
                }

            # 5. 이미지 품질 확인
            image_quality = self._evaluate_image_quality(capture_id)
            if image_quality < self.QUALITY_THRESHOLDS['image_quality_min']:
                return {
                    'is_valid': False,
                    'quality_score': 0.0,
                    'invalid_reason': f'Low image quality: {image_quality:.2f}',
                    'metrics': {'image_quality': image_quality}
                }

            # 6. 종합 품질 점수 계산
            quality_score = self._calculate_overall_score(
                bbox_count, avg_area, density, text_clarity, image_quality
            )

            return {
                'is_valid': True,
                'quality_score': quality_score,
                'invalid_reason': None,
                'metrics': {
                    'bbox_count': bbox_count,
                    'avg_bbox_area': avg_area,
                    'bbox_density': density,
                    'text_clarity': text_clarity,
                    'image_quality': image_quality
                }
            }

        except Exception as e:
            logger.error(f"Error evaluating capture {capture_id}: {e}")
            return {
                'is_valid': False,
                'quality_score': 0.0,
                'invalid_reason': f'Evaluation error: {str(e)}',
                'metrics': {}
            }

    def save_quality_metrics(self,
                            capture_id: int,
                            evaluation_result: Dict) -> None:
        """
        품질 평가 결과를 DB에 저장

        Args:
            capture_id: Capture ID
            evaluation_result: evaluate_capture() 반환값
        """
        metrics = evaluation_result.get('metrics', {})

        query = """
        MERGE INTO DATA_QUALITY_METRICS dqm
        USING (SELECT :capture_id as capture_id FROM DUAL) src
        ON (dqm.capture_id = src.capture_id)
        WHEN MATCHED THEN
            UPDATE SET
                bbox_count = :bbox_count,
                avg_bbox_area = :avg_area,
                bbox_density = :density,
                text_clarity_score = :text_clarity,
                image_quality_score = :image_quality,
                quality_score = :quality_score,
                is_valid = :is_valid,
                invalid_reason = :invalid_reason,
                calculated_at = SYSTIMESTAMP
        WHEN NOT MATCHED THEN
            INSERT (
                metric_id, capture_id, bbox_count, avg_bbox_area,
                bbox_density, text_clarity_score, image_quality_score,
                quality_score, is_valid, invalid_reason
            ) VALUES (
                DATA_QUALITY_METRICS_SEQ.NEXTVAL, :capture_id, :bbox_count,
                :avg_area, :density, :text_clarity, :image_quality,
                :quality_score, :is_valid, :invalid_reason
            )
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query, {
                'capture_id': capture_id,
                'bbox_count': metrics.get('bbox_count'),
                'avg_area': metrics.get('avg_bbox_area'),
                'density': metrics.get('bbox_density'),
                'text_clarity': metrics.get('text_clarity'),
                'image_quality': metrics.get('image_quality'),
                'quality_score': evaluation_result['quality_score'],
                'is_valid': 'Y' if evaluation_result['is_valid'] else 'N',
                'invalid_reason': evaluation_result.get('invalid_reason')
            })

            self.db.commit()

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving quality metrics for {capture_id}: {e}")
            raise

    def evaluate_all_pending(self, batch_size: int = 100) -> int:
        """
        평가되지 않은 모든 데이터 품질 평가

        Args:
            batch_size: 한 번에 처리할 데이터 개수

        Returns:
            int: 평가 완료된 데이터 개수
        """
        query = """
        SELECT wcd.capture_id
        FROM WEB_CAPTURE_DATA wcd
        LEFT JOIN DATA_QUALITY_METRICS dqm
            ON wcd.capture_id = dqm.capture_id
        WHERE wcd.deleted_at IS NULL
          AND (dqm.metric_id IS NULL
               OR dqm.calculated_at < wcd.updated_at)
        FETCH FIRST :batch_size ROWS ONLY
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query, {'batch_size': batch_size})
            pending_captures = [row[0] for row in cursor.fetchall()]

            logger.info(f"Found {len(pending_captures)} pending evaluations")

            evaluated_count = 0
            for capture_id in pending_captures:
                result = self.evaluate_capture(capture_id)
                self.save_quality_metrics(capture_id, result)
                evaluated_count += 1

            logger.info(f"Evaluated {evaluated_count} captures")
            return evaluated_count

        except Exception as e:
            logger.error(f"Error evaluating pending data: {e}")
            raise

    # Private helper methods

    def _get_bbox_count(self, capture_id: int) -> int:
        """BBox 개수 조회"""
        query = "SELECT COUNT(*) FROM TEXT_BOUNDING_BOXES WHERE capture_id = :cid"
        cursor = self.db.cursor()
        cursor.execute(query, {'cid': capture_id})
        return cursor.fetchone()[0]

    def _get_avg_bbox_area(self, capture_id: int) -> float:
        """평균 BBox 면적 계산"""
        query = """
        SELECT AVG(width * height)
        FROM TEXT_BOUNDING_BOXES
        WHERE capture_id = :cid
          AND width > 0 AND height > 0
        """
        cursor = self.db.cursor()
        cursor.execute(query, {'cid': capture_id})
        result = cursor.fetchone()[0]
        return float(result) if result else 0.0

    def _calculate_bbox_density(self, capture_id: int) -> float:
        """BBox 밀집도 계산 (overlap 비율)"""
        query = """
        SELECT X_COORDINATE, Y_COORDINATE, width, height
        FROM TEXT_BOUNDING_BOXES
        WHERE capture_id = :cid
          AND width > 0 AND height > 0
        """
        cursor = self.db.cursor()
        cursor.execute(query, {'cid': capture_id})
        boxes = cursor.fetchall()

        if len(boxes) < 2:
            return 0.0

        # 간단한 overlap 계산 (중심점 거리 기반)
        overlap_count = 0
        total_pairs = 0

        for i in range(len(boxes)):
            x1, y1, w1, h1 = boxes[i]
            cx1, cy1 = x1 + w1/2, y1 + h1/2

            for j in range(i+1, len(boxes)):
                x2, y2, w2, h2 = boxes[j]
                cx2, cy2 = x2 + w2/2, y2 + h2/2

                distance = np.sqrt((cx1-cx2)**2 + (cy1-cy2)**2)
                min_size = min(w1, h1, w2, h2)

                if distance < min_size * 0.5:  # 50% 이내면 overlap
                    overlap_count += 1

                total_pairs += 1

        return overlap_count / total_pairs if total_pairs > 0 else 0.0

    def _calculate_text_clarity(self, capture_id: int) -> float:
        """
        OCR 신뢰도 계산
        (text_content 길이와 bbox 크기의 비율로 추정)
        """
        query = """
        SELECT AVG(LENGTH(TEXT_CONTENT) * 10.0 / (width * height))
        FROM TEXT_BOUNDING_BOXES
        WHERE capture_id = :cid
          AND TEXT_CONTENT IS NOT NULL
          AND LENGTH(TEXT_CONTENT) > 0
          AND width > 0 AND height > 0
        """
        cursor = self.db.cursor()
        cursor.execute(query, {'cid': capture_id})
        result = cursor.fetchone()[0]

        if result is None:
            return 0.0

        # 0.0~1.0 범위로 정규화
        normalized = min(float(result), 1.0)
        return max(normalized, 0.0)

    def _evaluate_image_quality(self, capture_id: int) -> float:
        """
        이미지 품질 평가
        (bbox 분포 균일도로 추정)
        """
        query = """
        SELECT STDDEV(width), STDDEV(height), AVG(width), AVG(height)
        FROM TEXT_BOUNDING_BOXES
        WHERE capture_id = :cid
          AND width > 0 AND height > 0
        """
        cursor = self.db.cursor()
        cursor.execute(query, {'cid': capture_id})
        std_w, std_h, avg_w, avg_h = cursor.fetchone()

        if not all([std_w, std_h, avg_w, avg_h]):
            return 0.5  # 기본값

        # 변동계수 (CV) 계산
        cv_w = std_w / avg_w if avg_w > 0 else 1.0
        cv_h = std_h / avg_h if avg_h > 0 else 1.0

        # CV가 낮을수록 균일 → 품질 높음
        quality = 1.0 - min((cv_w + cv_h) / 2, 1.0)
        return max(quality, 0.0)

    def _calculate_overall_score(self,
                                 bbox_count: int,
                                 avg_area: float,
                                 density: float,
                                 text_clarity: float,
                                 image_quality: float) -> float:
        """
        종합 품질 점수 계산 (0.0 ~ 1.0)

        가중치:
        - text_clarity: 40%
        - image_quality: 30%
        - bbox_count: 15%
        - avg_area: 10%
        - density: 5% (낮을수록 좋음)
        """
        # 정규화
        bbox_score = min(bbox_count / 100.0, 1.0)  # 100개 기준
        area_score = min(avg_area / 1000.0, 1.0)   # 1000px² 기준
        density_score = 1.0 - density               # 낮을수록 높은 점수

        overall = (
            text_clarity * self.WEIGHTS['text_clarity'] +
            image_quality * self.WEIGHTS['image_quality'] +
            bbox_score * self.WEIGHTS['bbox_count'] +
            area_score * self.WEIGHTS['bbox_area'] +
            density_score * self.WEIGHTS['bbox_density']
        )

        return round(overall, 3)
