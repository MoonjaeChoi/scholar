import os
import re
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from enum import Enum
from urllib.parse import urlparse
from loguru import logger

try:
    import sys
    from pathlib import Path
    # Add parent directory to sys.path for absolute imports
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from database.connection import DatabaseConnection
    from database.models import WebCaptureData, TextBoundingBox
    DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f'Database modules not available, running in mock mode: {e}')
    DB_AVAILABLE = False

from .screenshot_service import ScreenshotService
from .html_parser import HTMLParser
from .ad_blocker import AdBlocker


class URLType(Enum):
    """URL 유형 분류"""
    NEWS = "news"
    BLOG_MAIN = "blog_main"
    COMMUNITY = "community"
    ARTICLE = "article"
    STATIC = "static"
    UNKNOWN = "unknown"


class WebCrawler:
    def __init__(self, data_root_path: str, ad_config: dict = None, enable_a4_split: bool = False):
        self.data_root_path = data_root_path
        self.screenshot_service = ScreenshotService(data_root_path, enable_a4_split=enable_a4_split)
        self.html_parser = HTMLParser()
        self.ad_blocker = AdBlocker(ad_config) if ad_config else None
        self.enable_a4_split = enable_a4_split
        
        # 데이터베이스 연결 (사용 가능한 경우)
        self.db_available = False
        if DB_AVAILABLE:
            try:
                self.db_connection = DatabaseConnection()
                # 연결 테스트
                if self.db_connection.test_connection():
                    self.db_available = True
                    logger.info('Database connection established')
                else:
                    logger.warning('Database connection test failed, running in file mode')
            except Exception as e:
                logger.warning(f'Database initialization failed: {e}, running in file mode')
        
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
        # 파일 기반 저장을 위한 디렉토리 생성
        self.metadata_path = os.path.join(data_root_path, 'metadata')
        os.makedirs(self.metadata_path, exist_ok=True)

    def _check_url_crawled(self, url: str) -> bool:
        """Check if URL has been crawled recently (within 7 days)

        DEPRECATED: Use should_crawl_url() instead for dynamic revisit policy
        """
        if not self.db_available:
            return False

        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()

                # Check if URL was crawled within last 7 days
                sql = '''
                SELECT COUNT(*) FROM WEB_CAPTURE_DATA
                WHERE url = :1
                AND crawl_timestamp >= SYSTIMESTAMP - INTERVAL '7' DAY
                AND processing_status != 'failed'
                '''

                cursor.execute(sql, (url,))
                count = cursor.fetchone()[0]

                if count > 0:
                    logger.info(f'URL already crawled recently: {url} (found {count} records)')
                    return True

                return False

        except Exception as e:
            logger.warning(f'Error checking URL crawl history: {e}')
            return False

    def classify_url_type(self, url: str) -> URLType:
        """URL 유형 자동 분류

        Args:
            url: 분류할 URL

        Returns:
            URLType: URL 유형 (NEWS, BLOG_MAIN, COMMUNITY, ARTICLE, STATIC, UNKNOWN)
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        # 뉴스 사이트 판별
        news_domains = [
            'news.naver.com', 'news.daum.net', 'news.nate.com',
            'chosun.com', 'joongang.co.kr', 'donga.com',
            'hani.co.kr', 'khan.co.kr', 'mk.co.kr',
            'yna.co.kr', 'ytn.co.kr', 'sbs.co.kr'
        ]
        if any(domain.endswith(d) for d in news_domains):
            return URLType.NEWS

        # 블로그 메인 페이지
        blog_patterns = [
            (r'blog\.naver\.com', r'^/[^/]+/?$'),  # blog.naver.com/user_id
            (r'\.tistory\.com', r'^/?$'),  # user.tistory.com/
            (r'brunch\.co\.kr', r'^/@[^/]+/?$'),  # brunch.co.kr/@user
        ]
        for domain_pattern, path_pattern in blog_patterns:
            if re.search(domain_pattern, domain) and re.search(path_pattern, path):
                return URLType.BLOG_MAIN

        # 커뮤니티
        community_domains = [
            'clien.net', 'ruliweb.com', 'ppomppu.co.kr',
            'slrclub.com', 'dcinside.com', 'fmkorea.com',
            'bobaedream.co.kr', '82cook.com', 'mlbpark.donga.com'
        ]
        if any(domain.endswith(d) for d in community_domains):
            return URLType.COMMUNITY

        # 게시글/기사 (detail 페이지)
        article_patterns = [
            r'/article/', r'/post/', r'/view/',
            r'/read/', r'/detail/', r'/show/',
            r'/\d+$'  # 숫자로 끝나는 경우 (게시글 번호)
        ]
        if any(re.search(p, path) for p in article_patterns):
            return URLType.ARTICLE

        # 정적 페이지 (회사 소개, 약관 등)
        static_patterns = [
            r'/about', r'/company', r'/terms',
            r'/privacy', r'/contact', r'/faq'
        ]
        if any(re.search(p, path) for p in static_patterns):
            return URLType.STATIC

        return URLType.UNKNOWN

    def get_revisit_interval(self, url_type: URLType) -> timedelta:
        """URL 유형별 재방문 간격

        Args:
            url_type: URL 유형

        Returns:
            timedelta: 재방문 간격
        """
        intervals = {
            URLType.NEWS: timedelta(hours=3),       # 뉴스: 3시간
            URLType.BLOG_MAIN: timedelta(hours=12), # 블로그 메인: 12시간
            URLType.COMMUNITY: timedelta(hours=6),  # 커뮤니티: 6시간
            URLType.ARTICLE: timedelta(days=7),     # 게시글: 7일
            URLType.STATIC: timedelta(days=30),     # 정적: 30일
            URLType.UNKNOWN: timedelta(days=7)      # 기본: 7일
        }
        return intervals.get(url_type, timedelta(days=7))

    def should_crawl_url(self, url: str) -> bool:
        """URL 크롤링 여부 판단 (재방문 정책 적용)

        Args:
            url: 크롤링 여부를 판단할 URL

        Returns:
            bool: 크롤링 허용 여부 (True: 크롤링, False: 스킵)
        """
        # DB가 없으면 항상 크롤링 허용
        if not self.db_available:
            return True

        # URL 유형 분류
        url_type = self.classify_url_type(url)

        # 재방문 간격 가져오기
        interval = self.get_revisit_interval(url_type)

        # DB에서 마지막 크롤링 시각 확인
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()

                sql = '''
                SELECT MAX(crawl_timestamp)
                FROM WEB_CAPTURE_DATA
                WHERE url = :1
                AND processing_status != 'failed'
                '''

                cursor.execute(sql, (url,))
                result = cursor.fetchone()

                if result and result[0]:
                    last_crawl = result[0]
                    elapsed = datetime.now() - last_crawl

                    if elapsed < interval:
                        logger.debug(
                            f"Skip (revisit): {url} "
                            f"(type={url_type.value}, "
                            f"last={elapsed.total_seconds()/3600:.1f}h ago, "
                            f"interval={interval.total_seconds()/3600:.0f}h)"
                        )
                        return False

                # 크롤링 허용
                logger.info(f"Allow crawl: {url} (type={url_type.value})")
                return True

        except Exception as e:
            logger.error(f"Error checking revisit policy: {e}")
            return True  # 에러 시 크롤링 허용

    def is_duplicate_content(self, url: str, image_hash: str) -> bool:
        """이미지 해시로 실제 컨텐츠 중복 확인

        같은 URL이어도 이미지가 다르면 중복 아님

        Args:
            url: 확인할 URL
            image_hash: 이미지 해시값

        Returns:
            bool: 중복 여부 (True: 중복, False: 신규)
        """
        # DB가 없으면 중복 아님
        if not self.db_available or not image_hash:
            return False

        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()

                sql = '''
                SELECT COUNT(*)
                FROM WEB_CAPTURE_DATA
                WHERE image_hash = :1
                AND crawl_timestamp >= SYSTIMESTAMP - INTERVAL '30' DAY
                '''

                cursor.execute(sql, (image_hash,))
                count = cursor.fetchone()[0]

                if count > 0:
                    logger.info(f"Duplicate content (hash): {url}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Error checking content duplicate: {e}")
            return False

    def _calculate_image_hash(self, image_path: str) -> Optional[str]:
        """이미지 해시 계산 (SHA256)

        Args:
            image_path: 이미지 파일 경로

        Returns:
            str: 이미지 해시값 (SHA256), 실패 시 None
        """
        try:
            with open(image_path, 'rb') as f:
                file_hash = hashlib.sha256()
                while chunk := f.read(8192):
                    file_hash.update(chunk)
                return file_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating image hash: {e}")
            return None

    def crawl_url(self, url: str, viewport_width: int = 1920,
                  viewport_height: int = 1080) -> dict:
        """단일 URL 크롤링 (Dynamic Revisit Policy 적용)

        Returns:
            dict: {
                'success': bool,
                'capture_id': Optional[int],
                'screenshot_saved': bool,
                'skipped': bool,
                'reason': Optional[str],  # 'revisit_policy' or 'duplicate_content'
                'error': Optional[str]
            }
        """
        logger.info(f'Starting crawl for URL: {url}')

        # 1. 재방문 정책 체크
        if not self.should_crawl_url(url):
            return {
                'success': False,
                'capture_id': None,
                'screenshot_saved': False,
                'skipped': True,
                'reason': 'revisit_policy',
                'error': None
            }

        for attempt in range(self.max_retries):
            try:
                # 2. 스크린샷 캡처 (광고 제거 적용)
                if self.ad_blocker and self.ad_blocker.enabled:
                    logger.info('Ad blocking enabled - capturing clean screenshot')
                    screenshot_result = self._capture_with_ad_blocking(
                        url, viewport_width, viewport_height
                    )
                else:
                    screenshot_result = self.screenshot_service.capture_full_page(
                        url, viewport_width, viewport_height
                    )

                if not screenshot_result:
                    logger.warning(f'Screenshot failed for {url}, attempt {attempt + 1}')
                    time.sleep(self.retry_delay)
                    continue

                image_file_path, file_size, temp_hash = screenshot_result

                # 3. 이미지 해시 계산 (SHA256)
                image_hash = self._calculate_image_hash(image_file_path)
                if not image_hash:
                    # 해시 계산 실패 시 기존 해시 사용
                    image_hash = temp_hash

                # 4. 컨텐츠 중복 체크 (이미지 해시 기반)
                if self.is_duplicate_content(url, image_hash):
                    return {
                        'success': False,
                        'capture_id': None,
                        'screenshot_saved': False,
                        'skipped': True,
                        'reason': 'duplicate_content',
                        'error': None
                    }

                # 5. HTML 소스코드 수집
                html_source = self.html_parser.fetch_html_source(url)
                if not html_source:
                    logger.warning(f'HTML fetch failed for {url}')
                    continue

                # 6. 텍스트 콘텐츠 추출
                extracted_text = self.html_parser.extract_text_content(html_source)

                # 7. PaddleOCR 학습용 라벨 파일 생성 (항상 실행)
                if extracted_text and image_file_path:
                    self._save_paddleocr_label(image_file_path, extracted_text)

                # 8. 데이터 저장 (이미지 해시 포함)
                if self.db_available:
                    capture_id = self._save_capture_data_to_db(
                        url, image_file_path, html_source, extracted_text,
                        viewport_width, viewport_height, file_size, image_hash
                    )
                else:
                    capture_id = self._save_capture_data_to_file(
                        url, image_file_path, html_source, extracted_text,
                        viewport_width, viewport_height, file_size
                    )

                if capture_id:
                    # 9. 텍스트 바운딩 박스 추출 및 저장
                    self._extract_and_save_bounding_boxes(url, capture_id)

                    logger.info(f'Successfully crawled {url} with ID: {capture_id}')
                    return {
                        'success': True,
                        'capture_id': capture_id,
                        'screenshot_saved': True,
                        'skipped': False,
                        'reason': None,
                        'error': None
                    }

            except Exception as e:
                error_msg = str(e)
                logger.error(f'Error crawling {url} (attempt {attempt + 1}): {error_msg}')
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)

        logger.error(f'Failed to crawl {url} after {self.max_retries} attempts')
        return {
            'success': False,
            'capture_id': None,
            'screenshot_saved': False,
            'skipped': False,
            'reason': None,
            'error': f'Failed after {self.max_retries} attempts'
        }

    def _capture_with_ad_blocking(self, url: str, viewport_width: int,
                                   viewport_height: int) -> Optional[tuple]:
        """광고 차단을 적용한 스크린샷 캡처"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            # 크롬 옵션 설정
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument(f'--window-size={viewport_width},{viewport_height}')

            driver = webdriver.Chrome(options=chrome_options)

            try:
                # 광고 차단 설정 적용
                self.ad_blocker.setup_driver_blocking(driver)

                # 페이지 로드
                driver.get(url)

                # 동적 광고 제거 및 스크린샷 저장
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'screenshot_{timestamp}.png'
                screenshot_path = os.path.join(
                    self.data_root_path, 'screenshots', filename
                )

                os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

                success = self.ad_blocker.get_clean_page_screenshot(
                    driver, screenshot_path
                )

                if success and os.path.exists(screenshot_path):
                    file_size = os.path.getsize(screenshot_path)
                    # Generate unique hash using URL + timestamp (no perceptual hash to avoid duplicates)
                    import hashlib
                    unique_string = f"{url}_{datetime.now().isoformat()}_{screenshot_path}"
                    image_hash = hashlib.md5(unique_string.encode()).hexdigest()[:16]
                    logger.info(f'Clean screenshot saved: {screenshot_path} ({file_size} bytes), hash: {image_hash}')
                    return (screenshot_path, file_size, image_hash)
                else:
                    logger.warning('Failed to capture clean screenshot')
                    return None

            finally:
                driver.quit()

        except Exception as e:
            logger.error(f'Error capturing with ad blocking: {e}')
            # Fallback to regular screenshot
            return self.screenshot_service.capture_full_page(
                url, viewport_width, viewport_height
            )

    def _save_capture_data_to_db(self, url: str, image_path: str, html_source: str,
                                extracted_text: str, viewport_width: int,
                                viewport_height: int, file_size: int, image_hash: str = None) -> Optional[int]:
        """캐처 데이터를 데이터베이스에 저장 (이미지 해시 포함)"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()

                # Get next sequence value
                cursor.execute("SELECT SEQ_CAPTURE.NEXTVAL FROM DUAL")
                capture_id = cursor.fetchone()[0]

                sql = '''
                INSERT INTO WEB_CAPTURE_DATA
                (capture_id, url, image_path, image_size, image_format, image_hash,
                 http_status_code, processing_status, metadata)
                VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9)
                '''

                import json
                metadata_json = json.dumps({
                    'viewport_width': viewport_width,
                    'viewport_height': viewport_height,
                    'extracted_text': extracted_text[:500]  # Sample only
                })

                cursor.execute(sql, (
                    capture_id,
                    url,
                    image_path,
                    file_size,
                    'PNG',
                    image_hash,  # 이미지 해시 추가
                    200,
                    'completed',
                    metadata_json
                ))

                conn.commit()
                logger.info(f'Saved to DB: capture_id={capture_id}, hash={image_hash}')
                return capture_id

        except Exception as e:
            logger.error(f'Error saving capture data to database: {e}')
            return None

    def _save_capture_data_to_file(self, url: str, image_path: str, html_source: str,
                                  extracted_text: str, viewport_width: int,
                                  viewport_height: int, file_size: int) -> Optional[int]:
        """캐처 데이터를 파일에 저장 (PaddleOCR 학습용 라벨 파일 포함)"""
        try:
            import json
            import hashlib

            # 고유 ID 생성
            capture_id = int(hashlib.md5(f'{url}_{datetime.now().isoformat()}'.encode()).hexdigest()[:8], 16)

            # 메타데이터 파일 생성
            metadata = {
                'capture_id': capture_id,
                'source_url': url,
                'image_file_path': image_path,
                'html_source': html_source[:1000] + '...' if len(html_source) > 1000 else html_source,  # 크기 제한
                'extracted_text': extracted_text,
                'viewport_width': viewport_width,
                'viewport_height': viewport_height,
                'file_size_bytes': file_size,
                'status': 'COLLECTED',
                'capture_timestamp': datetime.now().isoformat()
            }

            metadata_file = os.path.join(self.metadata_path, f'capture_{capture_id}.json')
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            # PaddleOCR 학습용 라벨 파일 생성 (이미지와 같은 이름, .txt 확장자)
            if extracted_text and image_path:
                self._save_paddleocr_label(image_path, extracted_text)

            logger.info(f'Saved capture data to file: {metadata_file}')
            return capture_id

        except Exception as e:
            logger.error(f'Error saving capture data to file: {e}')
            return None

    def _save_paddleocr_label(self, image_path: str, text: str) -> bool:
        """PaddleOCR 학습용 라벨 파일 생성

        Args:
            image_path: 이미지 파일 경로 (예: data/images/20251012/screenshot_001.png)
            text: 추출된 텍스트 내용

        Returns:
            bool: 저장 성공 여부
        """
        try:
            # labels 디렉토리 경로 생성
            labels_root = os.path.join(self.data_root_path, 'labels')
            os.makedirs(labels_root, exist_ok=True)

            # 이미지 파일명에서 확장자를 제거하고 .txt로 변경
            # 예: images/20251012/screenshot_001.png -> labels/20251012/screenshot_001.txt
            relative_image_path = os.path.relpath(image_path, self.data_root_path)
            label_path = relative_image_path.replace('images/', 'labels/').replace('.png', '.txt').replace('.jpg', '.txt')
            full_label_path = os.path.join(self.data_root_path, label_path)

            # 라벨 파일 디렉토리 생성
            os.makedirs(os.path.dirname(full_label_path), exist_ok=True)

            # 텍스트 저장 (UTF-8 인코딩)
            with open(full_label_path, 'w', encoding='utf-8') as f:
                f.write(text.strip())

            logger.info(f'Saved PaddleOCR label: {full_label_path}')
            return True

        except Exception as e:
            logger.error(f'Error saving PaddleOCR label for {image_path}: {e}')
            return False

    def _extract_and_save_bounding_boxes(self, url: str, capture_id: int) -> bool:
        """텍스트 바운딩 박스 추출 및 저장"""
        try:
            bounding_boxes = self.html_parser.extract_text_with_coordinates(url)

            if not bounding_boxes:
                logger.warning(f'No bounding boxes found for {url}')
                return False

            if self.db_available:
                return self._save_bounding_boxes_to_db(capture_id, bounding_boxes)
            else:
                return self._save_bounding_boxes_to_file(capture_id, bounding_boxes)

        except Exception as e:
            logger.error(f'Error extracting bounding boxes for {url}: {e}')
            return False

    def _save_bounding_boxes_to_db(self, capture_id: int, bounding_boxes: List) -> bool:
        """바운딩 박스를 데이터베이스에 저장"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()

                sql = '''
                INSERT INTO TEXT_BOUNDING_BOXES
                (box_id, capture_id, text_content, x_coordinate, y_coordinate,
                 width, height, confidence_score, font_size)
                VALUES (SEQ_BOX.NEXTVAL, :1, :2, :3, :4, :5, :6, :7, :8)
                '''

                for box in bounding_boxes:
                    cursor.execute(sql, (
                        capture_id,
                        box['text'],
                        box['x'],
                        box['y'],
                        box['width'],
                        box['height'],
                        1.0,
                        box.get('fontSize')
                    ))

                conn.commit()
                logger.info(f'Saved {len(bounding_boxes)} bounding boxes to database for capture {capture_id}')
                return True

        except Exception as e:
            logger.error(f'Error saving bounding boxes to database: {e}')
            return False

    def _save_bounding_boxes_to_file(self, capture_id: int, bounding_boxes: List) -> bool:
        """바운딩 박스를 파일에 저장"""
        try:
            import json
            
            bbox_file = os.path.join(self.metadata_path, f'bounding_boxes_{capture_id}.json')
            with open(bbox_file, 'w', encoding='utf-8') as f:
                json.dump(bounding_boxes, f, indent=2, ensure_ascii=False)
            
            logger.info(f'Saved {len(bounding_boxes)} bounding boxes to file: {bbox_file}')
            return True
            
        except Exception as e:
            logger.error(f'Error saving bounding boxes to file: {e}')
            return False

    def crawl_multiple_urls(self, urls: List[str], delay_seconds: int = 2, parallel: bool = False, max_workers: int = 3) -> List[int]:
        """여러 URL 크롤링 (순차 또는 병렬)

        Args:
            urls: 크롤링할 URL 리스트
            delay_seconds: 순차 크롤링 시 요청 간 지연 시간
            parallel: 병렬 크롤링 활성화 여부
            max_workers: 병렬 크롤링 시 최대 워커 수

        Returns:
            성공한 capture_id 리스트
        """
        if parallel:
            return self._crawl_parallel(urls, max_workers)
        else:
            return self._crawl_sequential(urls, delay_seconds)

    def _crawl_sequential(self, urls: List[str], delay_seconds: int = 2) -> List[int]:
        """순차 크롤링 (기존 로직)"""
        successful_crawls = []

        for i, url in enumerate(urls, 1):
            logger.info(f'Crawling {i}/{len(urls)}: {url}')

            result = self.crawl_url(url)
            if result['success'] and result['capture_id']:
                successful_crawls.append(result['capture_id'])

            # 요청 간 지연
            if i < len(urls):
                time.sleep(delay_seconds)

        logger.info(f'Crawling completed: {len(successful_crawls)}/{len(urls)} successful')
        return successful_crawls

    def _crawl_parallel(self, urls: List[str], max_workers: int = 3) -> List[int]:
        """병렬 크롤링 (ThreadPoolExecutor 사용)"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        logger.info(f'Starting parallel crawling with {max_workers} workers for {len(urls)} URLs')
        successful_crawls = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 각 URL에 대해 크롤링 작업 제출
            future_to_url = {executor.submit(self.crawl_url, url): url for url in urls}

            # 완료된 작업 처리
            for i, future in enumerate(as_completed(future_to_url), 1):
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result['success'] and result['capture_id']:
                        successful_crawls.append(result['capture_id'])
                        logger.info(f'[{i}/{len(urls)}] ✓ Successfully crawled {url} (ID: {result["capture_id"]})')
                    else:
                        logger.warning(f'[{i}/{len(urls)}] ✗ Failed to crawl {url}')
                except Exception as e:
                    logger.error(f'[{i}/{len(urls)}] ✗ Exception crawling {url}: {e}')

        logger.info(f'Parallel crawling completed: {len(successful_crawls)}/{len(urls)} successful')
        return successful_crawls
