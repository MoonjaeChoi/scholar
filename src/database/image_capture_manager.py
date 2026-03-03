#!/usr/bin/env python3
# Generated: 2025-10-16 18:00:00 KST
"""
이미지 캡처 관리 모듈

WEB_CAPTURE_DATA 테이블에 스크린샷 이미지를 저장하고 관리합니다.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import os
import hashlib
import json
from loguru import logger
from PIL import Image
from io import BytesIO

# 환경 변수로 Oracle 라이브러리 선택
USE_PYTHON_ORACLEDB = os.getenv('USE_PYTHON_ORACLEDB', 'false').lower() == 'true'

if USE_PYTHON_ORACLEDB:
    import oracledb as oracle_lib
    logger.info("✅ ImageCaptureManager: Using python-oracledb (Thin Mode)")
else:
    import cx_Oracle as oracle_lib
    logger.info("✅ ImageCaptureManager: Using cx_Oracle")


class ImageCaptureManager:
    """WEB_CAPTURE_DATA 테이블에 스크린샷 이미지 저장"""

    def __init__(self, connection, base_image_dir: Optional[str] = None):
        """
        Args:
            connection: Oracle DB 연결 객체
            base_image_dir: 이미지 저장 기본 경로 (기본값: 환경에 따라 자동 설정)
        """
        self.connection = connection

        # 기본 이미지 디렉토리 설정
        if base_image_dir:
            self.base_image_dir = base_image_dir
        else:
            # 환경별 기본 경로
            if os.path.exists('/home/pro301'):
                # 프로덕션 서버
                self.base_image_dir = '/home/pro301/git/en-zine/scholar/training/data/images'
            else:
                # 로컬 개발 환경
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                self.base_image_dir = os.path.join(project_root, 'training', 'data', 'images')

    def save_screenshot(
        self,
        url: str,
        image_data: bytes,
        image_format: str = 'PNG',
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """스크린샷 이미지 저장

        Args:
            url: 웹페이지 URL
            image_data: 이미지 바이너리 데이터
            image_format: 이미지 포맷 (PNG, JPEG 등)
            metadata: 추가 메타데이터 (JSON)

        Returns:
            생성된 CAPTURE_ID

        Raises:
            oracle_lib.IntegrityError: IMAGE_HASH 중복 시
        """
        cursor = self.connection.cursor()

        try:
            # 1. IMAGE_HASH 계산 (중복 체크)
            image_hash = self._calculate_hash(image_data)

            # 2. 중복 확인
            if self.is_image_exists(image_hash):
                logger.warning(f"Duplicate image detected: {image_hash[:16]}...")
                raise oracle_lib.IntegrityError("Duplicate IMAGE_HASH")

            # 3. CAPTURE_ID 생성용 변수
            capture_id_var = cursor.var(oracle_lib.NUMBER)

            # 4. 임시 경로 생성 (실제 capture_id는 아직 모름)
            # INSERT 후 실제 ID로 경로 업데이트하거나, 타임스탬프 기반으로 생성
            now = datetime.now()
            timestamp = now.strftime('%Y%m%d_%H%M%S')

            # 디렉토리 경로 생성
            year = now.strftime('%Y')
            month = now.strftime('%m')
            day = now.strftime('%d')
            dir_path = os.path.join(self.base_image_dir, year, month, day)

            # 임시 파일명 (capture_id는 나중에 업데이트)
            temp_filename = f"image_{timestamp}_temp.{image_format.lower()}"
            image_path = os.path.join(dir_path, temp_filename)

            # 5. 메타데이터 JSON 직렬화
            metadata_json = json.dumps(metadata) if metadata else None

            # 6. INSERT 쿼리
            query = """
                INSERT INTO WEB_CAPTURE_DATA (
                    CAPTURE_ID, URL, IMAGE_PATH, IMAGE_DATA, IMAGE_HASH,
                    IMAGE_SIZE, IMAGE_FORMAT, CRAWL_TIMESTAMP,
                    PROCESSING_STATUS, METADATA
                ) VALUES (
                    SEQ_CAPTURE.NEXTVAL, :url, :image_path, :image_data, :image_hash,
                    :image_size, :image_format, SYSTIMESTAMP,
                    'completed', :metadata
                )
                RETURNING CAPTURE_ID INTO :capture_id
            """

            cursor.execute(query, {
                'url': url,
                'image_path': image_path,
                'image_data': image_data,
                'image_hash': image_hash,
                'image_size': len(image_data),
                'image_format': image_format.upper(),
                'metadata': metadata_json,
                'capture_id': capture_id_var
            })

            self.connection.commit()

            capture_id = int(capture_id_var.getvalue()[0])

            # 7. 실제 파일명 생성 및 저장
            filename = f"image_{timestamp}_{capture_id:05d}.{image_format.lower()}"
            final_image_path = os.path.join(dir_path, filename)

            # 8. 경로 업데이트
            cursor.execute(
                "UPDATE WEB_CAPTURE_DATA SET IMAGE_PATH = :path WHERE CAPTURE_ID = :id",
                {'path': final_image_path, 'id': capture_id}
            )
            self.connection.commit()

            # 9. 파일 저장 (BLOB 외에 파일도 저장)
            self._save_image_file(final_image_path, image_data)

            logger.info(
                f"Screenshot saved: ID={capture_id}, URL={url}, "
                f"Size={len(image_data)} bytes, Hash={image_hash[:16]}..."
            )

            return capture_id

        except oracle_lib.IntegrityError as e:
            self.connection.rollback()
            if 'IMAGE_HASH' in str(e):
                logger.warning(f"Duplicate image for URL: {url}")
            raise

        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to save screenshot: {e}")
            raise

        finally:
            cursor.close()

    def is_image_exists(self, image_hash: str) -> bool:
        """IMAGE_HASH로 중복 확인

        Args:
            image_hash: SHA-256 해시

        Returns:
            True if 존재, False otherwise
        """
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                "SELECT COUNT(*) FROM WEB_CAPTURE_DATA WHERE IMAGE_HASH = :hash",
                {'hash': image_hash}
            )
            count = cursor.fetchone()[0]
            return count > 0

        finally:
            cursor.close()

    def get_screenshot_by_id(self, capture_id: int) -> Optional[Dict[str, Any]]:
        """CAPTURE_ID로 스크린샷 조회

        Args:
            capture_id: 캡처 ID

        Returns:
            스크린샷 정보 dict 또는 None
        """
        cursor = self.connection.cursor()

        try:
            cursor.execute("""
                SELECT
                    CAPTURE_ID, URL, IMAGE_PATH, IMAGE_HASH,
                    IMAGE_SIZE, IMAGE_FORMAT, CRAWL_TIMESTAMP,
                    PROCESSING_STATUS, METADATA
                FROM WEB_CAPTURE_DATA
                WHERE CAPTURE_ID = :id
            """, {'id': capture_id})

            row = cursor.fetchone()

            if not row:
                return None

            # CLOB 데이터 처리
            metadata_raw = row[8]
            metadata_json = None
            if metadata_raw:
                # CLOB 객체를 문자열로 변환
                if hasattr(metadata_raw, 'read'):
                    metadata_str = metadata_raw.read()
                else:
                    metadata_str = str(metadata_raw)
                metadata_json = json.loads(metadata_str) if metadata_str else None

            return {
                'capture_id': row[0],
                'url': row[1],
                'image_path': row[2],
                'image_hash': row[3],
                'image_size': row[4],
                'image_format': row[5],
                'crawl_timestamp': row[6],
                'processing_status': row[7],
                'metadata': metadata_json
            }

        finally:
            cursor.close()

    def get_recent_screenshots(self, limit: int = 10) -> list:
        """최근 스크린샷 조회

        Args:
            limit: 최대 조회 개수

        Returns:
            스크린샷 목록
        """
        cursor = self.connection.cursor()

        try:
            cursor.execute("""
                SELECT
                    CAPTURE_ID, URL, IMAGE_PATH, IMAGE_SIZE,
                    IMAGE_FORMAT, CRAWL_TIMESTAMP, PROCESSING_STATUS
                FROM WEB_CAPTURE_DATA
                ORDER BY CRAWL_TIMESTAMP DESC
                FETCH FIRST :limit ROWS ONLY
            """, {'limit': limit})

            screenshots = []
            for row in cursor:
                screenshots.append({
                    'capture_id': row[0],
                    'url': row[1],
                    'image_path': row[2],
                    'image_size': row[3],
                    'image_format': row[4],
                    'crawl_timestamp': row[5],
                    'processing_status': row[6]
                })

            return screenshots

        finally:
            cursor.close()

    def _calculate_hash(self, image_data: bytes) -> str:
        """이미지 데이터의 SHA-256 해시 계산

        Args:
            image_data: 이미지 바이너리

        Returns:
            64자리 16진수 해시
        """
        return hashlib.sha256(image_data).hexdigest()

    def _generate_image_path(
        self,
        capture_id: int,
        image_format: str
    ) -> str:
        """날짜별 이미지 경로 생성

        Args:
            capture_id: 캡처 ID
            image_format: 이미지 포맷

        Returns:
            절대 경로
        """
        now = datetime.now()

        # 날짜별 폴더
        year = now.strftime('%Y')
        month = now.strftime('%m')
        day = now.strftime('%d')

        # 디렉토리 경로
        dir_path = os.path.join(self.base_image_dir, year, month, day)

        # 파일명
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        filename = f"image_{timestamp}_{capture_id:05d}.{image_format.lower()}"

        return os.path.join(dir_path, filename)

    def _save_image_file(self, image_path: str, image_data: bytes):
        """이미지 파일 저장

        Args:
            image_path: 저장 경로
            image_data: 이미지 바이너리
        """
        try:
            # 디렉토리 생성
            os.makedirs(os.path.dirname(image_path), exist_ok=True)

            # 파일 저장
            with open(image_path, 'wb') as f:
                f.write(image_data)

            logger.debug(f"Image file saved: {image_path}")

        except Exception as e:
            logger.error(f"Failed to save image file {image_path}: {e}")
            # 파일 저장 실패해도 DB 저장은 유지
