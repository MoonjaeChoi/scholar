#!/usr/bin/env python3
"""
PaddleOCR 훈련을 위한 데이터베이스 연결 모듈
crawling 시스템의 database connection과 호환
"""

import cx_Oracle
import os
from contextlib import contextmanager
from loguru import logger

class DatabaseConnection:
    """Oracle 데이터베이스 연결 클래스"""

    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = os.getenv('DB_PORT', '1521')
        self.service_name = os.getenv('DB_SERVICE_NAME', 'pdb_ocr_system')
        self.username = os.getenv('DB_USERNAME', 'ocr_admin')
        self.password = os.getenv('DB_PASSWORD', 'SecurePassword123!')

        # Oracle 클라이언트 경로 설정
        oracle_home = os.getenv('ORACLE_HOME', '/opt/oracle/instantclient_21_15')
        if oracle_home and os.path.exists(oracle_home):
            try:
                # lib_dir에는 libclntsh.so가 있는 디렉토리를 지정
                # instantclient는 lib 서브디렉토리가 없으므로 oracle_home 자체 사용
                cx_Oracle.init_oracle_client(lib_dir=oracle_home)
            except cx_Oracle.ProgrammingError as e:
                # 이미 초기화된 경우 무시
                if "already initialized" not in str(e).lower():
                    logger.warning(f"Oracle client initialization warning: {e}")

        self.dsn = cx_Oracle.makedsn(self.host, self.port, service_name=self.service_name)

    @contextmanager
    def get_connection(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        connection = None
        try:
            connection = cx_Oracle.connect(
                user=self.username,
                password=self.password,
                dsn=self.dsn
            )
            logger.debug("Database connection established")
            yield connection

        except cx_Oracle.DatabaseError as e:
            logger.error(f"Database connection failed: {e}")
            raise

        finally:
            if connection:
                connection.close()
                logger.debug("Database connection closed")

    def test_connection(self) -> bool:
        """연결 테스트"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM DUAL")
                result = cursor.fetchone()
                return result[0] == 1
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False