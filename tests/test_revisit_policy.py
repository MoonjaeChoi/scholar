# Generated: 2025-10-14 21:00:00 KST
"""
Dynamic Revisit Policy 단위 테스트

URL 유형 분류 및 재방문 정책 테스트
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from crawler.web_crawler import WebCrawler, URLType


class TestURLClassification:
    """URL 유형 분류 테스트"""

    @pytest.fixture
    def crawler(self, tmp_path):
        """테스트용 WebCrawler 인스턴스"""
        return WebCrawler(data_root_path=str(tmp_path))

    def test_news_classification(self, crawler):
        """뉴스 사이트 분류 테스트"""
        news_urls = [
            "https://news.naver.com/main/article.nhn?id=123",
            "https://news.daum.net/breakingnews",
            "https://www.chosun.com/politics/2025/01/14/",
            "https://joongang.co.kr/article/123456",
            "https://www.donga.com/news/article/all/",
            "https://www.hani.co.kr/arti/",
            "https://www.khan.co.kr/national/",
            "https://www.mk.co.kr/news/"
        ]

        for url in news_urls:
            assert crawler.classify_url_type(url) == URLType.NEWS, f"Failed: {url}"

    def test_blog_main_classification(self, crawler):
        """블로그 메인 페이지 분류 테스트"""
        blog_main_urls = [
            "https://blog.naver.com/user123",
            "https://blog.naver.com/user123/",
            "https://example.tistory.com",
            "https://example.tistory.com/",
            "https://brunch.co.kr/@username",
            "https://brunch.co.kr/@username/"
        ]

        for url in blog_main_urls:
            result = crawler.classify_url_type(url)
            assert result == URLType.BLOG_MAIN, f"Failed: {url} -> {result.value}"

    def test_blog_article_classification(self, crawler):
        """블로그 게시글 분류 테스트 (ARTICLE로 분류되어야 함)"""
        blog_article_urls = [
            "https://blog.naver.com/user123/123456789",
            "https://example.tistory.com/123",
            "https://brunch.co.kr/@username/123"
        ]

        for url in blog_article_urls:
            # 게시글은 숫자 패턴으로 ARTICLE로 분류됨
            result = crawler.classify_url_type(url)
            assert result == URLType.ARTICLE, f"Failed: {url} -> {result.value}"

    def test_community_classification(self, crawler):
        """커뮤니티 사이트 분류 테스트"""
        community_urls = [
            "https://www.clien.net/service/board/park",
            "https://bbs.ruliweb.com/community/board/300143",
            "https://www.ppomppu.co.kr/zboard/",
            "https://www.slrclub.com/bbs/vx2.php",
            "https://gall.dcinside.com/board/view/",
            "https://www.fmkorea.com/best"
        ]

        for url in community_urls:
            assert crawler.classify_url_type(url) == URLType.COMMUNITY, f"Failed: {url}"

    def test_article_classification(self, crawler):
        """게시글/기사 분류 테스트"""
        article_urls = [
            "https://example.com/article/123456",
            "https://example.com/post/my-title",
            "https://example.com/view/notice",
            "https://example.com/read/announcement",
            "https://example.com/detail/report",
            "https://example.com/show/12345",
            "https://example.com/board/123"  # 숫자로 끝남
        ]

        for url in article_urls:
            result = crawler.classify_url_type(url)
            assert result == URLType.ARTICLE, f"Failed: {url} -> {result.value}"

    def test_static_classification(self, crawler):
        """정적 페이지 분류 테스트"""
        static_urls = [
            "https://example.com/about",
            "https://example.com/company",
            "https://example.com/terms",
            "https://example.com/privacy",
            "https://example.com/contact",
            "https://example.com/faq"
        ]

        for url in static_urls:
            assert crawler.classify_url_type(url) == URLType.STATIC, f"Failed: {url}"

    def test_unknown_classification(self, crawler):
        """알 수 없는 유형 분류 테스트"""
        unknown_urls = [
            "https://example.com",
            "https://example.com/",
            "https://example.com/random-page",
            "https://example.com/some/path/here"
        ]

        for url in unknown_urls:
            result = crawler.classify_url_type(url)
            assert result == URLType.UNKNOWN, f"Failed: {url} -> {result.value}"


class TestRevisitIntervals:
    """재방문 간격 테스트"""

    @pytest.fixture
    def crawler(self, tmp_path):
        """테스트용 WebCrawler 인스턴스"""
        return WebCrawler(data_root_path=str(tmp_path))

    def test_news_interval(self, crawler):
        """뉴스 재방문 간격: 3시간"""
        assert crawler.get_revisit_interval(URLType.NEWS) == timedelta(hours=3)

    def test_blog_main_interval(self, crawler):
        """블로그 메인 재방문 간격: 12시간"""
        assert crawler.get_revisit_interval(URLType.BLOG_MAIN) == timedelta(hours=12)

    def test_community_interval(self, crawler):
        """커뮤니티 재방문 간격: 6시간"""
        assert crawler.get_revisit_interval(URLType.COMMUNITY) == timedelta(hours=6)

    def test_article_interval(self, crawler):
        """게시글 재방문 간격: 7일"""
        assert crawler.get_revisit_interval(URLType.ARTICLE) == timedelta(days=7)

    def test_static_interval(self, crawler):
        """정적 페이지 재방문 간격: 30일"""
        assert crawler.get_revisit_interval(URLType.STATIC) == timedelta(days=30)

    def test_unknown_interval(self, crawler):
        """알 수 없는 유형 재방문 간격: 7일 (기본값)"""
        assert crawler.get_revisit_interval(URLType.UNKNOWN) == timedelta(days=7)


class TestImageHash:
    """이미지 해시 계산 테스트"""

    @pytest.fixture
    def crawler(self, tmp_path):
        """테스트용 WebCrawler 인스턴스"""
        return WebCrawler(data_root_path=str(tmp_path))

    @pytest.fixture
    def test_image(self, tmp_path):
        """테스트용 이미지 파일 생성"""
        image_path = tmp_path / "test_image.png"
        # 간단한 PNG 헤더만 있는 파일 생성
        image_path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'test image content')
        return str(image_path)

    def test_calculate_image_hash(self, crawler, test_image):
        """이미지 해시 계산 테스트"""
        hash1 = crawler._calculate_image_hash(test_image)

        assert hash1 is not None
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256은 64자

    def test_same_file_same_hash(self, crawler, test_image):
        """같은 파일은 같은 해시를 반환"""
        hash1 = crawler._calculate_image_hash(test_image)
        hash2 = crawler._calculate_image_hash(test_image)

        assert hash1 == hash2

    def test_different_files_different_hash(self, crawler, tmp_path):
        """다른 파일은 다른 해시를 반환"""
        image1 = tmp_path / "image1.png"
        image2 = tmp_path / "image2.png"

        image1.write_bytes(b'image content 1')
        image2.write_bytes(b'image content 2')

        hash1 = crawler._calculate_image_hash(str(image1))
        hash2 = crawler._calculate_image_hash(str(image2))

        assert hash1 != hash2

    def test_nonexistent_file(self, crawler):
        """존재하지 않는 파일은 None 반환"""
        hash_value = crawler._calculate_image_hash("/nonexistent/file.png")
        assert hash_value is None


class TestShouldCrawlURL:
    """URL 크롤링 여부 판단 테스트 (DB 없는 환경)"""

    @pytest.fixture
    def crawler(self, tmp_path):
        """테스트용 WebCrawler 인스턴스"""
        return WebCrawler(data_root_path=str(tmp_path))

    def test_should_crawl_without_db(self, crawler):
        """DB가 없으면 항상 크롤링 허용"""
        # DB가 없는 경우 (기본값)
        assert crawler.db_available is False

        # 어떤 URL이든 크롤링 허용
        assert crawler.should_crawl_url("https://news.naver.com") is True
        assert crawler.should_crawl_url("https://example.com") is True


def test_import_success():
    """모듈 import 성공 테스트"""
    from crawler.web_crawler import WebCrawler, URLType
    assert WebCrawler is not None
    assert URLType is not None


if __name__ == '__main__':
    # 직접 실행 시 pytest 실행
    pytest.main([__file__, '-v', '--tb=short'])
