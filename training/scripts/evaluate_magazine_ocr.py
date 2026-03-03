# Generated: 2025-10-12 00:20:00 KST
"""
잡지 특화 OCR 성능 평가 스크립트
Magazine-specific OCR Performance Evaluator

Features:
- 레이아웃 타입별 정확도 측정
- 폰트 타입별 정확도 측정
- Levenshtein distance 계산
- F1 Score, CER, WER 계산
- 상세 리포트 생성
"""

from pathlib import Path
from paddleocr import PaddleOCR
import json
from typing import Dict, List, Tuple
from datetime import datetime
from loguru import logger
import numpy as np


class MagazineOCREvaluator:
    """잡지 OCR 성능 평가"""

    def __init__(self, model_path: str, test_dataset_dir: Path):
        """
        Args:
            model_path: PaddleOCR 모델 디렉토리 경로
            test_dataset_dir: 테스트 데이터셋 기본 경로
        """
        self.model_path = model_path
        self.test_dir = Path(test_dataset_dir)

        # PaddleOCR 초기화
        try:
            self.ocr = PaddleOCR(
                det_model_dir=f"{model_path}/det" if Path(f"{model_path}/det").exists() else None,
                rec_model_dir=f"{model_path}/rec" if Path(f"{model_path}/rec").exists() else None,
                use_gpu=True,
                lang='korean',
                show_log=False
            )
            logger.info(f"PaddleOCR initialized with model: {model_path}")
        except Exception as e:
            logger.error(f"PaddleOCR initialization failed: {e}")
            # Fallback to default model
            self.ocr = PaddleOCR(use_gpu=True, lang='korean', show_log=False)
            logger.warning("Using default PaddleOCR model")

    def evaluate_by_category(self) -> Dict[str, Dict]:
        """카테고리별 평가"""
        logger.info("카테고리별 평가 시작...")
        print("\n" + "=" * 60)
        print("📊 카테고리별 OCR 성능 평가")
        print("=" * 60)

        categories = {
            "general_documents": self.test_dir / "validation/general_documents",
            "magazine_layouts": self.test_dir / "validation/magazine_layouts",
            "decorative_fonts": self.test_dir / "validation/decorative_fonts",
            "vertical_text": self.test_dir / "validation/vertical_text",
        }

        results = {}

        for category, cat_dir in categories.items():
            print(f"\n📁 평가 중: {category}")

            if not cat_dir.exists():
                print(f"  ⚠️ 디렉토리 없음: {cat_dir}")
                logger.warning(f"Category directory not found: {cat_dir}")
                continue

            images = list(cat_dir.glob("*.jpg")) + list(cat_dir.glob("*.png"))
            if not images:
                print(f"  ⚠️ 이미지 없음")
                logger.warning(f"No images found in: {cat_dir}")
                continue

            category_metrics = {
                'character_accuracy': [],
                'word_accuracy': [],
                'edit_distance': [],
                'cer': [],  # Character Error Rate
                'wer': [],  # Word Error Rate
                'predictions': []  # 예측 샘플 저장
            }

            for i, img_path in enumerate(images):
                try:
                    # Ground truth 로드
                    gt_path = img_path.with_suffix('.txt')
                    if not gt_path.exists():
                        logger.warning(f"Ground truth not found: {gt_path}")
                        continue

                    ground_truth = gt_path.read_text(encoding='utf-8').strip()

                    # OCR 실행
                    ocr_result = self.ocr.ocr(str(img_path), cls=True)
                    predicted_text = self._extract_text_from_result(ocr_result)

                    # 메트릭 계산
                    char_acc = self._calculate_character_accuracy(predicted_text, ground_truth)
                    word_acc = self._calculate_word_accuracy(predicted_text, ground_truth)
                    edit_dist = self._levenshtein_distance(predicted_text, ground_truth)
                    cer = self._calculate_cer(predicted_text, ground_truth)
                    wer = self._calculate_wer(predicted_text, ground_truth)

                    category_metrics['character_accuracy'].append(char_acc)
                    category_metrics['word_accuracy'].append(word_acc)
                    category_metrics['edit_distance'].append(edit_dist)
                    category_metrics['cer'].append(cer)
                    category_metrics['wer'].append(wer)

                    # 샘플 저장 (처음 5개만)
                    if len(category_metrics['predictions']) < 5:
                        category_metrics['predictions'].append({
                            'image': str(img_path),
                            'ground_truth': ground_truth,
                            'predicted': predicted_text,
                            'character_accuracy': char_acc,
                            'cer': cer
                        })

                    # 진행 상황
                    if (i + 1) % 10 == 0:
                        print(f"  진행: {i+1}/{len(images)}")

                except Exception as e:
                    logger.error(f"Error evaluating {img_path}: {e}")
                    continue

            # 평균 계산
            if category_metrics['character_accuracy']:
                results[category] = {
                    'character_accuracy': np.mean(category_metrics['character_accuracy']) * 100,
                    'word_accuracy': np.mean(category_metrics['word_accuracy']) * 100,
                    'avg_edit_distance': np.mean(category_metrics['edit_distance']),
                    'cer': np.mean(category_metrics['cer']) * 100,
                    'wer': np.mean(category_metrics['wer']) * 100,
                    'num_samples': len(category_metrics['character_accuracy']),
                    'sample_predictions': category_metrics['predictions']
                }

                print(f"  ✅ 문자 정확도: {results[category]['character_accuracy']:.2f}%")
                print(f"  ✅ 단어 정확도: {results[category]['word_accuracy']:.2f}%")
                print(f"  ✅ CER: {results[category]['cer']:.2f}%")
                print(f"  ✅ WER: {results[category]['wer']:.2f}%")
                print(f"  ✅ 평균 편집 거리: {results[category]['avg_edit_distance']:.2f}")
                print(f"  📊 샘플 수: {results[category]['num_samples']}")

                logger.info(f"Category {category}: CER={results[category]['cer']:.2f}%, WER={results[category]['wer']:.2f}%")
            else:
                print(f"  ❌ 평가 실패: 유효한 샘플 없음")

        return results

    def evaluate_from_split(self, split_file: Path) -> Dict:
        """분할 파일 (train.txt, val.txt, test.txt)에서 평가

        Args:
            split_file: 분할 파일 경로 (PaddleOCR 형식: image_path\tlabel_path)

        Returns:
            평가 결과 딕셔너리
        """
        print(f"\n📄 분할 파일에서 평가: {split_file}")
        logger.info(f"Evaluating from split file: {split_file}")

        if not split_file.exists():
            logger.error(f"Split file not found: {split_file}")
            return {}

        metrics = {
            'character_accuracy': [],
            'word_accuracy': [],
            'edit_distance': [],
            'cer': [],
            'wer': []
        }

        with open(split_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        total = len(lines)
        print(f"  총 {total}개 샘플 평가")

        for i, line in enumerate(lines):
            try:
                parts = line.strip().split('\t')
                if len(parts) < 2:
                    continue

                img_path = Path(parts[0])
                label_path = Path(parts[1]) if len(parts) > 1 else img_path.with_suffix('.txt')

                if not img_path.exists() or not label_path.exists():
                    continue

                # Ground truth 로드
                ground_truth = label_path.read_text(encoding='utf-8').strip()

                # OCR 실행
                ocr_result = self.ocr.ocr(str(img_path), cls=True)
                predicted_text = self._extract_text_from_result(ocr_result)

                # 메트릭 계산
                char_acc = self._calculate_character_accuracy(predicted_text, ground_truth)
                word_acc = self._calculate_word_accuracy(predicted_text, ground_truth)
                edit_dist = self._levenshtein_distance(predicted_text, ground_truth)
                cer = self._calculate_cer(predicted_text, ground_truth)
                wer = self._calculate_wer(predicted_text, ground_truth)

                metrics['character_accuracy'].append(char_acc)
                metrics['word_accuracy'].append(word_acc)
                metrics['edit_distance'].append(edit_dist)
                metrics['cer'].append(cer)
                metrics['wer'].append(wer)

                # 진행 상황
                if (i + 1) % 50 == 0:
                    print(f"  진행: {i+1}/{total} ({(i+1)/total*100:.1f}%)")

            except Exception as e:
                logger.error(f"Error evaluating line {i}: {e}")
                continue

        # 결과 계산
        if metrics['character_accuracy']:
            result = {
                'character_accuracy': np.mean(metrics['character_accuracy']) * 100,
                'word_accuracy': np.mean(metrics['word_accuracy']) * 100,
                'avg_edit_distance': np.mean(metrics['edit_distance']),
                'cer': np.mean(metrics['cer']) * 100,
                'wer': np.mean(metrics['wer']) * 100,
                'num_samples': len(metrics['character_accuracy'])
            }

            print(f"\n  ✅ 문자 정확도: {result['character_accuracy']:.2f}%")
            print(f"  ✅ CER: {result['cer']:.2f}%")
            print(f"  ✅ WER: {result['wer']:.2f}%")

            return result
        else:
            print(f"  ❌ 평가 실패")
            return {}

    def _extract_text_from_result(self, ocr_result) -> str:
        """OCR 결과에서 텍스트 추출"""
        if not ocr_result or not ocr_result[0]:
            return ""

        text_lines = []
        for line in ocr_result[0]:
            if line and len(line) > 1 and line[1]:
                text_lines.append(line[1][0])

        return " ".join(text_lines)

    def _calculate_character_accuracy(self, predicted: str, ground_truth: str) -> float:
        """문자 단위 정확도"""
        if not ground_truth:
            return 0.0

        max_len = max(len(predicted), len(ground_truth))
        if max_len == 0:
            return 1.0

        correct = sum(1 for p, g in zip(predicted, ground_truth) if p == g)
        return correct / max_len

    def _calculate_word_accuracy(self, predicted: str, ground_truth: str) -> float:
        """단어 단위 정확도"""
        pred_words = predicted.split()
        gt_words = ground_truth.split()

        if not gt_words:
            return 0.0

        max_len = max(len(pred_words), len(gt_words))
        if max_len == 0:
            return 1.0

        correct = sum(1 for p, g in zip(pred_words, gt_words) if p == g)
        return correct / max_len

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Levenshtein 편집 거리 계산"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # 삽입, 삭제, 교체 비용
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _calculate_cer(self, predicted: str, ground_truth: str) -> float:
        """Character Error Rate 계산"""
        if not ground_truth:
            return 0.0

        distance = self._levenshtein_distance(predicted, ground_truth)
        return distance / len(ground_truth)

    def _calculate_wer(self, predicted: str, ground_truth: str) -> float:
        """Word Error Rate 계산"""
        pred_words = predicted.split()
        gt_words = ground_truth.split()

        if not gt_words:
            return 0.0

        distance = self._levenshtein_distance(" ".join(pred_words), " ".join(gt_words))
        return distance / len(" ".join(gt_words))

    def generate_report(self, results: Dict, output_path: Path):
        """평가 리포트 생성"""
        logger.info(f"Generating evaluation report: {output_path}")

        # 전체 평균 계산
        if results:
            overall = {
                'character_accuracy': np.mean([r['character_accuracy'] for r in results.values() if 'character_accuracy' in r]),
                'word_accuracy': np.mean([r['word_accuracy'] for r in results.values() if 'word_accuracy' in r]),
                'cer': np.mean([r['cer'] for r in results.values() if 'cer' in r]),
                'wer': np.mean([r['wer'] for r in results.values() if 'wer' in r]),
                'total_samples': sum(r.get('num_samples', 0) for r in results.values())
            }
        else:
            overall = {}

        report = {
            "evaluation_date": datetime.now().isoformat(),
            "model_path": str(self.model_path),
            "test_dataset": str(self.test_dir),
            "results_by_category": results,
            "summary": overall
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

        print(f"\n✅ 리포트 저장: {output_path}")
        print(f"\n" + "=" * 60)
        print("📊 전체 요약")
        print("=" * 60)
        if overall:
            print(f"  문자 정확도: {overall['character_accuracy']:.2f}%")
            print(f"  단어 정확도: {overall['word_accuracy']:.2f}%")
            print(f"  CER: {overall['cer']:.2f}%")
            print(f"  WER: {overall['wer']:.2f}%")
            print(f"  총 샘플: {overall['total_samples']}개")

        logger.info(f"Report generated: {output_path}")


# 실행 스크립트
if __name__ == "__main__":
    from pathlib import Path
    import sys

    # 모델 경로 설정
    if len(sys.argv) > 1:
        model_path = sys.argv[1]
    else:
        model_path = "/home/pro301/git/en-zine/scholar/training/models/magazine_ocr_v1"

    # 테스트 데이터셋 경로
    if len(sys.argv) > 2:
        test_dir = Path(sys.argv[2])
    else:
        test_dir = Path("/home/pro301/git/en-zine/scholar/training/datasets")

    print("=" * 60)
    print("📊 Magazine OCR Evaluator")
    print("=" * 60)
    print(f"모델 경로: {model_path}")
    print(f"테스트 데이터: {test_dir}")
    print("=" * 60)

    evaluator = MagazineOCREvaluator(model_path, test_dir)

    # 카테고리별 평가
    results = evaluator.evaluate_by_category()

    # 분할 파일 평가 (test.txt가 있으면)
    test_split = test_dir / "splits" / "test_list.txt"
    if test_split.exists():
        print(f"\n추가 평가: 테스트 분할 파일")
        split_results = evaluator.evaluate_from_split(test_split)
        results['test_split'] = split_results

    # 리포트 생성
    report_path = Path("/home/pro301/git/en-zine/scholar/training/evaluation_reports/magazine_ocr_eval.json")
    evaluator.generate_report(results, report_path)

    print("\n" + "=" * 60)
    print("✅ 평가 완료!")
    print("=" * 60)
