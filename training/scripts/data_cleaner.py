# Generated: 2025-10-02 22:52:00 KST
"""
Data Cleaner - 불량 데이터 자동 제거
"""

import cx_Oracle
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DataCleaner:
    """불량 데이터 자동 제거 시스템"""

    def __init__(self, db_connection: cx_Oracle.Connection):
        """
        Args:
            db_connection: Oracle 데이터베이스 연결
        """
        self.db = db_connection

    def soft_delete_invalid_data(self,
                                 min_quality_score: float = 0.3,
                                 batch_size: int = 100) -> int:
        """
        품질 점수 기준 불량 데이터 논리적 삭제

        Args:
            min_quality_score: 이 점수 미만은 삭제 대상
            batch_size: 한 번에 처리할 데이터 개수

        Returns:
            int: 삭제된 데이터 개수
        """
        query = """
        SELECT capture_id, quality_score, invalid_reason
        FROM DATA_QUALITY_METRICS
        WHERE is_valid = 'N'
          AND quality_score < :min_quality
          AND capture_id IN (
              SELECT capture_id
              FROM WEB_CAPTURE_DATA
              WHERE deleted_at IS NULL
          )
        FETCH FIRST :batch_size ROWS ONLY
        """

        update_query = """
        UPDATE WEB_CAPTURE_DATA
        SET deleted_at = SYSTIMESTAMP,
            deletion_reason = :reason
        WHERE capture_id = :capture_id
          AND deleted_at IS NULL
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query, {
                'min_quality': min_quality_score,
                'batch_size': batch_size
            })

            invalid_data = cursor.fetchall()
            deleted_count = 0

            for capture_id, quality_score, invalid_reason in invalid_data:
                reason = f"Low quality score: {quality_score:.3f} - {invalid_reason}"

                cursor.execute(update_query, {
                    'capture_id': capture_id,
                    'reason': reason
                })
                deleted_count += 1

            self.db.commit()
            logger.info(f"Soft deleted {deleted_count} invalid data samples")
            return deleted_count

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error soft deleting invalid data: {e}")
            raise

    def delete_failed_training_data(self,
                                    max_failure_count: int = 3,
                                    batch_size: int = 100) -> int:
        """
        반복적으로 학습 실패한 데이터 삭제

        Args:
            max_failure_count: 이 횟수 이상 실패 시 삭제
            batch_size: 한 번에 처리할 데이터 개수

        Returns:
            int: 삭제된 데이터 개수
        """
        query = """
        SELECT capture_id, failure_count
        FROM (
            SELECT capture_id, COUNT(*) as failure_count
            FROM TRAINING_HISTORY
            WHERE is_successful = 'N'
            GROUP BY capture_id
        )
        WHERE failure_count >= :max_failures
          AND capture_id IN (
              SELECT capture_id
              FROM WEB_CAPTURE_DATA
              WHERE deleted_at IS NULL
          )
        FETCH FIRST :batch_size ROWS ONLY
        """

        update_query = """
        UPDATE WEB_CAPTURE_DATA
        SET deleted_at = SYSTIMESTAMP,
            deletion_reason = :reason
        WHERE capture_id = :capture_id
          AND deleted_at IS NULL
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query, {
                'max_failures': max_failure_count,
                'batch_size': batch_size
            })

            failed_data = cursor.fetchall()
            deleted_count = 0

            for capture_id, failure_count in failed_data:
                reason = f"Training failed {failure_count} times"

                cursor.execute(update_query, {
                    'capture_id': capture_id,
                    'reason': reason
                })
                deleted_count += 1

            self.db.commit()
            logger.info(f"Deleted {deleted_count} repeatedly failed training samples")
            return deleted_count

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting failed training data: {e}")
            raise

    def delete_duplicate_data(self, batch_size: int = 100) -> int:
        """
        중복 데이터 삭제 (URL + created_at 기준)

        Args:
            batch_size: 한 번에 처리할 데이터 개수

        Returns:
            int: 삭제된 중복 데이터 개수
        """
        query = """
        SELECT capture_id
        FROM (
            SELECT capture_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY URL, TRUNC(created_at)
                       ORDER BY created_at DESC
                   ) as rn
            FROM WEB_CAPTURE_DATA
            WHERE deleted_at IS NULL
        )
        WHERE rn > 1
        FETCH FIRST :batch_size ROWS ONLY
        """

        update_query = """
        UPDATE WEB_CAPTURE_DATA
        SET deleted_at = SYSTIMESTAMP,
            deletion_reason = 'Duplicate data (same URL + date)'
        WHERE capture_id = :capture_id
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query, {'batch_size': batch_size})

            duplicate_ids = [row[0] for row in cursor.fetchall()]
            deleted_count = 0

            for capture_id in duplicate_ids:
                cursor.execute(update_query, {'capture_id': capture_id})
                deleted_count += 1

            self.db.commit()
            logger.info(f"Deleted {deleted_count} duplicate data samples")
            return deleted_count

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting duplicate data: {e}")
            raise

    def cleanup_old_data(self,
                        days_to_keep: int = 365,
                        batch_size: int = 100) -> int:
        """
        오래된 저품질 데이터 삭제

        Args:
            days_to_keep: 이 일수보다 오래된 데이터 중 저품질 삭제
            batch_size: 한 번에 처리할 데이터 개수

        Returns:
            int: 삭제된 데이터 개수
        """
        query = """
        SELECT wcd.capture_id
        FROM WEB_CAPTURE_DATA wcd
        INNER JOIN DATA_QUALITY_METRICS dqm
            ON wcd.capture_id = dqm.capture_id
        WHERE wcd.deleted_at IS NULL
          AND wcd.created_at < SYSTIMESTAMP - :days_to_keep
          AND dqm.quality_score < 0.5
        FETCH FIRST :batch_size ROWS ONLY
        """

        update_query = """
        UPDATE WEB_CAPTURE_DATA
        SET deleted_at = SYSTIMESTAMP,
            deletion_reason = :reason
        WHERE capture_id = :capture_id
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query, {
                'days_to_keep': days_to_keep,
                'batch_size': batch_size
            })

            old_data = cursor.fetchall()
            deleted_count = 0

            for (capture_id,) in old_data:
                reason = f"Old low-quality data (>{days_to_keep} days)"

                cursor.execute(update_query, {
                    'capture_id': capture_id,
                    'reason': reason
                })
                deleted_count += 1

            self.db.commit()
            logger.info(f"Deleted {deleted_count} old low-quality data samples")
            return deleted_count

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cleaning up old data: {e}")
            raise

    def get_deletion_statistics(self) -> Dict:
        """
        삭제 통계 조회

        Returns:
            Dict: 삭제 통계 정보
        """
        query = """
        SELECT
            COUNT(*) as total_deleted,
            COUNT(DISTINCT deletion_reason) as unique_reasons,
            MIN(deleted_at) as first_deletion,
            MAX(deleted_at) as last_deletion
        FROM WEB_CAPTURE_DATA
        WHERE deleted_at IS NOT NULL
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query)
            row = cursor.fetchone()

            return {
                'total_deleted': row[0] or 0,
                'unique_reasons': row[1] or 0,
                'first_deletion': row[2],
                'last_deletion': row[3]
            }

        except Exception as e:
            logger.error(f"Error getting deletion statistics: {e}")
            return {}

    def run_all_cleanup(self,
                       min_quality: float = 0.3,
                       max_failures: int = 3,
                       days_to_keep: int = 365) -> Dict:
        """
        모든 정리 작업 실행

        Args:
            min_quality: 최소 품질 점수
            max_failures: 최대 실패 횟수
            days_to_keep: 데이터 보관 일수

        Returns:
            Dict: 각 정리 작업별 삭제 개수
        """
        results = {}

        try:
            # 1. 품질 기준 삭제
            results['quality_based'] = self.soft_delete_invalid_data(min_quality)

            # 2. 반복 실패 삭제
            results['failed_training'] = self.delete_failed_training_data(max_failures)

            # 3. 중복 데이터 삭제 - DISABLED (시계열 데이터 보존)
            # 이유: 같은 URL의 시간대별 크롤링은 정상 데이터
            # 108개 URL → 412개 레코드 (평균 3.8회 크롤링)
            results['duplicates'] = 0
            logger.info("Duplicate removal disabled - preserving time-series data")

            # 4. 오래된 저품질 데이터 삭제
            results['old_data'] = self.cleanup_old_data(days_to_keep)

            # 5. 전체 통계
            results['total_deleted'] = sum(results.values())

            logger.info(f"Cleanup completed: {results}")
            return results

        except Exception as e:
            logger.error(f"Error running all cleanup: {e}")
            raise
