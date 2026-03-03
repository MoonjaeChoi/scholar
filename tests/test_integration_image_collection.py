#!/usr/bin/env python3
# Generated: 2025-10-16 21:50:00 KST
"""
Phase 2B 통합 테스트

전체 이미지 수집 워크플로우를 테스트합니다:
1. Active targets 조회
2. Screenshot 전략 조회
3. A4 분할 캡처
4. WEB_CAPTURE_DATA 저장
"""

import pytest
import time
import os
import sys
from PIL import Image
from io import BytesIO

# scholar 모듈 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.connection import DatabaseConnection
from database.crawl_target_manager import CrawlTargetManager
from crawler.screenshot_strategy_retriever import ScreenshotStrategyRetriever
from crawler.screenshot_crawler import ScreenshotCrawler
from database.image_capture_manager import ImageCaptureManager
from loguru import logger


@pytest.fixture(scope="module")
def db_connection():
    """데이터베이스 연결 fixture (모듈 스코프)"""
    db = DatabaseConnection()
    with db.get_connection() as conn:
        yield conn


@pytest.fixture
def active_target(db_connection):
    """Active target 하나 조회"""
    target_manager = CrawlTargetManager(db_connection)
    targets = target_manager.get_active_targets(limit=1)

    if not targets:
        pytest.skip("No active targets available")

    return targets[0]


class TestImageCollectionIntegration:
    """이미지 수집 통합 테스트"""

    def test_full_workflow(self, db_connection, active_target):
        """전체 이미지 수집 워크플로우 테스트"""
        logger.info(f"Testing full workflow with target: {active_target['site_name']}")

        # 1. 타겟 조회 검증
        assert active_target['target_id'] > 0
        assert active_target['site_url']
        assert active_target['status'] == 'active'

        # 2. 전략 조회
        strategy_retriever = ScreenshotStrategyRetriever(db_connection)

        try:
            strategy = strategy_retriever.get_strategy(active_target['target_id'])
        except ValueError:
            pytest.skip(f"No strategy for target {active_target['target_id']}")

        # 전략 검증
        assert 'viewport' in strategy
        assert strategy['viewport']['width'] == 794
        assert strategy['viewport']['height'] == 1123

        # 3. 스크린샷 캡처
        start_time = time.time()

        with ScreenshotCrawler(strategy, headless=True) as crawler:
            screenshots = crawler.capture_with_split(active_target['site_url'])

        capture_duration = time.time() - start_time

        # 캡처 검증
        assert len(screenshots) > 0, "No screenshots captured"
        assert all(isinstance(s, bytes) for s in screenshots), "Invalid screenshot data"

        logger.info(
            f"Captured {len(screenshots)} screenshots in {capture_duration:.2f}s "
            f"({capture_duration/len(screenshots):.2f}s/screenshot)"
        )

        # 4. 이미지 저장 (처음 3개만 테스트)
        image_manager = ImageCaptureManager(db_connection)
        saved_ids = []

        for idx, screenshot_data in enumerate(screenshots[:3]):
            # 이미지 데이터 검증
            img = Image.open(BytesIO(screenshot_data))
            assert img.width == 794
            assert img.height <= 1123

            # 저장
            capture_id = image_manager.save_screenshot(
                url=f"{active_target['site_url']}#test_page{idx+1}",
                image_data=screenshot_data,
                image_format=strategy.get('image_format', 'PNG'),
                metadata={
                    'page_number': idx + 1,
                    'total_pages': len(screenshots),
                    'target_id': active_target['target_id'],
                    'test_mode': True
                }
            )

            assert capture_id > 0
            saved_ids.append(capture_id)

            logger.info(f"Saved screenshot {idx+1}/3: capture_id={capture_id}")

        # 5. 저장된 이미지 조회 검증
        for capture_id in saved_ids:
            screenshot = image_manager.get_screenshot_by_id(capture_id)
            assert screenshot is not None
            assert screenshot['url'].startswith(active_target['site_url'])
            assert screenshot['image_format'] == strategy.get('image_format', 'PNG')
            assert screenshot['processing_status'] == 'completed'

        logger.info(f"✅ Full workflow test passed: {len(saved_ids)} images saved")

    def test_target_manager_integration(self, db_connection):
        """CrawlTargetManager 통합 테스트"""
        target_manager = CrawlTargetManager(db_connection)

        # Active targets 조회
        targets = target_manager.get_active_targets(limit=5)
        assert isinstance(targets, list)

        if targets:
            target = targets[0]
            assert 'target_id' in target
            assert 'site_url' in target
            assert 'site_name' in target
            assert target['status'] == 'active'

            logger.info(f"Found {len(targets)} active targets")

    def test_strategy_retriever_integration(self, db_connection):
        """ScreenshotStrategyRetriever 통합 테스트"""
        retriever = ScreenshotStrategyRetriever(db_connection)

        # 모든 스크린샷 전략 조회
        strategies = retriever.get_all_screenshot_strategies()
        assert isinstance(strategies, list)

        if strategies:
            strategy = strategies[0]['strategy']

            # 필수 필드 검증
            assert 'viewport' in strategy
            assert 'split_strategy' in strategy
            assert strategy.get('strategy_type') == 'screenshot'

            logger.info(f"Found {len(strategies)} screenshot strategies")

    def test_image_capture_manager_integration(self, db_connection):
        """ImageCaptureManager 통합 테스트"""
        image_manager = ImageCaptureManager(db_connection)

        # 최근 스크린샷 조회
        recent = image_manager.get_recent_screenshots(limit=5)
        assert isinstance(recent, list)

        if recent:
            screenshot = recent[0]
            assert 'capture_id' in screenshot
            assert 'url' in screenshot
            assert 'image_path' in screenshot

            logger.info(f"Found {len(recent)} recent screenshots")


class TestPerformance:
    """성능 테스트"""

    def test_capture_performance(self, db_connection, active_target):
        """캡처 성능 측정"""
        strategy_retriever = ScreenshotStrategyRetriever(db_connection)

        try:
            strategy = strategy_retriever.get_strategy(active_target['target_id'])
        except ValueError:
            pytest.skip(f"No strategy for target {active_target['target_id']}")

        # 성능 측정
        start_time = time.time()

        with ScreenshotCrawler(strategy, headless=True) as crawler:
            screenshots = crawler.capture_with_split(active_target['site_url'])

        duration = time.time() - start_time

        # 성능 기준 검증
        assert duration < 60, f"Capture too slow: {duration:.2f}s (should be < 60s)"
        assert len(screenshots) > 0, "No screenshots captured"

        avg_time_per_screenshot = duration / len(screenshots)

        logger.info(
            f"Performance metrics:\n"
            f"  - Total duration: {duration:.2f}s\n"
            f"  - Screenshots: {len(screenshots)}\n"
            f"  - Avg time/screenshot: {avg_time_per_screenshot:.2f}s"
        )

        # 평균 시간 검증
        assert avg_time_per_screenshot < 10, "Screenshot capture too slow per image"

    def test_image_size(self, db_connection, active_target):
        """이미지 크기 검증"""
        strategy_retriever = ScreenshotStrategyRetriever(db_connection)

        try:
            strategy = strategy_retriever.get_strategy(active_target['target_id'])
        except ValueError:
            pytest.skip(f"No strategy for target {active_target['target_id']}")

        with ScreenshotCrawler(strategy, headless=True) as crawler:
            screenshots = crawler.capture_with_split(active_target['site_url'])

        if not screenshots:
            pytest.skip("No screenshots captured")

        # 첫 번째 이미지 크기 확인
        first_screenshot = screenshots[0]
        size_bytes = len(first_screenshot)
        size_kb = size_bytes / 1024

        logger.info(f"Image size: {size_kb:.2f} KB")

        # 크기 검증 (PNG는 크기가 클 수 있으므로 1MB 제한)
        assert size_kb < 1024, f"Image too large: {size_kb:.2f} KB (should be < 1MB)"

    def test_memory_usage(self, db_connection, active_target):
        """메모리 사용량 측정"""
        import psutil
        import os

        process = psutil.Process(os.getpid())

        # 시작 메모리
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        strategy_retriever = ScreenshotStrategyRetriever(db_connection)

        try:
            strategy = strategy_retriever.get_strategy(active_target['target_id'])
        except ValueError:
            pytest.skip(f"No strategy for target {active_target['target_id']}")

        with ScreenshotCrawler(strategy, headless=True) as crawler:
            screenshots = crawler.capture_with_split(active_target['site_url'])

        # 종료 메모리
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        mem_delta = mem_after - mem_before

        logger.info(
            f"Memory usage:\n"
            f"  - Before: {mem_before:.2f} MB\n"
            f"  - After: {mem_after:.2f} MB\n"
            f"  - Delta: {mem_delta:.2f} MB"
        )

        # 메모리 증가량 검증 (4GB 이내)
        assert mem_delta < 4096, f"Memory usage too high: {mem_delta:.2f} MB"


class TestDataValidation:
    """데이터 검증 테스트"""

    def test_image_format_validation(self, db_connection, active_target):
        """이미지 포맷 검증"""
        strategy_retriever = ScreenshotStrategyRetriever(db_connection)

        try:
            strategy = strategy_retriever.get_strategy(active_target['target_id'])
        except ValueError:
            pytest.skip(f"No strategy for target {active_target['target_id']}")

        with ScreenshotCrawler(strategy, headless=True) as crawler:
            screenshots = crawler.capture_with_split(active_target['site_url'])

        if not screenshots:
            pytest.skip("No screenshots captured")

        # 이미지 포맷 검증
        for idx, screenshot_data in enumerate(screenshots[:3]):
            img = Image.open(BytesIO(screenshot_data))

            assert img.width == 794, f"Invalid width: {img.width}"
            assert img.height <= 1123, f"Invalid height: {img.height}"
            assert img.format in ['PNG', 'JPEG'], f"Invalid format: {img.format}"

            logger.debug(
                f"Screenshot {idx+1}: {img.width}×{img.height}, "
                f"format={img.format}, mode={img.mode}"
            )

    def test_hash_uniqueness(self, db_connection):
        """이미지 해시 고유성 검증"""
        image_manager = ImageCaptureManager(db_connection)

        # 샘플 이미지 2개 생성 (다른 색상)
        img1 = Image.new('RGB', (794, 1123), color='red')
        buffer1 = BytesIO()
        img1.save(buffer1, format='PNG')
        data1 = buffer1.getvalue()

        img2 = Image.new('RGB', (794, 1123), color='blue')
        buffer2 = BytesIO()
        img2.save(buffer2, format='PNG')
        data2 = buffer2.getvalue()

        # 해시 계산
        hash1 = image_manager._calculate_hash(data1)
        hash2 = image_manager._calculate_hash(data2)

        # 해시 고유성 검증
        assert hash1 != hash2, "Different images should have different hashes"
        assert len(hash1) == 64, "SHA-256 hash should be 64 characters"
        assert len(hash2) == 64, "SHA-256 hash should be 64 characters"

        logger.info(f"Hash 1: {hash1[:16]}...")
        logger.info(f"Hash 2: {hash2[:16]}...")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--log-cli-level=INFO'])
