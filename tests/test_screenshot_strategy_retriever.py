#!/usr/bin/env python3
# Generated: 2025-10-16 21:00:00 KST
"""
ScreenshotStrategyRetriever 단위 테스트

CRAWL_STRATEGIES 테이블에서 스크린샷 전략 조회 기능 테스트
"""

import pytest
import json
import os
import sys

# scholar 모듈 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.connection import DatabaseConnection
from crawler.screenshot_strategy_retriever import ScreenshotStrategyRetriever


@pytest.fixture
def db_connection():
    """데이터베이스 연결 fixture"""
    db = DatabaseConnection()
    with db.get_connection() as conn:
        yield conn


@pytest.fixture
def retriever(db_connection):
    """ScreenshotStrategyRetriever fixture"""
    return ScreenshotStrategyRetriever(db_connection)


@pytest.fixture
def sample_screenshot_strategy():
    """샘플 스크린샷 전략"""
    return {
        "strategy_version": "2.0",
        "strategy_type": "screenshot",
        "viewport": {
            "width": 794,
            "height": 1123,
            "scale": 1.0
        },
        "scroll_strategy": {
            "type": "smooth",
            "speed": 500,
            "pause_between_scrolls": 1000
        },
        "split_strategy": {
            "unit": "A4",
            "overlap_px": 0,
            "max_splits": 50
        },
        "wait_strategy": {
            "type": "fixed",
            "duration": 3
        },
        "image_format": "PNG",
        "image_quality": 90
    }


class TestScreenshotStrategyRetriever:
    """ScreenshotStrategyRetriever 단위 테스트"""

    def test_get_strategy_success(self, retriever, db_connection, sample_screenshot_strategy):
        """전략 조회 성공 테스트"""
        # 테스트용 전략 삽입
        cursor = db_connection.cursor()
        try:
            # 먼저 테스트용 target 생성 (없는 경우)
            cursor.execute("""
                INSERT INTO CRAWL_TARGETS (
                    TARGET_ID, SITE_NAME, BASE_URL, STATUS
                ) VALUES (
                    9999, 'Test Site', 'https://test.com', 'active'
                )
            """)

            # 전략 삽입
            cursor.execute("""
                INSERT INTO CRAWL_STRATEGIES (
                    STRATEGY_ID, TARGET_ID, STRATEGY_JSON, STATUS
                ) VALUES (
                    SEQ_STRATEGY.NEXTVAL, 9999, :strategy_json, 'active'
                )
            """, {'strategy_json': json.dumps(sample_screenshot_strategy)})

            db_connection.commit()

            # 전략 조회
            strategy = retriever.get_strategy(target_id=9999)

            assert strategy is not None
            assert strategy['strategy_type'] == 'screenshot'
            assert strategy['viewport']['width'] == 794
            assert strategy['viewport']['height'] == 1123

        finally:
            # 테스트 데이터 정리
            cursor.execute("DELETE FROM CRAWL_STRATEGIES WHERE TARGET_ID = 9999")
            cursor.execute("DELETE FROM CRAWL_TARGETS WHERE TARGET_ID = 9999")
            db_connection.commit()
            cursor.close()

    def test_get_strategy_not_found(self, retriever):
        """존재하지 않는 전략 조회 시 예외 발생"""
        with pytest.raises(ValueError, match="No strategy found"):
            retriever.get_strategy(target_id=99999)

    def test_get_strategy_invalid_type(self, retriever, db_connection):
        """잘못된 strategy_type 조회 시 예외 발생"""
        cursor = db_connection.cursor()
        try:
            # 잘못된 타입의 전략 삽입
            cursor.execute("""
                INSERT INTO CRAWL_TARGETS (
                    TARGET_ID, SITE_NAME, BASE_URL, STATUS
                ) VALUES (
                    9998, 'Test Site 2', 'https://test2.com', 'active'
                )
            """)

            cursor.execute("""
                INSERT INTO CRAWL_STRATEGIES (
                    STRATEGY_ID, TARGET_ID, STRATEGY_JSON, STATUS
                ) VALUES (
                    SEQ_STRATEGY.NEXTVAL, 9998, :strategy_json, 'active'
                )
            """, {'strategy_json': json.dumps({
                "strategy_type": "article",  # 잘못된 타입
                "viewport": {"width": 800, "height": 600}
            })})

            db_connection.commit()

            # 조회 시 예외 발생
            with pytest.raises(ValueError, match="Invalid strategy_type"):
                retriever.get_strategy(target_id=9998)

        finally:
            # 테스트 데이터 정리
            cursor.execute("DELETE FROM CRAWL_STRATEGIES WHERE TARGET_ID = 9998")
            cursor.execute("DELETE FROM CRAWL_TARGETS WHERE TARGET_ID = 9998")
            db_connection.commit()
            cursor.close()

    def test_get_strategy_with_cache(self, retriever, db_connection, sample_screenshot_strategy):
        """캐시 사용 전략 조회"""
        cursor = db_connection.cursor()
        try:
            # 테스트용 데이터 삽입
            cursor.execute("""
                INSERT INTO CRAWL_TARGETS (
                    TARGET_ID, SITE_NAME, BASE_URL, STATUS
                ) VALUES (
                    9997, 'Test Site 3', 'https://test3.com', 'active'
                )
            """)

            cursor.execute("""
                INSERT INTO CRAWL_STRATEGIES (
                    STRATEGY_ID, TARGET_ID, STRATEGY_JSON, STATUS
                ) VALUES (
                    SEQ_STRATEGY.NEXTVAL, 9997, :strategy_json, 'active'
                )
            """, {'strategy_json': json.dumps(sample_screenshot_strategy)})

            db_connection.commit()

            # 첫 번째 조회 (DB에서)
            strategy1 = retriever.get_strategy_with_cache(target_id=9997)

            # 두 번째 조회 (캐시에서)
            strategy2 = retriever.get_strategy_with_cache(target_id=9997)

            # 동일한 객체여야 함
            assert strategy1 == strategy2

        finally:
            # 테스트 데이터 정리
            cursor.execute("DELETE FROM CRAWL_STRATEGIES WHERE TARGET_ID = 9997")
            cursor.execute("DELETE FROM CRAWL_TARGETS WHERE TARGET_ID = 9997")
            db_connection.commit()
            cursor.close()

    def test_clear_cache(self, retriever):
        """캐시 초기화"""
        # 캐시에 데이터 추가
        retriever._cache[1] = {"test": "data"}
        assert len(retriever._cache) > 0

        # 캐시 초기화
        retriever.clear_cache()
        assert len(retriever._cache) == 0

    def test_get_all_screenshot_strategies(self, retriever, db_connection, sample_screenshot_strategy):
        """모든 스크린샷 전략 조회"""
        cursor = db_connection.cursor()
        try:
            # 여러 전략 삽입
            for i in range(2):
                target_id = 9990 + i
                cursor.execute("""
                    INSERT INTO CRAWL_TARGETS (
                        TARGET_ID, SITE_NAME, BASE_URL, STATUS
                    ) VALUES (
                        :target_id, :site_name, :base_url, 'active'
                    )
                """, {
                    'target_id': target_id,
                    'site_name': f'Test Site {i}',
                    'base_url': f'https://test{i}.com'
                })

                cursor.execute("""
                    INSERT INTO CRAWL_STRATEGIES (
                        STRATEGY_ID, TARGET_ID, STRATEGY_JSON, STATUS
                    ) VALUES (
                        SEQ_STRATEGY.NEXTVAL, :target_id, :strategy_json, 'active'
                    )
                """, {
                    'target_id': target_id,
                    'strategy_json': json.dumps(sample_screenshot_strategy)
                })

            db_connection.commit()

            # 전략 조회
            strategies = retriever.get_all_screenshot_strategies()

            # 최소 2개 이상이어야 함
            assert len(strategies) >= 2

            # 각 전략에 target_id와 strategy 포함
            for item in strategies:
                assert 'target_id' in item
                assert 'strategy' in item
                assert item['strategy'].get('strategy_type') == 'screenshot'

        finally:
            # 테스트 데이터 정리
            for i in range(2):
                target_id = 9990 + i
                cursor.execute("DELETE FROM CRAWL_STRATEGIES WHERE TARGET_ID = :id", {'id': target_id})
                cursor.execute("DELETE FROM CRAWL_TARGETS WHERE TARGET_ID = :id", {'id': target_id})
            db_connection.commit()
            cursor.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
