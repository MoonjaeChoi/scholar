# Generated: 2025-10-11 23:45:00 KST
"""
Continuous Web Crawler - Infinite Loop Crawling System
무한 크롤링 시스템 - CronJob을 대체하는 자체 무한 루프 방식
"""

import json
import os
import sys
import time
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv
from prometheus_client import start_http_server, Counter, Gauge, Histogram

# 상대 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Prometheus metrics
crawl_total = Counter('scholar_crawl_total', 'Total number of crawl attempts', ['status'])
crawl_duration = Histogram('scholar_crawl_duration_seconds', 'Crawl duration in seconds')
active_crawls = Gauge('scholar_active_crawls', 'Number of currently active crawls')
urls_processed = Counter('scholar_urls_processed_total', 'Total URLs processed')
continuous_iterations = Counter('scholar_continuous_iterations', 'Total continuous crawling iterations')
sleep_duration = Gauge('scholar_sleep_duration_seconds', 'Current sleep duration between crawls')

try:
    from crawler.web_crawler import WebCrawler
except ImportError as e:
    logger.error(f'Import error: {e}')
    sys.exit(1)


def load_target_sites(config_path: str, enable_exploration: bool = True) -> tuple:
    """타겟 사이트 목록 로드 - 한글 블로그 우선

    Args:
        config_path: 설정 파일 경로
        enable_exploration: 페이지 탐색 활성화 여부

    Returns:
        (urls, ad_config) 튜플
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        urls = []
        ad_config = None

        # korean_blog_sites.json 형식 처리
        if 'ad_blocking' in config:
            ad_config = config.get('ad_blocking', {})
            logger.info('Ad blocking configuration loaded')

        # 페이지 탐색 활성화 시
        if enable_exploration and 'ad_blocking' in config:
            logger.info('🔍 Enabling Korean blog page exploration')
            from crawler.korean_blog_explorer import KoreanBlogExplorer

            explorer = KoreanBlogExplorer(max_pages_per_site=100)
            discovered_urls = explorer.explore_all_platforms(config)

            if discovered_urls:
                urls.extend(discovered_urls)
                logger.info(f'📋 Discovered {len(discovered_urls)} URLs through exploration')
            else:
                logger.warning('⚠️ Page exploration returned no URLs, using base URLs')

        # 기본 URL 수집 (탐색 실패 시 또는 비활성화 시)
        if not urls:
            # 각 블로그 플랫폼별 URL 수집 - 동적으로 모든 플랫폼 로드
            for platform_key, platform_config in config.items():
                # 메타데이터 키 제외
                if platform_key in ['description', 'generated', 'ad_blocking', 'quality_settings']:
                    continue

                # 딕셔너리 형태의 플랫폼 설정만 처리
                if not isinstance(platform_config, dict):
                    continue

                # enabled 체크
                if not platform_config.get('enabled', True):
                    logger.debug(f'Skipping disabled platform: {platform_key}')
                    continue

                # base_urls 추출
                base_urls = platform_config.get('base_urls', [])
                if base_urls:
                    urls.extend(base_urls)
                    logger.info(f'Loaded {len(base_urls)} URLs from {platform_key}')

        logger.info(f'Total loaded {len(urls)} URLs from {config_path}')
        return (urls, ad_config)

    except Exception as e:
        logger.error(f'Error loading target sites from {config_path}: {e}')
        # 기본 한국 블로그 및 뉴스 URL 반환
        return ([
            'https://blog.naver.com',
            'https://m.blog.naver.com',
            'https://post.naver.com',
            'https://news.naver.com',
            'https://news.daum.net',
            'https://news.nate.com',
            'https://www.tistory.com'
        ], None)


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


def notify_ml_control(api_url: str, endpoint: str, data: dict):
    """ML Control Dashboard에 작업 상태 알림

    Args:
        api_url: ML Control API base URL
        endpoint: API endpoint (예: /api/tasks/start)
        data: 전송할 데이터
    """
    if not api_url:
        return

    try:
        import requests
        url = f"{api_url}{endpoint}"
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            logger.debug(f'Notified ML Control: {endpoint}')
        else:
            logger.warning(f'ML Control notification failed: {response.status_code}')
    except Exception as e:
        logger.warning(f'Failed to notify ML Control: {e}')


def run_single_crawl_iteration(crawler: WebCrawler, target_urls: list, delay: int,
                                enable_parallel: bool, max_workers: int,
                                ml_control_api: str, iteration: int) -> bool:
    """단일 크롤링 반복 실행

    Args:
        crawler: WebCrawler 인스턴스
        target_urls: 크롤링 대상 URL 목록
        delay: 요청 간 지연 시간 (초)
        enable_parallel: 병렬 처리 활성화 여부
        max_workers: 병렬 처리 워커 수
        ml_control_api: ML Control API URL
        iteration: 현재 반복 횟수

    Returns:
        성공 여부 (bool)
    """
    task_id = f"crawl-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    start_time = time.time()

    logger.info('=' * 60)
    logger.info(f'🔄 Continuous Crawling Iteration #{iteration}')
    logger.info(f'Task ID: {task_id}')
    logger.info(f'Start Time: {datetime.now().isoformat()}')
    logger.info(f'Target URLs: {len(target_urls)}')
    logger.info('=' * 60)

    # ML Control에 작업 시작 알림
    notify_ml_control(ml_control_api, '/api/tasks/start', {
        'task_id': task_id,
        'task_type': 'crawling',
        'start_time': datetime.now().isoformat(),
        'config': {
            'mode': 'continuous',
            'iteration': iteration,
            'max_urls': len(target_urls)
        }
    })

    try:
        # Update Prometheus metrics
        urls_processed.inc(len(target_urls))
        active_crawls.set(len(target_urls))

        # 크롤링 실행
        if enable_parallel:
            logger.info(f'Starting parallel crawling with {max_workers} workers')
            successful_crawls = crawler.crawl_multiple_urls(
                target_urls, delay, parallel=True, max_workers=max_workers
            )
        else:
            logger.info('Starting sequential crawling')
            successful_crawls = crawler.crawl_multiple_urls(
                target_urls, delay, parallel=False
            )

        # Record metrics
        duration = time.time() - start_time
        crawl_duration.observe(duration)
        crawl_total.labels(status='success').inc(len(successful_crawls))
        crawl_total.labels(status='failed').inc(len(target_urls) - len(successful_crawls))
        active_crawls.set(0)
        continuous_iterations.inc()

        success_rate = len(successful_crawls) / len(target_urls) * 100 if target_urls else 0

        logger.info('=' * 60)
        logger.info(f'✅ Crawling Iteration #{iteration} Completed')
        logger.info(f'Duration: {duration:.2f}s')
        logger.info(f'Success: {len(successful_crawls)}/{len(target_urls)} ({success_rate:.1f}%)')
        logger.info(f'End Time: {datetime.now().isoformat()}')
        logger.info('=' * 60)

        # ML Control에 작업 완료 알림
        notify_ml_control(ml_control_api, '/api/tasks/complete', {
            'task_id': task_id,
            'status': 'completed',
            'end_time': datetime.now().isoformat(),
            'duration_seconds': int(duration),
            'exit_code': 0,
            'stats': {
                'successful': len(successful_crawls),
                'failed': len(target_urls) - len(successful_crawls),
                'success_rate': success_rate
            }
        })

        return True

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f'❌ Crawling iteration #{iteration} failed: {e}')
        active_crawls.set(0)
        crawl_total.labels(status='error').inc()

        # ML Control에 작업 실패 알림
        notify_ml_control(ml_control_api, '/api/tasks/complete', {
            'task_id': task_id,
            'status': 'failed',
            'end_time': datetime.now().isoformat(),
            'duration_seconds': int(duration),
            'exit_code': 1,
            'error_message': str(e)
        })

        return False


def main():
    """무한 크롤링 메인 함수"""
    logger.info('🚀 Starting Continuous Crawling System...')
    print('=' * 60)
    print('🚀 Continuous Crawling System')
    print('=' * 60)

    # Start Prometheus metrics server
    metrics_port = int(os.getenv('PROMETHEUS_METRICS_PORT', '8000'))
    try:
        start_http_server(metrics_port)
        logger.info(f'📊 Prometheus metrics server started on port {metrics_port}')
    except Exception as e:
        logger.warning(f'Failed to start Prometheus metrics server: {e}')

    # 환경 변수 로드
    env_path = os.getenv('ENV_FILE_PATH', '/home/pro301/git/en-zine/scholar/training/config/.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f'Loaded environment from {env_path}')
    else:
        logger.warning(f'Environment file not found: {env_path}')

    # 로깅 설정
    log_path = os.getenv('LOG_FILE_PATH', '/home/pro301/git/en-zine/scholar/training/logs/continuous_crawler.log')
    setup_logging(log_path)

    # 데이터 경로 설정
    data_root_path = os.getenv('DATA_ROOT_PATH', '/home/pro301/git/en-zine/scholar/training/data')
    logger.info(f'Data root path: {data_root_path}')

    # 무한 크롤링 설정
    crawl_interval = int(os.getenv('CRAWL_INTERVAL_SECONDS', '180'))  # 기본 3분 (180초)
    sleep_duration.set(crawl_interval)
    logger.info(f'⏰ Crawl interval: {crawl_interval} seconds ({crawl_interval/60:.1f} minutes)')

    # 타겟 사이트 로드
    config_path = os.getenv('BLOG_CONFIG_PATH', '/home/pro301/git/en-zine/scholar/training/config/korean_blog_sites.json')

    if not os.path.exists(config_path):
        # Fallback paths
        fallback_paths = [
            '/home/pro301/git/en-zine/scholar/training/config/korean_blog_sites.json',
            '/opt/ocr_system/crawling/config/korean_blog_sites.json',
            'scholar/config/korean_blog_sites.json'
        ]
        for path in fallback_paths:
            if os.path.exists(path):
                config_path = path
                break

    target_urls, ad_config = load_target_sites(config_path, enable_exploration=False)

    if not target_urls:
        logger.error('❌ No target URLs found')
        return 1

    logger.info(f'📋 Loaded {len(target_urls)} target URLs')
    if ad_config:
        logger.info('🛡️ Ad blocking enabled')

    # 크롤러 초기화
    try:
        crawler = WebCrawler(data_root_path, ad_config=ad_config, enable_a4_split=True)
        logger.info('✅ Crawler initialized (A4 split + driver pool enabled)')
    except Exception as e:
        logger.error(f'❌ Failed to initialize crawler: {e}')
        return 1

    # 크롤링 실행 옵션
    delay = int(os.getenv('REQUEST_DELAY', '2'))
    enable_parallel = os.getenv('ENABLE_PARALLEL_CRAWLING', 'true').lower() == 'true'
    max_workers = int(os.getenv('MAX_PARALLEL_WORKERS', '3'))
    ml_control_api = os.getenv('ML_CONTROL_API', '')

    logger.info(f'⚙️ Crawling configuration:')
    logger.info(f'  - Request delay: {delay}s')
    logger.info(f'  - Parallel crawling: {enable_parallel}')
    logger.info(f'  - Max workers: {max_workers}')
    logger.info(f'  - ML Control API: {ml_control_api or "disabled"}')

    # 무한 루프 시작
    iteration = 0
    consecutive_failures = 0
    max_consecutive_failures = 5

    logger.info('🔄 Starting infinite crawling loop...')
    print('=' * 60)
    print('🔄 Infinite Crawling Loop Started')
    print(f'⏰ Interval: {crawl_interval}s ({crawl_interval/60:.1f} min)')
    print('=' * 60)

    try:
        while True:
            iteration += 1

            # 크롤링 실행
            success = run_single_crawl_iteration(
                crawler, target_urls, delay, enable_parallel, max_workers,
                ml_control_api, iteration
            )

            # 연속 실패 카운트 관리
            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(f'⚠️ Consecutive failures: {consecutive_failures}/{max_consecutive_failures}')

            # 연속 실패 임계값 초과 시 종료
            if consecutive_failures >= max_consecutive_failures:
                logger.error(f'❌ Too many consecutive failures ({consecutive_failures}), exiting...')
                return 1

            # 다음 크롤링까지 대기
            logger.info(f'😴 Sleeping for {crawl_interval} seconds until next crawl...')
            print(f'\n😴 Sleeping {crawl_interval}s ({crawl_interval/60:.1f} min) until next crawl...\n')

            time.sleep(crawl_interval)

    except KeyboardInterrupt:
        logger.info('🛑 Continuous crawling stopped by user (Ctrl+C)')
        print('\n🛑 Continuous crawling stopped by user')
        return 0
    except Exception as e:
        logger.error(f'❌ Unexpected error in continuous crawling loop: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
