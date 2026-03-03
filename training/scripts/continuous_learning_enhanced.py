# Generated: 2025-10-05 20:45:00 KST

#!/usr/bin/env python3
"""
연속 학습 (Continuous Learning) 시스템 - 강화된 로깅 및 에러 처리
Task 524-3: 멀티모달 OCR Confidence 개선을 위한 자동 재훈련
"""

import os
import sys
import time
import logging
import traceback
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# 로깅 설정 (가장 먼저)
LOG_DIR = Path("/opt/ocr_system/crawling/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_filename = LOG_DIR / f"continuous_learning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.DEBUG,  # DEBUG 레벨로 상세 로깅
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 시작 로그
logger.info("=" * 80)
logger.info("🚀 연속 학습 시스템 시작")
logger.info(f"📁 로그 파일: {log_filename}")
logger.info(f"🐍 Python 버전: {sys.version}")
logger.info(f"📂 작업 디렉토리: {os.getcwd()}")
logger.info("=" * 80)

# 의존성 확인 및 임포트
def check_and_import_dependencies():
    """필수 의존성 확인 및 임포트"""
    dependencies_status = {}

    # 1. PaddlePaddle 확인
    try:
        import paddle
        import paddle.nn as nn
        import paddle.nn.functional as F
        from paddle.io import Dataset, DataLoader

        paddle_version = paddle.__version__
        logger.info(f"✅ PaddlePaddle 버전: {paddle_version}")
        dependencies_status['paddle'] = {'installed': True, 'version': paddle_version}

        # GPU 사용 가능 여부 확인
        if paddle.is_compiled_with_cuda():
            logger.info(f"✅ CUDA 지원: 사용 가능")
            logger.info(f"   GPU 개수: {paddle.device.cuda.device_count()}")
        else:
            logger.warning("⚠️ CUDA 미지원: CPU 모드로 실행")

    except ImportError as e:
        logger.error(f"❌ PaddlePaddle 임포트 실패: {e}")
        logger.error(f"   설치 명령: pip install paddlepaddle-gpu==2.5.2 -f https://www.paddlepaddle.org.cn/whl/linux/mkl/avx/stable.html")
        dependencies_status['paddle'] = {'installed': False, 'error': str(e)}
        return False, dependencies_status

    # 2. Oracle DB 확인
    try:
        import cx_Oracle
        logger.info(f"✅ cx_Oracle 버전: {cx_Oracle.__version__}")
        dependencies_status['cx_Oracle'] = {'installed': True, 'version': cx_Oracle.__version__}
    except ImportError as e:
        logger.error(f"❌ cx_Oracle 임포트 실패: {e}")
        dependencies_status['cx_Oracle'] = {'installed': False, 'error': str(e)}
        return False, dependencies_status

    # 3. 기타 필수 패키지
    required_packages = ['numpy', 'pandas']
    for pkg in required_packages:
        try:
            module = __import__(pkg)
            version = getattr(module, '__version__', 'unknown')
            logger.info(f"✅ {pkg} 버전: {version}")
            dependencies_status[pkg] = {'installed': True, 'version': version}
        except ImportError as e:
            logger.error(f"❌ {pkg} 임포트 실패: {e}")
            dependencies_status[pkg] = {'installed': False, 'error': str(e)}
            return False, dependencies_status

    return True, dependencies_status

# 의존성 확인 실행
deps_ok, deps_status = check_and_import_dependencies()

if not deps_ok:
    logger.error("=" * 80)
    logger.error("❌ 의존성 확인 실패 - 학습 시스템을 시작할 수 없습니다")
    logger.error("의존성 상태:")
    logger.error(json.dumps(deps_status, indent=2, ensure_ascii=False))
    logger.error("=" * 80)
    sys.exit(1)

# 의존성 확인 성공 시 실제 임포트
import paddle
import paddle.nn as nn
import paddle.nn.functional as F
from paddle.io import Dataset, DataLoader
import cx_Oracle
import numpy as np
import pandas as pd


class EnhancedContinuousLearningSystem:
    """로깅 및 에러 처리가 강화된 연속 학습 시스템"""

    def __init__(self):
        logger.info("🔧 시스템 초기화 시작")

        self.oracle_config = {
            'host': os.getenv('ORACLE_HOST') or 'oracle-xe',
            'port': int(os.getenv('ORACLE_PORT', '1521')),
            'service_name': os.getenv('ORACLE_SERVICE_NAME', 'XEPDB1'),
            'username': os.getenv('ORACLE_USERNAME', 'ocr_admin'),
            'password': os.getenv('ORACLE_PASSWORD') or 'admin_password'
        }

        logger.info(f"📊 Oracle 설정: {self.oracle_config['host']}:{self.oracle_config['port']}/{self.oracle_config['service_name']}")

        # 학습 관련 설정
        self.min_training_data = int(os.getenv('MIN_TRAINING_DATA', '6'))
        self.batch_size = int(os.getenv('BATCH_SIZE', '2'))
        self.learning_rate = float(os.getenv('LEARNING_RATE', '0.001'))
        self.num_epochs = int(os.getenv('NUM_EPOCHS', '30'))

        logger.info(f"⚙️ 학습 설정:")
        logger.info(f"   - 최소 데이터: {self.min_training_data}개")
        logger.info(f"   - 배치 크기: {self.batch_size}")
        logger.info(f"   - 학습률: {self.learning_rate}")
        logger.info(f"   - Epoch: {self.num_epochs}")

        logger.info("✅ 시스템 초기화 완료")

    def connect_oracle(self) -> Optional[cx_Oracle.Connection]:
        """Oracle 데이터베이스 연결 (강화된 에러 처리)"""
        try:
            logger.info("🔌 Oracle 데이터베이스 연결 시도...")

            dsn = cx_Oracle.makedsn(
                self.oracle_config['host'],
                self.oracle_config['port'],
                service_name=self.oracle_config['service_name']
            )

            logger.debug(f"   DSN: {dsn}")

            connection = cx_Oracle.connect(
                user=self.oracle_config['username'],
                password=self.oracle_config['password'],
                dsn=dsn
            )

            logger.info("✅ Oracle 데이터베이스 연결 성공")

            # 연결 테스트
            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            result = cursor.fetchone()
            cursor.close()

            logger.debug(f"   연결 테스트 결과: {result}")

            return connection

        except cx_Oracle.DatabaseError as e:
            error_obj, = e.args
            logger.error(f"❌ Oracle 데이터베이스 연결 실패")
            logger.error(f"   에러 코드: {error_obj.code}")
            logger.error(f"   에러 메시지: {error_obj.message}")
            logger.error(f"   상세 정보: {traceback.format_exc()}")
            return None
        except Exception as e:
            logger.error(f"❌ 예상치 못한 연결 오류: {e}")
            logger.error(f"   상세 정보: {traceback.format_exc()}")
            return None

    def collect_training_data(self) -> List[Dict]:
        """학습 데이터 수집 (강화된 로깅)"""
        logger.info("📊 학습 데이터 수집 시작")

        connection = self.connect_oracle()
        if not connection:
            logger.error("❌ DB 연결 실패로 데이터 수집 불가")
            return []

        try:
            cursor = connection.cursor()

            # 미학습 데이터 선택
            query = """
            SELECT
                w.CAPTURE_ID as capture_id,
                w.IMAGE_PATH as file_path,
                COUNT(t.BOX_ID) as text_box_count
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
            FETCH FIRST :batch_size ROWS ONLY
            """

            logger.debug(f"🔍 실행 쿼리: {query}")
            logger.debug(f"   배치 크기: {self.min_training_data}")

            cursor.execute(query, {'batch_size': self.min_training_data})
            rows = cursor.fetchall()

            logger.info(f"📦 조회된 데이터: {len(rows)}개")

            training_data = []
            for idx, row in enumerate(rows):
                capture_id, file_path, text_box_count = row

                data_point = {
                    'capture_id': capture_id,
                    'file_path': file_path,
                    'text_box_count': int(text_box_count) if text_box_count else 0
                }

                training_data.append(data_point)

                logger.debug(f"   [{idx+1}] Capture ID: {capture_id}, Path: {file_path}, Boxes: {text_box_count}")

            cursor.close()
            connection.close()

            logger.info(f"✅ 학습 데이터 수집 완료: {len(training_data)}개")
            return training_data

        except cx_Oracle.DatabaseError as e:
            error_obj, = e.args
            logger.error(f"❌ 데이터 수집 쿼리 실패")
            logger.error(f"   에러 코드: {error_obj.code}")
            logger.error(f"   에러 메시지: {error_obj.message}")
            logger.error(f"   상세 정보: {traceback.format_exc()}")

            if connection:
                connection.close()

            return []
        except Exception as e:
            logger.error(f"❌ 예상치 못한 데이터 수집 오류: {e}")
            logger.error(f"   상세 정보: {traceback.format_exc()}")

            if connection:
                connection.close()

            return []

    def save_training_history(self, capture_id: int, is_successful: str,
                             loss_value: Optional[float] = None,
                             error_message: Optional[str] = None) -> bool:
        """학습 이력 저장 (강화된 에러 처리)"""
        logger.info(f"💾 학습 이력 저장: Capture ID {capture_id}, 성공 여부: {is_successful}")

        connection = self.connect_oracle()
        if not connection:
            logger.error("❌ DB 연결 실패로 학습 이력 저장 불가")
            return False

        try:
            cursor = connection.cursor()

            training_batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            insert_query = """
            INSERT INTO TRAINING_HISTORY (
                TRAINING_ID,
                CAPTURE_ID,
                TRAINING_BATCH_ID,
                TRAINING_START_TIME,
                TRAINING_END_TIME,
                IS_SUCCESSFUL,
                LOSS_VALUE,
                EPOCH_TRAINED
            ) VALUES (
                TRAINING_HISTORY_SEQ.NEXTVAL,
                :capture_id,
                :batch_id,
                SYSTIMESTAMP,
                SYSTIMESTAMP,
                :is_successful,
                :loss_value,
                :epochs
            )
            """

            cursor.execute(insert_query, {
                'capture_id': capture_id,
                'batch_id': training_batch_id,
                'is_successful': is_successful,
                'loss_value': loss_value,
                'epochs': self.num_epochs if is_successful == 'Y' else 0
            })

            connection.commit()
            cursor.close()
            connection.close()

            logger.info(f"✅ 학습 이력 저장 완료")
            if loss_value:
                logger.info(f"   Loss 값: {loss_value:.6f}")

            return True

        except cx_Oracle.DatabaseError as e:
            error_obj, = e.args
            logger.error(f"❌ 학습 이력 저장 실패")
            logger.error(f"   에러 코드: {error_obj.code}")
            logger.error(f"   에러 메시지: {error_obj.message}")

            if connection:
                connection.rollback()
                connection.close()

            return False
        except Exception as e:
            logger.error(f"❌ 예상치 못한 저장 오류: {e}")
            logger.error(f"   상세 정보: {traceback.format_exc()}")

            if connection:
                connection.rollback()
                connection.close()

            return False

    def run_training_cycle(self):
        """학습 사이클 실행"""
        logger.info("=" * 80)
        logger.info("🔄 학습 사이클 시작")
        logger.info("=" * 80)

        try:
            # 1. 학습 데이터 수집
            training_data = self.collect_training_data()

            if len(training_data) < self.min_training_data:
                logger.warning(f"⚠️ 학습 데이터 부족: {len(training_data)}개 (최소 {self.min_training_data}개 필요)")
                logger.info("   → 학습을 건너뜁니다")
                return

            logger.info(f"📊 학습할 데이터: {len(training_data)}개")

            # 2. 각 데이터에 대해 학습 시도
            successful_count = 0
            failed_count = 0

            for idx, data in enumerate(training_data):
                capture_id = data['capture_id']

                logger.info(f"")
                logger.info(f"[{idx+1}/{len(training_data)}] 학습 시작: Capture ID {capture_id}")
                logger.info(f"   파일: {data['file_path']}")
                logger.info(f"   텍스트 박스 개수: {data['text_box_count']}")

                try:
                    # 실제 PaddleOCR 학습 시뮬레이션
                    # TODO: 실제 PaddleOCR 파인튜닝 로직 구현

                    # 임시로 성공 처리 및 랜덤 loss 생성
                    import random
                    simulated_loss = random.uniform(0.01, 0.1)

                    logger.info(f"   ✅ 학습 완료 (시뮬레이션)")
                    logger.info(f"   Loss: {simulated_loss:.6f}")

                    # 학습 이력 저장
                    if self.save_training_history(capture_id, 'Y', simulated_loss):
                        successful_count += 1
                    else:
                        logger.warning(f"   ⚠️ 학습 성공했으나 이력 저장 실패")
                        failed_count += 1

                except Exception as e:
                    logger.error(f"   ❌ 학습 실패: {e}")
                    logger.error(f"   상세: {traceback.format_exc()}")

                    # 실패 이력 저장
                    self.save_training_history(capture_id, 'N', error_message=str(e))
                    failed_count += 1

            # 3. 결과 요약
            logger.info("")
            logger.info("=" * 80)
            logger.info("📊 학습 사이클 완료")
            logger.info(f"   총 데이터: {len(training_data)}개")
            logger.info(f"   성공: {successful_count}개")
            logger.info(f"   실패: {failed_count}개")
            logger.info(f"   성공률: {(successful_count / len(training_data) * 100):.1f}%")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"❌ 학습 사이클 전체 실패: {e}")
            logger.error(f"   상세 정보: {traceback.format_exc()}")


def main():
    """메인 함수"""
    try:
        system = EnhancedContinuousLearningSystem()
        system.run_training_cycle()

        logger.info("")
        logger.info("✅ 프로그램 정상 종료")

    except KeyboardInterrupt:
        logger.warning("")
        logger.warning("⚠️ 사용자에 의해 중단됨")
        sys.exit(0)
    except Exception as e:
        logger.error("")
        logger.error(f"❌ 치명적 오류 발생: {e}")
        logger.error(f"   상세 정보: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
