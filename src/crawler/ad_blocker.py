# Generated: 2025-10-02 20:00:00 KST
"""
Ad Blocker - 광고 및 불필요한 요소 제거
"""

from typing import List, Set
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger
import time


class AdBlocker:
    """광고 및 불필요한 요소 제거 시스템"""

    def __init__(self, ad_config: dict = None):
        """
        Args:
            ad_config: 광고 차단 설정 (korean_blog_sites.json의 ad_blocking 섹션)
        """
        self.enabled = ad_config.get('enabled', True) if ad_config else True
        self.css_selectors = ad_config.get('css_selectors', []) if ad_config else []
        self.xpath_selectors = ad_config.get('xpath_selectors', []) if ad_config else []
        self.blocked_domains = set(ad_config.get('domains_to_block', [])) if ad_config else set()

        # 기본 광고 셀렉터 (설정이 없는 경우)
        if not self.css_selectors:
            self.css_selectors = self._get_default_css_selectors()

        if not self.xpath_selectors:
            self.xpath_selectors = self._get_default_xpath_selectors()

    def _get_default_css_selectors(self) -> List[str]:
        """기본 CSS 광고 셀렉터"""
        return [
            'iframe[src*="ad"]',
            'div[class*="ad"]',
            'div[id*="ad"]',
            'div[class*="advertisement"]',
            'div[class*="banner"]',
            'div[class*="sponsor"]',
            'div[class*="promotion"]',
            'aside[class*="sidebar"]',
            '.adsbygoogle',
            '.ad-container',
            '.advertisement',
        ]

    def _get_default_xpath_selectors(self) -> List[str]:
        """기본 XPath 광고 셀렉터"""
        return [
            "//iframe[contains(@src, 'ad')]",
            "//div[contains(@class, 'ad')]",
            "//div[contains(@id, 'ad')]",
        ]

    def setup_driver_blocking(self, driver: webdriver.Chrome) -> webdriver.Chrome:
        """
        Selenium WebDriver에 광고 차단 설정 적용

        Args:
            driver: Selenium WebDriver 인스턴스

        Returns:
            webdriver.Chrome: 설정이 적용된 드라이버
        """
        if not self.enabled:
            return driver

        # 도메인 차단을 위한 JavaScript 인젝션
        if self.blocked_domains:
            blocking_script = self._generate_domain_blocking_script()
            try:
                driver.execute_script(blocking_script)
                logger.debug(f"Blocked {len(self.blocked_domains)} ad domains")
            except Exception as e:
                logger.warning(f"Failed to inject domain blocking script: {e}")

        return driver

    def _generate_domain_blocking_script(self) -> str:
        """도메인 차단 JavaScript 생성"""
        domains_json = ','.join([f'"{d}"' for d in self.blocked_domains])

        return f"""
        (function() {{
            var blockedDomains = [{domains_json}];

            // XMLHttpRequest 차단
            var originalOpen = XMLHttpRequest.prototype.open;
            XMLHttpRequest.prototype.open = function(method, url) {{
                for (var i = 0; i < blockedDomains.length; i++) {{
                    if (url.indexOf(blockedDomains[i]) !== -1) {{
                        console.log('Blocked XHR request to: ' + url);
                        return;
                    }}
                }}
                return originalOpen.apply(this, arguments);
            }};

            // Fetch API 차단
            var originalFetch = window.fetch;
            window.fetch = function(url) {{
                for (var i = 0; i < blockedDomains.length; i++) {{
                    if (url.indexOf(blockedDomains[i]) !== -1) {{
                        console.log('Blocked Fetch request to: ' + url);
                        return Promise.reject(new Error('Blocked'));
                    }}
                }}
                return originalFetch.apply(this, arguments);
            }};
        }})();
        """

    def remove_ads_from_page(self, driver: webdriver.Chrome) -> int:
        """
        페이지에서 광고 요소 제거

        Args:
            driver: Selenium WebDriver 인스턴스

        Returns:
            int: 제거된 광고 요소 개수
        """
        if not self.enabled:
            return 0

        removed_count = 0

        # CSS 셀렉터로 광고 제거
        removed_count += self._remove_by_css_selectors(driver)

        # XPath 셀렉터로 광고 제거
        removed_count += self._remove_by_xpath_selectors(driver)

        # 숨겨진 광고 요소 제거
        removed_count += self._remove_hidden_ads(driver)

        logger.info(f"Removed {removed_count} ad elements from page")
        return removed_count

    def _remove_by_css_selectors(self, driver: webdriver.Chrome) -> int:
        """CSS 셀렉터로 광고 제거"""
        removed = 0

        for selector in self.css_selectors:
            try:
                script = f"""
                var elements = document.querySelectorAll('{selector}');
                for (var i = 0; i < elements.length; i++) {{
                    elements[i].remove();
                }}
                return elements.length;
                """
                count = driver.execute_script(script)
                removed += count
                if count > 0:
                    logger.debug(f"Removed {count} elements matching '{selector}'")
            except Exception as e:
                logger.warning(f"Error removing CSS selector '{selector}': {e}")

        return removed

    def _remove_by_xpath_selectors(self, driver: webdriver.Chrome) -> int:
        """XPath 셀렉터로 광고 제거"""
        removed = 0

        for xpath in self.xpath_selectors:
            try:
                elements = driver.find_elements(By.XPATH, xpath)
                for element in elements:
                    try:
                        driver.execute_script("arguments[0].remove();", element)
                        removed += 1
                    except:
                        pass

                if elements:
                    logger.debug(f"Removed {len(elements)} elements matching XPath '{xpath}'")
            except Exception as e:
                logger.warning(f"Error removing XPath '{xpath}': {e}")

        return removed

    def _remove_hidden_ads(self, driver: webdriver.Chrome) -> int:
        """display:none 또는 visibility:hidden인 광고 요소 제거"""
        try:
            script = """
            var hiddenElements = document.querySelectorAll('[style*="display: none"], [style*="visibility: hidden"]');
            var removed = 0;
            for (var i = 0; i < hiddenElements.length; i++) {
                var elem = hiddenElements[i];
                var classes = elem.className.toLowerCase();
                var id = elem.id.toLowerCase();
                if (classes.includes('ad') || id.includes('ad') ||
                    classes.includes('advertisement') || id.includes('advertisement')) {
                    elem.remove();
                    removed++;
                }
            }
            return removed;
            """
            count = driver.execute_script(script)
            return count
        except Exception as e:
            logger.warning(f"Error removing hidden ads: {e}")
            return 0

    def wait_and_remove_dynamic_ads(self, driver: webdriver.Chrome, wait_seconds: int = 3) -> int:
        """
        동적으로 로드되는 광고 대기 후 제거

        Args:
            driver: Selenium WebDriver 인스턴스
            wait_seconds: 광고 로딩 대기 시간 (초)

        Returns:
            int: 제거된 광고 요소 개수
        """
        if not self.enabled:
            return 0

        # 광고가 로드될 시간을 줌
        time.sleep(wait_seconds)

        # 광고 제거
        removed_count = self.remove_ads_from_page(driver)

        # 추가 동적 광고 체크
        time.sleep(1)
        additional_removed = self.remove_ads_from_page(driver)

        total_removed = removed_count + additional_removed
        logger.info(f"Dynamic ad removal completed: {total_removed} elements removed")

        return total_removed

    def get_clean_page_screenshot(self, driver: webdriver.Chrome, output_path: str) -> bool:
        """
        광고를 제거한 깨끗한 페이지 스크린샷 저장

        Args:
            driver: Selenium WebDriver 인스턴스
            output_path: 스크린샷 저장 경로

        Returns:
            bool: 성공 여부
        """
        try:
            # 광고 제거
            self.wait_and_remove_dynamic_ads(driver, wait_seconds=2)

            # 스크롤하여 전체 페이지 로드
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)

            # 다시 한번 광고 제거 (스크롤 후 새로 로드된 광고)
            self.remove_ads_from_page(driver)

            # 스크린샷 저장
            driver.save_screenshot(output_path)
            logger.info(f"Clean screenshot saved: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error taking clean screenshot: {e}")
            return False
