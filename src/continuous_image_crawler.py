#!/usr/bin/env python3
# Generated: 2025-10-16 21:30:00 KST
"""
Phase 2B: PaddleOCR 학습용 이미지 수집 시스템

CRAWL_STRATEGIES의 스크린샷 전략을 사용하여
웹페이지를 A4 단위로 분할 캡처하고 WEB_CAPTURE_DATA에 저장
"""

import os
import sys
import time
import signal
from typing import Dict
from loguru import logger
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# 경로 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database.connection import DatabaseConnection
from src.database.crawl_target_manager import CrawlTargetManager
from src.crawler.screenshot_strategy_retriever import ScreenshotStrategyRetriever
from src.crawler.screenshot_crawler import ScreenshotCrawler
from src.database.image_capture_manager import ImageCaptureManager

# 환경 변수
CRAWL_INTERVAL_SECONDS = int(os.getenv('CRAWL_INTERVAL_SECONDS', '300'))
IMAGE_CRAWL_BATCH_SIZE = int(os.getenv('IMAGE_CRAWL_BATCH_SIZE', '10'))
PROMETHEUS_METRICS_PORT = int(os.getenv('PROMETHEUS_METRICS_PORT', '8005'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Prometheus 메트릭
screenshot_captures_total = Counter(
    'screenshot_captures_total',
    'Total screenshot capture attempts',
    ['site_name', 'status']
)

image_splits_total = Counter(
    'image_splits_total',
    'Total A4 image splits saved',
    ['site_name']
)

capture_duration_seconds = Histogram(
    'screenshot_capture_duration_seconds',
    'Duration of screenshot capture operations',
    ['site_name'],
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

active_crawls_gauge = Gauge(
    'active_crawls',
    'Number of currently active crawl operations'
)

last_crawl_timestamp = Gauge(
    'last_crawl_timestamp',
    'Timestamp of last crawl operation'
)

# Graceful Shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """시그널 핸들러"""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def capture_site_screenshots(
    target: Dict,
    strategy_retriever: ScreenshotStrategyRetriever,
    image_manager: ImageCaptureManager
) -> int:
    """단일 사이트 스크린샷 캡처

    Args:
        target: CRAWL_TARGETS 레코드
        strategy_retriever: 전략 조회 객체
        image_manager: 이미지 저장 객체

    Returns:
        저장된 이미지 수
    """
    target_id = target['target_id']
    site_url = target['site_url']
    site_name = target['site_name']

    logger.info(f"📸 Capturing screenshots: {site_name} ({site_url})")

    try:
        active_crawls_gauge.inc()

        # 1. 전략 조회
        try:
            strategy = strategy_retriever.get_strategy_with_cache(target_id)
        except ValueError as e:
            logger.warning(f"❌ No screenshot strategy for {site_name}: {e}")
            screenshot_captures_total.labels(site_name=site_name, status='no_strategy').inc()
            return 0

        # 2. 스크린샷 캡처 (A4 분할)
        start_time = time.time()

        try:
            with ScreenshotCrawler(strategy, headless=True) as crawler:
                screenshots = crawler.capture_with_split(site_url)
        except Exception as e:
            logger.error(f"❌ Screenshot capture failed for {site_name}: {e}")
            screenshot_captures_total.labels(site_name=site_name, status='capture_failed').inc()
            return 0

        duration = time.time() - start_time

        logger.info(
            f"✅ Captured {len(screenshots)} screenshots from {site_name} "
            f"in {duration:.2f}s"
        )

        # 메트릭 기록
        screenshot_captures_total.labels(site_name=site_name, status='success').inc()
        capture_duration_seconds.labels(site_name=site_name).observe(duration)

        # 3. 각 분할 이미지 저장
        saved_count = 0
        image_format = strategy.get('image_format', 'PNG')

        for idx, screenshot_data in enumerate(screenshots):
            try:
                capture_id = image_manager.save_screenshot(
                    url=f"{site_url}#page{idx+1}",
                    image_data=screenshot_data,
                    image_format=image_format,
                    metadata={
                        'page_number': idx + 1,
                        'total_pages': len(screenshots),
                        'target_id': target_id,
                        'site_name': site_name,
                        'capture_date': time.strftime('%Y-%m-%d'),
                        'strategy_version': strategy.get('strategy_version', 'unknown')
                    }
                )
                saved_count += 1

                # 메트릭 기록
                image_splits_total.labels(site_name=site_name).inc()

                logger.debug(
                    f"💾 Saved screenshot {idx+1}/{len(screenshots)}: "
                    f"capture_id={capture_id}"
                )

            except Exception as e:
                logger.error(f"❌ Failed to save screenshot {idx+1}/{len(screenshots)}: {e}")

        logger.info(
            f"💾 Saved {saved_count}/{len(screenshots)} screenshots for {site_name}"
        )

        return saved_count

    except Exception as e:
        logger.exception(f"❌ Unexpected error during capture of {site_name}: {e}")
        screenshot_captures_total.labels(site_name=site_name, status='error').inc()
        return 0

    finally:
        active_crawls_gauge.dec()


def main():
    """메인 무한 루프"""
    global shutdown_requested

    logger.info("=" * 70)
    logger.info("🚀 Starting Phase 2B: Image Collection System")
    logger.info("=" * 70)
    logger.info(f"⏱️  Crawl interval: {CRAWL_INTERVAL_SECONDS}s")
    logger.info(f"📦 Batch size: {IMAGE_CRAWL_BATCH_SIZE}")
    logger.info(f"📊 Metrics port: {PROMETHEUS_METRICS_PORT}")
    logger.info(f"📝 Log level: {LOG_LEVEL}")
    logger.info("=" * 70)

    # Prometheus 메트릭 서버 시작
    try:
        start_http_server(PROMETHEUS_METRICS_PORT)
        logger.info(f"✅ Prometheus metrics server started on port {PROMETHEUS_METRICS_PORT}")
    except Exception as e:
        logger.error(f"❌ Failed to start Prometheus server: {e}")

    batch_count = 0

    while not shutdown_requested:
        batch_count += 1
        batch_start_time = time.time()

        logger.info(f"\n{'='*70}")
        logger.info(f"🔄 Starting crawl batch #{batch_count}")
        logger.info(f"{'='*70}")

        try:
            # 데이터베이스 연결
            db = DatabaseConnection()

            with db.get_connection() as conn:
                target_manager = CrawlTargetManager(conn)
                strategy_retriever = ScreenshotStrategyRetriever(conn)
                image_manager = ImageCaptureManager(conn)

                # Active 사이트 조회
                targets = target_manager.get_active_targets(
                    limit=IMAGE_CRAWL_BATCH_SIZE
                )

                if not targets:
                    logger.warning("⚠️  No active targets found")
                    time.sleep(60)
                    continue

                logger.info(f"📋 Processing {len(targets)} active targets")

                total_images = 0

                for idx, target in enumerate(targets):
                    if shutdown_requested:
                        logger.info("🛑 Shutdown requested, stopping batch")
                        break

                    logger.info(f"\n--- Target {idx+1}/{len(targets)} ---")

                    count = capture_site_screenshots(
                        target,
                        strategy_retriever,
                        image_manager
                    )
                    total_images += count

                    # 사이트 간 대기 (서버 부하 방지)
                    if idx < len(targets) - 1 and not shutdown_requested:
                        logger.debug("⏸️  Waiting 2s before next target...")
                        time.sleep(2)

                batch_duration = time.time() - batch_start_time

                logger.info(f"\n{'='*70}")
                logger.info(f"✅ Batch #{batch_count} complete:")
                logger.info(f"   - Sites processed: {len(targets)}")
                logger.info(f"   - Images saved: {total_images}")
                logger.info(f"   - Duration: {batch_duration:.2f}s")
                logger.info(f"{'='*70}")

                # 메트릭 업데이트
                last_crawl_timestamp.set(time.time())

        except KeyboardInterrupt:
            logger.info("⌨️  Keyboard interrupt received")
            shutdown_requested = True
            break

        except Exception as e:
            logger.exception(f"❌ Error in main loop (batch #{batch_count}): {e}")
            # 에러 후 잠시 대기
            time.sleep(30)

        if not shutdown_requested:
            logger.info(f"\n😴 Sleeping for {CRAWL_INTERVAL_SECONDS}s until next batch...\n")
            time.sleep(CRAWL_INTERVAL_SECONDS)

    logger.info("\n" + "="*70)
    logger.info("👋 Graceful shutdown completed")
    logger.info("="*70)


if __name__ == '__main__':
    # 로그 설정
    logger.remove()  # 기본 핸들러 제거

    # 콘솔 로그
    logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )

    # 파일 로그
    log_dir = os.getenv('LOG_DIR', '/opt/scholar/logs')
    os.makedirs(log_dir, exist_ok=True)

    logger.add(
        os.path.join(log_dir, "continuous_image_crawler.log"),
        rotation="100 MB",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    )

    logger.add(
        os.path.join(log_dir, "continuous_image_crawler_error.log"),
        rotation="50 MB",
        retention="60 days",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    )

    logger.info(f"📁 Logs directory: {log_dir}")

    try:
        main()
    except KeyboardInterrupt:
        logger.info("⌨️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"💥 Fatal error: {e}")
        sys.exit(1)
