# Generated: 2025-10-12 00:25:00 KST
"""
PaddleOCR Detection 모델 Fine-Tuning 스크립트
Magazine Layout Detection Model Training

This script fine-tunes PaddleOCR's detection model for magazine layouts.
"""

import os
import sys
from pathlib import Path
import argparse
from loguru import logger


def train_detection_model(config_file: str, dataset_dir: str, pretrained_model: str,
                         output_dir: str, epochs: int = 50, batch_size: int = 8,
                         learning_rate: float = 0.001):
    """
    Detection 모델 학습

    Args:
        config_file: PaddleOCR config 파일 경로
        dataset_dir: 데이터셋 디렉토리
        pretrained_model: 사전학습 모델 경로
        output_dir: 출력 디렉토리
        epochs: 학습 에폭 수
        batch_size: 배치 크기
        learning_rate: 학습률
    """
    logger.info("=" * 60)
    logger.info("Detection Model Fine-Tuning Started")
    logger.info("=" * 60)
    logger.info(f"Config: {config_file}")
    logger.info(f"Dataset: {dataset_dir}")
    logger.info(f"Pretrained: {pretrained_model}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Epochs: {epochs}, Batch: {batch_size}, LR: {learning_rate}")

    # PaddleOCR 학습 명령어 구성
    # Note: 실제 학습은 PaddleOCR 저장소의 tools/train.py를 사용해야 함

    paddle_ocr_dir = os.getenv('PADDLEOCR_DIR', '/opt/PaddleOCR')

    if not Path(paddle_ocr_dir).exists():
        logger.error(f"PaddleOCR directory not found: {paddle_ocr_dir}")
        logger.info("Please clone PaddleOCR repository:")
        logger.info("  git clone https://github.com/PaddlePaddle/PaddleOCR.git /opt/PaddleOCR")
        return False

    # 학습 명령어 출력
    train_cmd = f"""
cd {paddle_ocr_dir}

python tools/train.py \\
    -c {config_file} \\
    -o Global.pretrained_model={pretrained_model} \\
    -o Global.save_model_dir={output_dir} \\
    -o Global.epoch_num={epochs} \\
    -o Train.loader.batch_size_per_card={batch_size} \\
    -o Optimizer.lr.learning_rate={learning_rate} \\
    -o Train.dataset.data_dir={dataset_dir} \\
    -o Eval.dataset.data_dir={dataset_dir}
"""

    logger.info("\n" + "=" * 60)
    logger.info("학습 명령어:")
    logger.info("=" * 60)
    print(train_cmd)

    logger.info("\n위 명령어를 실행하여 학습을 시작하세요.")
    logger.info("또는 이 스크립트를 수정하여 자동 실행하도록 구현하세요.")

    return True


def main():
    parser = argparse.ArgumentParser(description="PaddleOCR Detection Model Training")
    parser.add_argument('--config', type=str,
                       default='/home/pro301/git/en-zine/scholar/training/configs/magazine_det_config.yml',
                       help='PaddleOCR config file path')
    parser.add_argument('--dataset_dir', type=str,
                       default='/home/pro301/git/en-zine/scholar/training/datasets',
                       help='Dataset directory')
    parser.add_argument('--pretrained_model', type=str,
                       default='/home/pro301/git/en-zine/scholar/training/models/base/ch_PP-OCRv4_det_train',
                       help='Pretrained model path')
    parser.add_argument('--output_dir', type=str,
                       default='/home/pro301/git/en-zine/scholar/training/models/magazine_det_v1',
                       help='Output directory')
    parser.add_argument('--epochs', type=int, default=50,
                       help='Number of epochs')
    parser.add_argument('--batch_size', type=int, default=8,
                       help='Batch size')
    parser.add_argument('--learning_rate', type=float, default=0.001,
                       help='Learning rate')

    args = parser.parse_args()

    print("=" * 60)
    print("🎯 Detection Model Fine-Tuning")
    print("=" * 60)

    train_detection_model(
        config_file=args.config,
        dataset_dir=args.dataset_dir,
        pretrained_model=args.pretrained_model,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate
    )


if __name__ == "__main__":
    main()
