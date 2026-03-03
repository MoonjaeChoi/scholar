#!/usr/bin/env python3
"""
Fine-tuned 모델 성능 평가 스크립트
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List
import cv2
import numpy as np
from paddleocr import PaddleOCR
from loguru import logger

def load_test_data() -> List[Dict]:
    """테스트 데이터 로드"""
    test_data = []
    test_dir = Path("/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/test")

    if not test_dir.exists():
        # 검증 데이터를 테스트용으로 사용
        test_dir = Path("/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/val")

    images_dir = test_dir / "images"
    labels_dir = test_dir / "labels"

    for img_file in images_dir.glob("*.jpg"):
        label_file = labels_dir / f"{img_file.stem}.txt"

        if label_file.exists():
            with open(label_file, 'r', encoding='utf-8') as f:
                ground_truth = []
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) >= 3:
                        ground_truth.append(parts[2])  # 텍스트 내용

            test_data.append({
                'image_path': str(img_file),
                'ground_truth': ground_truth
            })

    logger.info(f"Loaded {len(test_data)} test samples")
    return test_data

def evaluate_baseline_model(test_data: List[Dict]) -> Dict:
    """기본 PaddleOCR 모델 평가"""
    logger.info("Evaluating baseline PaddleOCR model...")

    try:
        # 기본 PaddleOCR 초기화
        ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)

        results = {
            'total_samples': len(test_data),
            'processed_samples': 0,
            'total_characters': 0,
            'correct_characters': 0,
            'total_words': 0,
            'correct_words': 0,
            'processing_times': []
        }

        for i, sample in enumerate(test_data):
            try:
                start_time = time.time()

                # OCR 실행
                result = ocr.ocr(sample['image_path'], cls=True)

                processing_time = time.time() - start_time
                results['processing_times'].append(processing_time)

                if result and result[0]:
                    # 추출된 텍스트 정리
                    extracted_texts = [line[1][0] for line in result[0]]
                    extracted_text = ' '.join(extracted_texts)

                    # Ground truth와 비교
                    ground_truth_text = ' '.join(sample['ground_truth'])

                    # 문자 단위 정확도
                    char_accuracy = calculate_character_accuracy(extracted_text, ground_truth_text)
                    results['total_characters'] += len(ground_truth_text)
                    results['correct_characters'] += int(char_accuracy * len(ground_truth_text))

                    # 단어 단위 정확도
                    word_accuracy = calculate_word_accuracy(extracted_text, ground_truth_text)
                    gt_words = len(ground_truth_text.split())
                    results['total_words'] += gt_words
                    results['correct_words'] += int(word_accuracy * gt_words)

                results['processed_samples'] += 1

                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(test_data)} samples")

            except Exception as e:
                logger.warning(f"Error processing sample {i}: {e}")
                continue

        # 최종 메트릭 계산
        results['char_accuracy'] = results['correct_characters'] / results['total_characters'] if results['total_characters'] > 0 else 0
        results['word_accuracy'] = results['correct_words'] / results['total_words'] if results['total_words'] > 0 else 0
        results['avg_processing_time'] = np.mean(results['processing_times']) if results['processing_times'] else 0

        logger.info("✓ Baseline model evaluation completed")
        return results

    except Exception as e:
        logger.error(f"Error evaluating baseline model: {e}")
        return {}

def evaluate_finetuned_model(test_data: List[Dict]) -> Dict:
    """Fine-tuned 모델 평가"""
    logger.info("Evaluating fine-tuned model...")

    det_model_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/output/det_custom_web_inference"
    rec_model_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/output/rec_custom_web_inference"

    if not (os.path.exists(det_model_path) and os.path.exists(rec_model_path)):
        logger.error("Fine-tuned models not found. Please complete training first.")
        return {}

    try:
        # Fine-tuned 모델로 PaddleOCR 초기화
        ocr = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            det_model_dir=det_model_path,
            rec_model_dir=rec_model_path,
            show_log=False
        )

        results = {
            'total_samples': len(test_data),
            'processed_samples': 0,
            'total_characters': 0,
            'correct_characters': 0,
            'total_words': 0,
            'correct_words': 0,
            'processing_times': []
        }

        for i, sample in enumerate(test_data):
            try:
                start_time = time.time()

                result = ocr.ocr(sample['image_path'], cls=True)

                processing_time = time.time() - start_time
                results['processing_times'].append(processing_time)

                if result and result[0]:
                    extracted_texts = [line[1][0] for line in result[0]]
                    extracted_text = ' '.join(extracted_texts)
                    ground_truth_text = ' '.join(sample['ground_truth'])

                    char_accuracy = calculate_character_accuracy(extracted_text, ground_truth_text)
                    results['total_characters'] += len(ground_truth_text)
                    results['correct_characters'] += int(char_accuracy * len(ground_truth_text))

                    word_accuracy = calculate_word_accuracy(extracted_text, ground_truth_text)
                    gt_words = len(ground_truth_text.split())
                    results['total_words'] += gt_words
                    results['correct_words'] += int(word_accuracy * gt_words)

                results['processed_samples'] += 1

                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(test_data)} samples")

            except Exception as e:
                logger.warning(f"Error processing sample {i}: {e}")
                continue

        results['char_accuracy'] = results['correct_characters'] / results['total_characters'] if results['total_characters'] > 0 else 0
        results['word_accuracy'] = results['correct_words'] / results['total_words'] if results['total_words'] > 0 else 0
        results['avg_processing_time'] = np.mean(results['processing_times']) if results['processing_times'] else 0

        logger.info("✓ Fine-tuned model evaluation completed")
        return results

    except Exception as e:
        logger.error(f"Error evaluating fine-tuned model: {e}")
        return {}

def calculate_character_accuracy(pred_text: str, gt_text: str) -> float:
    """문자 단위 정확도 계산"""
    if not gt_text:
        return 1.0 if not pred_text else 0.0

    # 간단한 edit distance 기반 정확도
    pred_chars = list(pred_text.lower())
    gt_chars = list(gt_text.lower())

    # Levenshtein distance 계산
    m, n = len(pred_chars), len(gt_chars)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if pred_chars[i-1] == gt_chars[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])

    edit_distance = dp[m][n]
    accuracy = max(0.0, 1.0 - edit_distance / max(m, n))
    return accuracy

def calculate_word_accuracy(pred_text: str, gt_text: str) -> float:
    """단어 단위 정확도 계산"""
    pred_words = set(pred_text.lower().split())
    gt_words = set(gt_text.lower().split())

    if not gt_words:
        return 1.0 if not pred_words else 0.0

    intersection = pred_words.intersection(gt_words)
    return len(intersection) / len(gt_words)

def generate_evaluation_report(baseline_results: Dict, finetuned_results: Dict):
    """평가 리포트 생성"""
    report = {
        "evaluation_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "baseline_performance": baseline_results,
        "finetuned_performance": finetuned_results,
        "improvement": {}
    }

    if baseline_results and finetuned_results:
        report["improvement"]["char_accuracy"] = finetuned_results.get("char_accuracy", 0) - baseline_results.get("char_accuracy", 0)
        report["improvement"]["word_accuracy"] = finetuned_results.get("word_accuracy", 0) - baseline_results.get("word_accuracy", 0)
        report["improvement"]["processing_time"] = baseline_results.get("avg_processing_time", 0) - finetuned_results.get("avg_processing_time", 0)

    # 결과 저장
    output_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/output/evaluation_report.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"Evaluation report saved to: {output_path}")

    # 콘솔 출력
    print("\n" + "="*60)
    print("MODEL EVALUATION REPORT")
    print("="*60)

    if baseline_results:
        print(f"\nBaseline Model Performance:")
        print(f"  Character Accuracy: {baseline_results.get('char_accuracy', 0):.3f}")
        print(f"  Word Accuracy: {baseline_results.get('word_accuracy', 0):.3f}")
        print(f"  Avg Processing Time: {baseline_results.get('avg_processing_time', 0):.3f}s")

    if finetuned_results:
        print(f"\nFine-tuned Model Performance:")
        print(f"  Character Accuracy: {finetuned_results.get('char_accuracy', 0):.3f}")
        print(f"  Word Accuracy: {finetuned_results.get('word_accuracy', 0):.3f}")
        print(f"  Avg Processing Time: {finetuned_results.get('avg_processing_time', 0):.3f}s")

    if baseline_results and finetuned_results:
        print(f"\nImprovement:")
        print(f"  Character Accuracy: {report['improvement']['char_accuracy']:+.3f}")
        print(f"  Word Accuracy: {report['improvement']['word_accuracy']:+.3f}")
        print(f"  Processing Time: {report['improvement']['processing_time']:+.3f}s")

    print("="*60)

def main():
    """메인 함수"""
    logger.info("=== Model Performance Evaluation ===")

    # 테스트 데이터 로드
    test_data = load_test_data()

    if not test_data:
        logger.error("No test data available")
        return 1

    # 기본 모델 평가
    baseline_results = evaluate_baseline_model(test_data)

    # Fine-tuned 모델 평가
    finetuned_results = evaluate_finetuned_model(test_data)

    # 평가 리포트 생성
    generate_evaluation_report(baseline_results, finetuned_results)

    logger.info("🎉 Model evaluation completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())