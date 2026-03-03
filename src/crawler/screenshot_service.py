import os
import hashlib
import time
import math
from datetime import datetime
from typing import Optional, Tuple, List
from loguru import logger
from PIL import Image
import requests
import imagehash
from .driver_pool import DriverPool

class ScreenshotService:
    # A4 용지 크기 (96 DPI 기준)
    A4_WIDTH = 1920   # 픽셀 (210mm @ 96 DPI)
    A4_HEIGHT = 2715  # 픽셀 (297mm @ 96 DPI)

    def __init__(self, data_root_path: str, enable_a4_split: bool = False, use_driver_pool: bool = True):
        self.data_root_path = data_root_path
        self.images_path = os.path.join(data_root_path, 'images')
        self.enable_a4_split = enable_a4_split  # A4 분할 캡처 활성화 플래그
        self.use_driver_pool = use_driver_pool  # 드라이버 풀 사용 여부
        os.makedirs(self.images_path, exist_ok=True)

        # 날짜별 폴더 생성을 위한 메서드
        self._ensure_date_folder()

        # Chrome 사용 가능 여부 초기화
        self.chrome_available = False
        self.driver_pool = None

        # Chrome이 사용 가능한지 확인
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            import shutil

            # Find Chrome/Chromium browser path
            chromium_path = shutil.which('google-chrome') or shutil.which('chromium-browser') or shutil.which('chromium')
            chromedriver_path = shutil.which('chromedriver')

            if not chromium_path or not chromedriver_path:
                raise Exception(f'Chrome/Chromium not found (browser: {chromium_path}, driver: {chromedriver_path})')

            options = Options()
            options.binary_location = chromium_path  # Explicitly set Chromium path
            options.add_argument('--headless=new')  # New headless mode (more stable)
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-setuid-sandbox')
            options.add_argument('--single-process')  # Help with ARM architecture

            # 뉴스 사이트 크롤링 개선: 봇 탐지 우회 (803 문서 적용)
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-blink-features=AutomationControlled')

            # Use system-installed ChromeDriver
            self.chrome_options = options
            self.chrome_service = Service(chromedriver_path)
            self.chrome_available = True

            # 드라이버 풀 초기화
            if self.use_driver_pool:
                self.driver_pool = DriverPool(pool_size=3, max_uses_per_driver=50)
                self.driver_pool.initialize(self.chrome_options, self.chrome_service)
                logger.info('Driver pool initialized successfully')

            logger.info(f'Chrome WebDriver configured: browser={chromium_path}, driver={chromedriver_path}')
        except Exception as e:
            logger.warning(f'Chrome WebDriver not available: {e}')
            logger.info('Screenshot service will create placeholder images')

    def _ensure_date_folder(self) -> str:
        """오늘 날짜의 YYYYMMDD 폴더를 생성하고 경로 반환"""
        today = datetime.now().strftime('%Y%m%d')
        date_folder_path = os.path.join(self.images_path, today)
        os.makedirs(date_folder_path, exist_ok=True)
        return date_folder_path

    def _get_relative_path(self, full_path: str) -> str:
        """전체 경로에서 data_root_path 이후의 상대 경로를 반환"""
        # /opt/ocr_system/data/images/20241004/screenshot_xxx.png
        # -> images/20241004/screenshot_xxx.png
        return os.path.relpath(full_path, self.data_root_path)

    def generate_filename(self, url: str) -> str:
        """URL을 기반으로 고유한 파일명 생성"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'screenshot_{timestamp}_{url_hash[:8]}.png'

    def calculate_image_hash(self, image_path: str) -> Optional[str]:
        """이미지 파일의 perceptual hash 계산 (804 문서 구현)"""
        try:
            img = Image.open(image_path)
            # pHash 계산 (8x8 크기)
            hash_value = imagehash.phash(img, hash_size=8)
            # 16진수 문자열로 반환
            return str(hash_value)
        except Exception as e:
            logger.error(f'Failed to calculate hash for {image_path}: {e}')
            return None

    def create_placeholder_image(self, url: str, width: int = 1920, height: int = 1080) -> Tuple[str, int, str]:
        """Chrome이 없을 때 플레이스홀더 이미지 생성 (해시 포함)"""
        try:
            # 플레이스홀더 이미지 생성
            img = Image.new('RGB', (width, height), color='lightgray')

            # 날짜별 폴더에 저장
            date_folder = self._ensure_date_folder()
            filename = self.generate_filename(url)
            file_path = os.path.join(date_folder, filename)
            img.save(file_path, 'PNG')

            file_size = os.path.getsize(file_path)
            relative_path = self._get_relative_path(file_path)

            # 이미지 해시 계산
            image_hash = self.calculate_image_hash(file_path)

            logger.info(f'Created placeholder image for {url}: {relative_path} ({file_size} bytes, hash={image_hash})')

            return file_path, file_size, image_hash

        except Exception as e:
            logger.error(f'Error creating placeholder image for {url}: {e}')
            raise

    def capture_full_page(self, url: str, viewport_width: int = 1920,
                         viewport_height: int = 1080, max_retries: int = 3) -> Optional[Tuple[str, int, str]]:
        """전체 페이지 스크린샷 캡처 (개선 버전: 재시도, Context Manager, 페이지 로딩 대기 강화, 이미지 해시)"""
        logger.info(f'Capturing screenshot for URL: {url}')

        # A4 분할 캡처가 활성화된 경우
        if self.enable_a4_split:
            return self.capture_pages_a4_split(url, viewport_width)

        if not self.chrome_available:
            logger.info(f'Using placeholder image for {url}')
            try:
                return self.create_placeholder_image(url, viewport_width, viewport_height)
            except Exception as e:
                logger.error(f'Failed to create placeholder image: {e}')
                return None

        # Chrome이 사용 가능한 경우 재시도 로직으로 실제 스크린샷 캡처
        for attempt in range(max_retries):
            try:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.common.exceptions import TimeoutException, WebDriverException

                logger.info(f'Screenshot attempt {attempt + 1}/{max_retries} for {url}')

                # 드라이버 풀 사용 또는 단일 드라이버 생성
                if self.use_driver_pool and self.driver_pool:
                    # 드라이버 풀에서 가져오기 (Context Manager)
                    with self.driver_pool.get_driver() as driver:
                        driver.set_window_size(viewport_width, viewport_height)

                        # 페이지 로드
                        driver.get(url)

                        # 쿠키 동의 자동 처리
                        self._handle_cookie_consent(driver)

                        # 팝업 및 광고 제거
                        self._remove_popups_and_ads(driver)

                        # 페이지 완전 로딩 대기 (개선됨 - 뉴스 콘텐츠 포함)
                        self._wait_for_page_load(driver, timeout=10, url=url)

                        # 전체 페이지 높이 가져오기
                        total_height = driver.execute_script('return document.body.scrollHeight')
                        driver.set_window_size(viewport_width, total_height)

                        # 추가 대기 (이미지 등 로딩)
                        time.sleep(2)

                        # 스크린샷 데이터 캡처
                        screenshot_data = driver.get_screenshot_as_png()

                        # 데이터 유효성 검증
                        if len(screenshot_data) < 1000:
                            raise ValueError(f'Screenshot too small: {len(screenshot_data)} bytes')

                        # 날짜별 폴더에 저장
                        date_folder = self._ensure_date_folder()
                        filename = self.generate_filename(url)
                        file_path = os.path.join(date_folder, filename)

                        # Context Manager로 안전하게 파일 저장 (개선됨)
                        with open(file_path, 'wb') as f:
                            f.write(screenshot_data)

                        # 파일 생성 확인
                        if not os.path.exists(file_path):
                            raise FileNotFoundError(f'Screenshot file not created: {file_path}')

                        file_size = os.path.getsize(file_path)
                        relative_path = self._get_relative_path(file_path)

                        # 이미지 해시 계산
                        image_hash = self.calculate_image_hash(file_path)

                        logger.info(f'✓ Screenshot saved on attempt {attempt + 1}: {relative_path} ({file_size} bytes, hash={image_hash})')

                        return file_path, file_size, image_hash
                else:
                    # 풀 미사용 시 단일 드라이버 생성 (기존 로직)
                    driver = None
                    try:
                        from selenium import webdriver

                        driver = webdriver.Chrome(service=self.chrome_service, options=self.chrome_options)
                        driver.set_window_size(viewport_width, viewport_height)

                        # WebDriver 속성 숨기기 (봇 탐지 우회)
                        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                            'source': '''
                                Object.defineProperty(navigator, 'webdriver', {
                                    get: () => undefined
                                });
                            '''
                        })

                        # 페이지 로드
                        driver.get(url)

                        # 쿠키 동의 자동 처리
                        self._handle_cookie_consent(driver)

                        # 팝업 및 광고 제거
                        self._remove_popups_and_ads(driver)

                        # 페이지 완전 로딩 대기 (개선됨 - 뉴스 콘텐츠 포함)
                        self._wait_for_page_load(driver, timeout=10, url=url)

                        # 전체 페이지 높이 가져오기
                        total_height = driver.execute_script('return document.body.scrollHeight')
                        driver.set_window_size(viewport_width, total_height)

                        # 추가 대기 (이미지 등 로딩)
                        time.sleep(2)

                        # 스크린샷 데이터 캡처
                        screenshot_data = driver.get_screenshot_as_png()

                        # 데이터 유효성 검증
                        if len(screenshot_data) < 1000:
                            raise ValueError(f'Screenshot too small: {len(screenshot_data)} bytes')

                        # 날짜별 폴더에 저장
                        date_folder = self._ensure_date_folder()
                        filename = self.generate_filename(url)
                        file_path = os.path.join(date_folder, filename)

                        # Context Manager로 안전하게 파일 저장 (개선됨)
                        with open(file_path, 'wb') as f:
                            f.write(screenshot_data)

                        # 파일 생성 확인
                        if not os.path.exists(file_path):
                            raise FileNotFoundError(f'Screenshot file not created: {file_path}')

                        file_size = os.path.getsize(file_path)
                        relative_path = self._get_relative_path(file_path)

                        # 이미지 해시 계산
                        image_hash = self.calculate_image_hash(file_path)

                        logger.info(f'✓ Screenshot saved on attempt {attempt + 1}: {relative_path} ({file_size} bytes, hash={image_hash})')

                        return file_path, file_size, image_hash

                    finally:
                        # WebDriver 안전하게 종료
                        if driver is not None:
                            try:
                                driver.quit()
                            except:
                                pass

            except Exception as e:
                logger.warning(f'✗ Attempt {attempt + 1} failed: {type(e).__name__}: {e}')

                if attempt < max_retries - 1:
                    # 지수 백오프
                    wait_time = (attempt + 1) * 2
                    logger.info(f'Retrying in {wait_time} seconds...')
                    time.sleep(wait_time)
                else:
                    logger.error(f'All {max_retries} attempts failed for {url}')
                    # 모든 재시도 실패 시 플레이스홀더 이미지로 대체
                    try:
                        return self.create_placeholder_image(url, viewport_width, viewport_height)
                    except:
                        return None

        # 폴백 (도달하지 않아야 함)
        try:
            return self.create_placeholder_image(url, viewport_width, viewport_height)
        except:
            return None

    def _wait_for_page_load(self, driver, timeout: int = 10, url: str = ''):
        """페이지 완전 로딩 대기 (개선된 버전 + 뉴스 콘텐츠 대기)"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            # 1. 문서 로딩 완료 대기
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            # 2. Body 요소 대기
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # 3. jQuery 로딩 완료 대기 (있는 경우)
            try:
                WebDriverWait(driver, 2).until(
                    lambda d: d.execute_script("return typeof jQuery != 'undefined' && jQuery.active == 0")
                )
            except:
                pass  # jQuery 없으면 스킵

            # 4. 뉴스 사이트 콘텐츠 대기 (803 문서 적용)
            if 'news.' in url or 'post.' in url or 'blog.' in url:
                try:
                    # article 태그 또는 main content 대기
                    WebDriverWait(driver, 5).until(
                        lambda d: d.find_element(By.TAG_NAME, 'article') or
                                 d.find_element(By.CSS_SELECTOR, 'div.content, div.article, div.post-content, div#content')
                    )
                    logger.debug('News content loaded')
                except:
                    logger.debug('News content selector not found, continuing')

            logger.debug('Page fully loaded')

        except Exception as e:
            logger.warning(f'Page load wait timeout: {e}')
            # 타임아웃 되어도 계속 진행

    def _handle_cookie_consent(self, driver):
        """쿠키 동의 팝업 자동 처리 (803 문서 적용)"""
        try:
            # 일반적인 쿠키 동의 버튼 클릭 시도
            cookie_selectors = [
                "button[id*='cookie'][id*='accept']",
                "button[class*='cookie'][class*='accept']",
                "a[id*='cookie'][id*='accept']",
                "a[class*='cookie'][class*='accept']",
                "button:contains('동의')",
                "button:contains('확인')",
                "button:contains('Accept')",
                "button:contains('OK')"
            ]

            for selector in cookie_selectors:
                try:
                    elements = driver.find_elements('css selector', selector)
                    if elements and elements[0].is_displayed():
                        elements[0].click()
                        logger.debug(f'Clicked cookie consent: {selector}')
                        time.sleep(0.5)
                        return
                except:
                    continue

            logger.debug('No cookie consent found or already accepted')

        except Exception as e:
            logger.debug(f'Cookie consent handling error (non-critical): {e}')

    def _remove_popups_and_ads(self, driver):
        """팝업 및 광고 제거 (803 문서 적용)"""
        try:
            # JavaScript로 일반적인 광고 및 팝업 요소 제거
            remove_script = """
            // 고정 팝업 제거
            document.querySelectorAll('[class*="popup"], [class*="modal"], [class*="overlay"]').forEach(el => {
                if (el.style.position === 'fixed' || el.style.position === 'absolute') {
                    el.remove();
                }
            });

            // 광고 제거
            document.querySelectorAll('[class*="ad"], [id*="ad"], [class*="banner"], iframe[src*="ad"]').forEach(el => {
                el.remove();
            });

            // body overflow 복원 (팝업이 스크롤 막는 경우)
            document.body.style.overflow = 'auto';
            """

            driver.execute_script(remove_script)
            logger.debug('Removed popups and ads')

        except Exception as e:
            logger.debug(f'Popup removal error (non-critical): {e}')

    def capture_pages_a4_split(self, url: str, viewport_width: int = 1920) -> Optional[List[Tuple[str, int]]]:
        """A4 용지 크기로 페이지를 나누어 스크롤 기반 캡처"""
        logger.info(f'Capturing A4-split screenshots for URL: {url}')

        if not self.chrome_available:
            logger.warning('Chrome not available for A4 split capture')
            return None

        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            # 드라이버 풀 사용 또는 단일 드라이버 생성
            if self.use_driver_pool and self.driver_pool:
                with self.driver_pool.get_driver() as driver:
                    return self._perform_a4_split_capture(driver, url, viewport_width)
            else:
                driver = None
                try:
                    from selenium import webdriver

                    driver = webdriver.Chrome(service=self.chrome_service, options=self.chrome_options)
                    driver.set_window_size(viewport_width, self.A4_HEIGHT)

                    # WebDriver 속성 숨기기 (봇 탐지 우회)
                    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                        'source': '''
                            Object.defineProperty(navigator, 'webdriver', {
                                get: () => undefined
                            });
                        '''
                    })

                    return self._perform_a4_split_capture(driver, url, viewport_width)

                finally:
                    if driver is not None:
                        try:
                            driver.quit()
                        except Exception as e:
                            logger.warning(f'Error closing driver: {e}')

        except Exception as e:
            logger.error(f'Error capturing A4-split screenshot for {url}: {e}')
            return None

    def _perform_a4_split_capture(self, driver, url: str, viewport_width: int) -> Optional[Tuple[str, int, str]]:
        """A4 분할 캡처 실제 수행 (드라이버 풀과 단일 드라이버 공통 로직)"""
        try:
            driver.set_window_size(viewport_width, self.A4_HEIGHT)

            driver.get(url)

            # 쿠키 동의 자동 처리
            self._handle_cookie_consent(driver)

            # 팝업 및 광고 제거
            self._remove_popups_and_ads(driver)

            # 페이지 완전 로딩 대기 (개선된 버전)
            self._wait_for_page_load(driver, timeout=10, url=url)

            # 전체 페이지 높이
            total_height = driver.execute_script('return document.body.scrollHeight')

            # 페이지 개수 계산
            num_pages = math.ceil(total_height / self.A4_HEIGHT)
            logger.info(f'Total height: {total_height}px, splitting into {num_pages} A4 pages')

            captured_pages = []
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # 날짜별 폴더 생성
            date_folder = self._ensure_date_folder()

            for page_num in range(num_pages):
                # 스크롤 위치 이동
                scroll_position = page_num * self.A4_HEIGHT
                driver.execute_script(f'window.scrollTo(0, {scroll_position})')
                time.sleep(0.5)  # 렌더링 대기

                # 페이지별 파일명 (날짜별 폴더에 저장)
                filename = f'screenshot_{timestamp}_{url_hash}_page{page_num+1:03d}.png'
                file_path = os.path.join(date_folder, filename)

                # 캡처
                driver.save_screenshot(file_path)
                file_size = os.path.getsize(file_path)
                relative_path = self._get_relative_path(file_path)

                captured_pages.append((file_path, file_size))
                logger.info(f'Captured A4 page {page_num+1}/{num_pages}: {relative_path} ({file_size} bytes)')

            logger.info(f'Successfully captured {num_pages} A4 pages for {url}')

            # 첫 번째 페이지의 정보를 반환 (기존 인터페이스 호환성 유지)
            # 향후 다중 페이지 지원을 위해서는 web_crawler.py 수정 필요
            if captured_pages:
                first_page_path, first_page_size = captured_pages[0]
                # 이미지 해시 계산 (파일 핸들 즉시 닫기)
                image_hash = self.calculate_image_hash(first_page_path)
                if not image_hash:
                    # 해시 계산 실패 시 기본값
                    image_hash = hashlib.md5(first_page_path.encode()).hexdigest()[:16]
                return (first_page_path, first_page_size, image_hash)
            return None

        except Exception as e:
            logger.error(f'Error in A4 split capture: {e}')
            return None

    def optimize_image(self, file_path: str, quality: int = 85) -> str:
        """이미지 최적화"""
        try:
            with Image.open(file_path) as img:
                if file_path.endswith('.png'):
                    rgb_img = img.convert('RGB')
                    jpeg_path = file_path.replace('.png', '.jpg')
                    rgb_img.save(jpeg_path, 'JPEG', quality=quality, optimize=True)
                    os.remove(file_path)
                    return jpeg_path
            return file_path
        except Exception as e:
            logger.error(f'Error optimizing image {file_path}: {e}')
            return file_path
