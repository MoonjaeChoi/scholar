# Generated: 2025-10-12 00:15:00 KST
"""
데이터셋 준비 및 분할 스크립트
Dataset Preparation and Split Manager

Features:
- Train/Val/Test 데이터 분할 (80%/10%/10%)
- 잡지/합성 데이터 통합 관리
- 데이터셋 통계 생성
- PaddleOCR 형식 출력
"""

from pathlib import Path
import json
import random
from typing import List, Tuple, Dict
from datetime import datetime
from loguru import logger
import shutil


class DatasetManager:
    """데이터셋 구성 및 분할 관리"""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.magazine_dir = self.base_dir / "magazine"
        self.synthetic_dir = self.base_dir / "synthetic"
        self.validation_dir = self.base_dir / "validation"
        self.splits_dir = self.base_dir / "splits"

        # 디렉토리 생성
        for d in [self.magazine_dir, self.synthetic_dir,
                 self.validation_dir, self.splits_dir]:
            (d / "images").mkdir(parents=True, exist_ok=True)
            (d / "labels").mkdir(parents=True, exist_ok=True)

        # 검증 데이터 카테고리 디렉토리
        val_categories = [
            "general_documents",
            "magazine_layouts",
            "decorative_fonts",
            "vertical_text"
        ]
        for cat in val_categories:
            (self.validation_dir / cat).mkdir(parents=True, exist_ok=True)

        logger.info(f"DatasetManager initialized: {self.base_dir}")

    def create_train_val_test_split(self, train_ratio=0.8, val_ratio=0.1, seed=42):
        """Train/Val/Test 분할 생성"""
        random.seed(seed)

        logger.info("데이터셋 분할 시작...")
        print("\n" + "=" * 60)
        print("📊 데이터셋 분할 시작")
        print("=" * 60)

        # 모든 이미지 수집
        all_images = []

        # 실제 잡지 데이터
        magazine_images = list((self.magazine_dir / "images").glob("*.jpg"))
        magazine_images.extend(list((self.magazine_dir / "images").glob("*.png")))
        all_images.extend([(img, "magazine") for img in magazine_images])
        logger.info(f"Magazine images: {len(magazine_images)}")
        print(f"📚 잡지 데이터: {len(magazine_images)}개")

        # 합성 데이터
        synthetic_images = list((self.synthetic_dir / "images").glob("*.jpg"))
        synthetic_images.extend(list((self.synthetic_dir / "images").glob("*.png")))
        all_images.extend([(img, "synthetic") for img in synthetic_images])
        logger.info(f"Synthetic images: {len(synthetic_images)}")
        print(f"🎨 합성 데이터: {len(synthetic_images)}개")

        if not all_images:
            logger.error("이미지가 없습니다!")
            print("❌ 오류: 이미지가 없습니다!")
            return

        # 랜덤 셔플
        random.shuffle(all_images)

        # 분할
        total = len(all_images)
        train_end = int(total * train_ratio)
        val_end = train_end + int(total * val_ratio)

        train_split = all_images[:train_end]
        val_split = all_images[train_end:val_end]
        test_split = all_images[val_end:]

        # 파일 저장
        self._save_split(train_split, self.splits_dir / "train.txt")
        self._save_split(val_split, self.splits_dir / "val.txt")
        self._save_split(test_split, self.splits_dir / "test.txt")

        # PaddleOCR 형식으로도 저장
        self._save_paddleocr_format(train_split, self.splits_dir / "train_list.txt")
        self._save_paddleocr_format(val_split, self.splits_dir / "val_list.txt")
        self._save_paddleocr_format(test_split, self.splits_dir / "test_list.txt")

        # 통계 생성
        stats = {
            "split_date": datetime.now().isoformat(),
            "seed": seed,
            "ratios": {
                "train": train_ratio,
                "val": val_ratio,
                "test": 1 - train_ratio - val_ratio
            },
            "total": total,
            "train": {
                "count": len(train_split),
                "percentage": len(train_split) / total * 100
            },
            "val": {
                "count": len(val_split),
                "percentage": len(val_split) / total * 100
            },
            "test": {
                "count": len(test_split),
                "percentage": len(test_split) / total * 100
            },
            "sources": {
                "magazine": len(magazine_images),
                "synthetic": len(synthetic_images)
            }
        }

        stats_path = self.splits_dir / "split_stats.json"
        stats_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding='utf-8')

        print(f"\n✅ 분할 완료:")
        print(f"  - Train: {len(train_split):,}개 ({len(train_split)/total*100:.1f}%)")
        print(f"  - Val:   {len(val_split):,}개 ({len(val_split)/total*100:.1f}%)")
        print(f"  - Test:  {len(test_split):,}개 ({len(test_split)/total*100:.1f}%)")
        print(f"\n📝 파일 저장:")
        print(f"  - {self.splits_dir / 'train.txt'}")
        print(f"  - {self.splits_dir / 'val.txt'}")
        print(f"  - {self.splits_dir / 'test.txt'}")
        print(f"  - {self.splits_dir / 'train_list.txt'} (PaddleOCR 형식)")
        print(f"  - {stats_path}")

        logger.info(f"분할 완료: Train={len(train_split)}, Val={len(val_split)}, Test={len(test_split)}")

    def _save_split(self, split: List[Tuple[Path, str]], output_path: Path):
        """분할 정보를 텍스트 파일로 저장 (일반 형식)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for img_path, source in split:
                f.write(f"{img_path}\t{source}\n")

    def _save_paddleocr_format(self, split: List[Tuple[Path, str]], output_path: Path):
        """PaddleOCR 학습 형식으로 저장

        형식: image_path\tlabel_path
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            for img_path, source in split:
                # 라벨 파일 경로 찾기
                label_path = img_path.parent.parent / "labels" / img_path.with_suffix('.txt').name

                if label_path.exists():
                    f.write(f"{img_path}\t{label_path}\n")
                else:
                    logger.warning(f"Label not found: {label_path}")

    def generate_dataset_report(self) -> Dict:
        """데이터셋 전체 리포트 생성"""
        print("\n" + "=" * 60)
        print("📈 데이터셋 리포트 생성")
        print("=" * 60)

        report = {
            "report_date": datetime.now().isoformat(),
            "base_dir": str(self.base_dir),
            "datasets": {}
        }

        # 각 데이터셋 통계
        for name, dataset_dir in [
            ("magazine", self.magazine_dir),
            ("synthetic", self.synthetic_dir),
            ("validation", self.validation_dir)
        ]:
            images = list((dataset_dir / "images").glob("*.*"))
            labels = list((dataset_dir / "labels").glob("*.txt"))

            report["datasets"][name] = {
                "images": len(images),
                "labels": len(labels),
                "path": str(dataset_dir)
            }

            print(f"\n📁 {name.upper()}:")
            print(f"  - 이미지: {len(images):,}개")
            print(f"  - 라벨:   {len(labels):,}개")

        # 분할 통계 (있으면)
        if (self.splits_dir / "split_stats.json").exists():
            split_stats = json.loads((self.splits_dir / "split_stats.json").read_text(encoding='utf-8'))
            report["splits"] = split_stats

            print(f"\n🔀 데이터 분할:")
            print(f"  - Train: {split_stats['train']['count']:,}개 ({split_stats['train']['percentage']:.1f}%)")
            print(f"  - Val:   {split_stats['val']['count']:,}개 ({split_stats['val']['percentage']:.1f}%)")
            print(f"  - Test:  {split_stats['test']['count']:,}개 ({split_stats['test']['percentage']:.1f}%)")

        # 리포트 저장
        report_path = self.base_dir / "dataset_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

        print(f"\n✅ 리포트 저장: {report_path}")
        logger.info(f"Dataset report generated: {report_path}")

        return report

    def validate_dataset(self) -> Dict[str, List[str]]:
        """데이터셋 검증 (이미지-라벨 매칭 확인)"""
        print("\n" + "=" * 60)
        print("🔍 데이터셋 검증")
        print("=" * 60)

        issues = {
            "missing_labels": [],
            "missing_images": [],
            "empty_labels": []
        }

        for name, dataset_dir in [
            ("magazine", self.magazine_dir),
            ("synthetic", self.synthetic_dir)
        ]:
            print(f"\n검증 중: {name}...")

            images_dir = dataset_dir / "images"
            labels_dir = dataset_dir / "labels"

            # 이미지에 대응하는 라벨이 있는지 확인
            images = list(images_dir.glob("*.*"))
            for img_path in images:
                label_path = labels_dir / img_path.with_suffix('.txt').name

                if not label_path.exists():
                    issues["missing_labels"].append(str(img_path))
                elif label_path.stat().st_size == 0:
                    issues["empty_labels"].append(str(label_path))

            # 라벨에 대응하는 이미지가 있는지 확인
            labels = list(labels_dir.glob("*.txt"))
            for label_path in labels:
                img_extensions = ['.jpg', '.png', '.jpeg']
                has_image = any((images_dir / label_path.stem).with_suffix(ext).exists()
                              for ext in img_extensions)

                if not has_image:
                    issues["missing_images"].append(str(label_path))

        # 결과 출력
        total_issues = sum(len(v) for v in issues.values())

        if total_issues == 0:
            print("\n✅ 검증 완료: 문제 없음")
        else:
            print(f"\n⚠️ 검증 완료: {total_issues}개 문제 발견")
            if issues["missing_labels"]:
                print(f"  - 라벨 없는 이미지: {len(issues['missing_labels'])}개")
            if issues["missing_images"]:
                print(f"  - 이미지 없는 라벨: {len(issues['missing_images'])}개")
            if issues["empty_labels"]:
                print(f"  - 빈 라벨 파일: {len(issues['empty_labels'])}개")

            # 이슈 파일 저장
            issues_path = self.base_dir / "validation_issues.json"
            issues_path.write_text(json.dumps(issues, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"\n📝 이슈 목록 저장: {issues_path}")

        logger.info(f"Dataset validation complete: {total_issues} issues found")

        return issues


# 실행 스크립트
if __name__ == "__main__":
    from pathlib import Path
    import sys

    # 기본 디렉토리 설정
    if len(sys.argv) > 1:
        base_dir = Path(sys.argv[1])
    else:
        base_dir = Path("/home/pro301/git/en-zine/scholar/training/datasets")

    print("=" * 60)
    print("📊 Dataset Preparation Tool")
    print("=" * 60)
    print(f"데이터셋 경로: {base_dir}")
    print("=" * 60)

    manager = DatasetManager(base_dir)

    # 1. 데이터셋 검증
    print("\n[1/3] 데이터셋 검증...")
    issues = manager.validate_dataset()

    # 2. Train/Val/Test 분할 생성 (80%/10%/10%)
    print("\n[2/3] 데이터 분할...")
    manager.create_train_val_test_split(train_ratio=0.8, val_ratio=0.1)

    # 3. 리포트 생성
    print("\n[3/3] 리포트 생성...")
    report = manager.generate_dataset_report()

    print("\n" + "=" * 60)
    print("✅ 모든 작업 완료!")
    print("=" * 60)
