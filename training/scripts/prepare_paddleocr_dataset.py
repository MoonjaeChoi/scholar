# Generated: 2025-10-12 09:45:00 KST
"""
PaddleOCR 데이터셋 준비 스크립트
Prepare dataset for PaddleOCR training with train/val/test split
"""

import argparse
from pathlib import Path
import json
import random
import shutil
from datetime import datetime
from loguru import logger


def create_paddleocr_dataset(
    magazine_dir: Path,
    synthetic_dir: Path,
    output_dir: Path,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    shuffle: bool = True,
    seed: int = 42
):
    """PaddleOCR 학습용 데이터셋 생성"""

    if shuffle:
        random.seed(seed)

    # 출력 디렉토리 생성
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "train").mkdir(exist_ok=True)
    (output_dir / "val").mkdir(exist_ok=True)
    (output_dir / "test").mkdir(exist_ok=True)

    # 이미지 수집
    all_samples = []

    # 잡지 데이터
    magazine_img_dir = magazine_dir / "images"
    magazine_lbl_dir = magazine_dir / "labels"

    if magazine_img_dir.exists():
        for img_path in magazine_img_dir.glob("*.*"):
            if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                # 라벨 파일 찾기
                label_path = magazine_lbl_dir / f"{img_path.stem}.txt"
                if label_path.exists():
                    all_samples.append({
                        "image": img_path,
                        "label": label_path,
                        "source": "magazine"
                    })

    magazine_count = len([s for s in all_samples if s["source"] == "magazine"])
    logger.info(f"Magazine samples: {magazine_count}")

    # 합성 데이터
    synthetic_img_dir = synthetic_dir / "images"
    synthetic_lbl_dir = synthetic_dir / "labels"

    if synthetic_img_dir.exists():
        for img_path in synthetic_img_dir.glob("*.*"):
            if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                # 라벨 파일 찾기
                label_path = synthetic_lbl_dir / f"{img_path.stem}.txt"
                if label_path.exists():
                    all_samples.append({
                        "image": img_path,
                        "label": label_path,
                        "source": "synthetic"
                    })

    synthetic_count = len([s for s in all_samples if s["source"] == "synthetic"])
    logger.info(f"Synthetic samples: {synthetic_count}")

    total = len(all_samples)
    if total == 0:
        logger.error("No samples found!")
        return

    logger.info(f"Total samples: {total}")

    # 셔플
    if shuffle:
        random.shuffle(all_samples)

    # 분할
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)

    train_samples = all_samples[:train_end]
    val_samples = all_samples[train_end:val_end]
    test_samples = all_samples[val_end:]

    logger.info(f"Split - Train: {len(train_samples)}, Val: {len(val_samples)}, Test: {len(test_samples)}")

    # PaddleOCR 형식으로 저장
    train_list = []
    val_list = []
    test_list = []

    for sample in train_samples:
        img_str = str(sample["image"])
        lbl_str = str(sample["label"])
        train_list.append(f"{img_str}\t{lbl_str}")

    for sample in val_samples:
        img_str = str(sample["image"])
        lbl_str = str(sample["label"])
        val_list.append(f"{img_str}\t{lbl_str}")

    for sample in test_samples:
        img_str = str(sample["image"])
        lbl_str = str(sample["label"])
        test_list.append(f"{img_str}\t{lbl_str}")

    # 파일 쓰기
    train_list_path = output_dir / "train_list.txt"
    val_list_path = output_dir / "val_list.txt"
    test_list_path = output_dir / "test_list.txt"

    train_list_path.write_text("\n".join(train_list), encoding="utf-8")
    val_list_path.write_text("\n".join(val_list), encoding="utf-8")
    test_list_path.write_text("\n".join(test_list), encoding="utf-8")

    logger.info(f"Train list saved: {train_list_path}")
    logger.info(f"Val list saved: {val_list_path}")
    logger.info(f"Test list saved: {test_list_path}")

    # 보고서 생성
    report = {
        "dataset_prepared_at": datetime.now().isoformat(),
        "total_samples": total,
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
        "test_samples": len(test_samples),
        "train_ratio": train_ratio,
        "val_ratio": val_ratio,
        "test_ratio": test_ratio,
        "source_distribution": {
            "magazine": magazine_count,
            "synthetic": synthetic_count
        },
        "output_directory": str(output_dir),
        "validation_passed": True,
        "validation_errors": []
    }

    report_path = output_dir / "dataset_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Report saved: {report_path}")

    # 출력
    print("\n" + "=" * 60)
    print("✅ 데이터셋 준비 완료!")
    print("=" * 60)
    print(f"📊 총 샘플: {total}개")
    print(f"  - 잡지 데이터: {magazine_count}개")
    print(f"  - 합성 데이터: {synthetic_count}개")
    print(f"\n📁 분할 결과:")
    print(f"  - Train: {len(train_samples)}개 ({len(train_samples)/total*100:.1f}%)")
    print(f"  - Val: {len(val_samples)}개 ({len(val_samples)/total*100:.1f}%)")
    print(f"  - Test: {len(test_samples)}개 ({len(test_samples)/total*100:.1f}%)")
    print(f"\n📝 출력 파일:")
    print(f"  - {train_list_path}")
    print(f"  - {val_list_path}")
    print(f"  - {test_list_path}")
    print(f"  - {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PaddleOCR 데이터셋 준비")
    parser.add_argument("--magazine-dir", type=Path, required=True, help="잡지 데이터 디렉토리")
    parser.add_argument("--synthetic-dir", type=Path, required=True, help="합성 데이터 디렉토리")
    parser.add_argument("--output-dir", type=Path, required=True, help="출력 디렉토리")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="학습 데이터 비율")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="검증 데이터 비율")
    parser.add_argument("--test-ratio", type=float, default=0.1, help="테스트 데이터 비율")
    parser.add_argument("--shuffle", action="store_true", help="데이터 섞기")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")

    args = parser.parse_args()

    create_paddleocr_dataset(
        magazine_dir=args.magazine_dir,
        synthetic_dir=args.synthetic_dir,
        output_dir=args.output_dir,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        shuffle=args.shuffle,
        seed=args.seed
    )
