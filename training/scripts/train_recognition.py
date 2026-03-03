#!/usr/bin/env python3
"""
Recognition 모델 Fine-tuning 스크립트
"""

import os
import sys
import subprocess
from pathlib import Path
from loguru import logger

def setup_environment():
    """환경 설정"""
    paddleocr_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR"
    if paddleocr_path not in sys.path:
        sys.path.insert(0, paddleocr_path)

    os.environ["PYTHONPATH"] = f"{paddleocr_path}:{os.environ.get('PYTHONPATH', '')}"
    logger.info(f"PaddleOCR path: {paddleocr_path}")

def prepare_recognition_dataset():
    """Recognition용 데이터셋 준비"""
    try:
        # Detection 결과를 이용하여 Recognition 데이터셋 생성
        from database_connection import DatabaseConnection

        db_connection = DatabaseConnection()

        train_rec_list = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train_rec_list.txt"
        val_rec_list = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/val_rec_list.txt"

        # 간단한 Recognition 데이터셋 생성 (실제로는 더 정교한 처리 필요)
        logger.info("Preparing recognition dataset...")

        with open(train_rec_list, 'w') as f:
            # 예시: train/images 디렉토리의 이미지들을 Recognition 형식으로 변환
            train_img_dir = Path("/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train/images")
            for img_file in train_img_dir.glob("*.jpg"):
                # 간단한 형식: image_path\ttext_content
                f.write(f"{img_file}\tSample Text\n")

        with open(val_rec_list, 'w') as f:
            val_img_dir = Path("/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/val/images")
            for img_file in val_img_dir.glob("*.jpg"):
                f.write(f"{img_file}\tSample Text\n")

        logger.info("✓ Recognition dataset prepared")
        return True

    except Exception as e:
        logger.error(f"Error preparing recognition dataset: {e}")
        return False

def start_training():
    """Recognition Fine-tuning 시작"""
    try:
        os.chdir("/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR")

        cmd = [
            "python", "-m", "paddle.distributed.launch",
            "--gpus", "0",
            "tools/train.py",
            "-c", "../configs/rec/custom_web_recognition.yml"
        ]

        logger.info(f"Starting recognition training: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        for line in iter(process.stdout.readline, ''):
            logger.info(f"TRAIN: {line.strip()}")

        process.wait()

        if process.returncode == 0:
            logger.info("✓ Recognition training completed successfully")
            return True
        else:
            logger.error(f"✗ Recognition training failed: {process.returncode}")
            return False

    except Exception as e:
        logger.error(f"Error during training: {e}")
        return False

def export_inference_model():
    """추론용 모델 내보내기"""
    try:
        os.chdir("/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR")

        output_dir = Path("../output/rec_custom_web")
        best_model_path = output_dir / "best_accuracy.pdparams"

        if not best_model_path.exists():
            latest_model = max(output_dir.glob("iter_*.pdparams"), default=None)
            if latest_model:
                best_model_path = latest_model
            else:
                logger.error("No trained model found")
                return False

        cmd = [
            "python", "tools/export_model.py",
            "-c", "../configs/rec/custom_web_recognition.yml",
            "-o", f"Global.pretrained_model={best_model_path}",
            "Global.save_inference_dir=../output/rec_custom_web_inference"
        ]

        logger.info(f"Exporting inference model: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info("✓ Recognition inference model exported successfully")
            return True
        else:
            logger.error(f"✗ Model export failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error exporting model: {e}")
        return False

def main():
    """메인 함수"""
    logger.info("=== Recognition Model Fine-tuning ===")

    setup_environment()

    if not prepare_recognition_dataset():
        logger.error("Failed to prepare recognition dataset")
        return 1

    logger.info("Starting recognition model fine-tuning...")

    if not start_training():
        logger.error("Training failed")
        return 1

    logger.info("Exporting inference model...")

    if not export_inference_model():
        logger.error("Model export failed")
        return 1

    logger.info("🎉 Recognition model fine-tuning completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())