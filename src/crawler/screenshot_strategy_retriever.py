#!/usr/bin/env python3
# Generated: 2025-10-16 18:50:00 KST
"""
스크린샷 전략 조회 모듈

CRAWL_STRATEGIES 테이블에서 스크린샷 전략을 조회합니다.
"""

from typing import Dict, Any, Optional
import json
import os
from loguru import logger

# 환경 변수로 Oracle 라이브러리 선택
USE_PYTHON_ORACLEDB = os.getenv('USE_PYTHON_ORACLEDB', 'false').lower() == 'true'

if USE_PYTHON_ORACLEDB:
    import oracledb as oracle_lib
    logger.info("✅ ScreenshotStrategyRetriever: Using python-oracledb (Thin Mode)")
else:
    import cx_Oracle as oracle_lib
    logger.info("✅ ScreenshotStrategyRetriever: Using cx_Oracle")


class ScreenshotStrategyRetriever:
    """CRAWL_STRATEGIES 테이블에서 스크린샷 전략 조회"""

    def __init__(self, connection):
        """
        Args:
            connection: Oracle DB 연결 객체
        """
        self.connection = connection
        self._cache = {}

    def get_strategy(self, target_id: int) -> Dict[str, Any]:
        """최신 스크린샷 전략 조회

        Args:
            target_id: CRAWL_TARGETS.TARGET_ID

        Returns:
            전략 JSON (dict)

        Raises:
            ValueError: 전략 없음 또는 strategy_type이 'screenshot'가 아님
        """
        cursor = self.connection.cursor()

        try:
            query = """
                SELECT STRATEGY_JSON
                FROM CRAWL_STRATEGIES
                WHERE TARGET_ID = :target_id
                  AND STATUS = 'active'
                ORDER BY CREATED_AT DESC
                FETCH FIRST 1 ROWS ONLY
            """

            cursor.execute(query, {'target_id': target_id})
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"No strategy found for target_id={target_id}")

            # CLOB 처리 (python-oracledb Thin Mode는 자동으로 dict로 변환)
            strategy_raw = row[0]
            if isinstance(strategy_raw, dict):
                strategy = strategy_raw
            elif hasattr(strategy_raw, 'read'):
                strategy_str = strategy_raw.read()
                strategy = json.loads(strategy_str)
            else:
                strategy = json.loads(str(strategy_raw))

            # strategy_type 검증 (있는 경우에만)
            strategy_type = strategy.get('strategy_type')
            if strategy_type and strategy_type != 'screenshot':
                raise ValueError(
                    f"Invalid strategy_type: {strategy_type} "
                    "(expected 'screenshot')"
                )

            logger.info(f"Strategy retrieved: target_id={target_id}")
            return strategy

        finally:
            cursor.close()

    def get_strategy_with_cache(self, target_id: int) -> Dict[str, Any]:
        """캐시 사용 전략 조회

        Args:
            target_id: CRAWL_TARGETS.TARGET_ID

        Returns:
            전략 JSON (dict)
        """
        if target_id in self._cache:
            logger.debug(f"Strategy cache hit: target_id={target_id}")
            return self._cache[target_id]

        strategy = self.get_strategy(target_id)
        self._cache[target_id] = strategy
        return strategy

    def clear_cache(self):
        """캐시 초기화"""
        self._cache.clear()
        logger.debug("Strategy cache cleared")

    def get_all_screenshot_strategies(self) -> list:
        """모든 활성 스크린샷 전략 조회

        Returns:
            전략 목록 (각 전략은 target_id와 strategy 포함)
        """
        cursor = self.connection.cursor()

        try:
            query = """
                SELECT
                    TARGET_ID,
                    STRATEGY_JSON
                FROM CRAWL_STRATEGIES
                WHERE STATUS = 'active'
                ORDER BY TARGET_ID
            """

            cursor.execute(query)

            strategies = []
            for row in cursor:
                target_id = row[0]
                strategy_raw = row[1]

                # CLOB 처리 (python-oracledb Thin Mode는 자동으로 dict로 변환)
                if isinstance(strategy_raw, dict):
                    strategy = strategy_raw
                elif hasattr(strategy_raw, 'read'):
                    strategy_str = strategy_raw.read()
                    strategy = json.loads(strategy_str)
                else:
                    strategy = json.loads(str(strategy_raw))

                # strategy_type이 'screenshot'인 경우만 포함
                strategy_type = strategy.get('strategy_type')
                if strategy_type == 'screenshot':
                    strategies.append({
                        'target_id': target_id,
                        'strategy': strategy
                    })

            logger.info(f"Found {len(strategies)} screenshot strategies")
            return strategies

        finally:
            cursor.close()
