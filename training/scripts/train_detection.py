#!/usr/bin/env python3
"""
Detection 모델 Fine-tuning 스크립트
"""

import os
import sys
import subprocess
from pathlib import Path
from loguru import logger

def setup_environment():
    """환경 설정"""
    # PaddleOCR 소스코드 경로를 Python path에 추가
    paddleocr_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR"
    if paddleocr_path not in sys.path:
        sys.path.insert(0, paddleocr_path)

    # 환경 변수 설정
    os.environ["PYTHONPATH"] = f"{paddleocr_path}:{os.environ.get('PYTHONPATH', '')}"

    logger.info(f"PaddleOCR path: {paddleocr_path}")

def check_prerequisites():
    """사전 조건 확인"""
    required_paths = [
        "/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR",
        "/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train_list.txt",
        "/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/val_list.txt",
        "/home/pro301/git/en-zine/ocr_system/paddleocr_training/models/detection/en_PP-OCRv3_det_distill_train",
        "/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/custom_web_detection.yml"
    ]

    for path in required_paths:
        if not os.path.exists(path):
            logger.error(f"Required path not found: {path}")
            return False

    logger.info("✓ All prerequisites checked")
    return True

def start_training():
    """Fine-tuning 시작"""
    try:
        # 작업 디렉토리를 PaddleOCR로 변경
        os.chdir("/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR")

        # 학습 명령어 구성
        cmd = [
            "python", "-m", "paddle.distributed.launch",
            "--gpus", "0",
            "tools/train.py",
            "-c", "../configs/det/custom_web_detection.yml"
        ]

        logger.info(f"Starting detection training with command: {' '.join(cmd)}")

        # 학습 실행
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # 실시간 로그 출력
        for line in iter(process.stdout.readline, ''):
            logger.info(f"TRAIN: {line.strip()}")

        process.wait()

        if process.returncode == 0:
            logger.info("✓ Detection training completed successfully")
            return True
        else:
            logger.error(f"✗ Detection training failed with return code: {process.returncode}")
            return False

    except Exception as e:
        logger.error(f"Error during training: {e}")
        return False

def export_inference_model():
    """추론용 모델 내보내기"""
    try:
        os.chdir("/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR")

        # 최고 성능 모델 찾기
        output_dir = Path("../output/det_custom_web")
        if not output_dir.exists():
            logger.error("Training output directory not found")
            return False

        best_model_path = output_dir / "best_accuracy.pdparams"
        if not best_model_path.exists():
            # latest 모델 사용
            latest_model = max(output_dir.glob("iter_*.pdparams"), default=None)
            if latest_model:
                best_model_path = latest_model
            else:
                logger.error("No trained model found")
                return False

        # 추론 모델 내보내기
        cmd = [
            "python", "tools/export_model.py",
            "-c", "../configs/det/custom_web_detection.yml",
            "-o", f"Global.pretrained_model={best_model_path}",
            "Global.save_inference_dir=../output/det_custom_web_inference"
        ]

        logger.info(f"Exporting inference model: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info("✓ Inference model exported successfully")
            return True
        else:
            logger.error(f"✗ Model export failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error exporting model: {e}")
        return False

def main():
    """메인 함수"""
    logger.info("=== Detection Model Fine-tuning ===")

    setup_environment()

    if not check_prerequisites():
        logger.error("Prerequisites not met. Please run data conversion first.")
        return 1

    logger.info("Starting detection model fine-tuning...")

    if not start_training():
        logger.error("Training failed")
        return 1

    logger.info("Exporting inference model...")

    if not export_inference_model():
        logger.error("Model export failed")
        return 1

    logger.info("🎉 Detection model fine-tuning completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())