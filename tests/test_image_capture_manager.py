#!/usr/bin/env python3
# Generated: 2025-10-16 18:05:00 KST
"""
ImageCaptureManager 단위 테스트

WEB_CAPTURE_DATA 테이블에 스크린샷 저장 및 조회 기능 테스트
"""

import pytest
from PIL import Image
from io import BytesIO
import os
import sys

# scholar 모듈 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.connection import DatabaseConnection
from database.image_capture_manager import ImageCaptureManager


@pytest.fixture
def db_connection():
    """데이터베이스 연결 fixture"""
    db = DatabaseConnection()
    with db.get_connection() as conn:
        yield conn


@pytest.fixture
def manager(db_connection):
    """ImageCaptureManager fixture"""
    return ImageCaptureManager(db_connection)


@pytest.fixture
def sample_image_data():
    """샘플 이미지 생성 (A4 크기)"""
    image = Image.new('RGB', (794, 1123), color='red')
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


class TestImageCaptureManager:
    """ImageCaptureManager 단위 테스트"""

    def test_save_screenshot(self, manager, sample_image_data):
        """스크린샷 저장 성공"""
        capture_id = manager.save_screenshot(
            url='https://test.com/page1',
            image_data=sample_image_data,
            image_format='PNG'
        )
        assert capture_id > 0

    def test_duplicate_image(self, manager, sample_image_data):
        """중복 이미지 저장 시 예외 발생"""
        # 첫 번째 저장
        manager.save_screenshot(
            url='https://test.com/page2',
            image_data=sample_image_data
        )

        # 두 번째 저장 (동일 이미지)
        with pytest.raises(Exception):  # IntegrityError
            manager.save_screenshot(
                url='https://test.com/page3',
                image_data=sample_image_data
            )

    def test_is_image_exists(self, manager, sample_image_data):
        """이미지 존재 확인"""
        image_hash = manager._calculate_hash(sample_image_data)

        # 저장 전
        assert manager.is_image_exists(image_hash) is False

        # 저장
        manager.save_screenshot(
            url='https://test.com/page4',
            image_data=sample_image_data
        )

        # 저장 후
        assert manager.is_image_exists(image_hash) is True

    def test_get_screenshot_by_id(self, manager, sample_image_data):
        """ID로 스크린샷 조회"""
        url = 'https://test.com/page5'
        capture_id = manager.save_screenshot(
            url=url,
            image_data=sample_image_data
        )

        screenshot = manager.get_screenshot_by_id(capture_id)
        assert screenshot is not None
        assert screenshot['url'] == url
        assert screenshot['image_format'] == 'PNG'

    def test_get_recent_screenshots(self, manager, sample_image_data):
        """최근 스크린샷 조회"""
        # 여러 개 저장
        for i in range(3):
            img = Image.new('RGB', (794, 1123), color=(i*50, 0, 0))
            buffer = BytesIO()
            img.save(buffer, format='PNG')

            manager.save_screenshot(
                url=f'https://test.com/page{i}',
                image_data=buffer.getvalue()
            )

        recent = manager.get_recent_screenshots(limit=5)
        assert len(recent) >= 3

    def test_save_with_metadata(self, manager, sample_image_data):
        """메타데이터와 함께 저장"""
        metadata = {
            'page_number': 1,
            'total_pages': 5,
            'site_name': '경향신문'
        }

        capture_id = manager.save_screenshot(
            url='https://test.com/page6',
            image_data=sample_image_data,
            metadata=metadata
        )

        screenshot = manager.get_screenshot_by_id(capture_id)
        assert screenshot is not None
        assert screenshot['metadata'] == metadata

    def test_calculate_hash(self, manager, sample_image_data):
        """해시 계산 테스트"""
        hash1 = manager._calculate_hash(sample_image_data)
        hash2 = manager._calculate_hash(sample_image_data)

        # 동일한 데이터는 동일한 해시
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256은 64자리 16진수

    def test_different_images_different_hash(self, manager):
        """다른 이미지는 다른 해시"""
        img1 = Image.new('RGB', (100, 100), color='red')
        buffer1 = BytesIO()
        img1.save(buffer1, format='PNG')

        img2 = Image.new('RGB', (100, 100), color='blue')
        buffer2 = BytesIO()
        img2.save(buffer2, format='PNG')

        hash1 = manager._calculate_hash(buffer1.getvalue())
        hash2 = manager._calculate_hash(buffer2.getvalue())

        assert hash1 != hash2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
