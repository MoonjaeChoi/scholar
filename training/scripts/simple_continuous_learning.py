#!/usr/bin/env python3
# Generated: 2025-10-05 21:40:00 KST
# Updated: 2025-10-05 22:14:00 KST - Added file logging support
"""
간단한 연속 학습 스크립트 - 최소한의 의존성으로 동작
"""

import os
import sys
import time
import cx_Oracle
import random
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

# 로그 디렉토리 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 로그 파일 경로
LOG_FILE = os.path.join(LOG_DIR, 'continuous_learning.log')

# 로거 설정
logger = logging.getLogger('continuous_learning')
logger.setLevel(logging.INFO)

# 파일 핸들러 (10MB 크기, 최대 5개 백업)
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# 콘솔 핸들러
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)

# 핸들러 추가
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("="*80)
logger.info(f"🚀 연속 학습 시스템 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info(f"📄 로그 파일: {LOG_FILE}")
logger.info("="*80)

# Oracle 연결 설정
ORACLE_HOST = os.getenv('ORACLE_HOST') or 'oracle-xe'
ORACLE_PORT = int(os.getenv('ORACLE_PORT', '1521'))
ORACLE_SERVICE = os.getenv('ORACLE_SERVICE_NAME', 'XEPDB1')
ORACLE_USER = os.getenv('ORACLE_USERNAME', 'ocr_admin')
ORACLE_PASS = os.getenv('ORACLE_PASSWORD') or 'admin_password'

logger.info(f"📊 Oracle 설정: {ORACLE_HOST}:{ORACLE_PORT}/{ORACLE_SERVICE}")

def connect_oracle():
    """Oracle 데이터베이스 연결"""
    try:
        dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)
        connection = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASS, dsn=dsn)
        logger.info("✅ Oracle 연결 성공")
        return connection
    except Exception as e:
        logger.error(f"❌ Oracle 연결 실패: {e}")
        return None

def get_training_data(connection, limit=6):
    """미학습 데이터 조회"""
    try:
        cursor = connection.cursor()
        query = """
        SELECT
            w.CAPTURE_ID,
            w.IMAGE_PATH,
            COUNT(t.BOX_ID) as bbox_count
        FROM WEB_CAPTURE_DATA w
        LEFT JOIN TEXT_BOUNDING_BOXES t ON w.CAPTURE_ID = t.CAPTURE_ID
        WHERE w.DELETED_AT IS NULL
          AND UPPER(w.PROCESSING_STATUS) = 'COMPLETED'
          AND NOT EXISTS (
              SELECT 1 FROM TRAINING_HISTORY h
              WHERE h.CAPTURE_ID = w.CAPTURE_ID
              AND h.IS_SUCCESSFUL = 'Y'
          )
        GROUP BY w.CAPTURE_ID, w.IMAGE_PATH, w.CREATED_AT
        HAVING COUNT(t.BOX_ID) >= 1
        ORDER BY w.CREATED_AT DESC
        FETCH FIRST :limit ROWS ONLY
        """
        cursor.execute(query, {'limit': limit})
        rows = cursor.fetchall()
        cursor.close()

        logger.info(f"📦 조회된 학습 데이터: {len(rows)}개")
        return rows
    except Exception as e:
        logger.error(f"❌ 데이터 조회 실패: {e}")
        return []

def save_training_result(connection, capture_id, success, loss_value=None, batch_id=None):
    """학습 결과 저장"""
    try:
        cursor = connection.cursor()

        # batch_id가 없으면 타임스탬프 기반으로 생성
        if not batch_id:
            batch_id = f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        insert_sql = """
        INSERT INTO TRAINING_HISTORY (
            TRAINING_ID, CAPTURE_ID, TRAINING_BATCH_ID, TRAINING_START_TIME, TRAINING_END_TIME,
            IS_SUCCESSFUL, LOSS_VALUE
        ) VALUES (
            TRAINING_HISTORY_SEQ.NEXTVAL, :capture_id, :batch_id, SYSTIMESTAMP, SYSTIMESTAMP,
            :is_successful, :loss_value
        )
        """

        cursor.execute(insert_sql, {
            'capture_id': capture_id,
            'batch_id': batch_id,
            'is_successful': 'Y' if success else 'N',
            'loss_value': loss_value
        })

        connection.commit()
        cursor.close()
        logger.info(f"  ✅ 학습 결과 저장: Capture ID {capture_id}, Success={success}, Loss={loss_value}")
        return True
    except Exception as e:
        logger.error(f"  ❌ 결과 저장 실패: {e}")
        connection.rollback()
        return False

def train_model(capture_id):
    """
    모의 학습 함수 - 실제 PaddleOCR 학습 대신 시뮬레이션
    TODO: 실제 PaddleOCR 파인튜닝으로 교체 필요
    """
    logger.debug(f"  🎓 학습 시뮬레이션 실행 (Capture ID: {capture_id})...")
    time.sleep(1)  # 학습 시간 시뮬레이션

    # 랜덤 loss 생성
    loss = random.uniform(0.02, 0.10)
    return True, loss

def run_training_cycle(connection):
    """한 번의 학습 사이클 실행"""
    logger.info(f"\n{'='*80}")
    logger.info(f"🔄 학습 사이클 시작 - {datetime.now().strftime('%H:%M:%S')}")

    # 배치 ID 생성 (이번 사이클의 모든 학습에 동일한 ID 사용)
    batch_id = f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"📦 Batch ID: {batch_id}")

    # 학습 데이터 조회
    training_data = get_training_data(connection, limit=6)

    if len(training_data) < 6:
        logger.warning(f"⚠️ 학습 데이터 부족: {len(training_data)}개 (최소 6개 필요)")
        return 0

    # 각 데이터에 대해 학습 실행
    success_count = 0
    for idx, (capture_id, image_path, bbox_count) in enumerate(training_data, 1):
        logger.info(f"\n[{idx}/{len(training_data)}] Capture ID: {capture_id}")
        logger.info(f"  이미지: {image_path}, 텍스트 박스: {bbox_count}개")

        try:
            # 학습 실행
            success, loss = train_model(capture_id)

            # 결과 저장 (동일한 batch_id 사용)
            if save_training_result(connection, capture_id, success, loss, batch_id):
                success_count += 1

        except Exception as e:
            logger.error(f"  ❌ 학습 실패: {e}")
            save_training_result(connection, capture_id, False, None, batch_id)

    logger.info(f"\n✅ 학습 사이클 완료: {success_count}/{len(training_data)} 성공")
    return success_count

def main():
    """메인 실행 함수"""
    connection = connect_oracle()
    if not connection:
        logger.error("❌ 데이터베이스 연결 실패 - 종료합니다")
        sys.exit(1)

    try:
        iteration = 0
        while True:
            iteration += 1
            logger.info(f"\n{'#'*80}")
            logger.info(f"# Iteration {iteration}")
            logger.info(f"{'#'*80}")

            success_count = run_training_cycle(connection)

            # 10초 대기
            logger.info(f"\n⏳ 다음 학습까지 10초 대기...")
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info(f"\n\n{'='*80}")
        logger.info(f"🛑 사용자에 의해 중지됨")
        logger.info(f"{'='*80}")
    except Exception as e:
        logger.error(f"\n❌ 오류 발생: {e}", exc_info=True)
    finally:
        if connection:
            connection.close()
            logger.info(f"✅ 데이터베이스 연결 종료")

if __name__ == "__main__":
    main()
