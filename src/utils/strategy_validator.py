# Generated: 2025-10-14 11:30:00 KST
"""
Strategy Validator - Step 3 of Sonic Koi Methodology

크롤링 전략을 실제로 테스트하여 유효성을 검증합니다.
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from loguru import logger

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        WebDriverException
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium not installed. Validation will fail.")


class StrategyValidator:
    """크롤링 전략 검증기"""

    def __init__(self, strategy: Dict):
        """
        Args:
            strategy: Step 2에서 생성된 크롤링 전략 JSON
        """
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium not installed. Please run: pip install selenium")

        self.strategy = strategy
        self.driver: Optional[webdriver.Chrome] = None
        self.results = {
            "validation_timestamp": datetime.now().isoformat(),
            "site_url": strategy.get("site_url", "unknown"),
            "strategy_version": strategy.get("strategy_version", "unknown"),
            "total_tests": 0,
            "successful_tests": 0,
            "failed_tests": 0,
            "test_details": [],
            "issues_found": [],
            "actual_success_rate": 0.0
        }

    def _init_driver(self) -> webdriver.Chrome:
        """Selenium WebDriver 초기화"""
        logger.info("Initializing Chrome WebDriver...")

        chrome_options = Options()

        # 전략의 browser_options 적용
        if "initialization" in self.strategy and "browser_options" in self.strategy["initialization"]:
            browser_opts = self.strategy["initialization"]["browser_options"]

            if browser_opts.get("headless", True):
                chrome_options.add_argument("--headless")
                logger.info("Headless mode enabled")

            window_size = browser_opts.get("window_size", [1920, 1080])
            chrome_options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")

            user_agent = browser_opts.get("user_agent")
            if user_agent:
                chrome_options.add_argument(f"user-agent={user_agent}")

            if browser_opts.get("disable_images", False):
                prefs = {"profile.managed_default_content_settings.images": 2}
                chrome_options.add_experimental_option("prefs", prefs)

        # 기본 옵션
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        try:
            driver = webdriver.Chrome(options=chrome_options)
            logger.info("✅ WebDriver initialized successfully")
            return driver
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def validate(self, test_url: str, sample_size: int = 5) -> Dict:
        """
        전략 검증 실행

        Args:
            test_url: 테스트할 URL
            sample_size: 샘플링할 게시글 수

        Returns:
            검증 결과 딕셔너리
        """
        logger.info("="*80)
        logger.info("Starting Strategy Validation")
        logger.info("="*80)
        logger.info(f"Test URL: {test_url}")
        logger.info(f"Sample size: {sample_size}")

        try:
            # 1. WebDriver 초기화
            self.driver = self._init_driver()

            # 2. Index 페이지 로드 테스트
            self._test_page_load(test_url)

            # 3. 게시글 목록 추출 테스트
            article_links = self._test_article_list_extraction()

            if article_links:
                # 4. 페이지네이션 테스트 (선택적)
                if self.strategy.get("pagination_strategy", {}).get("type") != "none":
                    self._test_pagination(test_url)

                # 5. 샘플 게시글 내용 추출 테스트
                sample_links = article_links[:min(sample_size, len(article_links))]
                for i, link in enumerate(sample_links, 1):
                    logger.info(f"Testing article {i}/{len(sample_links)}: {link}")
                    self._test_article_content_extraction(link)
                    time.sleep(2)  # 요청 간 지연

            # 6. 성공률 계산
            self._calculate_success_rate()

            # 7. 이슈 분석
            self._analyze_issues()

        except Exception as e:
            logger.error(f"Validation failed with exception: {e}")
            self.results["validation_error"] = str(e)

        finally:
            # WebDriver 종료
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver closed")

        return {"validation_results": self.results}

    def _test_page_load(self, url: str):
        """페이지 로드 테스트"""
        test_name = "index_page_load"
        self.results["total_tests"] += 1

        logger.info(f"[Test] {test_name}: Loading {url}")

        try:
            start_time = time.time()

            # 페이지 로드
            self.driver.get(url)

            # Wait strategy 적용
            if "wait_strategy" in self.strategy and "conditions" in self.strategy["wait_strategy"]:
                conditions = self.strategy["wait_strategy"]["conditions"]
                if conditions:
                    wait_config = conditions[0]
                    selector = wait_config.get("selector")
                    timeout = wait_config.get("timeout", 10)

                    logger.info(f"Waiting for element: {selector} (timeout: {timeout}s)")
                    wait = WebDriverWait(self.driver, timeout)
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))

            elapsed = time.time() - start_time

            self.results["successful_tests"] += 1
            self.results["test_details"].append({
                "test_name": test_name,
                "status": "success",
                "time_taken": round(elapsed, 2),
                "url": url,
                "page_title": self.driver.title
            })

            logger.info(f"✅ {test_name}: Success ({elapsed:.2f}s)")

        except TimeoutException as e:
            self.results["failed_tests"] += 1
            error_msg = f"Timeout waiting for element: {str(e)}"
            self.results["test_details"].append({
                "test_name": test_name,
                "status": "failed",
                "error": error_msg,
                "url": url
            })
            logger.error(f"❌ {test_name}: {error_msg}")

        except Exception as e:
            self.results["failed_tests"] += 1
            error_msg = str(e)
            self.results["test_details"].append({
                "test_name": test_name,
                "status": "failed",
                "error": error_msg,
                "url": url
            })
            logger.error(f"❌ {test_name}: {error_msg}")

    def _test_article_list_extraction(self) -> List[str]:
        """게시글 목록 추출 테스트 (supports both primary_selector and sections[] array)"""
        test_name = "article_list_extraction"
        self.results["total_tests"] += 1

        logger.info(f"[Test] {test_name}")

        try:
            extraction_config = self.strategy.get("extraction_strategy", {}).get("article_list", {})
            links = []
            fallback_used = False
            sections_used = False

            # Check for sections array first (multi-section extraction)
            sections = extraction_config.get("sections", [])

            if sections:
                # Multi-section extraction strategy
                logger.info(f"Using multi-section extraction ({len(sections)} sections)")
                sections_used = True
                section_results = {}

                for section in sections:
                    section_name = section.get("name", "unknown")
                    selector_config = section.get("selector", {})
                    selector_value = selector_config.get("value")
                    attribute = selector_config.get("attribute", "href")

                    if not selector_value:
                        logger.warning(f"Section '{section_name}': No selector defined, skipping")
                        continue

                    logger.info(f"Section '{section_name}': Testing selector: {selector_value}")

                    # Try primary selector for this section
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector_value)
                    section_fallback_used = False

                    # Try fallback selectors if primary fails
                    if len(elements) == 0:
                        fallback_selectors = section.get("fallback_selectors", [])
                        for fallback in fallback_selectors:
                            fallback_value = fallback.get("value")
                            logger.warning(f"Section '{section_name}': Primary failed, trying fallback: {fallback_value}")
                            elements = self.driver.find_elements(By.CSS_SELECTOR, fallback_value)
                            if len(elements) > 0:
                                section_fallback_used = True
                                fallback_used = True
                                break

                    # Extract links from this section
                    section_links = []
                    for elem in elements:
                        try:
                            link = elem.get_attribute(attribute)
                            if link and link.startswith("http"):
                                section_links.append(link)
                        except Exception:
                            continue

                    section_results[section_name] = {
                        "links_found": len(section_links),
                        "fallback_used": section_fallback_used
                    }
                    links.extend(section_links)

                    logger.info(f"Section '{section_name}': Found {len(section_links)} links (fallback: {section_fallback_used})")

                logger.info(f"Multi-section extraction complete: {len(links)} total links from {len(section_results)} sections")

            else:
                # Single selector extraction strategy (backward compatibility)
                primary_selector = extraction_config.get("primary_selector", {})
                selector_value = primary_selector.get("value")
                attribute = primary_selector.get("attribute", "href")

                if not selector_value:
                    raise ValueError("No primary selector or sections array defined for article list")

                logger.info(f"Using single selector: {selector_value}")

                # Primary 선택자 시도
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector_value)

                # Fallback 시도
                if len(elements) == 0:
                    fallback_selectors = extraction_config.get("fallback_selectors", [])
                    for fallback in fallback_selectors:
                        fallback_value = fallback.get("value")
                        logger.warning(f"Primary failed, trying fallback: {fallback_value}")
                        elements = self.driver.find_elements(By.CSS_SELECTOR, fallback_value)
                        if len(elements) > 0:
                            fallback_used = True
                            break

                if len(elements) == 0:
                    raise NoSuchElementException("No article links found (primary and fallbacks failed)")

                # 링크 추출
                for elem in elements:
                    try:
                        link = elem.get_attribute(attribute)
                        if link and link.startswith("http"):
                            links.append(link)
                    except Exception:
                        continue

            # Deduplicate links
            links = list(dict.fromkeys(links))  # Preserve order while removing duplicates

            if len(links) == 0:
                raise NoSuchElementException("No article links found after extraction")

            self.results["successful_tests"] += 1
            test_result = {
                "test_name": test_name,
                "status": "success",
                "links_found": len(links),
                "fallback_used": fallback_used,
                "sample_links": links[:3]
            }

            if sections_used:
                test_result["extraction_method"] = "multi_section"
                test_result["sections_processed"] = len(sections)
            else:
                test_result["extraction_method"] = "single_selector"

            self.results["test_details"].append(test_result)

            logger.info(f"✅ {test_name}: Found {len(links)} links (method: {'multi-section' if sections_used else 'single-selector'}, fallback: {fallback_used})")

            return links

        except Exception as e:
            self.results["failed_tests"] += 1
            error_msg = str(e)
            self.results["test_details"].append({
                "test_name": test_name,
                "status": "failed",
                "error": error_msg
            })
            logger.error(f"❌ {test_name}: {error_msg}")
            return []

    def _test_pagination(self, base_url: str):
        """페이지네이션 테스트"""
        test_name = "pagination_test"
        self.results["total_tests"] += 1

        logger.info(f"[Test] {test_name}")

        try:
            pagination_config = self.strategy.get("pagination_strategy", {})
            pagination_type = pagination_config.get("type")

            if pagination_type == "page_number":
                # URL 템플릿 기반 페이지네이션
                url_template = pagination_config.get("url_template")
                if not url_template:
                    raise ValueError("No URL template for page_number pagination")

                # 2페이지로 이동
                next_page_url = url_template.format(page=2)
                logger.info(f"Testing pagination: {next_page_url}")

                self.driver.get(next_page_url)
                time.sleep(2)

                # 게시글 목록이 로드되는지 확인
                extraction_config = self.strategy.get("extraction_strategy", {}).get("article_list", {})

                # Try to get selector (support both primary_selector and sections array)
                selector_value = None
                primary_selector = extraction_config.get("primary_selector", {})
                if primary_selector:
                    selector_value = primary_selector.get("value")
                else:
                    # Try sections array
                    sections = extraction_config.get("sections", [])
                    if sections and len(sections) > 0:
                        # Use first section's selector for pagination test
                        first_section = sections[0]
                        selector_config = first_section.get("selector", {})
                        selector_value = selector_config.get("value")

                if selector_value:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector_value)
                    if len(elements) > 0:
                        self.results["successful_tests"] += 1
                        self.results["test_details"].append({
                            "test_name": test_name,
                            "status": "success",
                            "pagination_type": pagination_type,
                            "next_page_url": next_page_url,
                            "articles_on_page_2": len(elements)
                        })
                        logger.info(f"✅ {test_name}: Page 2 loaded with {len(elements)} articles")
                    else:
                        raise NoSuchElementException("No articles found on page 2")

            else:
                # 다른 페이지네이션 타입은 skip
                logger.info(f"Pagination type '{pagination_type}' not tested in this version")
                self.results["successful_tests"] += 1
                self.results["test_details"].append({
                    "test_name": test_name,
                    "status": "skipped",
                    "reason": f"Pagination type '{pagination_type}' not implemented"
                })

        except Exception as e:
            self.results["failed_tests"] += 1
            error_msg = str(e)
            self.results["test_details"].append({
                "test_name": test_name,
                "status": "failed",
                "error": error_msg
            })
            logger.error(f"❌ {test_name}: {error_msg}")

    def _test_article_content_extraction(self, article_url: str):
        """게시글 내용 추출 테스트"""
        article_id = article_url.split('/')[-1]
        test_name = f"content_extraction_{article_id}"
        self.results["total_tests"] += 1

        logger.info(f"[Test] {test_name}: {article_url}")

        try:
            # 게시글 페이지 로드
            self.driver.get(article_url)
            time.sleep(2)  # 페이지 로딩 대기

            extraction_config = self.strategy.get("extraction_strategy", {}).get("article_content", {})
            elements_config = extraction_config.get("elements", {})

            # 제목 추출
            title_config = elements_config.get("title", {})
            title_selector = title_config.get("primary")
            title = None
            title_fallback_used = False

            if title_selector:
                try:
                    title_element = self.driver.find_element(By.CSS_SELECTOR, title_selector)
                    title = title_element.text
                except NoSuchElementException:
                    # Fallback 시도
                    for fallback in title_config.get("fallback", []):
                        try:
                            title_element = self.driver.find_element(By.CSS_SELECTOR, fallback)
                            title = title_element.text
                            title_fallback_used = True
                            break
                        except NoSuchElementException:
                            continue

            # 본문 추출
            content_config = elements_config.get("content", {})
            content_selector = content_config.get("primary")
            content = None
            content_fallback_used = False

            if content_selector:
                try:
                    content_element = self.driver.find_element(By.CSS_SELECTOR, content_selector)
                    content = content_element.text
                except NoSuchElementException:
                    # Fallback 시도
                    for fallback in content_config.get("fallback", []):
                        try:
                            content_element = self.driver.find_element(By.CSS_SELECTOR, fallback)
                            content = content_element.text
                            content_fallback_used = True
                            break
                        except NoSuchElementException:
                            continue

            # 검증: 제목 또는 본문이 있어야 성공
            if title or content:
                self.results["successful_tests"] += 1
                self.results["test_details"].append({
                    "test_name": test_name,
                    "status": "success",
                    "url": article_url,
                    "title": title[:50] if title else None,
                    "content_length": len(content) if content else 0,
                    "title_fallback_used": title_fallback_used,
                    "content_fallback_used": content_fallback_used
                })
                logger.info(f"✅ {test_name}: Success (title: {bool(title)}, content: {len(content) if content else 0} chars)")
            else:
                raise ValueError("Neither title nor content extracted")

        except Exception as e:
            self.results["failed_tests"] += 1
            error_msg = str(e)
            self.results["test_details"].append({
                "test_name": test_name,
                "status": "failed",
                "url": article_url,
                "error": error_msg
            })
            logger.error(f"❌ {test_name}: {error_msg}")

    def _calculate_success_rate(self):
        """성공률 계산"""
        if self.results["total_tests"] > 0:
            self.results["actual_success_rate"] = (
                self.results["successful_tests"] / self.results["total_tests"]
            )
        else:
            self.results["actual_success_rate"] = 0.0

        logger.info(
            f"Success Rate: {self.results['actual_success_rate']:.2%} "
            f"({self.results['successful_tests']}/{self.results['total_tests']})"
        )

    def _analyze_issues(self):
        """실패 패턴 분석 및 이슈 생성"""
        failed_tests = [
            test for test in self.results["test_details"]
            if test["status"] == "failed"
        ]

        if not failed_tests:
            logger.info("No issues found - all tests passed!")
            return

        # 실패 패턴 분석
        error_patterns = {}
        for test in failed_tests:
            error = test.get("error", "Unknown error")
            if error not in error_patterns:
                error_patterns[error] = []
            error_patterns[error].append(test["test_name"])

        # 이슈 생성
        for error, affected_tests in error_patterns.items():
            severity = self._determine_severity(len(affected_tests), self.results["total_tests"])

            issue = {
                "severity": severity,
                "issue": f"Test failures: {error}",
                "affected_tests": affected_tests,
                "frequency": len(affected_tests),
                "percentage": len(affected_tests) / self.results["total_tests"],
                "recommendation": self._generate_recommendation(error)
            }

            self.results["issues_found"].append(issue)
            logger.warning(
                f"Issue ({severity}): {error} "
                f"[{len(affected_tests)}/{self.results['total_tests']} tests]"
            )

    @staticmethod
    def _determine_severity(failed_count: int, total_count: int) -> str:
        """실패 비율에 따라 심각도 결정"""
        ratio = failed_count / total_count if total_count > 0 else 0

        if ratio >= 0.5:
            return "critical"
        elif ratio >= 0.3:
            return "high"
        elif ratio >= 0.1:
            return "medium"
        else:
            return "low"

    @staticmethod
    def _generate_recommendation(error: str) -> str:
        """에러 유형에 따른 권장사항 생성"""
        if "Timeout" in error or "timeout" in error:
            return "Increase timeout values in wait_strategy"
        elif "NoSuchElementException" in error or "not found" in error:
            return "Update selector or add better fallback selectors"
        elif "not clickable" in error:
            return "Add explicit wait for element to be clickable"
        else:
            return "Review error message and adjust strategy accordingly"
