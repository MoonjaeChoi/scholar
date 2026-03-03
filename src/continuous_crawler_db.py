# Generated: 2025-10-16 10:40:00 KST
"""
Database-Driven Continuous Web Crawler
데이터베이스 기반 무한 크롤링 시스템 (300+ 사이트)
"""

import os
import sys
import time
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv
from prometheus_client import start_http_server, Counter, Gauge, Histogram
from typing import List, Dict

# 상대 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Prometheus metrics
crawl_total = Counter('scholar_db_crawl_total', 'Total number of crawl attempts', ['status'])
crawl_duration = Histogram('scholar_db_crawl_duration_seconds', 'Crawl duration in seconds')
active_crawls = Gauge('scholar_db_active_crawls', 'Number of currently active crawls')
urls_processed = Counter('scholar_db_urls_processed_total', 'Total URLs processed')
continuous_iterations = Counter('scholar_db_continuous_iterations', 'Total continuous crawling iterations')
targets_from_db = Gauge('scholar_db_targets_count', 'Number of targets loaded from database')
db_query_duration = Histogram('scholar_db_query_duration_seconds', 'Database query duration')

try:
    from crawler.web_crawler import WebCrawler
    from database.crawl_target_manager import CrawlTargetManager
except ImportError as e:
    logger.error(f'Import error: {e}')
    sys.exit(1)


def setup_logging(log_path: str):
    """로깅 설정"""
    try:
        # 로그 디렉토리 생성
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        # 로거 설정
        logger.add(
            log_path,
            rotation='10 MB',
            retention='1 month',
            format='{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}'
        )
        logger.info('Logging initialized')
    except Exception as e:
        logger.error(f'Failed to setup logging: {e}')


def load_targets_from_database(manager: CrawlTargetManager, batch_size: int = 50) -> List[str]:
    """데이터베이스에서 크롤 대상 URL 로드

    Args:
        manager: CrawlTargetManager 인스턴스
        batch_size: 한 번에 처리할 타겟 개수

    Returns:
        URL 리스트
    """
    try:
        start_time = time.time()

        # 활성 타겟 조회 (우선순위 1-5만)
        targets = manager.get_active_targets(limit=batch_size, priority_min=1)

        if not targets:
            logger.warning('No active targets found in database')
            return []

        # URL 추출
        urls = [target['site_url'] for target in targets if target.get('site_url')]

        # 메트릭 업데이트
        duration = time.time() - start_time
        db_query_duration.observe(duration)
        targets_from_db.set(len(urls))

        logger.info(f'✅ Loaded {len(urls)} active URLs from database (query took {duration:.2f}s)')

        # 우선순위별 통계
        priority_stats = {}
        for target in targets:
            priority = target.get('priority', 'unknown')
            priority_stats[priority] = priority_stats.get(priority, 0) + 1

        logger.info(f'Priority distribution: {priority_stats}')

        return urls

    except Exception as e:
        logger.error(f'Failed to load targets from database: {e}')
        return []


def main():
    """메인 실행 함수"""
    # 환경 변수 로드
    load_dotenv()

    # 환경 변수에서 설정 읽기
    DB_HOST = os.getenv('DB_HOST', '192.168.75.194')
    DB_PORT = os.getenv('DB_PORT', '1521')
    DB_SERVICE_NAME = os.getenv('DB_SERVICE_NAME', 'XEPDB1')
    DB_USERNAME = os.getenv('DB_USERNAME', 'ocr_admin')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'admin_password')

    LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', '/var/log/scholar/continuous_crawler_db.log')
    DATA_ROOT_PATH = os.getenv('DATA_ROOT_PATH', '/opt/scholar/data')
    CRAWL_INTERVAL_SECONDS = int(os.getenv('CRAWL_INTERVAL_SECONDS', '300'))  # 5분
    BATCH_SIZE = int(os.getenv('CRAWL_BATCH_SIZE', '50'))  # 한 번에 처리할 타겟 수
    PROMETHEUS_METRICS_PORT = int(os.getenv('PROMETHEUS_METRICS_PORT', '8003'))
    REQUEST_DELAY = int(os.getenv('REQUEST_DELAY', '2'))
    MAX_PARALLEL_WORKERS = int(os.getenv('MAX_PARALLEL_WORKERS', '5'))

    # 로깅 설정
    setup_logging(LOG_FILE_PATH)

    logger.info('=' * 80)
    logger.info('📊 Database-Driven Continuous Crawler Started')
    logger.info('=' * 80)
    logger.info(f'Database: {DB_HOST}:{DB_PORT}/{DB_SERVICE_NAME}')
    logger.info(f'Crawl interval: {CRAWL_INTERVAL_SECONDS} seconds')
    logger.info(f'Batch size: {BATCH_SIZE} targets per iteration')
    logger.info(f'Request delay: {REQUEST_DELAY} seconds')
    logger.info(f'Max parallel workers: {MAX_PARALLEL_WORKERS}')
    logger.info(f'Data root path: {DATA_ROOT_PATH}')
    logger.info(f'Prometheus metrics port: {PROMETHEUS_METRICS_PORT}')

    # Prometheus metrics 서버 시작
    try:
        start_http_server(PROMETHEUS_METRICS_PORT)
        logger.info(f'✅ Prometheus metrics server started on port {PROMETHEUS_METRICS_PORT}')
    except Exception as e:
        logger.warning(f'Failed to start Prometheus metrics server: {e}')

    # 데이터베이스 연결 설정
    connection_params = {
        'host': DB_HOST,
        'port': DB_PORT,
        'service_name': DB_SERVICE_NAME,
        'username': DB_USERNAME,
        'password': DB_PASSWORD
    }

    # CrawlTargetManager 초기화
    try:
        manager = CrawlTargetManager(connection_params)
        manager.connect()

        # 초기 통계 조회
        stats = manager.get_target_count_by_status()
        logger.info(f'📊 Database Statistics: {stats}')

    except Exception as e:
        logger.error(f'❌ Failed to initialize CrawlTargetManager: {e}')
        sys.exit(1)

    # WebCrawler 초기화
    try:
        crawler = WebCrawler(
            data_root_path=DATA_ROOT_PATH,
            ad_config=None,
            enable_a4_split=False
        )
        logger.info('✅ WebCrawler initialized')
        logger.info(f'   - Parallel workers: {MAX_PARALLEL_WORKERS} (handled by crawl_urls)')
        logger.info(f'   - Request delay: {REQUEST_DELAY}s')
    except Exception as e:
        logger.error(f'❌ Failed to initialize WebCrawler: {e}')
        manager.disconnect()
        sys.exit(1)

    # 무한 크롤링 루프
    iteration = 0
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 5

    logger.info('🚀 Starting continuous crawling loop...')

    try:
        while True:
            iteration += 1
            continuous_iterations.inc()

            logger.info('')
            logger.info('=' * 80)
            logger.info(f'🔄 Iteration #{iteration} - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            logger.info('=' * 80)

            try:
                # 데이터베이스에서 크롤 대상 로드
                urls = load_targets_from_database(manager, batch_size=BATCH_SIZE)

                if not urls:
                    logger.warning('⚠️ No URLs loaded from database, waiting...')
                    consecutive_failures += 1

                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        logger.error(f'❌ Failed to load URLs {consecutive_failures} times consecutively. Exiting.')
                        break

                    time.sleep(CRAWL_INTERVAL_SECONDS)
                    continue

                # 크롤링 실행
                start_time = time.time()
                active_crawls.set(len(urls))

                logger.info(f'🕷️ Starting crawl for {len(urls)} URLs...')

                results = crawler.crawl_multiple_urls(
                    urls=urls,
                    delay_seconds=REQUEST_DELAY,
                    parallel=True,
                    max_workers=MAX_PARALLEL_WORKERS
                )

                duration = time.time() - start_time
                crawl_duration.observe(duration)
                active_crawls.set(0)

                # 결과 처리 (capture_id 리스트)
                success_count = len(results) if isinstance(results, list) else 0
                failure_count = len(urls) - success_count

                # 메트릭 업데이트
                crawl_total.labels(status='success').inc(success_count)
                crawl_total.labels(status='failure').inc(failure_count)
                urls_processed.inc(len(urls))

                logger.info(f'✅ Crawl completed in {duration:.2f}s')
                logger.info(f'📊 Results: Success={success_count}, Failure={failure_count}, Total={len(urls)}')

                # 성공률 계산
                success_rate = (success_count / len(urls) * 100) if urls else 0
                logger.info(f'📈 Success rate: {success_rate:.1f}%')

                consecutive_failures = 0

            except Exception as e:
                logger.error(f'❌ Error in crawling iteration: {e}')
                crawl_total.labels(status='error').inc()
                consecutive_failures += 1

                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error(f'❌ Too many consecutive failures ({consecutive_failures}). Exiting.')
                    break

            # 다음 크롤링까지 대기
            logger.info(f'⏳ Waiting {CRAWL_INTERVAL_SECONDS} seconds before next iteration...')
            time.sleep(CRAWL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info('⚠️ Received shutdown signal (Ctrl+C)')

    except Exception as e:
        logger.error(f'❌ Fatal error in main loop: {e}')

    finally:
        # 정리 작업
        logger.info('🧹 Cleaning up...')

        if manager:
            manager.disconnect()

        logger.info('=' * 80)
        logger.info(f'📊 Final Statistics - Iteration #{iteration}')
        logger.info('=' * 80)
        logger.info('✅ Database-Driven Continuous Crawler Stopped')


if __name__ == '__main__':
    main()
