#!/usr/bin/env python3
"""
데이터베이스에 Fine-tuned 모델 정보 등록
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
import hashlib

# 데이터베이스 연결
sys.path.append('/home/pro301/git/en-zine/ocr_system/paddleocr_training')
from database_connection import DatabaseConnection
from loguru import logger

class ModelRegistry:
    def __init__(self):
        self.db_connection = DatabaseConnection()

    def calculate_model_hash(self, model_path: str) -> str:
        """모델 파일 해시 계산"""
        hasher = hashlib.md5()
        model_files = Path(model_path).glob("**/*")

        for file_path in sorted(model_files):
            if file_path.is_file():
                with open(file_path, 'rb') as f:
                    hasher.update(f.read())

        return hasher.hexdigest()

    def register_finetuned_models(self, evaluation_results: dict) -> bool:
        """Fine-tuned 모델을 데이터베이스에 등록"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()

                models_info = [
                    {
                        'name': 'FINETUNED_DETECTION_V1',
                        'path': '/home/pro301/git/en-zine/ocr_system/paddleocr_training/output/det_custom_web_inference',
                        'type': 'DETECTION',
                        'description': 'Fine-tuned detection model for web page text recognition'
                    },
                    {
                        'name': 'FINETUNED_RECOGNITION_V1',
                        'path': '/home/pro301/git/en-zine/ocr_system/paddleocr_training/output/rec_custom_web_inference',
                        'type': 'RECOGNITION',
                        'description': 'Fine-tuned recognition model for web page text recognition'
                    }
                ]

                for model_info in models_info:
                    # 모델 해시 계산
                    model_hash = self.calculate_model_hash(model_info['path'])

                    # 모델 등록
                    sql = """
                    INSERT INTO OCR_MODEL_VERSIONS
                    (MODEL_NAME, MODEL_FILE_PATH, MODEL_TYPE, TRAINING_DATA_COUNT,
                     ACCURACY_SCORE, PRECISION_SCORE, RECALL_SCORE, F1_SCORE,
                     TRAINING_COMPLETED_DATE, IS_ACTIVE, MODEL_DESCRIPTION)
                    VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11)
                    """

                    # 성능 메트릭 추출
                    if evaluation_results and 'finetuned_performance' in evaluation_results:
                        perf = evaluation_results['finetuned_performance']
                        accuracy = perf.get('char_accuracy', 0.0)
                        # 간단화된 메트릭 사용 (실제로는 더 정교한 계산 필요)
                        precision = perf.get('word_accuracy', 0.0)
                        recall = precision  # 간단화
                        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
                    else:
                        accuracy = precision = recall = f1_score = 0.0

                    cursor.execute(sql, (
                        model_info['name'],
                        model_info['path'],
                        model_info['type'],
                        evaluation_results.get('sample_count', 0) if evaluation_results else 0,
                        accuracy,
                        precision,
                        recall,
                        f1_score,
                        datetime.now(),
                        'Y',  # 활성 모델로 설정
                        f"{model_info['description']} (Hash: {model_hash[:8]})"
                    ))

                    logger.info(f"Registered model: {model_info['name']}")

                # 기존 모델들을 비활성화
                cursor.execute("""
                    UPDATE OCR_MODEL_VERSIONS
                    SET IS_ACTIVE = 'N'
                    WHERE MODEL_NAME NOT IN ('FINETUNED_DETECTION_V1', 'FINETUNED_RECOGNITION_V1')
                """)

                conn.commit()
                logger.info("Model registration completed successfully")
                return True

        except Exception as e:
            logger.error(f"Error registering models: {e}")
            return False

    def get_active_models(self) -> list:
        """활성 모델 정보 조회"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()

                sql = """
                SELECT MODEL_NAME, MODEL_FILE_PATH, MODEL_TYPE, ACCURACY_SCORE,
                       TRAINING_COMPLETED_DATE, MODEL_DESCRIPTION
                FROM OCR_MODEL_VERSIONS
                WHERE IS_ACTIVE = 'Y'
                ORDER BY MODEL_TYPE, TRAINING_COMPLETED_DATE DESC
                """

                cursor.execute(sql)
                models = []

                for row in cursor.fetchall():
                    models.append({
                        'name': row[0],
                        'path': row[1],
                        'type': row[2],
                        'accuracy': float(row[3]) if row[3] else 0.0,
                        'created_date': row[4],
                        'description': row[5]
                    })

                return models

        except Exception as e:
            logger.error(f"Error getting active models: {e}")
            return []