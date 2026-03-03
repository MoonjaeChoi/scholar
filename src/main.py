import json
import os
import sys
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
urls_skipped = Counter('scholar_urls_skipped_total', 'URLs skipped due to deduplication')

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
                # 메타데이터 키 제외 (description, ad_blocking, quality_settings 등)
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

        # 기존 형식 호환성 (target_sites_300.json)
        if not urls:
            for category, category_urls in config.items():
                if isinstance(category_urls, list):
                    urls.extend(category_urls)
                elif isinstance(category_urls, dict) and 'base_url' in category_urls:
                    urls.append(category_urls['base_url'])

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
            'https://blog.daum.net',
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

def main():
    """메인 실행 함수"""
    print('Starting OCR Web Crawler...')

    # Start Prometheus metrics server on port 8000
    metrics_port = int(os.getenv('PROMETHEUS_METRICS_PORT', '8000'))
    try:
        start_http_server(metrics_port)
        logger.info(f'Prometheus metrics server started on port {metrics_port}')
    except Exception as e:
        logger.warning(f'Failed to start Prometheus metrics server: {e}')

    # 환경 변수 로드
    env_path = '/home/pro301/git/en-zine/ocr_system/crawling/config/.env'
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f'Loaded environment from {env_path}')
    else:
        logger.warning(f'Environment file not found: {env_path}')

    # 로깅 설정
    log_path = os.getenv('LOG_FILE_PATH', '/home/pro301/git/en-zine/logs/crawler.log')
    setup_logging(log_path)

    # 데이터 경로 설정
    data_root_path = os.getenv('DATA_ROOT_PATH', '/home/pro301/git/en-zine/ocr_system/crawling/data')
    logger.info(f'Data root path: {data_root_path}')

    # 타겟 사이트 로드 - korean_blog_sites.json 최우선 사용
    korean_blog_config = '/opt/ocr_system/crawling/config/korean_blog_sites.json'
    config_path_300 = '/opt/ocr_system/crawling/config/target_sites_300.json'
    config_path_old = '/opt/ocr_system/crawling/config/target_sites.json'

    target_urls = []
    ad_config = None

    # korean_blog_sites.json 파일이 있으면 최우선 사용 (페이지 탐색 비활성화 - 설정된 base_urls 사용)
    if os.path.exists(korean_blog_config):
        target_urls, ad_config = load_target_sites(korean_blog_config, enable_exploration=False)
        logger.info(f'Using korean_blog_sites.json with {len(target_urls)} URLs')
        if ad_config:
            logger.info('Ad blocking enabled')
    elif os.path.exists(config_path_300):
        target_urls, _ = load_target_sites(config_path_300)
        logger.info(f'Using target_sites_300.json')
    elif os.path.exists(config_path_old):
        target_urls, _ = load_target_sites(config_path_old)
        logger.info(f'Using target_sites.json')
    else:
        logger.warning('No config file found, using default URLs')
        target_urls, ad_config = load_target_sites('')

    if not target_urls:
        logger.error('No target URLs found')
        return 1

    # 크롤러 초기화 (광고 차단 설정 포함, A4 분할 캡처 활성화 - 드라이버 풀과 통합)
    try:
        crawler = WebCrawler(data_root_path, ad_config=ad_config, enable_a4_split=True)
        logger.info('Crawler initialized successfully with A4 split capture and driver pool enabled')
        if ad_config:
            logger.info(f'Ad blocking configured with {len(ad_config.get("css_selectors", []))} CSS selectors')
    except Exception as e:
        logger.error(f'Failed to initialize crawler: {e}')
        return 1

    logger.info(f'Starting crawl for {len(target_urls)} URLs')
    print(f'Target URLs: {target_urls}')

    # 크롤링 실행 (병렬 처리 옵션)
    delay = int(os.getenv('REQUEST_DELAY', '2'))
    enable_parallel = os.getenv('ENABLE_PARALLEL_CRAWLING', 'true').lower() == 'true'
    max_workers = int(os.getenv('MAX_PARALLEL_WORKERS', '3'))

    try:
        # Update Prometheus metrics
        urls_processed.inc(len(target_urls))
        active_crawls.set(len(target_urls))

        import time
        start_time = time.time()

        if enable_parallel:
            logger.info(f'Starting parallel crawling with {max_workers} workers')
            successful_crawls = crawler.crawl_multiple_urls(target_urls, delay, parallel=True, max_workers=max_workers)
        else:
            logger.info('Starting sequential crawling')
            successful_crawls = crawler.crawl_multiple_urls(target_urls, delay, parallel=False)

        # Record metrics
        duration = time.time() - start_time
        crawl_duration.observe(duration)
        crawl_total.labels(status='success').inc(len(successful_crawls))
        crawl_total.labels(status='failed').inc(len(target_urls) - len(successful_crawls))
        active_crawls.set(0)

        logger.info(f'Crawling completed: {len(successful_crawls)} successful crawls')
        print(f'Crawling completed: {len(successful_crawls)}/{len(target_urls)} successful')

        if successful_crawls:
            print('Successful capture IDs:', successful_crawls)

        return 0
    except Exception as e:
        logger.error(f'Crawling failed: {e}')
        print(f'Crawling failed: {e}')
        active_crawls.set(0)
        crawl_total.labels(status='error').inc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
