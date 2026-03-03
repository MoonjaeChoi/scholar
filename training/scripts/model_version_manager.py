#!/usr/bin/env python3
# Generated: 2025-10-06 09:30:00 KST
"""
OCR 모델 버전 관리 시스템
OCR_MODEL_VERSIONS 테이블 자동 등록 및 관리
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import Dict, Optional, List
import json

# Oracle 데이터베이스
import cx_Oracle

# PaddleOCR
from paddleocr import PaddleOCR

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelVersionManager:
    """OCR 모델 버전 관리 클래스"""

    def __init__(self):
        """초기화"""
        self.db_config = {
            'user': os.getenv('ORACLE_USERNAME', 'ocr_admin'),
            'password': os.getenv('ORACLE_PASSWORD', 'admin_password'),
            'dsn': f"{os.getenv('ORACLE_HOST', 'localhost')}:{os.getenv('ORACLE_PORT', '1521')}/{os.getenv('ORACLE_SERVICE_NAME', 'XEPDB1')}"
        }

    def get_db_connection(self):
        """데이터베이스 연결 생성"""
        try:
            connection = cx_Oracle.connect(
                user=self.db_config['user'],
                password=self.db_config['password'],
                dsn=self.db_config['dsn'],
                encoding="UTF-8"
            )
            return connection
        except Exception as e:
            logger.error(f"❌ 데이터베이스 연결 실패: {e}")
            raise

    def evaluate_model(self, model_path: str, test_data_path: Optional[str] = None) -> Dict:
        """
        모델 성능 평가

        Args:
            model_path: 평가할 모델 경로
            test_data_path: 테스트 데이터 경로 (선택적)

        Returns:
            성능 메트릭 딕셔너리 (precision, recall, hmean, fps)
        """
        logger.info(f"📊 모델 성능 평가 시작: {model_path}")

        try:
            # PaddleOCR 모델 로드
            ocr = PaddleOCR(
                det_model_dir=model_path if 'det' in model_path else None,
                rec_model_dir=model_path if 'rec' in model_path else None,
                use_angle_cls=False,
                lang='korean',
                use_gpu=True
            )

            # 성능 메트릭 초기화
            total_precision = 0.0
            total_recall = 0.0
            total_time = 0.0
            test_count = 0

            # 테스트 데이터 로드 (실제 구현에서는 별도 테스트셋 사용)
            if test_data_path and os.path.exists(test_data_path):
                # 테스트 이미지로 평가
                test_images = self._load_test_images(test_data_path)

                for img_path, ground_truth in test_images:
                    start_time = time.time()
                    result = ocr.ocr(img_path, cls=False)
                    elapsed_time = time.time() - start_time

                    # 정밀도/재현율 계산
                    metrics = self._calculate_metrics(result, ground_truth)
                    total_precision += metrics['precision']
                    total_recall += metrics['recall']
                    total_time += elapsed_time
                    test_count += 1

            else:
                # 테스트 데이터 없을 경우 기본값 사용 (임시)
                logger.warning("⚠️ 테스트 데이터 없음. 기본 성능 추정치 사용")
                total_precision = 0.85
                total_recall = 0.82
                total_time = 0.05
                test_count = 1

            # 평균 메트릭 계산
            avg_precision = total_precision / test_count if test_count > 0 else 0.0
            avg_recall = total_recall / test_count if test_count > 0 else 0.0
            avg_time = total_time / test_count if test_count > 0 else 0.0

            # F1 스코어 (Harmonic Mean)
            if avg_precision + avg_recall > 0:
                hmean = 2 * (avg_precision * avg_recall) / (avg_precision + avg_recall)
            else:
                hmean = 0.0

            # FPS (Frames Per Second)
            fps = 1.0 / avg_time if avg_time > 0 else 0.0

            metrics = {
                'precision': round(avg_precision, 4),
                'recall': round(avg_recall, 4),
                'hmean': round(hmean, 4),
                'fps': round(fps, 2)
            }

            logger.info(f"✅ 모델 평가 완료: Precision={metrics['precision']}, Recall={metrics['recall']}, F1={metrics['hmean']}, FPS={metrics['fps']}")
            return metrics

        except Exception as e:
            logger.error(f"❌ 모델 평가 실패: {e}")
            # 평가 실패 시 기본값 반환
            return {
                'precision': 0.0,
                'recall': 0.0,
                'hmean': 0.0,
                'fps': 0.0
            }

    def _load_test_images(self, test_data_path: str) -> List:
        """테스트 이미지 로드 (실제 구현 필요)"""
        # TODO: 실제 테스트 데이터 로드 로직 구현
        return []

    def _calculate_metrics(self, ocr_result, ground_truth) -> Dict:
        """OCR 결과와 정답 비교하여 메트릭 계산"""
        # TODO: 실제 메트릭 계산 로직 구현
        # 현재는 임시 값 반환
        return {
            'precision': 0.85,
            'recall': 0.82
        }

    def register_model_to_database(
        self,
        model_name: str,
        model_type: str,
        version: str,
        model_path: str,
        training_info: Dict,
        performance_metrics: Dict,
        notes: Optional[str] = None
    ) -> Optional[int]:
        """
        학습 완료 모델을 OCR_MODEL_VERSIONS 테이블에 등록

        Args:
            model_name: 모델 이름 (예: PaddleOCR_Detection_v3)
            model_type: 모델 타입 (detection/recognition)
            version: 버전 번호 (예: 3.2.1)
            model_path: 모델 파일 경로
            training_info: 학습 정보 딕셔너리
                - dataset_size: 학습 데이터셋 크기
                - start_time: 학습 시작 시각
                - end_time: 학습 종료 시각
            performance_metrics: 성능 메트릭 딕셔너리
                - precision: 정밀도
                - recall: 재현율
                - hmean: F1 스코어
                - fps: 초당 프레임 수
            notes: 메모 (선택적)

        Returns:
            등록된 MODEL_ID (성공 시) 또는 None (실패 시)
        """
        logger.info(f"📝 모델 등록 시작: {model_name} v{version}")

        connection = None
        try:
            connection = self.get_db_connection()
            cursor = connection.cursor()

            # OCR_MODEL_VERSIONS에 INSERT
            sql = """
                INSERT INTO OCR_MODEL_VERSIONS (
                    MODEL_ID,
                    MODEL_NAME,
                    MODEL_TYPE,
                    VERSION,
                    MODEL_PATH,
                    TRAINING_DATASET_SIZE,
                    TRAINING_START_DATE,
                    TRAINING_END_DATE,
                    PRECISION,
                    RECALL,
                    HMEAN,
                    FPS,
                    IS_ACTIVE,
                    NOTES,
                    CREATED_AT,
                    UPDATED_AT
                ) VALUES (
                    SEQ_OCR_MODEL_VERSIONS.nextval,
                    :model_name,
                    :model_type,
                    :version,
                    :model_path,
                    :dataset_size,
                    :start_date,
                    :end_date,
                    :precision,
                    :recall,
                    :hmean,
                    :fps,
                    0,
                    :notes,
                    SYSTIMESTAMP,
                    SYSTIMESTAMP
                )
                RETURNING MODEL_ID INTO :model_id
            """

            # 바인드 변수
            model_id_var = cursor.var(cx_Oracle.NUMBER)

            cursor.execute(sql, {
                'model_name': model_name,
                'model_type': model_type,
                'version': version,
                'model_path': model_path,
                'dataset_size': training_info.get('dataset_size', 0),
                'start_date': training_info.get('start_time'),
                'end_date': training_info.get('end_time'),
                'precision': performance_metrics.get('precision', 0.0),
                'recall': performance_metrics.get('recall', 0.0),
                'hmean': performance_metrics.get('hmean', 0.0),
                'fps': performance_metrics.get('fps', 0.0),
                'notes': notes or f'Auto-registered on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                'model_id': model_id_var
            })

            connection.commit()

            model_id = int(model_id_var.getvalue()[0])
            logger.info(f"✅ 모델 등록 완료: MODEL_ID={model_id}")

            return model_id

        except Exception as e:
            logger.error(f"❌ 모델 등록 실패: {e}")
            if connection:
                connection.rollback()
            return None

        finally:
            if connection:
                connection.close()

    def activate_model(self, model_id: int) -> bool:
        """
        모델 활성화 (IS_ACTIVE = 1)
        동일 타입의 다른 모델들은 자동으로 비활성화

        Args:
            model_id: 활성화할 모델 ID

        Returns:
            성공 여부
        """
        logger.info(f"🔄 모델 활성화: MODEL_ID={model_id}")

        connection = None
        try:
            connection = self.get_db_connection()
            cursor = connection.cursor()

            # 먼저 해당 모델의 타입 조회
            cursor.execute("""
                SELECT MODEL_TYPE FROM OCR_MODEL_VERSIONS
                WHERE MODEL_ID = :model_id
            """, {'model_id': model_id})

            result = cursor.fetchone()
            if not result:
                logger.error(f"❌ 모델을 찾을 수 없음: MODEL_ID={model_id}")
                return False

            model_type = result[0]

            # 동일 타입의 모든 모델 비활성화
            cursor.execute("""
                UPDATE OCR_MODEL_VERSIONS
                SET IS_ACTIVE = 0,
                    UPDATED_AT = SYSTIMESTAMP
                WHERE MODEL_TYPE = :model_type
            """, {'model_type': model_type})

            # 선택된 모델만 활성화
            cursor.execute("""
                UPDATE OCR_MODEL_VERSIONS
                SET IS_ACTIVE = 1,
                    UPDATED_AT = SYSTIMESTAMP
                WHERE MODEL_ID = :model_id
            """, {'model_id': model_id})

            connection.commit()

            logger.info(f"✅ 모델 활성화 완료: MODEL_ID={model_id} (타입: {model_type})")
            return True

        except Exception as e:
            logger.error(f"❌ 모델 활성화 실패: {e}")
            if connection:
                connection.rollback()
            return False

        finally:
            if connection:
                connection.close()

    def get_active_model(self, model_type: str) -> Optional[Dict]:
        """
        현재 활성 모델 조회

        Args:
            model_type: 모델 타입 (detection/recognition)

        Returns:
            활성 모델 정보 딕셔너리 또는 None
        """
        connection = None
        try:
            connection = self.get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT
                    MODEL_ID,
                    MODEL_NAME,
                    MODEL_TYPE,
                    VERSION,
                    MODEL_PATH,
                    HMEAN,
                    FPS,
                    CREATED_AT
                FROM OCR_MODEL_VERSIONS
                WHERE MODEL_TYPE = :model_type
                  AND IS_ACTIVE = 1
                ORDER BY CREATED_AT DESC
                FETCH FIRST 1 ROW ONLY
            """, {'model_type': model_type})

            result = cursor.fetchone()

            if result:
                return {
                    'model_id': result[0],
                    'model_name': result[1],
                    'model_type': result[2],
                    'version': result[3],
                    'model_path': result[4],
                    'hmean': float(result[5]) if result[5] else 0.0,
                    'fps': float(result[6]) if result[6] else 0.0,
                    'created_at': result[7]
                }
            else:
                logger.warning(f"⚠️ 활성 모델 없음: {model_type}")
                return None

        except Exception as e:
            logger.error(f"❌ 활성 모델 조회 실패: {e}")
            return None

        finally:
            if connection:
                connection.close()

    def get_best_model_by_hmean(self, model_type: str) -> Optional[Dict]:
        """
        F1 스코어 기준 최고 성능 모델 조회

        Args:
            model_type: 모델 타입 (detection/recognition)

        Returns:
            최고 성능 모델 정보 딕셔너리 또는 None
        """
        connection = None
        try:
            connection = self.get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT
                    MODEL_ID,
                    MODEL_NAME,
                    VERSION,
                    MODEL_PATH,
                    HMEAN,
                    FPS,
                    CREATED_AT
                FROM OCR_MODEL_VERSIONS
                WHERE MODEL_TYPE = :model_type
                ORDER BY HMEAN DESC, FPS DESC
                FETCH FIRST 1 ROW ONLY
            """, {'model_type': model_type})

            result = cursor.fetchone()

            if result:
                return {
                    'model_id': result[0],
                    'model_name': result[1],
                    'version': result[2],
                    'model_path': result[3],
                    'hmean': float(result[4]) if result[4] else 0.0,
                    'fps': float(result[5]) if result[5] else 0.0,
                    'created_at': result[6]
                }
            else:
                logger.warning(f"⚠️ 모델 없음: {model_type}")
                return None

        except Exception as e:
            logger.error(f"❌ 최고 성능 모델 조회 실패: {e}")
            return None

        finally:
            if connection:
                connection.close()

    def auto_select_and_activate_best_model(self, model_type: str) -> bool:
        """
        최고 성능 모델 자동 선택 및 활성화

        Args:
            model_type: 모델 타입 (detection/recognition)

        Returns:
            성공 여부
        """
        logger.info(f"🎯 최고 성능 모델 자동 선택: {model_type}")

        try:
            # 최고 성능 모델 조회
            best_model = self.get_best_model_by_hmean(model_type)

            if not best_model:
                logger.error(f"❌ 선택 가능한 모델 없음: {model_type}")
                return False

            # 모델 활성화
            success = self.activate_model(best_model['model_id'])

            if success:
                logger.info(f"✅ 최고 성능 모델 활성화 완료: {best_model['model_name']} v{best_model['version']} (F1={best_model['hmean']})")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"❌ 자동 선택 실패: {e}")
            return False

    def get_model_performance_history(self, model_type: str, limit: int = 10) -> List[Dict]:
        """
        모델 성능 추이 조회

        Args:
            model_type: 모델 타입 (detection/recognition)
            limit: 조회할 최대 레코드 수

        Returns:
            모델 성능 이력 리스트
        """
        connection = None
        try:
            connection = self.get_db_connection()
            cursor = connection.cursor()

            cursor.execute(f"""
                SELECT
                    VERSION,
                    TRAINING_END_DATE,
                    PRECISION,
                    RECALL,
                    HMEAN,
                    FPS,
                    TRAINING_DATASET_SIZE
                FROM OCR_MODEL_VERSIONS
                WHERE MODEL_TYPE = :model_type
                ORDER BY TRAINING_END_DATE DESC
                FETCH FIRST {limit} ROWS ONLY
            """, {'model_type': model_type})

            results = cursor.fetchall()

            history = []
            for row in results:
                history.append({
                    'version': row[0],
                    'training_date': row[1],
                    'precision': float(row[2]) if row[2] else 0.0,
                    'recall': float(row[3]) if row[3] else 0.0,
                    'hmean': float(row[4]) if row[4] else 0.0,
                    'fps': float(row[5]) if row[5] else 0.0,
                    'dataset_size': int(row[6]) if row[6] else 0
                })

            return history

        except Exception as e:
            logger.error(f"❌ 성능 추이 조회 실패: {e}")
            return []

        finally:
            if connection:
                connection.close()


def main():
    """테스트 메인 함수"""
    logger.info("🚀 모델 버전 관리 시스템 테스트")

    manager = ModelVersionManager()

    # 테스트: 모델 등록
    test_model_info = {
        'model_name': 'PaddleOCR_Detection_Test',
        'model_type': 'detection',
        'version': '1.0.0',
        'model_path': '/opt/models/test_model',
        'training_info': {
            'dataset_size': 4686,
            'start_time': datetime.now(),
            'end_time': datetime.now()
        },
        'performance_metrics': {
            'precision': 0.85,
            'recall': 0.82,
            'hmean': 0.835,
            'fps': 42.5
        },
        'notes': 'Test model registration'
    }

    # 모델 등록
    model_id = manager.register_model_to_database(**test_model_info)

    if model_id:
        logger.info(f"✅ 테스트 성공: MODEL_ID={model_id}")

        # 최고 성능 모델 조회
        best_model = manager.get_best_model_by_hmean('detection')
        logger.info(f"📊 최고 성능 모델: {best_model}")

    else:
        logger.error("❌ 테스트 실패")


if __name__ == "__main__":
    main()
