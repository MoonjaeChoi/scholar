# Generated: 2025-10-11 23:47:00 KST
"""
Continuous Training System - Infinite Loop Training
무한 학습 시스템 - CronJob을 대체하는 자체 무한 루프 방식
"""

import os
import sys
import time
from datetime import datetime
from loguru import logger
from prometheus_client import start_http_server, Counter, Gauge, Histogram

# Prometheus metrics
training_total = Counter('scholar_training_total', 'Total number of training attempts', ['status'])
training_duration = Histogram('scholar_training_duration_seconds', 'Training duration in seconds')
active_training = Gauge('scholar_active_training', 'Training in progress (0 or 1)')
continuous_training_iterations = Counter('scholar_continuous_training_iterations', 'Total continuous training iterations')
training_sleep_duration = Gauge('scholar_training_sleep_duration_seconds', 'Current sleep duration between training')


def setup_logging(log_path: str):
    """로깅 설정"""
    try:
        # 로그 디렉토리 생성
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        # 로거 설정
        logger.add(
            log_path,
            rotation='10 MB',
            retention='1 month',
            format='{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}'
        )
        logger.info('Training logging initialized')
    except Exception as e:
        logger.error(f'Failed to setup logging: {e}')


def notify_ml_control(api_url: str, endpoint: str, data: dict):
    """ML Control Dashboard에 작업 상태 알림"""
    if not api_url:
        return

    try:
        import requests
        url = f"{api_url}{endpoint}"
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            logger.debug(f'Notified ML Control: {endpoint}')
        else:
            logger.warning(f'ML Control notification failed: {response.status_code}')
    except Exception as e:
        logger.warning(f'Failed to notify ML Control: {e}')


def check_trainable_data(db_host: str, db_port: str, db_service: str,
                         db_user: str, db_password: str) -> int:
    """학습 가능한 데이터 개수 확인

    Returns:
        학습 가능한 데이터 개수 (오류 시 -1)
    """
    try:
        import cx_Oracle
        dsn = cx_Oracle.makedsn(db_host, db_port, service_name=db_service)
        conn = cx_Oracle.connect(user=db_user, password=db_password, dsn=dsn)
        cursor = conn.cursor()

        # V_TRAINABLE_DATA view에서 카운트
        cursor.execute("""
            SELECT COUNT(*) FROM ocr_admin.V_TRAINABLE_DATA
        """)
        count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        logger.info(f'📊 Trainable data count: {count}')
        return count

    except Exception as e:
        logger.error(f'Failed to check trainable data: {e}')
        return -1


def run_single_training_iteration(ml_control_api: str, iteration: int) -> bool:
    """단일 학습 반복 실행

    Args:
        ml_control_api: ML Control API URL
        iteration: 현재 반복 횟수

    Returns:
        성공 여부 (bool)
    """
    task_id = f"train-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    start_time = time.time()

    logger.info('=' * 60)
    logger.info(f'🔄 Continuous Training Iteration #{iteration}')
    logger.info(f'Task ID: {task_id}')
    logger.info(f'Start Time: {datetime.now().isoformat()}')
    logger.info('=' * 60)

    # ML Control에 작업 시작 알림
    notify_ml_control(ml_control_api, '/api/tasks/start', {
        'task_id': task_id,
        'task_type': 'training',
        'start_time': datetime.now().isoformat(),
        'config': {
            'mode': 'continuous',
            'iteration': iteration,
            'model_type': 'paddleocr'
        }
    })

    try:
        active_training.set(1)

        # 학습 가능한 데이터 확인
        db_host = os.getenv('DB_HOST', '192.168.75.194')
        db_port = os.getenv('DB_PORT', '1521')
        db_service = os.getenv('DB_SERVICE_NAME', 'XEPDB1')
        db_user = os.getenv('DB_USERNAME', 'ocr_admin')
        db_password = os.getenv('DB_PASSWORD', 'admin_password')

        trainable_count = check_trainable_data(
            db_host, db_port, db_service, db_user, db_password
        )

        # 학습 가능한 데이터가 없으면 스킵
        if trainable_count == 0:
            logger.info('⏭️ No trainable data available, skipping training iteration')
            active_training.set(0)
            continuous_training_iterations.inc()

            notify_ml_control(ml_control_api, '/api/tasks/complete', {
                'task_id': task_id,
                'status': 'skipped',
                'end_time': datetime.now().isoformat(),
                'duration_seconds': int(time.time() - start_time),
                'exit_code': 0,
                'message': 'No trainable data available'
            })

            return True

        # 학습 데이터가 있으면 학습 실행
        logger.info(f'🎓 Starting training with {trainable_count} trainable samples')

        # PaddleOCR 학습 스크립트 실행
        import subprocess
        train_script = os.getenv('TRAIN_SCRIPT_PATH', '/home/pro301/git/en-zine/scholar/training/train_paddleocr.py')

        if not os.path.exists(train_script):
            logger.error(f'Training script not found: {train_script}')
            raise FileNotFoundError(f'Training script not found: {train_script}')

        # 학습 실행
        result = subprocess.run(
            ['python', train_script],
            capture_output=True,
            text=True,
            timeout=7200  # 2시간 타임아웃
        )

        exit_code = result.returncode
        duration = time.time() - start_time

        # 로그 출력
        if result.stdout:
            logger.info(f'Training stdout:\n{result.stdout}')
        if result.stderr:
            logger.warning(f'Training stderr:\n{result.stderr}')

        # Record metrics
        training_duration.observe(duration)
        active_training.set(0)
        continuous_training_iterations.inc()

        if exit_code == 0:
            training_total.labels(status='success').inc()
            logger.info('=' * 60)
            logger.info(f'✅ Training Iteration #{iteration} Completed Successfully')
            logger.info(f'Duration: {duration:.2f}s ({duration/60:.1f} minutes)')
            logger.info(f'Trained samples: {trainable_count}')
            logger.info(f'End Time: {datetime.now().isoformat()}')
            logger.info('=' * 60)

            # ML Control에 작업 완료 알림
            notify_ml_control(ml_control_api, '/api/tasks/complete', {
                'task_id': task_id,
                'status': 'completed',
                'end_time': datetime.now().isoformat(),
                'duration_seconds': int(duration),
                'exit_code': 0,
                'stats': {
                    'trainable_count': trainable_count
                }
            })

            return True
        else:
            training_total.labels(status='failed').inc()
            logger.error(f'❌ Training Iteration #{iteration} Failed (exit code: {exit_code})')

            notify_ml_control(ml_control_api, '/api/tasks/complete', {
                'task_id': task_id,
                'status': 'failed',
                'end_time': datetime.now().isoformat(),
                'duration_seconds': int(duration),
                'exit_code': exit_code,
                'error_message': result.stderr[:500] if result.stderr else 'Training failed'
            })

            return False

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        logger.error(f'❌ Training iteration #{iteration} timeout after {duration:.0f}s')
        active_training.set(0)
        training_total.labels(status='timeout').inc()

        notify_ml_control(ml_control_api, '/api/tasks/complete', {
            'task_id': task_id,
            'status': 'timeout',
            'end_time': datetime.now().isoformat(),
            'duration_seconds': int(duration),
            'exit_code': -1,
            'error_message': 'Training timeout (2 hours)'
        })

        return False

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f'❌ Training iteration #{iteration} failed: {e}')
        active_training.set(0)
        training_total.labels(status='error').inc()

        notify_ml_control(ml_control_api, '/api/tasks/complete', {
            'task_id': task_id,
            'status': 'failed',
            'end_time': datetime.now().isoformat(),
            'duration_seconds': int(duration),
            'exit_code': 1,
            'error_message': str(e)
        })

        return False


def main():
    """무한 학습 메인 함수"""
    logger.info('🚀 Starting Continuous Training System...')
    print('=' * 60)
    print('🚀 Continuous Training System')
    print('=' * 60)

    # Start Prometheus metrics server
    metrics_port = int(os.getenv('PROMETHEUS_METRICS_PORT', '8001'))
    try:
        start_http_server(metrics_port)
        logger.info(f'📊 Prometheus metrics server started on port {metrics_port}')
    except Exception as e:
        logger.warning(f'Failed to start Prometheus metrics server: {e}')

    # 로깅 설정
    log_path = os.getenv('LOG_FILE_PATH', '/home/pro301/git/en-zine/scholar/training/logs/continuous_trainer.log')
    setup_logging(log_path)

    # 무한 학습 설정
    training_interval = int(os.getenv('TRAINING_INTERVAL_SECONDS', '300'))  # 기본 5분 (300초)
    training_sleep_duration.set(training_interval)
    logger.info(f'⏰ Training interval: {training_interval} seconds ({training_interval/60:.1f} minutes)')

    # ML Control API
    ml_control_api = os.getenv('ML_CONTROL_API', '')
    logger.info(f'⚙️ ML Control API: {ml_control_api or "disabled"}')

    # 무한 루프 시작
    iteration = 0
    consecutive_failures = 0
    max_consecutive_failures = 5

    logger.info('🔄 Starting infinite training loop...')
    print('=' * 60)
    print('🔄 Infinite Training Loop Started')
    print(f'⏰ Interval: {training_interval}s ({training_interval/60:.1f} min)')
    print('=' * 60)

    try:
        while True:
            iteration += 1

            # 학습 실행
            success = run_single_training_iteration(ml_control_api, iteration)

            # 연속 실패 카운트 관리
            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(f'⚠️ Consecutive failures: {consecutive_failures}/{max_consecutive_failures}')

            # 연속 실패 임계값 초과 시 종료
            if consecutive_failures >= max_consecutive_failures:
                logger.error(f'❌ Too many consecutive failures ({consecutive_failures}), exiting...')
                return 1

            # 다음 학습까지 대기
            logger.info(f'😴 Sleeping for {training_interval} seconds until next training...')
            print(f'\n😴 Sleeping {training_interval}s ({training_interval/60:.1f} min) until next training...\n')

            time.sleep(training_interval)

    except KeyboardInterrupt:
        logger.info('🛑 Continuous training stopped by user (Ctrl+C)')
        print('\n🛑 Continuous training stopped by user')
        return 0
    except Exception as e:
        logger.error(f'❌ Unexpected error in continuous training loop: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
