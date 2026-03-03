# Generated: 2025-10-16 10:35:00 KST
"""
Crawl Target Manager - Database-Driven Site Management
데이터베이스 기반 크롤 대상 관리
"""

import cx_Oracle
from typing import List, Dict, Optional
from loguru import logger
from datetime import datetime


class CrawlTargetManager:
    """CRAWL_TARGETS 테이블 관리 클래스"""

    def __init__(self, connection_or_params):
        """
        Args:
            connection_or_params: Oracle 연결 객체 또는 연결 정보 dict
                - connection 객체: 기존 연결 사용 (권장)
                - dict: 연결 정보로 새로 연결 생성
                    - host: 데이터베이스 호스트
                    - port: 포트 번호
                    - service_name: 서비스 이름
                    - username: 사용자명
                    - password: 비밀번호
        """
        # connection 객체가 전달된 경우
        if hasattr(connection_or_params, 'cursor'):
            self.connection = connection_or_params
            self.connection_params = None
            self._owns_connection = False  # 외부 연결 사용
        # dict가 전달된 경우 (기존 방식)
        else:
            self.connection_params = connection_or_params
            self.connection = None
            self._owns_connection = True  # 자체 연결 관리

    def connect(self):
        """데이터베이스 연결 (자체 연결 관리 시에만)"""
        # 외부 연결을 사용하는 경우 연결하지 않음
        if not self._owns_connection:
            return

        # 이미 연결된 경우
        if self.connection:
            return

        try:
            dsn = cx_Oracle.makedsn(
                self.connection_params['host'],
                self.connection_params['port'],
                service_name=self.connection_params['service_name']
            )
            self.connection = cx_Oracle.connect(
                user=self.connection_params['username'],
                password=self.connection_params['password'],
                dsn=dsn,
                encoding="UTF-8"
            )
            logger.info(f"Connected to Oracle database: {self.connection_params['host']}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def disconnect(self):
        """데이터베이스 연결 해제 (자체 연결 관리 시에만)"""
        # 외부 연결을 사용하는 경우 해제하지 않음
        if not self._owns_connection:
            return

        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Disconnected from Oracle database")

    def get_active_targets(self, limit: Optional[int] = None, priority_min: int = 1) -> List[Dict]:
        """활성 크롤 대상 목록 조회

        Args:
            limit: 최대 조회 개수 (None이면 전체)
            priority_min: 최소 우선순위 (1-10, 낮을수록 높은 우선순위)

        Returns:
            크롤 대상 정보 리스트
        """
        if not self.connection:
            self.connect()

        try:
            cursor = self.connection.cursor()

            query = """
                SELECT
                    target_id,
                    site_url,
                    site_name,
                    site_type,
                    priority,
                    status,
                    current_strategy_version,
                    current_success_rate,
                    last_step_completed
                FROM CRAWL_TARGETS
                WHERE status = 'active'
                  AND priority >= :priority_min
                ORDER BY priority ASC, target_id ASC
            """

            if limit:
                query += f" FETCH FIRST {limit} ROWS ONLY"

            cursor.execute(query, {'priority_min': priority_min})

            columns = [col[0].lower() for col in cursor.description]
            results = []

            for row in cursor:
                target = dict(zip(columns, row))
                results.append(target)

            cursor.close()
            logger.info(f"Retrieved {len(results)} active crawl targets")
            return results

        except Exception as e:
            logger.error(f"Failed to get active targets: {e}")
            return []

    def get_pending_targets(self, limit: Optional[int] = None) -> List[Dict]:
        """대기 중인 크롤 대상 목록 조회"""
        if not self.connection:
            self.connect()

        try:
            cursor = self.connection.cursor()

            query = """
                SELECT
                    target_id,
                    site_url,
                    site_name,
                    site_type,
                    priority,
                    status
                FROM CRAWL_TARGETS
                WHERE status = 'pending'
                ORDER BY priority ASC, target_id ASC
            """

            if limit:
                query += f" FETCH FIRST {limit} ROWS ONLY"

            cursor.execute(query)

            columns = [col[0].lower() for col in cursor.description]
            results = []

            for row in cursor:
                target = dict(zip(columns, row))
                results.append(target)

            cursor.close()
            logger.info(f"Retrieved {len(results)} pending crawl targets")
            return results

        except Exception as e:
            logger.error(f"Failed to get pending targets: {e}")
            return []

    def update_target_status(self, target_id: int, status: str, notes: Optional[str] = None):
        """크롤 대상 상태 업데이트

        Args:
            target_id: 대상 ID
            status: 새로운 상태 (pending, active, paused, completed, failed)
            notes: 메모 (선택)
        """
        if not self.connection:
            self.connect()

        try:
            cursor = self.connection.cursor()

            if notes:
                cursor.execute("""
                    UPDATE CRAWL_TARGETS
                    SET status = :status,
                        notes = :notes,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE target_id = :target_id
                """, {
                    'status': status,
                    'notes': notes,
                    'target_id': target_id
                })
            else:
                cursor.execute("""
                    UPDATE CRAWL_TARGETS
                    SET status = :status,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE target_id = :target_id
                """, {
                    'status': status,
                    'target_id': target_id
                })

            self.connection.commit()
            cursor.close()
            logger.info(f"Updated target {target_id} status to '{status}'")

        except Exception as e:
            logger.error(f"Failed to update target status: {e}")
            if self.connection:
                self.connection.rollback()

    def update_success_rate(self, target_id: int, success_rate: float):
        """크롤 성공률 업데이트"""
        if not self.connection:
            self.connect()

        try:
            cursor = self.connection.cursor()

            cursor.execute("""
                UPDATE CRAWL_TARGETS
                SET current_success_rate = :success_rate,
                    updated_at = CURRENT_TIMESTAMP
                WHERE target_id = :target_id
            """, {
                'success_rate': success_rate,
                'target_id': target_id
            })

            self.connection.commit()
            cursor.close()
            logger.debug(f"Updated target {target_id} success rate to {success_rate}%")

        except Exception as e:
            logger.error(f"Failed to update success rate: {e}")
            if self.connection:
                self.connection.rollback()

    def get_target_count_by_status(self) -> Dict[str, int]:
        """상태별 크롤 대상 개수 조회"""
        if not self.connection:
            self.connect()

        try:
            cursor = self.connection.cursor()

            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM CRAWL_TARGETS
                GROUP BY status
                ORDER BY status
            """)

            results = {}
            for row in cursor:
                results[row[0]] = row[1]

            cursor.close()
            return results

        except Exception as e:
            logger.error(f"Failed to get target count: {e}")
            return {}

    def __enter__(self):
        """Context manager 진입"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.disconnect()
