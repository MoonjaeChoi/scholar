#!/usr/bin/env python3
# Generated: 2025-10-16 21:20:00 KST
"""
ScreenshotCrawler 단위 테스트

A4 단위 스크린샷 분할 크롤러 기능 테스트
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from PIL import Image

# scholar 모듈 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from crawler.screenshot_crawler import ScreenshotCrawler


@pytest.fixture
def sample_strategy():
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
            "pause_between_scrolls": 100  # 테스트용으로 짧게
        },
        "split_strategy": {
            "unit": "A4",
            "overlap_px": 0,
            "max_splits": 50
        },
        "wait_strategy": {
            "type": "fixed",
            "duration": 0.1  # 테스트용으로 짧게
        },
        "image_format": "PNG",
        "image_quality": 90
    }


@pytest.fixture
def mock_driver():
    """Mock Selenium WebDriver"""
    driver = MagicMock()
    driver.get = Mock()
    driver.quit = Mock()
    driver.set_window_size = Mock()
    driver.set_page_load_timeout = Mock()
    driver.execute_script = Mock(return_value=5000)  # 5000px 페이지

    # 샘플 이미지 생성 (A4 크기)
    img = Image.new('RGB', (794, 1123), color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    driver.get_screenshot_as_png = Mock(return_value=buffer.getvalue())

    return driver


class TestScreenshotCrawler:
    """ScreenshotCrawler 단위 테스트"""

    @patch('crawler.screenshot_crawler.webdriver.Chrome')
    def test_init_driver(self, mock_chrome, sample_strategy):
        """WebDriver 초기화 테스트"""
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        crawler = ScreenshotCrawler(sample_strategy, headless=True)

        assert crawler.driver is not None
        assert crawler.viewport['width'] == 794
        assert crawler.viewport['height'] == 1123

        crawler.close()

    @patch('crawler.screenshot_crawler.webdriver.Chrome')
    def test_context_manager(self, mock_chrome, sample_strategy):
        """Context manager 동작 테스트"""
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        with ScreenshotCrawler(sample_strategy) as crawler:
            assert crawler.driver is not None

        # __exit__ 후 driver.quit() 호출 확인
        mock_driver.quit.assert_called_once()

    @patch('crawler.screenshot_crawler.webdriver.Chrome')
    def test_get_page_height(self, mock_chrome, sample_strategy):
        """페이지 높이 측정 테스트"""
        mock_driver = MagicMock()
        mock_driver.execute_script.side_effect = [5000, 4800, 1123]  # 여러 높이 반환
        mock_chrome.return_value = mock_driver

        crawler = ScreenshotCrawler(sample_strategy)
        height = crawler._get_page_height()

        assert height == 5000  # 최대값

        crawler.close()

    @patch('crawler.screenshot_crawler.webdriver.Chrome')
    @patch('crawler.screenshot_crawler.time.sleep')  # sleep mock
    def test_capture_with_split(self, mock_sleep, mock_chrome, sample_strategy):
        """A4 단위 분할 캡처 테스트"""
        # Mock driver 설정
        mock_driver = MagicMock()
        mock_driver.execute_script.side_effect = [
            None,  # scrollTo
            True,  # readyState
            5000,  # body.scrollHeight
            5000,  # documentElement.scrollHeight
            1123,  # window.innerHeight
        ]

        # 샘플 이미지 생성
        img = Image.new('RGB', (794, 1123), color='red')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        mock_driver.get_screenshot_as_png.return_value = buffer.getvalue()

        mock_chrome.return_value = mock_driver

        crawler = ScreenshotCrawler(sample_strategy)

        # 짧은 페이지로 테스트 (2개 분할)
        mock_driver.execute_script.side_effect = [
            None,  # scrollTo
            True,  # readyState
            2246,  # body.scrollHeight (A4 높이 * 2)
            2246,  # documentElement.scrollHeight
            1123,  # window.innerHeight
        ] + [None, None] * 10  # scrollTo 반복

        screenshots = crawler.capture_with_split('https://test.com')

        # 2246px = 2개 A4 (1123px * 2)
        assert len(screenshots) == 2
        assert all(isinstance(s, bytes) for s in screenshots)

        crawler.close()

    @patch('crawler.screenshot_crawler.webdriver.Chrome')
    def test_crop_to_a4(self, mock_chrome, sample_strategy):
        """A4 크롭 테스트"""
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        crawler = ScreenshotCrawler(sample_strategy)

        # 샘플 이미지 생성 (A4 크기)
        img = Image.new('RGB', (794, 1123), color='blue')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        screenshot_png = buffer.getvalue()

        # 크롭
        cropped = crawler._crop_to_a4(screenshot_png, remaining_height=1123)

        # 크롭된 이미지 검증
        cropped_img = Image.open(BytesIO(cropped))
        assert cropped_img.width == 794
        assert cropped_img.height == 1123

        crawler.close()

    @patch('crawler.screenshot_crawler.webdriver.Chrome')
    def test_crop_last_page(self, mock_chrome, sample_strategy):
        """마지막 페이지 크롭 (높이 부족) 테스트"""
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        crawler = ScreenshotCrawler(sample_strategy)

        # 샘플 이미지 생성 (A4보다 작은 크기)
        img = Image.new('RGB', (794, 500), color='green')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        screenshot_png = buffer.getvalue()

        # 크롭 (남은 높이 500px)
        cropped = crawler._crop_to_a4(screenshot_png, remaining_height=500)

        # 크롭된 이미지 검증 (500px 이하)
        cropped_img = Image.open(BytesIO(cropped))
        assert cropped_img.width == 794
        assert cropped_img.height <= 500

        crawler.close()

    @patch('crawler.screenshot_crawler.webdriver.Chrome')
    @patch('crawler.screenshot_crawler.time.sleep')
    def test_apply_wait_strategy_fixed(self, mock_sleep, mock_chrome, sample_strategy):
        """Fixed wait 전략 테스트"""
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        crawler = ScreenshotCrawler(sample_strategy)
        crawler._apply_wait_strategy()

        # sleep 호출 확인 (duration=0.1)
        mock_sleep.assert_called()

        crawler.close()

    @patch('crawler.screenshot_crawler.webdriver.Chrome')
    def test_jpeg_format(self, mock_chrome, sample_strategy):
        """JPEG 포맷 저장 테스트"""
        sample_strategy['image_format'] = 'JPEG'
        sample_strategy['image_quality'] = 85

        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        crawler = ScreenshotCrawler(sample_strategy)

        # 샘플 이미지 생성
        img = Image.new('RGB', (794, 1123), color='yellow')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        screenshot_png = buffer.getvalue()

        # 크롭 (JPEG로 변환)
        cropped = crawler._crop_to_a4(screenshot_png, remaining_height=1123)

        # JPEG 이미지 검증
        cropped_img = Image.open(BytesIO(cropped))
        assert cropped_img.format == 'JPEG'

        crawler.close()

    @patch('crawler.screenshot_crawler.webdriver.Chrome')
    def test_max_splits_limit(self, mock_chrome, sample_strategy):
        """최대 분할 수 제한 테스트"""
        # max_splits를 3으로 제한
        sample_strategy['split_strategy']['max_splits'] = 3

        mock_driver = MagicMock()
        mock_driver.execute_script.side_effect = [
            None,  # scrollTo
            True,  # readyState
            10000,  # body.scrollHeight (매우 긴 페이지)
            10000,
            1123,
        ] + [None] * 50  # scrollTo 반복

        img = Image.new('RGB', (794, 1123), color='red')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        mock_driver.get_screenshot_as_png.return_value = buffer.getvalue()

        mock_chrome.return_value = mock_driver

        crawler = ScreenshotCrawler(sample_strategy)

        with patch('crawler.screenshot_crawler.time.sleep'):
            screenshots = crawler._capture_splits(total_height=10000)

        # 최대 3개만 캡처
        assert len(screenshots) <= 3

        crawler.close()

    def test_a4_constants(self):
        """A4 크기 상수 테스트"""
        assert ScreenshotCrawler.A4_WIDTH == 794
        assert ScreenshotCrawler.A4_HEIGHT == 1123


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
