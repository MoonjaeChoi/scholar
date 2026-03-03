#!/usr/bin/env python3
"""
PaddleOCR 환경 테스트 스크립트
"""

import paddle
import cv2
import numpy as np
from paddleocr import PaddleOCR
import os

def test_paddle_installation():
    """PaddlePaddle 설치 테스트"""
    print("Testing PaddlePaddle installation...")
    try:
        print(f"PaddlePaddle version: {paddle.__version__}")

        # GPU 지원 테스트
        if paddle.device.is_compiled_with_cuda():
            print("✓ CUDA support available")
            if paddle.device.cuda.device_count() > 0:
                print(f"✓ GPU devices available: {paddle.device.cuda.device_count()}")
            else:
                print("⚠ CUDA compiled but no GPU devices found")
        else:
            print("ℹ CPU-only version")

        # 간단한 연산 테스트
        x = paddle.randn([2, 3])
        y = paddle.matmul(x, x.t())
        print("✓ Basic paddle operations working")

        return True
    except Exception as e:
        print(f"✗ PaddlePaddle test failed: {e}")
        return False

def test_paddleocr():
    """PaddleOCR 기본 기능 테스트"""
    print("\nTesting PaddleOCR functionality...")
    try:
        # 테스트 이미지 생성
        test_img = np.ones((100, 300, 3), dtype=np.uint8) * 255
        cv2.putText(test_img, "Hello PaddleOCR", (10, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

        test_img_path = "/tmp/test_paddleocr.png"
        cv2.imwrite(test_img_path, test_img)

        # PaddleOCR 인스턴스 생성
        ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)

        # OCR 실행
        result = ocr.ocr(test_img_path, cls=True)

        if result and result[0]:
            detected_text = result[0][0][1][0]
            print(f"✓ OCR test successful. Detected: '{detected_text}'")

            # 정확도 확인
            if "Hello" in detected_text and "PaddleOCR" in detected_text:
                print("✓ OCR accuracy test passed")
            else:
                print("⚠ OCR accuracy test warning: text recognition may be inaccurate")
        else:
            print("⚠ OCR test warning: no text detected")

        # 임시 파일 삭제
        os.remove(test_img_path)

        return True
    except Exception as e:
        print(f"✗ PaddleOCR test failed: {e}")
        return False

def test_pretrained_models():
    """사전 학습된 모델 테스트"""
    print("\nTesting pretrained models...")

    model_paths = [
        "/home/pro301/git/en-zine/ocr_system/paddleocr_training/models/detection/en_PP-OCRv3_det_infer",
        "/home/pro301/git/en-zine/ocr_system/paddleocr_training/models/recognition/en_PP-OCRv3_rec_infer"
    ]

    for model_path in model_paths:
        if os.path.exists(model_path):
            print(f"✓ Model found: {os.path.basename(model_path)}")
        else:
            print(f"✗ Model missing: {os.path.basename(model_path)}")
            return False

    return True

def test_dataset_structure():
    """데이터셋 구조 테스트"""
    print("\nTesting dataset structure...")

    required_dirs = [
        "/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train/images",
        "/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train/labels",
        "/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/val/images",
        "/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/val/labels"
    ]

    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            file_count = len(os.listdir(dir_path))
            print(f"✓ Directory exists: {dir_path} ({file_count} files)")
        else:
            print(f"✗ Directory missing: {dir_path}")
            return False

    return True

def main():
    """전체 환경 테스트"""
    print("="*60)
    print("PaddleOCR Environment Test")
    print("="*60)

    tests = [
        ("PaddlePaddle Installation", test_paddle_installation),
        ("PaddleOCR Functionality", test_paddleocr),
        ("Pretrained Models", test_pretrained_models),
        ("Dataset Structure", test_dataset_structure)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 40)
        if test_func():
            passed += 1

    print("\n" + "="*60)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All tests passed! PaddleOCR environment is ready for training.")
        return 0
    else:
        print("✗ Some tests failed. Please check the configuration.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())