# Generated: 2025-10-14 11:20:00 KST
"""
Path Diversity Crawler - 다양한 경로 탐색을 위한 고급 크롤러

Features:
- Path Fingerprinting: URL 구조 패턴 추출로 중복 방지
- Priority-Based Selection: 덜 방문한 경로 우선 선택
- Diversity-First: 구조적으로 다양한 링크 우선 탐색
"""

import hashlib
import heapq
import random
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple
from urllib.parse import urlparse

from loguru import logger

from .smart_link_crawler import SmartLinkCrawler


class PathDiversityCrawler(SmartLinkCrawler):
    """다양한 경로 탐색을 위한 고급 크롤러

    SmartLinkCrawler를 상속받아 Path Diversity 알고리즘 추가:
    - URL 패턴 정규화 (Path Fingerprinting)
    - 우선순위 기반 링크 선택
    - 다양성 우선 크롤링
    """

    def __init__(
        self,
        db_config: Dict[str, str],
        max_depth: int = 3,
        max_links_per_page: int = 20,
        same_domain_only: bool = True,
        cache_duration_hours: int = 168,
        use_priority_queue: bool = True
    ):
        """
        PathDiversityCrawler 초기화

        Args:
            db_config: Oracle DB 연결 설정
            max_depth: 최대 크롤링 깊이
            max_links_per_page: 페이지당 최대 링크 수
            same_domain_only: 같은 도메인만 크롤링 여부
            cache_duration_hours: 캐시 유지 시간
            use_priority_queue: 우선순위 큐 사용 여부
        """
        super().__init__(
            db_config=db_config,
            max_depth=max_depth,
            max_links_per_page=max_links_per_page,
            same_domain_only=same_domain_only,
            cache_duration_hours=cache_duration_hours
        )

        # Path 다양성 추적
        self.path_history: Dict[str, int] = {}  # path_fingerprint → 방문 횟수
        self.path_fingerprints: Set[str] = set()  # 전체 발견된 패턴

        # 우선순위 큐 사용 여부
        self.use_priority_queue = use_priority_queue

        logger.info(
            f"PathDiversityCrawler initialized: "
            f"priority_queue={use_priority_queue}, "
            f"max_depth={max_depth}, "
            f"max_links={max_links_per_page}"
        )

    def create_path_fingerprint(self, url: str) -> str:
        """
        URL 구조 패턴 추출 (Path Fingerprinting)

        숫자, 날짜, UUID 등을 정규화하여 구조적 패턴 추출

        Examples:
            /article/123/view → /article/*/view
            /news/2025/10/14/story → /news/*/*/story
            /post/550e8400-e29b-41d4-a716-446655440000 → /post/UUID

        Args:
            url: 대상 URL

        Returns:
            정규화된 path 패턴
        """
        try:
            path = urlparse(url).path

            # 1. UUID 패턴 치환 (먼저 처리해야 숫자 패턴에 영향받지 않음)
            normalized = re.sub(
                r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
                '/UUID',
                path,
                flags=re.IGNORECASE
            )

            # 2. 날짜 패턴 치환 (YYYY/MM/DD → /*/*/)
            normalized = re.sub(r'/\d{4}/\d{2}/\d{2}/', '/*/*/', normalized)

            # 3. 해시 패턴 (긴 hex 문자열 → HASH)
            normalized = re.sub(r'/[0-9a-f]{32,}/?', '/HASH/', normalized, flags=re.IGNORECASE)

            # 4. 숫자 패턴 치환 (/123/ → /*/, /123 at end → /*)
            normalized = re.sub(r'/\d+/', '/*/', normalized)
            normalized = re.sub(r'/\d+$', '/*', normalized)

            # 5. 연속된 숫자 패턴 (article123 → article*)
            normalized = re.sub(r'([a-z]+)\d+', r'\1*', normalized, flags=re.IGNORECASE)

            return normalized

        except Exception as e:
            logger.warning(f"Path fingerprint creation error for {url}: {e}")
            return url

    def calculate_link_priority(self, url: str, depth: int) -> float:
        """
        링크 우선순위 계산

        우선순위 = 깊이 가중치 - 방문횟수 페널티 + 랜덤 보너스

        Args:
            url: 대상 URL
            depth: 현재 깊이

        Returns:
            우선순위 점수 (높을수록 우선)
        """
        fingerprint = self.create_path_fingerprint(url)
        visit_count = self.path_history.get(fingerprint, 0)

        # 우선순위 공식
        # = 깊이*10 (깊이 우선) - 방문횟수*5 (덜 방문한 것 우선) + random(0-5) (랜덤성)
        priority = (depth * 10.0) - (visit_count * 5.0) + (random.random() * 5.0)

        return priority

    def select_diverse_links(self, links: List[str], max_count: int = 20) -> List[str]:
        """
        구조적으로 다양한 링크를 우선 선택

        같은 패턴의 링크가 한꺼번에 선택되지 않도록 Round-robin 방식 사용

        Args:
            links: 후보 링크 리스트
            max_count: 최대 선택 개수

        Returns:
            선택된 링크 리스트
        """
        if not links:
            return []

        # 1. Path 패턴별로 그룹화
        path_groups = defaultdict(list)
        for link in links:
            pattern = self.create_path_fingerprint(link)
            path_groups[pattern].append(link)

        # 2. 각 그룹에서 골고루 선택 (Round-robin)
        selected = []
        while len(selected) < max_count and path_groups:
            for pattern in list(path_groups.keys()):
                group = path_groups[pattern]
                if group:
                    # 각 그룹에서 하나씩 선택
                    selected.append(group.pop(0))
                    if len(selected) >= max_count:
                        break
                else:
                    # 그룹이 비었으면 제거
                    del path_groups[pattern]

        logger.debug(f"Selected {len(selected)} diverse links from {len(links)} candidates")
        return selected

    def crawl_with_diversity(
        self,
        start_url: str,
        crawler_instance,  # WebCrawler 인스턴스
        data_root_path: Path
    ) -> Dict[str, any]:
        """
        다양성 우선 크롤링 수행

        우선순위 큐를 사용하여 덜 방문한 경로를 우선 탐색

        Args:
            start_url: 시작 URL
            crawler_instance: WebCrawler 인스턴스
            data_root_path: 데이터 저장 경로

        Returns:
            크롤링 통계 딕셔너리
        """
        # 우선순위 큐: (priority, url, depth)
        # heapq는 최소 힙이므로 priority에 음수를 사용 (높은 우선순위 = 낮은 숫자)
        priority_queue = []

        # 초기 URL 추가 (높은 우선순위: -100)
        heapq.heappush(priority_queue, (-100.0, start_url, 0))

        # 통계
        stats = {
            'total_urls': 0,
            'crawled_urls': 0,
            'skipped_urls': 0,
            'failed_urls': 0,
            'new_data': 0,
            'path_diversity': 0.0,
            'unique_patterns': 0,
            'total_patterns_visits': 0
        }

        base_domain = urlparse(start_url).netloc

        logger.info(
            f"Starting diversity-first crawl from {start_url} "
            f"(max_depth={self.max_depth})"
        )

        start_time = time.time()

        while priority_queue:
            # 우선순위가 높은 URL 추출
            priority, current_url, depth = heapq.heappop(priority_queue)

            # 깊이 제한
            if depth > self.max_depth:
                continue

            # 중복 체크 (메모리 캐시)
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

            # Path 패턴 추적
            fingerprint = self.create_path_fingerprint(current_url)
            self.path_history[fingerprint] = self.path_history.get(fingerprint, 0) + 1
            self.path_fingerprints.add(fingerprint)

            stats['total_urls'] += 1

            logger.info(
                f"[{depth}/{self.max_depth}] "
                f"Priority={-priority:.2f} "
                f"Pattern={fingerprint[:50]} "
                f"URL={current_url}"
            )

            try:
                # 크롤링 수행
                result = crawler_instance.crawl_url(current_url)

                if result.get('success'):
                    stats['crawled_urls'] += 1

                    if result.get('screenshot_saved'):
                        stats['new_data'] += 1

                    # 링크 추출 및 다양성 선택
                    if depth < self.max_depth and crawler_instance.driver:
                        links = self._extract_links(
                            crawler_instance.driver,
                            current_url,
                            base_domain
                        )

                        # 다양성 우선 링크 선택
                        diverse_links = self.select_diverse_links(
                            links,
                            self.max_links_per_page
                        )

                        # 우선순위 계산 후 큐에 추가
                        for link in diverse_links:
                            if self._url_hash(link) not in self.url_hashes:
                                link_priority = self.calculate_link_priority(
                                    link,
                                    depth + 1
                                )
                                heapq.heappush(
                                    priority_queue,
                                    (-link_priority, link, depth + 1)
                                )
                                logger.debug(
                                    f"Added to queue [depth {depth + 1}] "
                                    f"priority={link_priority:.2f}: {link[:80]}"
                                )

                else:
                    stats['failed_urls'] += 1
                    logger.warning(f"Crawl failed: {current_url}")

                # Rate limiting
                time.sleep(2)

            except Exception as e:
                logger.error(f"Crawl error for {current_url}: {e}")
                stats['failed_urls'] += 1

        # Path 다양성 계산
        unique_patterns = len(self.path_fingerprints)
        total_visits = sum(self.path_history.values())

        stats['unique_patterns'] = unique_patterns
        stats['total_patterns_visits'] = total_visits
        stats['path_diversity'] = unique_patterns / max(total_visits, 1)

        elapsed_time = time.time() - start_time

        logger.info(
            f"Diversity crawl completed in {elapsed_time:.1f}s: "
            f"crawled={stats['crawled_urls']}, "
            f"new={stats['new_data']}, "
            f"diversity={stats['path_diversity']:.2%} "
            f"({unique_patterns} unique patterns / {total_visits} visits)"
        )

        return stats

    def get_path_diversity_report(self) -> Dict[str, any]:
        """
        Path 다양성 리포트 생성

        Returns:
            다양성 통계 딕셔너리
        """
        unique_patterns = len(self.path_fingerprints)
        total_visits = sum(self.path_history.values())
        diversity_score = unique_patterns / max(total_visits, 1)

        # 가장 많이 방문한 패턴 Top 10
        top_patterns = sorted(
            self.path_history.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        report = {
            'unique_patterns': unique_patterns,
            'total_visits': total_visits,
            'diversity_score': diversity_score,
            'top_patterns': [
                {'pattern': pattern, 'visits': count}
                for pattern, count in top_patterns
            ],
            'average_visits_per_pattern': total_visits / max(unique_patterns, 1)
        }

        return report


def test_path_diversity_crawler():
    """PathDiversityCrawler 간단한 테스트"""

    # Mock DB config
    db_config = {
        'host': 'localhost',
        'port': '1521',
        'service_name': 'XEPDB1',
        'username': 'ocr_admin',
        'password': 'admin_password'
    }

    # Crawler 생성
    crawler = PathDiversityCrawler(
        db_config=db_config,
        max_depth=2,
        max_links_per_page=10
    )

    # Path fingerprinting 테스트
    print("\n=== Path Fingerprinting Test ===")
    test_urls = [
        "/article/123/view",
        "/article/456/view",
        "/news/2025/10/14/story",
        "/post/550e8400-e29b-41d4-a716-446655440000",
        "/board/notice/12345"
    ]

    for url in test_urls:
        fingerprint = crawler.create_path_fingerprint(url)
        print(f"{url:50s} → {fingerprint}")

    # Diversity selection 테스트
    print("\n=== Diversity Selection Test ===")
    test_links = [
        "/article/1/view",
        "/article/2/view",
        "/article/3/view",
        "/board/100/read",
        "/board/101/read",
        "/news/20251014/story",
        "/news/20251013/story",
        "/blog/post-title-1",
        "/blog/post-title-2"
    ]

    selected = crawler.select_diverse_links(test_links, max_count=5)
    print(f"Selected {len(selected)} links:")
    for link in selected:
        print(f"  - {link}")

    # Priority 테스트
    print("\n=== Priority Calculation Test ===")
    for url in test_links[:3]:
        priority = crawler.calculate_link_priority(url, depth=1)
        print(f"{url:30s} priority={priority:.2f}")

    # 방문 후 우선순위 변화
    crawler.path_history["/article/*/view"] = 5
    for url in test_links[:3]:
        priority = crawler.calculate_link_priority(url, depth=1)
        print(f"{url:30s} priority={priority:.2f} (after visits)")

    print("\n✅ Test completed!")


if __name__ == "__main__":
    test_path_diversity_crawler()
