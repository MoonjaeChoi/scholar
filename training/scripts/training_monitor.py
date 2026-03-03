# Generated: 2025-10-02 22:55:00 KST
"""
Training Monitor - 학습 진행 알림 및 모니터링
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TrainingMonitor:
    """학습 진행 알림 및 모니터링 시스템"""

    def __init__(self, config: Dict):
        """
        Args:
            config: 알림 설정 (email, slack 등)
        """
        self.config = config
        self.email_enabled = config.get('notifications', {}).get('email_enabled', False)
        self.slack_enabled = config.get('notifications', {}).get('slack_enabled', False)

    def notify_iteration_start(self, iteration_num: int, selected_count: int) -> None:
        """
        반복 시작 알림

        Args:
            iteration_num: 반복 번호
            selected_count: 선택된 데이터 개수
        """
        message = f"""
🚀 Training Iteration {iteration_num} Started

Selected Data: {selected_count} samples
Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        logger.info(message)
        self._send_notification("Training Iteration Started", message)

    def notify_iteration_complete(self,
                                  iteration_num: int,
                                  evaluation: Dict,
                                  duration_hours: float) -> None:
        """
        반복 완료 알림

        Args:
            iteration_num: 반복 번호
            evaluation: 평가 결과
            duration_hours: 소요 시간 (시간)
        """
        metrics = evaluation['metrics']
        gaps = evaluation['gaps']

        message = f"""
✅ Training Iteration {iteration_num} Completed

Duration: {duration_hours:.2f} hours
Completion Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Performance Metrics:
  Precision: {metrics['precision']:.4f} (Gap: {gaps['precision']:+.4f})
  Recall:    {metrics['recall']:.4f} (Gap: {gaps['recall']:+.4f})
  Hmean:     {metrics['hmean']:.4f} (Gap: {gaps['hmean']:+.4f})
  FPS:       {metrics['fps']:.2f} (Gap: {gaps['fps']:+.2f})

Overall Progress: {evaluation['overall_progress']:.1%}
Goals Met: {'Yes ✅' if evaluation['goals_met'] else 'Not Yet ⏳'}
"""
        logger.info(message)
        self._send_notification("Training Iteration Completed", message)

    def notify_goals_achieved(self, final_evaluation: Dict, summary: Dict) -> None:
        """
        목표 달성 알림

        Args:
            final_evaluation: 최종 평가 결과
            summary: 학습 요약 정보
        """
        metrics = final_evaluation['metrics']

        message = f"""
🎉 TRAINING GOALS ACHIEVED! 🎉

Final Performance:
  Precision: {metrics['precision']:.4f} (Target: 0.9500)
  Recall:    {metrics['recall']:.4f} (Target: 0.9200)
  Hmean:     {metrics['hmean']:.4f} (Target: 0.9300)
  FPS:       {metrics['fps']:.2f} (Target: 30.00)

Training Summary:
  Total Iterations: {summary['total_iterations']}
  Total Duration: {summary['total_duration_hours']:.2f} hours
  Best Hmean: {summary['best_hmean']:.4f}
  Success Rate: {summary['successful_iterations']}/{summary['total_iterations']}

Completion Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        logger.info(message)
        self._send_notification("🎉 Training Goals Achieved!", message, priority='high')

    def notify_early_stopping(self, iteration_num: int, reason: str) -> None:
        """
        Early stopping 알림

        Args:
            iteration_num: 중단 시점 반복 번호
            reason: 중단 사유
        """
        message = f"""
🛑 Training Stopped Early

Iteration: {iteration_num}
Reason: {reason}
Stop Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The model has reached a plateau and further training may not improve performance.
"""
        logger.warning(message)
        self._send_notification("Training Early Stopping", message, priority='medium')

    def notify_max_limit_reached(self, limit_check: Dict) -> None:
        """
        최대 제한 도달 알림

        Args:
            limit_check: 제한 확인 결과
        """
        limits = limit_check['limits']

        message = f"""
⚠️ Training Maximum Limit Reached

Reason: {limit_check['reason']}

Current Status:
  Iterations: {limits['current_iteration']}/{limits['max_iterations']}
  Duration: {limits['hours_elapsed']:.1f}/{limits['max_hours']} hours

Stop Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        logger.warning(message)
        self._send_notification("Training Limit Reached", message, priority='high')

    def notify_error(self, iteration_num: int, error_message: str) -> None:
        """
        에러 발생 알림

        Args:
            iteration_num: 에러 발생 반복 번호
            error_message: 에러 메시지
        """
        message = f"""
❌ Training Error Occurred

Iteration: {iteration_num}
Error Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Error Details:
{error_message}

Please check the logs for more information.
"""
        logger.error(message)
        self._send_notification("❌ Training Error", message, priority='urgent')

    def notify_data_cleanup(self, cleanup_results: Dict) -> None:
        """
        데이터 정리 결과 알림

        Args:
            cleanup_results: 정리 결과
        """
        message = f"""
🧹 Data Cleanup Completed

Quality-based deletion: {cleanup_results.get('quality_based', 0)}
Failed training deletion: {cleanup_results.get('failed_training', 0)}
Duplicate deletion: {cleanup_results.get('duplicates', 0)}
Old data deletion: {cleanup_results.get('old_data', 0)}

Total Deleted: {cleanup_results.get('total_deleted', 0)} samples
Cleanup Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        logger.info(message)

    def _send_notification(self,
                          subject: str,
                          message: str,
                          priority: str = 'normal') -> None:
        """
        알림 전송 (이메일 또는 Slack)

        Args:
            subject: 제목
            message: 메시지
            priority: 우선순위 (normal, medium, high, urgent)
        """
        if self.email_enabled:
            self._send_email(subject, message, priority)

        if self.slack_enabled:
            self._send_slack(subject, message, priority)

    def _send_email(self, subject: str, message: str, priority: str) -> None:
        """이메일 전송"""
        try:
            email_config = self.config.get('notifications', {}).get('email', {})

            if not all([email_config.get('smtp_server'),
                       email_config.get('sender'),
                       email_config.get('recipients')]):
                logger.warning("Email configuration incomplete, skipping email notification")
                return

            msg = MIMEMultipart()
            msg['From'] = email_config['sender']
            msg['To'] = ', '.join(email_config['recipients'])
            msg['Subject'] = f"[{priority.upper()}] {subject}"

            msg.attach(MIMEText(message, 'plain'))

            with smtplib.SMTP(email_config['smtp_server'], email_config.get('smtp_port', 587)) as server:
                if email_config.get('use_tls', True):
                    server.starttls()

                if email_config.get('username') and email_config.get('password'):
                    server.login(email_config['username'], email_config['password'])

                server.send_message(msg)

            logger.debug(f"Email sent: {subject}")

        except Exception as e:
            logger.error(f"Failed to send email: {e}")

    def _send_slack(self, subject: str, message: str, priority: str) -> None:
        """Slack 알림 전송"""
        try:
            # Slack webhook 구현 (추후 확장 가능)
            logger.debug(f"Slack notification: {subject}")
            pass

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    def get_training_status_report(self, summary: Dict) -> str:
        """
        학습 현황 리포트 생성

        Args:
            summary: 학습 요약 정보

        Returns:
            str: 포맷된 리포트
        """
        report = f"""
{'='*80}
Training Status Report
{'='*80}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Overall Statistics:
  Total Iterations: {summary.get('total_iterations', 0)}
  Successful Iterations: {summary.get('successful_iterations', 0)}
  Best Hmean: {summary.get('best_hmean', 0.0):.4f}
  Average Duration: {summary.get('avg_duration_hours', 0.0):.2f} hours
  Total Duration: {summary.get('total_duration_hours', 0.0):.2f} hours

{'='*80}
"""
        return report
