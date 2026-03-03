# Generated: 2025-10-14 15:40:00 KST
"""
Strategy Database Helper
크롤링 전략 관련 DB 작업을 위한 헬퍼 함수
"""

import json
from typing import Dict, Any, Optional, Tuple
from loguru import logger


class StrategyDatabaseHelper:
    """크롤링 전략 DB 작업 헬퍼 클래스"""

    def __init__(self, db_manager):
        """
        Args:
            db_manager: CrawlDatabaseManager 인스턴스
        """
        self.db = db_manager

    def save_strategy(
        self,
        target_id: int,
        strategy: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Tuple[int, bool]:
        """
        크롤링 전략 저장 (INSERT or UPDATE)

        Args:
            target_id: 대상 사이트 ID
            strategy: 전략 JSON (step2_strategy.json 내용)
            validation_result: 검증 결과 JSON (step3_validation.json 내용)

        Returns:
            (strategy_id, is_new): 전략 ID와 신규 생성 여부
        """
        strategy_version = strategy.get('strategy_version', '1.0')
        tool_selected = strategy['approach']['tool']
        estimated_success_rate = strategy['estimated_success_rate']
        actual_success_rate = validation_result['success_rate']

        strategy_json_str = json.dumps(strategy, ensure_ascii=False)
        notes = (
            f'Sonic Koi 방법론 Step 1-3 완료. '
            f'검증 성공률: {actual_success_rate:.1%}'
        )

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 기존 전략 확인
            cursor.execute('''
                SELECT STRATEGY_ID FROM CRAWL_STRATEGIES
                WHERE TARGET_ID = :1 AND STRATEGY_VERSION = :2
            ''', (target_id, strategy_version))

            existing = cursor.fetchone()

            if existing:
                # UPDATE 기존 전략
                strategy_id = existing[0]
                logger.info(f'기존 전략 업데이트 (STRATEGY_ID: {strategy_id})')

                cursor.execute('''
                    UPDATE CRAWL_STRATEGIES
                    SET STRATEGY_JSON = :1,
                        TOOL_SELECTED = :2,
                        ESTIMATED_SUCCESS_RATE = :3,
                        STATUS = 'active',
                        VALIDATION_COUNT = VALIDATION_COUNT + 1,
                        NOTES = :4
                    WHERE STRATEGY_ID = :5
                ''', (
                    strategy_json_str,
                    tool_selected,
                    estimated_success_rate,
                    notes,
                    strategy_id
                ))

                is_new = False
            else:
                # INSERT 새 전략
                logger.info('새로운 전략 생성')

                # 시퀀스 확인 및 생성
                cursor.execute('''
                    SELECT COUNT(*) FROM user_sequences
                    WHERE sequence_name = 'CRAWL_STRATEGIES_SEQ'
                ''')

                if cursor.fetchone()[0] == 0:
                    logger.info('CRAWL_STRATEGIES_SEQ 시퀀스 생성')
                    cursor.execute('''
                        CREATE SEQUENCE CRAWL_STRATEGIES_SEQ
                        START WITH 1 INCREMENT BY 1
                    ''')

                cursor.execute('''
                    INSERT INTO CRAWL_STRATEGIES (
                        STRATEGY_ID, TARGET_ID, STRATEGY_VERSION, STRATEGY_JSON,
                        TOOL_SELECTED, ESTIMATED_SUCCESS_RATE, STATUS,
                        VALIDATION_COUNT, CREATED_AT, CREATED_BY, NOTES
                    ) VALUES (
                        CRAWL_STRATEGIES_SEQ.NEXTVAL, :1, :2, :3, :4, :5,
                        'active', 1, SYSTIMESTAMP, 'claude_code', :6
                    )
                ''', (
                    target_id,
                    strategy_version,
                    strategy_json_str,
                    tool_selected,
                    estimated_success_rate,
                    notes
                ))

                # 생성된 STRATEGY_ID 가져오기
                cursor.execute('SELECT CRAWL_STRATEGIES_SEQ.CURRVAL FROM DUAL')
                strategy_id = cursor.fetchone()[0]

                is_new = True

            conn.commit()
            logger.info(f'✅ 전략 저장 완료 (STRATEGY_ID: {strategy_id})')

            return strategy_id, is_new

    def update_target_status(
        self,
        target_id: int,
        strategy_id: int,
        strategy_version: str,
        success_rate: float,
        html_file_path: Optional[str] = None,
        last_step: int = 3
    ) -> None:
        """
        CRAWL_TARGETS 테이블 업데이트

        Args:
            target_id: 대상 사이트 ID
            strategy_id: 저장된 전략 ID
            strategy_version: 전략 버전
            success_rate: 검증 성공률
            html_file_path: HTML 샘플 파일 경로 (선택)
            last_step: 마지막 완료 단계 (기본값: 3)
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            notes = (
                f'Step {last_step} 완료. '
                f'성공률: {success_rate:.1%}. '
                f'STRATEGY_ID: {strategy_id}'
            )

            # CRAWL_TARGETS 업데이트 (UPDATED_AT 사용)
            if html_file_path:
                cursor.execute('''
                    UPDATE CRAWL_TARGETS
                    SET LAST_STEP_COMPLETED = :1,
                        CURRENT_STRATEGY_VERSION = :2,
                        CURRENT_SUCCESS_RATE = :3,
                        STATUS = 'active',
                        SAMPLE_HTML_PATH = :4,
                        UPDATED_AT = SYSTIMESTAMP,
                        NOTES = :5
                    WHERE TARGET_ID = :6
                ''', (
                    last_step,
                    strategy_version,
                    success_rate,
                    html_file_path,
                    notes,
                    target_id
                ))
            else:
                cursor.execute('''
                    UPDATE CRAWL_TARGETS
                    SET LAST_STEP_COMPLETED = :1,
                        CURRENT_STRATEGY_VERSION = :2,
                        CURRENT_SUCCESS_RATE = :3,
                        STATUS = 'active',
                        UPDATED_AT = SYSTIMESTAMP,
                        NOTES = :4
                    WHERE TARGET_ID = :5
                ''', (
                    last_step,
                    strategy_version,
                    success_rate,
                    notes,
                    target_id
                ))

            rows_updated = cursor.rowcount
            conn.commit()

            logger.info(f'✅ CRAWL_TARGETS 업데이트 완료 ({rows_updated} row)')

    def mark_target_as_failed(
        self,
        target_id: int,
        reason: str
    ) -> None:
        """
        사이트를 'failed' 상태로 표시

        Args:
            target_id: 대상 사이트 ID
            reason: 실패 사유
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE CRAWL_TARGETS
                SET STATUS = 'failed',
                    NOTES = :1,
                    UPDATED_AT = SYSTIMESTAMP
                WHERE TARGET_ID = :2
            ''', (reason, target_id))

            conn.commit()
            logger.info(f'✅ 사이트 #{target_id} 실패 처리 완료: {reason}')
