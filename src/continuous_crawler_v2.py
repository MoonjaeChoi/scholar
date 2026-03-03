# Generated: 2025-10-12 15:50:00 KST
"""
Continuous Crawler V2 - 100+ 한글 사이트 스마트 링크 크롤링
Intelligent crawling with link following across 100+ Korean websites
"""

import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from loguru import logger
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, '/opt/scholar')

from src.crawler.path_diversity_crawler import PathDiversityCrawler
from src.crawler.smart_link_crawler import get_all_sites_flat, load_expanded_sites_config
from src.crawler.web_crawler import WebCrawler


# Prometheus 메트릭
crawl_counter = Counter(
    'scholar_crawl_v2_total',
    'Total number of crawl attempts (V2)',
    ['status', 'site_category']
)
crawl_duration = Histogram(
    'scholar_crawl_v2_duration_seconds',
    'Crawl duration in seconds (V2)',
    ['site_category']
)
active_sites = Gauge(
    'scholar_active_sites',
    'Number of active sites being crawled'
)
new_data_collected = Counter(
    'scholar_new_data_total',
    'Total new data collected',
    ['site_category']
)
path_diversity_score = Gauge(
    'scholar_path_diversity_score',
    'Path diversity score (unique patterns / total visits)',
    ['site_category']
)
unique_path_patterns = Gauge(
    'scholar_unique_path_patterns',
    'Number of unique path patterns discovered',
    ['site_category']
)


class ContinuousCrawlerV2:
    """100+ 사이트 스마트 링크 크롤링 시스템"""

    def __init__(
        self,
        config_path: str = None,
        interval_seconds: int = 300,  # 5분
        data_root_path: str = None,
        max_depth: int = 3,
        max_links_per_page: int = 20
    ):
        # Use environment variables with fallback defaults
        if config_path is None:
            config_path = os.getenv('CONFIG_PATH', '/opt/scholar/config/korean_sites_expanded.json')
        if data_root_path is None:
            data_root_path = os.getenv('DATA_ROOT_PATH', '/opt/scholar/data')

        self.config_path = Path(config_path)
        self.interval_seconds = interval_seconds
        self.data_root_path = Path(data_root_path)
        self.max_depth = max_depth
        self.max_links_per_page = max_links_per_page

        # DB 설정
        self.db_config = {
            'host': os.getenv('DB_HOST', '192.168.75.194'),
            'port': os.getenv('DB_PORT', '1521'),
            'service_name': os.getenv('DB_SERVICE_NAME', 'XEPDB1'),
            'username': os.getenv('DB_USERNAME', 'ocr_admin'),
            'password': os.getenv('DB_PASSWORD', 'admin_password')
        }

        # 설정 로드
        self.sites_config = load_expanded_sites_config(self.config_path)
        self.all_sites = get_all_sites_flat(self.sites_config)

        # 크롤러 초기화
        self.web_crawler = WebCrawler(
            data_root_path=str(self.data_root_path)
        )

        # PathDiversityCrawler 사용 (다양성 우선 크롤링)
        self.diversity_crawler = PathDiversityCrawler(
            db_config=self.db_config,
            max_depth=self.max_depth,
            max_links_per_page=self.max_links_per_page,
            same_domain_only=True,
            use_priority_queue=True
        )

        logger.info(f"ContinuousCrawlerV2 initialized with {len(self.all_sites)} sites")
        logger.info("Using PathDiversityCrawler for diversity-first crawling")
        active_sites.set(len(self.all_sites))

    def get_site_category(self, site: Dict) -> str:
        """사이트 카테고리 결정"""
        # 카테고리를 역으로 찾기
        for category_key, category_data in self.sites_config.items():
            if isinstance(category_data, dict) and 'sites' in category_data:
                if site in category_data['sites']:
                    return category_key
        return 'unknown'

    def crawl_single_site(self, site: Dict) -> Dict:
        """단일 사이트 크롤링 (다양성 우선 알고리즘 사용)"""
        site_name = site.get('name', 'Unknown')
        category = self.get_site_category(site)

        logger.info(f"Starting diversity crawl for site: {site_name} (category: {category})")

        start_time = time.time()

        try:
            # 시작 URL 가져오기 (첫 번째 start_url 사용)
            start_urls = site.get('start_urls', [site.get('base_url')])
            if not start_urls or not start_urls[0]:
                raise ValueError(f"No valid start URL for site: {site_name}")

            start_url = start_urls[0]

            # 다양성 우선 크롤링 수행
            stats = self.diversity_crawler.crawl_with_diversity(
                start_url=start_url,
                crawler_instance=self.web_crawler,
                data_root_path=self.data_root_path
            )

            duration = time.time() - start_time

            # 메트릭 업데이트
            crawl_duration.labels(site_category=category).observe(duration)

            # Path diversity 메트릭 업데이트
            if 'path_diversity' in stats:
                path_diversity_score.labels(site_category=category).set(stats['path_diversity'])
            if 'unique_patterns' in stats:
                unique_path_patterns.labels(site_category=category).set(stats['unique_patterns'])

            if stats['new_data'] > 0:
                crawl_counter.labels(status='success', site_category=category).inc(stats['new_data'])
                new_data_collected.labels(site_category=category).inc(stats['new_data'])
            else:
                crawl_counter.labels(status='skipped', site_category=category).inc()

            logger.info(
                f"✅ Site crawl completed: {site_name} - "
                f"new_data={stats['new_data']}, "
                f"diversity={stats.get('path_diversity', 0):.2%}, "
                f"unique_patterns={stats.get('unique_patterns', 0)}"
            )
            return {'success': True, 'stats': stats}

        except Exception as e:
            duration = time.time() - start_time
            crawl_duration.labels(site_category=category).observe(duration)
            crawl_counter.labels(status='failed', site_category=category).inc()

            logger.error(f"❌ Site crawl failed: {site_name} - {e}")
            return {'success': False, 'error': str(e)}

    def run_single_iteration(self, iteration: int):
        """단일 반복 실행"""
        logger.info(f"{'='*80}")
        logger.info(f"🚀 Starting Crawl Iteration #{iteration}")
        logger.info(f"{'='*80}")
        logger.info(f"Total sites: {len(self.all_sites)}")
        logger.info(f"Max depth: {self.max_depth}, Max links/page: {self.max_links_per_page}")

        # 사이트 목록 셔플 (매번 다른 순서로)
        shuffled_sites = self.all_sites.copy()
        random.shuffle(shuffled_sites)

        total_stats = {
            'iteration': iteration,
            'sites_total': len(shuffled_sites),
            'sites_success': 0,
            'sites_failed': 0,
            'total_new_data': 0,
            'total_unique_patterns': 0,
            'avg_diversity_score': 0.0,
            'categories': {}
        }

        # 각 사이트 크롤링
        for idx, site in enumerate(shuffled_sites, 1):
            site_name = site.get('name', 'Unknown')
            category = self.get_site_category(site)

            logger.info(f"[{idx}/{len(shuffled_sites)}] Crawling: {site_name}")

            result = self.crawl_single_site(site)

            if result['success']:
                total_stats['sites_success'] += 1
                stats = result['stats']
                total_stats['total_new_data'] += stats.get('new_data', 0)
                total_stats['total_unique_patterns'] += stats.get('unique_patterns', 0)
                total_stats['avg_diversity_score'] += stats.get('path_diversity', 0.0)

                # 카테고리별 통계
                if category not in total_stats['categories']:
                    total_stats['categories'][category] = {
                        'sites': 0,
                        'new_data': 0,
                        'unique_patterns': 0,
                        'diversity_score': 0.0
                    }
                total_stats['categories'][category]['sites'] += 1
                total_stats['categories'][category]['new_data'] += stats.get('new_data', 0)
                total_stats['categories'][category]['unique_patterns'] += stats.get('unique_patterns', 0)
                total_stats['categories'][category]['diversity_score'] += stats.get('path_diversity', 0.0)
            else:
                total_stats['sites_failed'] += 1

            # Rate limiting (사이트 간 대기)
            time.sleep(3)

        # 평균 다양성 점수 계산
        if total_stats['sites_success'] > 0:
            total_stats['avg_diversity_score'] /= total_stats['sites_success']

        # 반복 완료 로그
        logger.info(f"{'='*80}")
        logger.info(f"✅ Crawling Iteration #{iteration} Completed")
        logger.info(f"{'='*80}")
        logger.info(f"Sites crawled: {total_stats['sites_success']}/{total_stats['sites_total']}")
        logger.info(f"Sites failed: {total_stats['sites_failed']}")
        logger.info(f"New data collected: {total_stats['total_new_data']}")
        logger.info(f"Path Diversity: {total_stats['avg_diversity_score']:.2%} avg, "
                   f"{total_stats['total_unique_patterns']} unique patterns")

        # 카테고리별 통계 출력
        logger.info("Category Statistics:")
        for cat, cat_stats in total_stats['categories'].items():
            avg_diversity = cat_stats['diversity_score'] / max(cat_stats['sites'], 1)
            logger.info(
                f"  - {cat}: {cat_stats['sites']} sites, "
                f"{cat_stats['new_data']} new data, "
                f"{avg_diversity:.2%} diversity, "
                f"{cat_stats['unique_patterns']} patterns"
            )

        return total_stats

    def run_infinite(self):
        """무한 반복 실행"""
        iteration = 1

        logger.info("Starting Continuous Crawler V2 (Infinite Mode)")
        logger.info(f"Interval: {self.interval_seconds} seconds")
        logger.info(f"Sites: {len(self.all_sites)}")
        logger.info(f"Max depth: {self.max_depth}")

        while True:
            try:
                self.run_single_iteration(iteration)

                logger.info(f"Waiting {self.interval_seconds} seconds until next iteration...")
                time.sleep(self.interval_seconds)

                iteration += 1

            except KeyboardInterrupt:
                logger.info("Received interrupt signal. Shutting down gracefully...")
                break
            except Exception as e:
                logger.error(f"Error in iteration {iteration}: {e}")
                logger.info("Waiting 60 seconds before retry...")
                time.sleep(60)
                iteration += 1


def main():
    """메인 실행"""
    # Prometheus 메트릭 서버 시작
    metrics_port = int(os.getenv('PROMETHEUS_METRICS_PORT', '8000'))
    start_http_server(metrics_port)
    logger.info(f"Prometheus metrics server started on port {metrics_port}")

    # 크롤러 설정 (환경 변수 사용)
    crawler = ContinuousCrawlerV2(
        config_path=None,  # Will use environment variable or default
        interval_seconds=int(os.getenv('CRAWL_INTERVAL_SECONDS', '300')),  # 5분
        max_depth=int(os.getenv('MAX_CRAWL_DEPTH', '3')),
        max_links_per_page=int(os.getenv('MAX_LINKS_PER_PAGE', '20'))
    )

    # 무한 실행
    crawler.run_infinite()


if __name__ == "__main__":
    main()
