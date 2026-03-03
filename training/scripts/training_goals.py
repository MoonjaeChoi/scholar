# Generated: 2025-10-02 22:53:00 KST
"""
Training Goals - 학습 목표 관리 및 달성도 평가
"""

import cx_Oracle
from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TrainingGoals:
    """학습 목표 정의 및 달성도 평가"""

    # 최종 목표 지표
    TARGET_METRICS = {
        'precision': 0.95,     # 95% 정밀도
        'recall': 0.92,        # 92% 재현율
        'hmean': 0.93,         # 93% F1-score
        'fps': 30.0            # 30 FPS 이상
    }

    # 허용 오차 범위 (목표 달성 판정)
    TOLERANCE = {
        'precision': 0.01,     # ±1%
        'recall': 0.01,        # ±1%
        'hmean': 0.01,         # ±1%
        'fps': 2.0             # ±2 FPS
    }

    # Early stopping 기준
    EARLY_STOPPING = {
        'patience': 10,              # 개선 없으면 10회까지 대기
        'min_improvement': 0.001     # 최소 개선 폭
    }

    # 최대 제한
    MAX_LIMITS = {
        'epochs_per_iteration': 500,  # 반복당 최대 epoch
        'total_iterations': 100,      # 최대 반복 횟수
        'total_hours': 168            # 최대 학습 시간 (7일)
    }

    def __init__(self, db_connection: cx_Oracle.Connection):
        """
        Args:
            db_connection: Oracle 데이터베이스 연결
        """
        self.db = db_connection

    def evaluate_current_model(self, model_id: int) -> Dict:
        """
        현재 모델의 성능 평가

        Args:
            model_id: 평가할 모델 ID

        Returns:
            Dict: {
                'metrics': Dict (precision, recall, hmean, fps),
                'goals_met': bool,
                'gaps': Dict (각 지표의 목표 대비 갭),
                'overall_progress': float (0.0~1.0)
            }
        """
        query = """
        SELECT precision_score, recall_score, f1_score, inference_fps
        FROM OCR_MODEL_VERSIONS
        WHERE model_id = :model_id
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query, {'model_id': model_id})
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"Model {model_id} not found")

            metrics = {
                'precision': float(row[0]) if row[0] else 0.0,
                'recall': float(row[1]) if row[1] else 0.0,
                'hmean': float(row[2]) if row[2] else 0.0,
                'fps': float(row[3]) if row[3] else 0.0
            }

            # 목표 달성도 계산
            gaps = {
                'precision': self.TARGET_METRICS['precision'] - metrics['precision'],
                'recall': self.TARGET_METRICS['recall'] - metrics['recall'],
                'hmean': self.TARGET_METRICS['hmean'] - metrics['hmean'],
                'fps': self.TARGET_METRICS['fps'] - metrics['fps']
            }

            # 전체 목표 달성 여부
            goals_met = all([
                abs(gaps['precision']) <= self.TOLERANCE['precision'],
                abs(gaps['recall']) <= self.TOLERANCE['recall'],
                abs(gaps['hmean']) <= self.TOLERANCE['hmean'],
                gaps['fps'] <= 0  # FPS는 목표 이상이면 됨
            ])

            # 전체 진행도 (0.0 ~ 1.0)
            progress_scores = [
                min(metrics['precision'] / self.TARGET_METRICS['precision'], 1.0),
                min(metrics['recall'] / self.TARGET_METRICS['recall'], 1.0),
                min(metrics['hmean'] / self.TARGET_METRICS['hmean'], 1.0),
                min(metrics['fps'] / self.TARGET_METRICS['fps'], 1.0)
            ]
            overall_progress = sum(progress_scores) / len(progress_scores)

            return {
                'metrics': metrics,
                'goals_met': goals_met,
                'gaps': gaps,
                'overall_progress': overall_progress
            }

        except Exception as e:
            logger.error(f"Error evaluating model {model_id}: {e}")
            raise

    def check_early_stopping(self,
                            metric_history: list,
                            current_metric: float) -> bool:
        """
        Early stopping 조건 확인

        Args:
            metric_history: 이전 hmean 값들의 리스트
            current_metric: 현재 hmean 값

        Returns:
            bool: True면 early stopping 실행
        """
        if len(metric_history) < self.EARLY_STOPPING['patience']:
            return False

        # 최근 patience 회 동안 개선이 없는지 확인
        recent_history = metric_history[-self.EARLY_STOPPING['patience']:]
        best_recent = max(recent_history)

        improvement = current_metric - best_recent

        if improvement < self.EARLY_STOPPING['min_improvement']:
            logger.info(f"Early stopping triggered: no improvement for {self.EARLY_STOPPING['patience']} iterations")
            return True

        return False

    def save_training_iteration_result(self,
                                      iteration_num: int,
                                      model_id: int,
                                      metrics: Dict,
                                      training_duration_hours: float) -> None:
        """
        학습 반복 결과 저장

        Args:
            iteration_num: 반복 번호
            model_id: 생성된 모델 ID
            metrics: 평가 지표
            training_duration_hours: 학습 소요 시간 (시간)
        """
        query = """
        INSERT INTO TRAINING_ITERATION_RESULTS (
            iteration_id, iteration_num, model_id,
            precision_score, recall_score, hmean_score, fps,
            training_duration_hours, goals_achieved
        ) VALUES (
            TRAINING_ITERATION_SEQ.NEXTVAL, :iteration_num, :model_id,
            :precision, :recall, :hmean, :fps,
            :duration, :goals_achieved
        )
        """

        try:
            evaluation = self.evaluate_current_model(model_id)
            goals_achieved = 'Y' if evaluation['goals_met'] else 'N'

            cursor = self.db.cursor()
            cursor.execute(query, {
                'iteration_num': iteration_num,
                'model_id': model_id,
                'precision': metrics['precision'],
                'recall': metrics['recall'],
                'hmean': metrics['hmean'],
                'fps': metrics['fps'],
                'duration': training_duration_hours,
                'goals_achieved': goals_achieved
            })

            self.db.commit()
            logger.info(f"Saved iteration {iteration_num} results (goals_achieved={goals_achieved})")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving iteration result: {e}")
            raise

    def get_best_model_so_far(self) -> Optional[Dict]:
        """
        지금까지 학습된 최고 성능 모델 조회

        Returns:
            Dict: 최고 모델 정보 또는 None
        """
        query = """
        SELECT model_id, precision_score, recall_score, f1_score, inference_fps,
               created_at
        FROM OCR_MODEL_VERSIONS
        WHERE is_production_ready = 'Y'
        ORDER BY f1_score DESC
        FETCH FIRST 1 ROW ONLY
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query)
            row = cursor.fetchone()

            if not row:
                return None

            return {
                'model_id': row[0],
                'precision': float(row[1]) if row[1] else 0.0,
                'recall': float(row[2]) if row[2] else 0.0,
                'hmean': float(row[3]) if row[3] else 0.0,
                'fps': float(row[4]) if row[4] else 0.0,
                'created_at': row[5]
            }

        except Exception as e:
            logger.error(f"Error getting best model: {e}")
            return None

    def check_max_limits_exceeded(self,
                                  current_iteration: int,
                                  total_hours_elapsed: float) -> Dict:
        """
        최대 제한 초과 여부 확인

        Args:
            current_iteration: 현재 반복 횟수
            total_hours_elapsed: 총 경과 시간 (시간)

        Returns:
            Dict: {
                'exceeded': bool,
                'reason': str or None,
                'limits': Dict (현재값 및 최대값)
            }
        """
        exceeded = False
        reason = None

        if current_iteration >= self.MAX_LIMITS['total_iterations']:
            exceeded = True
            reason = f"Maximum iterations reached: {current_iteration}/{self.MAX_LIMITS['total_iterations']}"

        if total_hours_elapsed >= self.MAX_LIMITS['total_hours']:
            exceeded = True
            reason = f"Maximum training time reached: {total_hours_elapsed:.1f}/{self.MAX_LIMITS['total_hours']} hours"

        return {
            'exceeded': exceeded,
            'reason': reason,
            'limits': {
                'current_iteration': current_iteration,
                'max_iterations': self.MAX_LIMITS['total_iterations'],
                'hours_elapsed': total_hours_elapsed,
                'max_hours': self.MAX_LIMITS['total_hours']
            }
        }

    def get_training_summary(self) -> Dict:
        """
        전체 학습 진행 요약 조회

        Returns:
            Dict: 학습 요약 정보
        """
        query = """
        SELECT
            COUNT(*) as total_iterations,
            MAX(hmean_score) as best_hmean,
            AVG(training_duration_hours) as avg_duration,
            SUM(training_duration_hours) as total_duration,
            COUNT(CASE WHEN goals_achieved = 'Y' THEN 1 END) as successful_iterations
        FROM TRAINING_ITERATION_RESULTS
        """

        try:
            cursor = self.db.cursor()
            cursor.execute(query)
            row = cursor.fetchone()

            if not row:
                return {
                    'total_iterations': 0,
                    'best_hmean': 0.0,
                    'avg_duration_hours': 0.0,
                    'total_duration_hours': 0.0,
                    'successful_iterations': 0
                }

            return {
                'total_iterations': row[0] or 0,
                'best_hmean': float(row[1]) if row[1] else 0.0,
                'avg_duration_hours': float(row[2]) if row[2] else 0.0,
                'total_duration_hours': float(row[3]) if row[3] else 0.0,
                'successful_iterations': row[4] or 0
            }

        except Exception as e:
            logger.error(f"Error getting training summary: {e}")
            return {}
