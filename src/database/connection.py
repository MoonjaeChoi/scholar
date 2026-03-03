import os
from typing import Optional
from loguru import logger
from contextlib import contextmanager

# 환경 변수로 Oracle 라이브러리 선택
# 기본값(true): python-oracledb Thin Mode (Oracle 23ai Free 호환)
# 레거시: USE_PYTHON_ORACLEDB=false (cx_Oracle, Oracle 21c 이하)
USE_PYTHON_ORACLEDB = os.getenv('USE_PYTHON_ORACLEDB', 'true').lower() == 'true'

if USE_PYTHON_ORACLEDB:
    import oracledb as oracle_lib
    logger.info("✅ DatabaseConnection: Using python-oracledb (Thin Mode)")
else:
    import cx_Oracle as oracle_lib
    logger.info("✅ DatabaseConnection: Using cx_Oracle")

    # cx_Oracle 초기화
    # Note: We rely on LD_LIBRARY_PATH being set correctly by docker-entrypoint.sh
    # and ldconfig configuration in the Docker image. Explicit init_oracle_client()
    # can cause issues with library loading in some environments.
    try:
        # Only initialize if LD_LIBRARY_PATH is not set
        if not os.environ.get('LD_LIBRARY_PATH'):
            oracle_lib.init_oracle_client(lib_dir="/opt/oracle/instantclient_21_15")
            logger.info("Oracle Client initialized with explicit lib_dir")
        else:
            logger.info(f"Oracle Client will use LD_LIBRARY_PATH: {os.environ.get('LD_LIBRARY_PATH')}")
    except Exception as e:
        logger.warning(f"Oracle Client initialization skipped or failed: {e}")

class DatabaseConnection:
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = os.getenv('DB_PORT', '1521')
        self.service_name = os.getenv('DB_SERVICE_NAME', 'pdb_ocr_system')
        self.username = os.getenv('DB_USERNAME', 'ocr_admin')
        self.password = os.getenv('DB_PASSWORD')

        if not self.password:
            raise ValueError('DB_PASSWORD environment variable is required')

    def get_dsn(self) -> str:
        if USE_PYTHON_ORACLEDB:
            # python-oracledb: 간단한 DSN 형식
            return f"{self.host}:{self.port}/{self.service_name}"
        else:
            # cx_Oracle: makedsn 함수 사용
            return oracle_lib.makedsn(self.host, self.port, service_name=self.service_name)

    @contextmanager
    def get_connection(self):
        connection = None
        try:
            dsn = self.get_dsn()
            connection = oracle_lib.connect(
                user=self.username,
                password=self.password,
                dsn=dsn
            )
            yield connection
        except Exception as e:
            logger.error(f'Database connection failed: {e}')
            raise
        finally:
            if connection:
                connection.close()

    def test_connection(self) -> bool:
        """데이터베이스 연결 테스트"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT SYSDATE FROM DUAL')
                result = cursor.fetchone()
                cursor.close()
                logger.info(f'Database connection test successful: {result[0]}')
                return True
        except Exception as e:
            logger.error(f'Database connection test failed: {e}')
            return False
