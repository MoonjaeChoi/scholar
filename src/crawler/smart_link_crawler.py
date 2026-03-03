# Generated: 2025-10-12 15:45:00 KST
"""
Smart Link Crawler - 페이지 내 링크를 따라가는 지능형 크롤러
Systematically crawls websites by following internal links
"""

import hashlib
import json
import os
import re
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# 환경 변수로 Oracle 라이브러리 선택
# 로컬 개발: USE_PYTHON_ORACLEDB=true (python-oracledb Thin Mode)
# 서버 프로덕션: USE_PYTHON_ORACLEDB=false 또는 미설정 (cx_Oracle)
USE_PYTHON_ORACLEDB = os.getenv('USE_PYTHON_ORACLEDB', 'false').lower() == 'true'

if USE_PYTHON_ORACLEDB:
    import oracledb as oracle_lib
    logger.info("✅ SmartLinkCrawler: Using python-oracledb (Thin Mode)")
else:
    import cx_Oracle as oracle_lib
    logger.info("✅ SmartLinkCrawler: Using cx_Oracle")


class SmartLinkCrawler:
    """링크를 따라가며 체계적으로 크롤링하는 스마트 크롤러"""

    def __init__(
        self,
        db_config: Dict[str, str],
        max_depth: int = 3,
        max_links_per_page: int = 20,
        same_domain_only: bool = True,
        cache_duration_hours: int = 168  # 7 days
    ):
        self.db_config = db_config
        self.max_depth = max_depth
        self.max_links_per_page = max_links_per_page
        self.same_domain_only = same_domain_only
        self.cache_duration_hours = cache_duration_hours

        # URL 중복 방지를 위한 메모리 캐시
        self.visited_urls: Set[str] = set()
        self.url_hashes: Set[str] = set()

        # 링크 따라가기 패턴
        self.follow_patterns = [
            r'/article/', r'/post/', r'/board/', r'/view/',
            r'/detail/', r'/read/', r'/show/', r'/content/',
            r'/news/', r'/story/', r'/blog/'
        ]

        self.skip_patterns = [
            r'/login', r'/signup', r'/register', r'/mypage',
            r'/cart', r'/checkout', r'/admin', r'/api/',
            r'/download', r'/pdf', r'/image', r'/video'
        ]

        logger.info(f"SmartLinkCrawler initialized: max_depth={max_depth}, max_links={max_links_per_page}")

    def _url_hash(self, url: str) -> str:
        """URL을 해시값으로 변환"""
        return hashlib.md5(url.encode()).hexdigest()

    def _is_valid_url(self, url: str, base_domain: str) -> bool:
        """URL이 크롤링 가능한지 검증"""
        try:
            parsed = urlparse(url)

            # 스킵 패턴 체크
            for pattern in self.skip_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return False

            # 같은 도메인만 허용하는 경우
            if self.same_domain_only:
                if parsed.netloc != base_domain and parsed.netloc != f"www.{base_domain}" and base_domain not in parsed.netloc:
                    return False

            # 팔로우 패턴 체크 (하나라도 매치되면 OK)
            for pattern in self.follow_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return True

            # 패턴 매치 없으면 기본 페이지만 허용
            if parsed.path in ['/', ''] or parsed.path.endswith('.html'):
                return True

            return False

        except Exception as e:
            logger.warning(f"URL validation error: {url} - {e}")
            return False

    def _check_url_crawled_in_db(self, url: str) -> bool:
        """DB에서 URL이 최근에 크롤링되었는지 확인"""
        try:
            conn = oracle_lib.connect(
                user=self.db_config['username'],
                password=self.db_config['password'],
                dsn=f"{self.db_config['host']}:{self.db_config['port']}/{self.db_config['service_name']}"
            )
            cursor = conn.cursor()

            # 캐시 기간 내에 크롤링된 URL 확인
            cache_cutoff = datetime.now() - timedelta(hours=self.cache_duration_hours)

            cursor.execute("""
                SELECT COUNT(*) FROM WEB_CAPTURE_DATA
                WHERE url = :url
                AND crawl_timestamp >= :cache_cutoff
            """, {
                'url': url,
                'cache_cutoff': cache_cutoff
            })

            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()

            return count > 0

        except Exception as e:
            logger.error(f"DB check error for URL {url}: {e}")
            return False

    def _extract_links(self, driver: webdriver.Chrome, current_url: str, base_domain: str) -> List[str]:
        """페이지에서 링크 추출"""
        links = []

        try:
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # 모든 링크 추출
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']

                # 상대 URL을 절대 URL로 변환
                absolute_url = urljoin(current_url, href)

                # URL 정규화 (fragment 제거)
                parsed = urlparse(absolute_url)
                normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    normalized_url += f"?{parsed.query}"

                # 유효성 검증
                if self._is_valid_url(normalized_url, base_domain):
                    links.append(normalized_url)

            # 중복 제거 및 제한
            unique_links = list(set(links))[:self.max_links_per_page]

            logger.debug(f"Extracted {len(unique_links)} valid links from {current_url}")
            return unique_links

        except Exception as e:
            logger.error(f"Link extraction error from {current_url}: {e}")
            return []

    def crawl_with_links(
        self,
        start_url: str,
        crawler_instance,  # WebCrawler 인스턴스
        data_root_path: Path
    ) -> Dict[str, any]:
        """링크를 따라가며 크롤링 수행"""

        # BFS를 위한 큐: (url, depth)
        queue = deque([(start_url, 0)])

        # 통계
        stats = {
            'total_urls': 0,
            'crawled_urls': 0,
            'skipped_urls': 0,
            'failed_urls': 0,
            'new_data': 0
        }

        base_domain = urlparse(start_url).netloc

        logger.info(f"Starting smart crawl from {start_url} (max_depth={self.max_depth})")

        while queue:
            current_url, depth = queue.popleft()

            # 깊이 제한 체크
            if depth > self.max_depth:
                continue

            # URL 해시 확인 (메모리 캐시)
            url_hash = self._url_hash(current_url)
            if url_hash in self.url_hashes:
                stats['skipped_urls'] += 1
                continue

            # DB 캐시 확인
            if self._check_url_crawled_in_db(current_url):
                logger.debug(f"URL already crawled recently: {current_url}")
                self.url_hashes.add(url_hash)
                stats['skipped_urls'] += 1
                continue

            # 방문 표시
            self.url_hashes.add(url_hash)
            self.visited_urls.add(current_url)
            stats['total_urls'] += 1

            logger.info(f"Crawling [{depth}/{self.max_depth}]: {current_url}")

            try:
                # 크롤링 수행 (기존 WebCrawler 사용)
                result = crawler_instance.crawl_url(current_url)

                if result.get('success'):
                    stats['crawled_urls'] += 1

                    if result.get('screenshot_saved'):
                        stats['new_data'] += 1

                    # 링크 추출 (다음 깊이로)
                    if depth < self.max_depth and crawler_instance.driver:
                        links = self._extract_links(
                            crawler_instance.driver,
                            current_url,
                            base_domain
                        )

                        # 큐에 추가
                        for link in links:
                            if self._url_hash(link) not in self.url_hashes:
                                queue.append((link, depth + 1))
                                logger.debug(f"Added to queue [depth {depth + 1}]: {link}")

                else:
                    stats['failed_urls'] += 1

                # Rate limiting
                time.sleep(2)

            except Exception as e:
                logger.error(f"Crawl error for {current_url}: {e}")
                stats['failed_urls'] += 1

        # 최종 통계
        logger.info(f"Smart crawl completed: {stats}")
        return stats

    def crawl_site_batch(
        self,
        site_config: Dict[str, any],
        crawler_instance,
        data_root_path: Path
    ) -> Dict[str, any]:
        """사이트 배치 크롤링 (여러 start URLs)"""

        site_name = site_config.get('name', 'Unknown')
        start_urls = site_config.get('start_urls', [])

        logger.info(f"Batch crawling site: {site_name} ({len(start_urls)} start URLs)")

        total_stats = {
            'site_name': site_name,
            'total_urls': 0,
            'crawled_urls': 0,
            'skipped_urls': 0,
            'failed_urls': 0,
            'new_data': 0,
            'start_urls_count': len(start_urls)
        }

        for start_url in start_urls:
            logger.info(f"Processing start URL: {start_url}")

            stats = self.crawl_with_links(
                start_url,
                crawler_instance,
                data_root_path
            )

            # 통계 누적
            total_stats['total_urls'] += stats['total_urls']
            total_stats['crawled_urls'] += stats['crawled_urls']
            total_stats['skipped_urls'] += stats['skipped_urls']
            total_stats['failed_urls'] += stats['failed_urls']
            total_stats['new_data'] += stats['new_data']

        logger.info(f"Site batch crawl completed for {site_name}: {total_stats}")
        return total_stats


def load_expanded_sites_config(config_path: Path) -> Dict:
    """확장된 사이트 설정 로드"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"Loaded expanded sites config from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}


def get_all_sites_flat(config: Dict) -> List[Dict]:
    """설정에서 모든 사이트를 평탄화하여 리스트로 반환"""
    all_sites = []

    # 각 카테고리에서 사이트 추출
    for category_key, category_data in config.items():
        if category_key in ['description', 'generated', 'version', 'crawling_strategy', 'existing_sites']:
            continue

        if isinstance(category_data, dict) and 'sites' in category_data:
            all_sites.extend(category_data['sites'])

    logger.info(f"Total sites extracted: {len(all_sites)}")
    return all_sites
