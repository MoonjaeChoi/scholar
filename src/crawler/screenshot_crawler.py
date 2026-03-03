#!/usr/bin/env python3
# Generated: 2025-10-16 21:15:00 KST
"""
A4 단위 스크린샷 분할 크롤러

Selenium WebDriver를 사용하여 웹페이지를 A4 용지 크기(794×1123px)로 분할 캡처합니다.
"""

from typing import Dict, List, Any, Optional
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException
from PIL import Image
from io import BytesIO
from loguru import logger


class ScreenshotCrawler:
    """A4 단위 스크린샷 분할 크롤러"""

    # A4 크기 상수 (96 DPI)
    A4_WIDTH = 794
    A4_HEIGHT = 1123

    def __init__(self, strategy: Dict[str, Any], headless: bool = True):
        """
        Args:
            strategy: 스크린샷 전략 JSON
            headless: Headless 모드 사용 여부 (기본: True)
        """
        self.strategy = strategy
        self.viewport = strategy.get('viewport', {
            'width': self.A4_WIDTH,
            'height': self.A4_HEIGHT,
            'scale': 1.0
        })
        self.headless = headless
        self.driver = None
        self._init_driver()

    def _init_driver(self):
        """Selenium WebDriver 초기화"""
        try:
            options = Options()

            if self.headless:
                options.add_argument('--headless')
                logger.debug("Chrome running in headless mode")

            # 기본 옵션
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-blink-features=AutomationControlled')

            # User-Agent 설정 (봇 감지 우회)
            options.add_argument(
                'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            # 창 크기 설정
            width = self.viewport['width']
            height = self.viewport['height']
            options.add_argument(f'--window-size={width},{height}')

            # WebDriver 초기화
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_window_size(width, height)

            # 페이지 로드 타임아웃
            self.driver.set_page_load_timeout(30)

            logger.info(
                f"WebDriver initialized: {width}×{height}px, "
                f"headless={self.headless}"
            )

        except WebDriverException as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def capture_with_split(self, url: str) -> List[bytes]:
        """URL 접속 후 A4 단위로 분할 캡처

        Args:
            url: 대상 URL

        Returns:
            분할된 이미지 목록 (각 A4 크기 PNG)

        Raises:
            WebDriverException: 페이지 로드 실패
        """
        if not self.driver:
            raise RuntimeError("WebDriver not initialized")

        logger.info(f"Capturing screenshots: {url}")

        try:
            # 1. 페이지 로드
            self.driver.get(url)
            logger.debug(f"Page loaded: {url}")

            # 2. Wait 전략 적용
            self._apply_wait_strategy()

            # 3. 전체 페이지 높이 측정
            total_height = self._get_page_height()
            logger.info(f"Page height: {total_height}px")

            # 4. A4 단위로 분할 캡처
            screenshots = self._capture_splits(total_height)

            logger.info(f"Captured {len(screenshots)} screenshots from {url}")
            return screenshots

        except TimeoutException as e:
            logger.error(f"Page load timeout: {url} - {e}")
            raise

        except WebDriverException as e:
            logger.error(f"WebDriver error: {url} - {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error during capture: {url} - {e}")
            raise

    def _get_page_height(self) -> int:
        """전체 페이지 높이 측정

        Returns:
            페이지 높이 (px)
        """
        # 여러 방법으로 높이 측정 (가장 큰 값 사용)
        heights = []

        try:
            # document.body.scrollHeight
            h1 = self.driver.execute_script("return document.body.scrollHeight")
            heights.append(h1)

            # document.documentElement.scrollHeight
            h2 = self.driver.execute_script("return document.documentElement.scrollHeight")
            heights.append(h2)

            # window.innerHeight
            h3 = self.driver.execute_script("return window.innerHeight")
            heights.append(h3)

        except Exception as e:
            logger.warning(f"Failed to measure page height: {e}")
            # 기본값 사용
            heights = [self.A4_HEIGHT]

        max_height = max(heights)
        logger.debug(f"Page heights measured: {heights}, using max: {max_height}px")

        return max_height

    def _capture_splits(self, total_height: int) -> List[bytes]:
        """A4 단위로 분할 캡처

        Args:
            total_height: 전체 페이지 높이

        Returns:
            분할된 이미지 목록
        """
        a4_height = self.viewport['height']
        max_splits = self.strategy.get('split_strategy', {}).get('max_splits', 50)
        scroll_pause = self.strategy.get('scroll_strategy', {}).get('pause_between_scrolls', 500) / 1000.0

        screenshots = []
        current_y = 0
        split_count = 0

        while current_y < total_height and split_count < max_splits:
            # 스크롤 위치 설정
            self.driver.execute_script(f"window.scrollTo(0, {current_y});")

            # 렌더링 대기
            time.sleep(scroll_pause)

            # 스크린샷 캡처 (PNG)
            try:
                screenshot_png = self.driver.get_screenshot_as_png()

                # A4 영역만 크롭
                remaining_height = total_height - current_y
                cropped = self._crop_to_a4(screenshot_png, remaining_height)

                screenshots.append(cropped)

                logger.debug(
                    f"Split {split_count + 1}: y={current_y}~{current_y + a4_height}, "
                    f"remaining={remaining_height}px"
                )

            except Exception as e:
                logger.error(f"Failed to capture split {split_count + 1}: {e}")
                # 계속 진행

            # 다음 위치
            current_y += a4_height
            split_count += 1

        return screenshots

    def _crop_to_a4(self, screenshot_png: bytes, remaining_height: int) -> bytes:
        """A4 크기로 크롭

        Args:
            screenshot_png: 스크린샷 PNG
            remaining_height: 남은 페이지 높이

        Returns:
            크롭된 PNG
        """
        try:
            image = Image.open(BytesIO(screenshot_png))

            # A4 크기
            a4_width = self.viewport['width']
            a4_height = self.viewport['height']

            # 크롭 영역 계산
            left = 0
            top = 0
            right = min(a4_width, image.width)
            bottom = min(a4_height, image.height, remaining_height)

            # 크롭
            cropped = image.crop((left, top, right, bottom))

            # PNG로 변환
            buffer = BytesIO()
            image_format = self.strategy.get('image_format', 'PNG').upper()
            image_quality = self.strategy.get('image_quality', 90)

            if image_format == 'JPEG':
                # JPEG은 RGB 모드 필요
                if cropped.mode != 'RGB':
                    cropped = cropped.convert('RGB')
                cropped.save(buffer, format='JPEG', quality=image_quality)
            else:
                # PNG (기본)
                cropped.save(buffer, format='PNG')

            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Failed to crop image: {e}")
            raise

    def _apply_wait_strategy(self):
        """Wait 전략 적용"""
        wait_strategy = self.strategy.get('wait_strategy', {})
        wait_type = wait_strategy.get('type', 'fixed')
        duration = wait_strategy.get('duration', 3)

        logger.debug(f"Applying wait strategy: type={wait_type}, duration={duration}s")

        if wait_type == 'fixed':
            time.sleep(duration)

        elif wait_type == 'dynamic':
            # 동적 대기 (페이지가 완전히 로드될 때까지)
            try:
                self.driver.execute_script(
                    "return document.readyState === 'complete'"
                )
                time.sleep(duration)  # 추가 대기
            except Exception as e:
                logger.warning(f"Dynamic wait failed: {e}, falling back to fixed wait")
                time.sleep(duration)

        # 이미지 로드 대기 (옵션)
        if wait_strategy.get('wait_for_images', False):
            self._wait_for_images()

    def _wait_for_images(self, timeout: int = 10):
        """모든 이미지 로드 대기

        Args:
            timeout: 타임아웃 (초)
        """
        try:
            logger.debug("Waiting for images to load...")

            script = """
                return Array.from(document.images).every(img => img.complete);
            """

            start_time = time.time()
            while time.time() - start_time < timeout:
                all_loaded = self.driver.execute_script(script)
                if all_loaded:
                    logger.debug("All images loaded")
                    return
                time.sleep(0.5)

            logger.warning("Image load timeout")

        except Exception as e:
            logger.warning(f"Failed to wait for images: {e}")

    def close(self):
        """WebDriver 종료"""
        if self.driver:
            try:
                self.driver.quit()
                logger.debug("WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None

    def __enter__(self):
        """Context manager 진입"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.close()
        return False  # 예외를 다시 발생시킴

    def __del__(self):
        """소멸자"""
        self.close()
