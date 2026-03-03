# Generated: 2025-10-02 22:54:00 KST
"""
Continuous Training Orchestrator - 무한 학습 자동화 시스템
"""

import cx_Oracle
import subprocess
import logging
import time
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from data_quality_evaluator import DataQualityEvaluator
from incremental_data_selector import IncrementalDataSelector
from data_cleaner import DataCleaner
from training_goals import TrainingGoals

logger = logging.getLogger(__name__)


class ContinuousTrainingOrchestrator:
    """무한 학습 자동화 오케스트레이터"""

    def __init__(self,
                 db_connection: cx_Oracle.Connection,
                 config_path: str):
        """
        Args:
            db_connection: Oracle 데이터베이스 연결
            config_path: 학습 설정 JSON 파일 경로
        """
        self.db = db_connection
        self.config = self._load_config(config_path)

        # 서브 시스템 초기화
        self.quality_evaluator = DataQualityEvaluator(db_connection)
        self.data_selector = IncrementalDataSelector(db_connection)
        self.data_cleaner = DataCleaner(db_connection)
        self.goals = TrainingGoals(db_connection)

        # 상태 추적
        self.iteration_num = 0
        self.start_time = datetime.now()
        self.hmean_history = []

    def _load_config(self, config_path: str) -> Dict:
        """설정 파일 로드"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def run_infinite_training_loop(self) -> Dict:
        """
        무한 학습 루프 실행

        Returns:
            Dict: 최종 학습 결과
        """
        logger.info("🚀 Starting Continuous Training Loop...")
        logger.info(f"Target Metrics: Precision={self.goals.TARGET_METRICS['precision']:.2%}, "
                   f"Recall={self.goals.TARGET_METRICS['recall']:.2%}, "
                   f"Hmean={self.goals.TARGET_METRICS['hmean']:.2%}")

        try:
            while True:
                self.iteration_num += 1
                iteration_start = datetime.now()

                logger.info(f"\n{'='*80}")
                logger.info(f"📊 Iteration {self.iteration_num} Started")
                logger.info(f"{'='*80}\n")

                # 1. 데이터 품질 평가
                self._run_quality_evaluation()

                # 2. 불량 데이터 정리
                self._run_data_cleanup()

                # 3. 학습 데이터 선택
                selected_data = self._select_training_data()

                if not selected_data:
                    logger.warning("⚠️ No untrained data available. Waiting for new data...")
                    time.sleep(self.config['data_cleanup']['data_check_interval_seconds'])
                    continue

                # 4. 학습 수행
                training_result = self._execute_training(selected_data)

                # 5. 모델 평가
                evaluation = self._evaluate_trained_model(training_result['model_id'])

                # 6. 반복 결과 저장
                iteration_duration = (datetime.now() - iteration_start).total_seconds() / 3600.0
                self._save_iteration_result(training_result, evaluation, iteration_duration)

                # 7. 목표 달성 확인
                if evaluation['goals_met']:
                    logger.info("🎉 Training goals achieved!")
                    return self._finalize_training(success=True, evaluation=evaluation)

                # 8. Early stopping 확인
                self.hmean_history.append(evaluation['metrics']['hmean'])
                if self.goals.check_early_stopping(self.hmean_history, evaluation['metrics']['hmean']):
                    logger.info("🛑 Early stopping triggered")
                    return self._finalize_training(success=False, evaluation=evaluation)

                # 9. 최대 제한 확인
                total_hours = (datetime.now() - self.start_time).total_seconds() / 3600.0
                limit_check = self.goals.check_max_limits_exceeded(self.iteration_num, total_hours)

                if limit_check['exceeded']:
                    logger.warning(f"⚠️ {limit_check['reason']}")
                    return self._finalize_training(success=False, evaluation=evaluation)

                # 10. 다음 반복 대기
                logger.info(f"⏸️ Waiting {self.config['training']['iteration_interval_seconds']}s before next iteration...")
                time.sleep(self.config['training']['iteration_interval_seconds'])

        except Exception as e:
            logger.error(f"❌ Training loop error: {e}")
            raise

    def _run_quality_evaluation(self) -> int:
        """데이터 품질 평가 실행"""
        logger.info("🔍 Step 1/6: Running quality evaluation...")
        evaluated_count = self.quality_evaluator.evaluate_all_pending(
            batch_size=self.config['quality']['quality_evaluation_batch_size']
        )
        logger.info(f"✅ Evaluated {evaluated_count} samples")
        return evaluated_count

    def _run_data_cleanup(self) -> Dict:
        """불량 데이터 정리 실행"""
        logger.info("🧹 Step 2/6: Cleaning up invalid data...")
        cleanup_results = self.data_cleaner.run_all_cleanup(
            min_quality=self.config['quality']['min_quality_score'],
            max_failures=self.config['quality']['max_training_failures'],
            days_to_keep=self.config['quality']['data_retention_days']
        )
        logger.info(f"✅ Cleaned {cleanup_results['total_deleted']} samples")
        return cleanup_results

    def _select_training_data(self) -> List[int]:
        """학습 데이터 선택"""
        logger.info("📋 Step 3/6: Selecting untrained data...")
        selected = self.data_selector.get_untrained_data(
            batch_size=self.config['training']['training_batch_size'],
            min_quality_score=self.config['quality']['min_quality_score'],
            min_bbox_count=self.config['training']['min_bbox_count']
        )
        logger.info(f"✅ Selected {len(selected)} samples for training")
        return selected

    def _execute_training(self, capture_ids: List[int]) -> Dict:
        """
        PaddleOCR 학습 실행

        Args:
            capture_ids: 학습할 데이터 ID 리스트

        Returns:
            Dict: {'model_id': int, 'metrics': Dict}
        """
        logger.info("🎓 Step 4/6: Executing PaddleOCR training...")

        # 배치 ID 생성
        batch_id = f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 학습 시작 기록
        self.data_selector.mark_training_started(capture_ids, batch_id)

        # PaddleOCR 학습 스크립트 실행
        training_script = Path(self.config['training']['training_script_path'])
        config_file = Path(self.config['training']['training_config_path'])

        cmd = [
            'python3.9',
            str(training_script),
            '-c', str(config_file),
            '-o', f'Global.epoch_num={self.config["training"]["epochs_per_iteration"]}',
            '-o', 'Global.use_gpu=False'  # Changed to False - RTX 5070 Ti (Compute 12.0) not supported
        ]

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid UTF-8 bytes with replacement character
                timeout=self.config['training']['training_timeout_seconds']
            )

            if result.returncode != 0:
                logger.error(f"Training failed: {result.stderr}")
                self.data_selector.mark_training_completed(
                    capture_ids, batch_id, is_successful=False
                )
                raise RuntimeError(f"Training process failed: {result.stderr}")

            # 학습 로그에서 메트릭 추출
            metrics = self._parse_training_log(result.stdout)

            # 학습 완료 기록
            self.data_selector.mark_training_completed(
                capture_ids,
                batch_id,
                is_successful=True,
                loss_value=metrics.get('loss'),
                epoch_trained=self.config['training']['epochs_per_iteration']
            )

            # 새 모델 등록
            model_id = self._register_new_model(batch_id, metrics)

            logger.info(f"✅ Training completed (Model ID: {model_id})")
            return {
                'model_id': model_id,
                'metrics': metrics,
                'batch_id': batch_id
            }

        except subprocess.TimeoutExpired:
            logger.error("Training timeout exceeded")
            self.data_selector.mark_training_completed(
                capture_ids, batch_id, is_successful=False
            )
            raise

    def _parse_training_log(self, log_output: str) -> Dict:
        """학습 로그에서 메트릭 추출"""
        metrics = {
            'loss': 0.0,
            'precision': 0.0,
            'recall': 0.0,
            'hmean': 0.0
        }

        # 간단한 로그 파싱 (실제로는 더 정교한 파싱 필요)
        lines = log_output.split('\n')
        for line in lines:
            if 'loss:' in line.lower():
                try:
                    metrics['loss'] = float(line.split('loss:')[-1].strip().split()[0])
                except:
                    pass

        return metrics

    def _register_new_model(self, batch_id: str, metrics: Dict) -> int:
        """새 모델 DB 등록"""
        query = """
        INSERT INTO OCR_MODEL_VERSIONS (
            model_id, model_name, version,
            precision_score, recall_score, f1_score,
            is_production_ready, training_notes
        ) VALUES (
            OCR_MODEL_SEQ.NEXTVAL, :model_name, :version,
            :precision, :recall, :hmean,
            'N', :notes
        )
        RETURNING model_id INTO :model_id
        """

        try:
            cursor = self.db.cursor()
            model_id_var = cursor.var(int)

            cursor.execute(query, {
                'model_name': f'continuous_training_{batch_id}',
                'version': f'v{self.iteration_num}',
                'precision': metrics.get('precision', 0.0),
                'recall': metrics.get('recall', 0.0),
                'hmean': metrics.get('hmean', 0.0),
                'notes': f'Iteration {self.iteration_num}',
                'model_id': model_id_var
            })

            self.db.commit()
            return model_id_var.getvalue()[0]

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error registering model: {e}")
            raise

    def _evaluate_trained_model(self, model_id: int) -> Dict:
        """학습된 모델 평가"""
        logger.info("📈 Step 5/6: Evaluating trained model...")
        evaluation = self.goals.evaluate_current_model(model_id)

        logger.info(f"Precision: {evaluation['metrics']['precision']:.4f} "
                   f"(Gap: {evaluation['gaps']['precision']:+.4f})")
        logger.info(f"Recall: {evaluation['metrics']['recall']:.4f} "
                   f"(Gap: {evaluation['gaps']['recall']:+.4f})")
        logger.info(f"Hmean: {evaluation['metrics']['hmean']:.4f} "
                   f"(Gap: {evaluation['gaps']['hmean']:+.4f})")
        logger.info(f"Overall Progress: {evaluation['overall_progress']:.1%}")

        return evaluation

    def _save_iteration_result(self,
                               training_result: Dict,
                               evaluation: Dict,
                               duration_hours: float) -> None:
        """반복 결과 저장"""
        logger.info("💾 Step 6/6: Saving iteration results...")
        self.goals.save_training_iteration_result(
            iteration_num=self.iteration_num,
            model_id=training_result['model_id'],
            metrics=evaluation['metrics'],
            training_duration_hours=duration_hours
        )
        logger.info("✅ Iteration results saved")

    def _finalize_training(self, success: bool, evaluation: Dict) -> Dict:
        """학습 종료 처리"""
        logger.info(f"\n{'='*80}")
        logger.info("🏁 Continuous Training Completed")
        logger.info(f"{'='*80}\n")

        summary = self.goals.get_training_summary()

        logger.info(f"Total Iterations: {summary['total_iterations']}")
        logger.info(f"Best Hmean: {summary['best_hmean']:.4f}")
        logger.info(f"Total Duration: {summary['total_duration_hours']:.2f} hours")
        logger.info(f"Successful Iterations: {summary['successful_iterations']}")

        if success:
            logger.info("🎉 Training goals achieved!")
        else:
            logger.info("⚠️ Training stopped without achieving goals")

        return {
            'success': success,
            'final_evaluation': evaluation,
            'summary': summary
        }
