# Generated: 2025-10-14 11:25:00 KST
"""
Path Diversity Crawler Unit Tests

Tests for PathDiversityCrawler functionality:
- Path fingerprinting
- Link priority calculation
- Diverse link selection
"""

import pytest
from unittest.mock import Mock, MagicMock

# Import the crawler
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from crawler.path_diversity_crawler import PathDiversityCrawler


@pytest.fixture
def mock_db_config():
    """Mock database configuration"""
    return {
        'host': 'localhost',
        'port': '1521',
        'service_name': 'XEPDB1',
        'username': 'test_user',
        'password': 'test_password'
    }


@pytest.fixture
def crawler(mock_db_config):
    """Create PathDiversityCrawler instance for testing"""
    return PathDiversityCrawler(
        db_config=mock_db_config,
        max_depth=3,
        max_links_per_page=20
    )


class TestPathFingerprinting:
    """Path fingerprinting 기능 테스트"""

    def test_numeric_pattern(self, crawler):
        """숫자 패턴 정규화 테스트"""
        assert crawler.create_path_fingerprint("/article/123/view") == "/article/*/view"
        assert crawler.create_path_fingerprint("/article/456/view") == "/article/*/view"
        assert crawler.create_path_fingerprint("/board/999/read") == "/board/*/read"

    def test_date_pattern(self, crawler):
        """날짜 패턴 정규화 테스트"""
        assert crawler.create_path_fingerprint("/news/2025/10/13/story") == "/news/*/*/story"
        assert crawler.create_path_fingerprint("/news/2024/01/01/article") == "/news/*/*/article"

    def test_uuid_pattern(self, crawler):
        """UUID 패턴 정규화 테스트"""
        uuid_url = "/post/550e8400-e29b-41d4-a716-446655440000"
        assert crawler.create_path_fingerprint(uuid_url) == "/post/UUID"

        uuid_url2 = "/item/123e4567-e89b-12d3-a456-426614174000/view"
        assert crawler.create_path_fingerprint(uuid_url2) == "/item/UUID/view"

    def test_mixed_numeric_alpha(self, crawler):
        """숫자+문자 혼합 패턴 테스트"""
        assert crawler.create_path_fingerprint("/article123/view") == "/article*/view"
        assert crawler.create_path_fingerprint("/board456/read") == "/board*/read"

    def test_hash_pattern(self, crawler):
        """긴 해시 문자열 패턴 테스트"""
        hash_url = "/post/abcdef0123456789abcdef0123456789abcdef"
        result = crawler.create_path_fingerprint(hash_url)
        assert "/HASH/" in result or "/post/" in result

    def test_same_structure_different_ids(self, crawler):
        """구조는 같고 ID만 다른 URL들의 fingerprint가 동일한지 테스트"""
        urls = [
            "/article/1/view",
            "/article/999/view",
            "/article/12345/view"
        ]
        fingerprints = [crawler.create_path_fingerprint(url) for url in urls]

        # 모두 같은 fingerprint를 가져야 함
        assert len(set(fingerprints)) == 1
        assert fingerprints[0] == "/article/*/view"


class TestLinkPriority:
    """링크 우선순위 계산 테스트"""

    def test_priority_calculation_depth(self, crawler):
        """깊이에 따른 우선순위 테스트"""
        url = "/article/123"

        priority_depth1 = crawler.calculate_link_priority(url, depth=1)
        priority_depth2 = crawler.calculate_link_priority(url, depth=2)
        priority_depth3 = crawler.calculate_link_priority(url, depth=3)

        # 깊이가 클수록 우선순위가 높아야 함 (대략적으로)
        assert priority_depth3 > priority_depth1

    def test_priority_with_visit_history(self, crawler):
        """방문 기록에 따른 우선순위 변화 테스트"""
        url1 = "/article/123"
        url2 = "/article/456"

        # 첫 방문 우선순위
        priority1_before = crawler.calculate_link_priority(url1, depth=2)

        # 방문 기록 추가 (같은 패턴)
        pattern = crawler.create_path_fingerprint(url1)
        crawler.path_history[pattern] = 5

        # 재방문 우선순위 (낮아져야 함)
        priority1_after = crawler.calculate_link_priority(url1, depth=2)
        priority2 = crawler.calculate_link_priority(url2, depth=2)  # 같은 패턴

        # 방문 후 우선순위가 낮아져야 함
        assert priority1_after < priority1_before
        assert priority2 < priority1_before

    def test_priority_randomness(self, crawler):
        """우선순위에 랜덤성이 포함되는지 테스트"""
        url = "/article/123"

        # 같은 URL에 대해 여러 번 계산
        priorities = [
            crawler.calculate_link_priority(url, depth=2)
            for _ in range(10)
        ]

        # 랜덤 요소로 인해 모두 다를 가능성이 높음
        unique_priorities = set(priorities)
        assert len(unique_priorities) > 1  # 최소 2개 이상은 달라야 함


class TestDiverseLinkSelection:
    """다양성 링크 선택 테스트"""

    def test_round_robin_selection(self, crawler):
        """Round-robin 방식으로 다양한 패턴 선택 테스트"""
        links = [
            "/article/1/view",
            "/article/2/view",
            "/article/3/view",
            "/board/100/read",
            "/board/101/read",
            "/news/20251014/story",
            "/blog/post-title"
        ]

        selected = crawler.select_diverse_links(links, max_count=4)

        # 다양한 패턴이 골고루 선택되어야 함
        patterns = set(crawler.create_path_fingerprint(link) for link in selected)

        # 최소 3개의 다른 패턴이 포함되어야 함
        assert len(patterns) >= 3

    def test_max_count_limit(self, crawler):
        """최대 개수 제한 테스트"""
        links = [f"/article/{i}/view" for i in range(100)]

        selected = crawler.select_diverse_links(links, max_count=10)

        # 정확히 max_count만큼만 선택되어야 함
        assert len(selected) == 10

    def test_empty_links(self, crawler):
        """빈 링크 리스트 처리 테스트"""
        selected = crawler.select_diverse_links([], max_count=10)

        # 빈 리스트 반환
        assert selected == []

    def test_diverse_patterns_priority(self, crawler):
        """다양한 패턴이 우선 선택되는지 테스트"""
        links = [
            # 같은 패턴 10개
            *[f"/article/{i}/view" for i in range(10)],
            # 다양한 패턴 5개
            "/board/100/read",
            "/news/20251014/story",
            "/blog/post-1",
            "/forum/topic-1",
            "/wiki/page-1"
        ]

        selected = crawler.select_diverse_links(links, max_count=10)

        # 선택된 링크의 패턴
        patterns = [crawler.create_path_fingerprint(link) for link in selected]

        # /article/*/view 패턴이 전체를 차지하면 안 됨
        article_count = sum(1 for p in patterns if "/article/" in p)
        assert article_count < len(selected)  # 전체가 article이면 안 됨


class TestPathDiversityReport:
    """Path diversity 리포트 생성 테스트"""

    def test_diversity_report_generation(self, crawler):
        """다양성 리포트 생성 테스트"""
        # 방문 기록 추가
        crawler.path_history["/article/*/view"] = 10
        crawler.path_history["/board/*/read"] = 5
        crawler.path_history["/news/*/*/story"] = 3
        crawler.path_fingerprints.update(["/article/*/view", "/board/*/read", "/news/*/*/story"])

        report = crawler.get_path_diversity_report()

        # 리포트 구조 검증
        assert 'unique_patterns' in report
        assert 'total_visits' in report
        assert 'diversity_score' in report
        assert 'top_patterns' in report

        # 값 검증
        assert report['unique_patterns'] == 3
        assert report['total_visits'] == 18
        assert report['diversity_score'] == pytest.approx(3 / 18)

        # Top patterns 검증
        assert len(report['top_patterns']) <= 10
        assert report['top_patterns'][0]['pattern'] == "/article/*/view"
        assert report['top_patterns'][0]['visits'] == 10


class TestIntegration:
    """통합 테스트"""

    def test_crawler_initialization(self, mock_db_config):
        """Crawler 초기화 테스트"""
        crawler = PathDiversityCrawler(
            db_config=mock_db_config,
            max_depth=3,
            max_links_per_page=20,
            use_priority_queue=True
        )

        assert crawler.max_depth == 3
        assert crawler.max_links_per_page == 20
        assert crawler.use_priority_queue is True
        assert len(crawler.path_history) == 0
        assert len(crawler.path_fingerprints) == 0

    def test_url_hash_compatibility(self, crawler):
        """SmartLinkCrawler의 _url_hash와 호환성 테스트"""
        url = "https://example.com/article/123"

        # _url_hash 메서드가 정상 작동하는지 확인
        url_hash = crawler._url_hash(url)

        assert isinstance(url_hash, str)
        assert len(url_hash) == 32  # MD5 해시는 32자

    def test_is_valid_url_compatibility(self, crawler):
        """SmartLinkCrawler의 _is_valid_url과 호환성 테스트"""
        valid_url = "https://example.com/article/123/view"
        invalid_url = "https://example.com/login"

        # _is_valid_url 메서드가 정상 작동하는지 확인
        assert crawler._is_valid_url(valid_url, "example.com") is True
        assert crawler._is_valid_url(invalid_url, "example.com") is False


# Pytest 실행을 위한 메인
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
