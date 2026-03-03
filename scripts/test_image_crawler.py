#!/usr/bin/env python3
# Generated: 2025-10-16 21:35:00 KST
"""
Phase 2B 이미지 크롤러 테스트 스크립트

continuous_image_crawler.py의 핵심 기능을 테스트합니다.
"""

import os
import sys

# scholar 모듈 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from database.connection import DatabaseConnection
from database.crawl_target_manager import CrawlTargetManager
from crawler.screenshot_strategy_retriever import ScreenshotStrategyRetriever
from crawler.screenshot_crawler import ScreenshotCrawler
from database.image_capture_manager import ImageCaptureManager
from loguru import logger


def test_single_site_capture(target_id: int):
    """단일 사이트 캡처 테스트

    Args:
        target_id: CRAWL_TARGETS.TARGET_ID
    """
    logger.info(f"Testing screenshot capture for target_id={target_id}")

    db = DatabaseConnection()

    with db.get_connection() as conn:
        # 1. Target 조회
        target_manager = CrawlTargetManager(conn)
        targets = target_manager.get_active_targets(limit=1)

        if not targets:
            logger.error("No active targets found")
            return

        target = targets[0]
        logger.info(f"Target: {target['site_name']} ({target['site_url']})")

        # 2. 전략 조회
        strategy_retriever = ScreenshotStrategyRetriever(conn)

        try:
            strategy = strategy_retriever.get_strategy(target_id)
            logger.info(f"Strategy retrieved: {strategy.get('strategy_type')}")
        except ValueError as e:
            logger.error(f"No strategy found: {e}")
            return

        # 3. 스크린샷 캡처
        logger.info("Capturing screenshots...")

        with ScreenshotCrawler(strategy, headless=True) as crawler:
            screenshots = crawler.capture_with_split(target['site_url'])

        logger.info(f"Captured {len(screenshots)} screenshots")

        # 4. 이미지 저장
        image_manager = ImageCaptureManager(conn)
        saved_count = 0

        for idx, screenshot_data in enumerate(screenshots):
            try:
                capture_id = image_manager.save_screenshot(
                    url=f"{target['site_url']}#page{idx+1}",
                    image_data=screenshot_data,
                    image_format=strategy.get('image_format', 'PNG'),
                    metadata={
                        'page_number': idx + 1,
                        'total_pages': len(screenshots),
                        'target_id': target_id,
                        'site_name': target['site_name'],
                        'test_mode': True
                    }
                )
                saved_count += 1
                logger.info(f"Saved {idx+1}/{len(screenshots)}: capture_id={capture_id}")

            except Exception as e:
                logger.error(f"Failed to save screenshot {idx+1}: {e}")

        logger.info(f"✅ Test complete: {saved_count}/{len(screenshots)} images saved")


def test_list_targets():
    """Active targets 목록 출력"""
    logger.info("Listing active targets...")

    db = DatabaseConnection()

    with db.get_connection() as conn:
        target_manager = CrawlTargetManager(conn)
        targets = target_manager.get_active_targets(limit=10)

        if not targets:
            logger.warning("No active targets found")
            return

        logger.info(f"Found {len(targets)} active targets:")

        for idx, target in enumerate(targets):
            logger.info(
                f"  {idx+1}. ID={target['target_id']}, "
                f"Name={target['site_name']}, "
                f"URL={target['site_url']}"
            )


def test_list_strategies():
    """스크린샷 전략 목록 출력"""
    logger.info("Listing screenshot strategies...")

    db = DatabaseConnection()

    with db.get_connection() as conn:
        retriever = ScreenshotStrategyRetriever(conn)
        strategies = retriever.get_all_screenshot_strategies()

        if not strategies:
            logger.warning("No screenshot strategies found")
            return

        logger.info(f"Found {len(strategies)} screenshot strategies:")

        for idx, item in enumerate(strategies):
            strategy = item['strategy']
            logger.info(
                f"  {idx+1}. Target ID={item['target_id']}, "
                f"Version={strategy.get('strategy_version')}, "
                f"Format={strategy.get('image_format')}"
            )


if __name__ == '__main__':
    # 로그 설정
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    import argparse

    parser = argparse.ArgumentParser(description='Test Phase 2B Image Crawler')
    parser.add_argument('--list-targets', action='store_true', help='List active targets')
    parser.add_argument('--list-strategies', action='store_true', help='List screenshot strategies')
    parser.add_argument('--capture', type=int, metavar='TARGET_ID', help='Capture screenshots for target')

    args = parser.parse_args()

    try:
        if args.list_targets:
            test_list_targets()
        elif args.list_strategies:
            test_list_strategies()
        elif args.capture:
            test_single_site_capture(args.capture)
        else:
            parser.print_help()

    except Exception as e:
        logger.exception(f"Test failed: {e}")
        sys.exit(1)
