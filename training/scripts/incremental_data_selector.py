# Generated: 2025-10-02 22:50:00 KST
"""
Incremental Data Selector - 중복 없는 학습 데이터 선택
"""

import cx_Oracle
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class IncrementalDataSelector:
    """중복 학습 방지를 위한 학습 데이터 선택기"""

    def __init__(self, db_connection: cx_Oracle.Connection):
        """
        Args:
            db_connection: Oracle 데이터베이스 연결
        """
        self.db = db_connection

    def get_untrained_data(self,
                          batch_size: int = 500,
                          min_quality_score: float = 0.7,
                          min_bbox_count: int = 50) -> List[int]:
        """
        아직 학습하지 않았거나 실패한 고품질 데이터 선택

        Args:
            batch_size: 한 번에 가져올 데이터 개수
            min_quality_score: 최소 품질 점수 (0.0~1.0)
            min_bbox_count: 최소 bbox 개수

        Returns:
            List[int]: 선택된 capture_id 리스트
        """
        query = """
        SELECT
            wcd.capture_id,
            dqm.bbox_count,
            dqm.text_clarity_score,
            dqm.quality_score
        FROM WEB_CAPTURE_DATA wcd
        INNER JOIN DATA_QUALITY_METRICS dqm
            ON wcd.capture_id = dqm.capture_id
        LEFT JOIN TRAINING_HISTORY th
            ON wcd.capture_id = th.capture_id
            AND th.is_successful = 'Y'
        WHERE
            -- 아직 학습하지 않았거나
            th.training_id IS NULL
            -- 논리적 삭제 안 됨
            AND wcd.deleted_at IS NULL
            -- 품질 기준 통과
            AND dqm.is_valid = 'Y'
            AND dqm.quality_score >= :min_quality
            -- bbox 개수 기준
            AND dqm.bbox_count >= :min_bbox
        ORDER BY
            dqm.quality_score DESC,
            wcd.created_at DESC
        FETCH FIRST :batch_size ROWS ONLY
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query, {
                'min_quality': min_quality_score,
                'min_bbox': min_bbox_count,
                'batch_size': batch_size
            })

            results = cursor.fetchall()
            capture_ids = [row[0] for row in results]

            logger.info(f"Selected {len(capture_ids)} untrained samples")
            return capture_ids

        except Exception as e:
            logger.error(f"Error selecting untrained data: {e}")
            raise

    def mark_training_started(self,
                             capture_ids: List[int],
                             batch_id: str) -> None:
        """
        학습 시작 기록 (중복 학습 추적용)

        Args:
            capture_ids: 학습 시작할 capture_id 리스트
            batch_id: 학습 배치 식별자 (예: BATCH_20251002_225000)
        """
        query = """
        INSERT INTO TRAINING_HISTORY (
            training_id, capture_id, training_batch_id,
            training_start_time, is_successful
        ) VALUES (
            TRAINING_HISTORY_SEQ.NEXTVAL, :capture_id, :batch_id,
            SYSTIMESTAMP, 'P'
        )
        """

        try:
            cursor = self.db.cursor()
            for capture_id in capture_ids:
                cursor.execute(query, {
                    'capture_id': capture_id,
                    'batch_id': batch_id
                })

            self.db.commit()
            logger.info(f"Marked {len(capture_ids)} samples as training started")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error marking training started: {e}")
            raise

    def mark_training_completed(self,
                               capture_ids: List[int],
                               batch_id: str,
                               is_successful: bool,
                               loss_value: Optional[float] = None,
                               epoch_trained: Optional[int] = None) -> None:
        """
        학습 완료 기록

        Args:
            capture_ids: 학습 완료된 capture_id 리스트
            batch_id: 학습 배치 식별자
            is_successful: 학습 성공 여부
            loss_value: 최종 loss 값
            epoch_trained: 학습 epoch 수
        """
        query = """
        UPDATE TRAINING_HISTORY
        SET training_end_time = SYSTIMESTAMP,
            is_successful = :is_successful,
            loss_value = :loss_value,
            epoch_trained = :epoch_trained
        WHERE capture_id = :capture_id
          AND training_batch_id = :batch_id
        """

        try:
            cursor = self.db.cursor()
            success_flag = 'Y' if is_successful else 'N'

            for capture_id in capture_ids:
                cursor.execute(query, {
                    'capture_id': capture_id,
                    'batch_id': batch_id,
                    'is_successful': success_flag,
                    'loss_value': loss_value,
                    'epoch_trained': epoch_trained
                })

            self.db.commit()
            logger.info(f"Marked {len(capture_ids)} samples as completed (success={is_successful})")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error marking training completed: {e}")
            raise

    def get_training_statistics(self) -> Dict:
        """
        학습 통계 조회

        Returns:
            Dict: 학습 통계 정보
        """
        query = """
        SELECT
            COUNT(DISTINCT capture_id) as total_samples,
            COUNT(DISTINCT CASE WHEN is_successful = 'Y' THEN capture_id END) as trained_samples,
            COUNT(DISTINCT CASE WHEN is_successful = 'N' THEN capture_id END) as failed_samples,
            COUNT(DISTINCT CASE WHEN is_successful = 'P' THEN capture_id END) as training_samples
        FROM TRAINING_HISTORY
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query)
            row = cursor.fetchone()

            return {
                'total_samples': row[0] or 0,
                'trained_samples': row[1] or 0,
                'failed_samples': row[2] or 0,
                'training_samples': row[3] or 0
            }

        except Exception as e:
            logger.error(f"Error getting training statistics: {e}")
            return {}
