# Generated: 2025-10-04 15:30:00 KST
"""
한글 블로그 사이트 페이지 탐색 및 URL 수집기
각 블로그 플랫폼의 구조를 분석하여 최대한 많은 페이지를 자동으로 탐색
"""

import time
import re
from typing import List, Set, Dict, Optional
from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class KoreanBlogExplorer:
    """한글 블로그 사이트 탐색 및 URL 수집기"""

    def __init__(self, max_pages_per_site: int = 100):
        """
        Args:
            max_pages_per_site: 사이트당 최대 수집 페이지 수
        """
        self.max_pages_per_site = max_pages_per_site
        self.visited_urls: Set[str] = set()
        self.discovered_urls: Set[str] = set()

    def explore_naver_blog(self, base_url: str, max_posts: int = 50) -> List[str]:
        """
        네이버 블로그 탐색
        - 블로그 메인 페이지에서 게시글 목록 수집
        - 페이지네이션을 따라 이동하며 URL 수집
        """
        logger.info(f'Exploring Naver Blog: {base_url}')
        urls = []

        try:
            driver = self._create_driver()
            driver.get(base_url)
            time.sleep(2)

            # 네이버 블로그 iframe 처리
            try:
                iframe = driver.find_element(By.ID, 'mainFrame')
                driver.switch_to.frame(iframe)
            except NoSuchElementException:
                logger.warning('No iframe found, continuing with main page')

            # 게시글 링크 수집
            page = 1
            while len(urls) < max_posts and page <= 10:
                logger.info(f'Collecting Naver blog page {page}')

                # 게시글 링크 찾기
                post_links = driver.find_elements(By.CSS_SELECTOR, 'a.pcol1')
                for link in post_links:
                    try:
                        url = link.get_attribute('href')
                        if url and url not in urls and 'blog.naver.com' in url:
                            urls.append(url)
                            if len(urls) >= max_posts:
                                break
                    except Exception as e:
                        logger.debug(f'Error extracting link: {e}')
                        continue

                # 다음 페이지로 이동
                try:
                    next_button = driver.find_element(By.CSS_SELECTOR, 'a.btn_next')
                    if next_button.get_attribute('aria-disabled') == 'true':
                        break
                    next_button.click()
                    time.sleep(2)
                    page += 1
                except NoSuchElementException:
                    logger.info('No more pages available')
                    break

            driver.quit()
            logger.info(f'Collected {len(urls)} URLs from Naver blog')
            return urls[:max_posts]

        except Exception as e:
            logger.error(f'Error exploring Naver blog {base_url}: {e}')
            if 'driver' in locals():
                driver.quit()
            return []

    def explore_tistory(self, base_url: str, max_posts: int = 50) -> List[str]:
        """
        티스토리 블로그 탐색
        - 글 목록 페이지에서 게시글 수집
        - /category, /notice, /guestbook 등 다양한 경로 탐색
        """
        logger.info(f'Exploring Tistory: {base_url}')
        urls = []

        try:
            driver = self._create_driver()
            driver.get(base_url)
            time.sleep(2)

            # 티스토리 게시글 링크 패턴
            post_selectors = [
                'article a',
                '.article-content a',
                '.entry-title a',
                'h2 a',
                '.post-item a'
            ]

            page = 1
            while len(urls) < max_posts and page <= 10:
                logger.info(f'Collecting Tistory page {page}')

                # 여러 선택자로 링크 찾기
                for selector in post_selectors:
                    try:
                        links = driver.find_elements(By.CSS_SELECTOR, selector)
                        for link in links:
                            url = link.get_attribute('href')
                            if url and url not in urls and self._is_tistory_post(url):
                                urls.append(url)
                                if len(urls) >= max_posts:
                                    break
                    except Exception as e:
                        logger.debug(f'Selector {selector} failed: {e}')
                        continue

                    if len(urls) >= max_posts:
                        break

                # 다음 페이지로 이동
                try:
                    # 티스토리 페이지네이션 버튼 찾기
                    next_page_url = f'{base_url}/page/{page + 1}'
                    driver.get(next_page_url)
                    time.sleep(2)

                    # 404 또는 빈 페이지 체크
                    if '404' in driver.title or 'not found' in driver.title.lower():
                        break

                    page += 1
                except Exception as e:
                    logger.info(f'No more pages: {e}')
                    break

            driver.quit()
            logger.info(f'Collected {len(urls)} URLs from Tistory')
            return urls[:max_posts]

        except Exception as e:
            logger.error(f'Error exploring Tistory {base_url}: {e}')
            if 'driver' in locals():
                driver.quit()
            return []

    def explore_brunch(self, base_url: str, max_posts: int = 50) -> List[str]:
        """
        브런치 탐색
        - 작가 페이지에서 글 목록 수집
        - 무한 스크롤 처리
        """
        logger.info(f'Exploring Brunch: {base_url}')
        urls = []

        try:
            driver = self._create_driver()
            driver.get(base_url)
            time.sleep(3)

            # 무한 스크롤 처리
            last_height = driver.execute_script('return document.body.scrollHeight')
            scroll_attempts = 0
            max_scrolls = 20

            while len(urls) < max_posts and scroll_attempts < max_scrolls:
                # 페이지 끝까지 스크롤
                driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
                time.sleep(2)

                # 글 링크 수집
                article_links = driver.find_elements(By.CSS_SELECTOR, 'a.link_post')
                for link in article_links:
                    try:
                        url = link.get_attribute('href')
                        if url and url not in urls and 'brunch.co.kr' in url and '/@@' in url:
                            urls.append(url)
                            if len(urls) >= max_posts:
                                break
                    except Exception as e:
                        logger.debug(f'Error extracting Brunch link: {e}')
                        continue

                # 스크롤 높이 변화 체크
                new_height = driver.execute_script('return document.body.scrollHeight')
                if new_height == last_height:
                    logger.info('No more content to load')
                    break

                last_height = new_height
                scroll_attempts += 1

            driver.quit()
            logger.info(f'Collected {len(urls)} URLs from Brunch')
            return urls[:max_posts]

        except Exception as e:
            logger.error(f'Error exploring Brunch {base_url}: {e}')
            if 'driver' in locals():
                driver.quit()
            return []

    def explore_velog(self, base_url: str, max_posts: int = 50) -> List[str]:
        """
        벨로그 탐색
        - trending, recent, tags 페이지에서 게시글 수집
        - 무한 스크롤 처리
        """
        logger.info(f'Exploring Velog: {base_url}')
        urls = []

        try:
            driver = self._create_driver()
            driver.get(base_url)
            time.sleep(3)

            # 무한 스크롤 처리
            last_height = driver.execute_script('return document.body.scrollHeight')
            scroll_attempts = 0
            max_scrolls = 20

            while len(urls) < max_posts and scroll_attempts < max_scrolls:
                # 페이지 끝까지 스크롤
                driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
                time.sleep(2)

                # 글 링크 수집 (여러 선택자 시도)
                selectors = [
                    'a[href*="/@"]',
                    'a.post-item',
                    'h2 a',
                    'article a'
                ]

                for selector in selectors:
                    try:
                        links = driver.find_elements(By.CSS_SELECTOR, selector)
                        for link in links:
                            url = link.get_attribute('href')
                            if url and url not in urls and 'velog.io/@' in url:
                                urls.append(url)
                                if len(urls) >= max_posts:
                                    break
                    except Exception as e:
                        logger.debug(f'Selector {selector} failed: {e}')
                        continue

                    if len(urls) >= max_posts:
                        break

                # 스크롤 높이 변화 체크
                new_height = driver.execute_script('return document.body.scrollHeight')
                if new_height == last_height:
                    logger.info('No more content to load')
                    break

                last_height = new_height
                scroll_attempts += 1

            driver.quit()
            logger.info(f'Collected {len(urls)} URLs from Velog')
            return urls[:max_posts]

        except Exception as e:
            logger.error(f'Error exploring Velog {base_url}: {e}')
            if 'driver' in locals():
                driver.quit()
            return []

    def explore_medium_korean(self, base_url: str, max_posts: int = 50) -> List[str]:
        """
        미디엄 한국어 탐색
        - 태그 페이지에서 게시글 수집
        - 무한 스크롤 처리
        """
        logger.info(f'Exploring Medium Korean: {base_url}')
        urls = []

        try:
            driver = self._create_driver()
            driver.get(base_url)
            time.sleep(3)

            # 무한 스크롤 처리
            last_height = driver.execute_script('return document.body.scrollHeight')
            scroll_attempts = 0
            max_scrolls = 20

            while len(urls) < max_posts and scroll_attempts < max_scrolls:
                # 페이지 끝까지 스크롤
                driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
                time.sleep(2)

                # 글 링크 수집
                article_links = driver.find_elements(By.CSS_SELECTOR, 'article a, h2 a, h3 a')
                for link in article_links:
                    try:
                        url = link.get_attribute('href')
                        if url and url not in urls and 'medium.com' in url and not url.endswith('/tag/'):
                            # Medium의 트래킹 파라미터 제거
                            clean_url = url.split('?')[0]
                            if clean_url not in urls:
                                urls.append(clean_url)
                                if len(urls) >= max_posts:
                                    break
                    except Exception as e:
                        logger.debug(f'Error extracting Medium link: {e}')
                        continue

                # 스크롤 높이 변화 체크
                new_height = driver.execute_script('return document.body.scrollHeight')
                if new_height == last_height:
                    logger.info('No more content to load')
                    break

                last_height = new_height
                scroll_attempts += 1

            driver.quit()
            logger.info(f'Collected {len(urls)} URLs from Medium')
            return urls[:max_posts]

        except Exception as e:
            logger.error(f'Error exploring Medium {base_url}: {e}')
            if 'driver' in locals():
                driver.quit()
            return []

    def explore_all_platforms(self, config: Dict) -> List[str]:
        """
        모든 플랫폼 탐색하여 URL 수집

        Args:
            config: korean_blog_sites.json의 설정

        Returns:
            수집된 모든 URL 리스트
        """
        all_urls = []

        # 네이버 블로그
        if config.get('naver_blog', {}).get('enabled', False):
            max_posts = config['naver_blog'].get('max_posts_per_blog', 20)
            for base_url in config['naver_blog'].get('base_urls', []):
                urls = self.explore_naver_blog(base_url, max_posts)
                all_urls.extend(urls)
                logger.info(f'Naver Blog: collected {len(urls)} URLs from {base_url}')

        # 티스토리
        if config.get('tistory', {}).get('enabled', False):
            max_posts = config['tistory'].get('max_posts_per_blog', 15)
            for base_url in config['tistory'].get('base_urls', []):
                urls = self.explore_tistory(base_url, max_posts)
                all_urls.extend(urls)
                logger.info(f'Tistory: collected {len(urls)} URLs from {base_url}')

        # 브런치
        if config.get('brunch', {}).get('enabled', False):
            max_posts = config['brunch'].get('max_posts_per_author', 10)
            for base_url in config['brunch'].get('base_urls', []):
                urls = self.explore_brunch(base_url, max_posts)
                all_urls.extend(urls)
                logger.info(f'Brunch: collected {len(urls)} URLs from {base_url}')

        # 벨로그
        if config.get('velog', {}).get('enabled', False):
            max_posts = config['velog'].get('max_posts_per_tag', 10)
            for base_url in config['velog'].get('base_urls', []):
                urls = self.explore_velog(base_url, max_posts)
                all_urls.extend(urls)
                logger.info(f'Velog: collected {len(urls)} URLs from {base_url}')

        # 미디엄 한국어
        if config.get('medium_korean', {}).get('enabled', False):
            max_posts = config['medium_korean'].get('max_posts_per_tag', 10)
            for base_url in config['medium_korean'].get('base_urls', []):
                urls = self.explore_medium_korean(base_url, max_posts)
                all_urls.extend(urls)
                logger.info(f'Medium: collected {len(urls)} URLs from {base_url}')

        # 중복 제거
        unique_urls = list(set(all_urls))
        logger.info(f'Total unique URLs collected: {len(unique_urls)}')

        return unique_urls

    def _create_driver(self) -> webdriver.Chrome:
        """Chrome 드라이버 생성"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        return webdriver.Chrome(options=options)

    def _is_tistory_post(self, url: str) -> bool:
        """티스토리 게시글 URL인지 확인"""
        if not url or 'tistory.com' not in url:
            return False

        # 제외할 URL 패턴
        exclude_patterns = [
            '/category/',
            '/tag/',
            '/guestbook',
            '/notice',
            '/location',
            '/media',
            '/attachment'
        ]

        for pattern in exclude_patterns:
            if pattern in url:
                return False

        # 숫자가 포함된 URL은 대부분 게시글
        if re.search(r'/\d+', url):
            return True

        return True
