#!/usr/bin/env python3.9
# Generated: 2025-10-02 22:59:00 KST
"""
Main Continuous Training Entry Point
"""

import cx_Oracle
import argparse
import json
import logging
import sys
import os
from pathlib import Path
from prometheus_client import start_http_server, Counter, Gauge, Histogram

from continuous_training import ContinuousTrainingOrchestrator
from training_monitor import TrainingMonitor

# Prometheus metrics
training_iterations = Counter('scholar_training_iterations_total', 'Total training iterations')
training_duration = Histogram('scholar_training_duration_hours', 'Training duration in hours')
model_hmean = Gauge('scholar_model_hmean', 'Current model Hmean score')
model_precision = Gauge('scholar_model_precision', 'Current model precision')
model_recall = Gauge('scholar_model_recall', 'Current model recall')
training_status = Gauge('scholar_training_status', 'Training status (1=running, 0=stopped)')


def setup_logging(config: dict) -> None:
    """로깅 설정"""
    log_config = config.get('logging', {})

    log_level = getattr(logging, log_config.get('log_level', 'INFO'))
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    handlers = []

    if log_config.get('console_output', True):
        handlers.append(logging.StreamHandler(sys.stdout))

    if log_config.get('file_output', True) and log_config.get('log_file'):
        log_file = Path(log_config['log_file'])
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(str(log_file)))

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers
    )


def create_database_connection(config: dict) -> cx_Oracle.Connection:
    """Oracle 데이터베이스 연결 생성"""
    db_config = config['database']

    dsn = cx_Oracle.makedsn(
        db_config['host'],
        db_config['port'],
        service_name=db_config['service_name']
    )

    connection = cx_Oracle.connect(
        user=db_config['username'],
        password=db_config['password'],
        dsn=dsn
    )

    return connection


def main():
    """메인 진입점"""
    parser = argparse.ArgumentParser(
        description='Continuous Training System - 무한 학습 자동화'
    )
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Configuration file path (JSON)'
    )
    args = parser.parse_args()

    # Start Prometheus metrics server on port 8001
    metrics_port = int(os.getenv('PROMETHEUS_METRICS_PORT', '8001'))
    try:
        start_http_server(metrics_port)
        print(f'Prometheus metrics server started on port {metrics_port}')
    except Exception as e:
        print(f'Failed to start Prometheus metrics server: {e}')

    # 설정 파일 로드
    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 로깅 설정
    setup_logging(config)
    logger = logging.getLogger(__name__)

    logger.info("="*80)
    logger.info("Continuous Training System Starting")
    logger.info("="*80)

    try:
        # 데이터베이스 연결
        logger.info("Connecting to Oracle database...")
        db_connection = create_database_connection(config)
        logger.info("Database connected successfully")

        # 모니터 초기화
        monitor = TrainingMonitor(config)

        # 학습 오케스트레이터 초기화
        logger.info("Initializing training orchestrator...")
        orchestrator = ContinuousTrainingOrchestrator(
            db_connection=db_connection,
            config_path=args.config
        )

        # Set training status to running
        training_status.set(1)

        # 무한 학습 루프 실행
        result = orchestrator.run_infinite_training_loop()

        # Update Prometheus metrics
        summary = result.get('summary', {})
        training_iterations.inc(summary.get('total_iterations', 0))
        training_duration.observe(summary.get('total_duration_hours', 0.0))

        final_eval = result.get('final_evaluation', {})
        if final_eval:
            model_hmean.set(final_eval.get('hmean', 0.0))
            model_precision.set(final_eval.get('precision', 0.0))
            model_recall.set(final_eval.get('recall', 0.0))

        # 결과 출력
        logger.info("\n" + "="*80)
        logger.info("Training Summary")
        logger.info("="*80)

        logger.info(f"Total Iterations: {summary.get('total_iterations', 0)}")
        logger.info(f"Best Hmean: {summary.get('best_hmean', 0.0):.4f}")
        logger.info(f"Total Duration: {summary.get('total_duration_hours', 0.0):.2f} hours")

        if result.get('success'):
            logger.info("\n🎉 Training goals achieved!")
            monitor.notify_goals_achieved(
                result.get('final_evaluation', {}),
                summary
            )
            exit_code = 0
        else:
            logger.warning("\n⚠️ Training stopped without achieving goals")
            exit_code = 1

        # Set training status to stopped
        training_status.set(0)

        # 연결 종료
        db_connection.close()
        logger.info("\nDatabase connection closed")

        return exit_code

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Training interrupted by user (Ctrl+C)")
        training_status.set(0)
        if 'db_connection' in locals():
            db_connection.close()
        return 130

    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}", exc_info=True)
        training_status.set(0)
        if 'db_connection' in locals():
            db_connection.close()
        return 1


if __name__ == '__main__':
    sys.exit(main())
