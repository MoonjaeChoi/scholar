#!/usr/bin/env python3
"""
C++에서 사용할 Python OCR API 서비스 생성
"""

import os
import sys
import json
import argparse
from pathlib import Path
from paddleocr import PaddleOCR
from loguru import logger

class PythonOCRService:
    def __init__(self, det_model_path: str, rec_model_path: str):
        """Fine-tuned 모델로 OCR 서비스 초기화"""
        try:
            self.ocr = PaddleOCR(
                use_angle_cls=True,
                lang='en',
                det_model_dir=det_model_path,
                rec_model_dir=rec_model_path,
                show_log=False
            )
            logger.info("OCR service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize OCR service: {e}")
            raise

    def process_image(self, image_path: str) -> dict:
        """이미지 OCR 처리"""
        try:
            if not os.path.exists(image_path):
                return {"error": f"Image file not found: {image_path}"}

            # OCR 실행
            results = self.ocr.ocr(image_path, cls=True)

            if not results or not results[0]:
                return {"text_boxes": [], "extracted_text": ""}

            # 결과 정리
            text_boxes = []
            all_text = []

            for line in results[0]:
                bbox = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                text_info = line[1]  # (text, confidence)

                text_content = text_info[0]
                confidence = text_info[1]

                # 바운딩 박스 좌표 정리
                x_coords = [point[0] for point in bbox]
                y_coords = [point[1] for point in bbox]

                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)

                text_box = {
                    "text": text_content,
                    "confidence": confidence,
                    "bbox": {
                        "x": x_min,
                        "y": y_min,
                        "width": x_max - x_min,
                        "height": y_max - y_min
                    },
                    "points": bbox
                }

                text_boxes.append(text_box)
                all_text.append(text_content)

            return {
                "text_boxes": text_boxes,
                "extracted_text": " ".join(all_text),
                "total_boxes": len(text_boxes)
            }

        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")
            return {"error": str(e)}

def create_service_script():
    """C++에서 호출할 OCR 서비스 스크립트 생성"""
    service_script = '''#!/usr/bin/env python3
"""
C++에서 호출하는 PaddleOCR 서비스 스크립트
사용법: python ocr_service.py <detection_model_path> <recognition_model_path> <image_path>
"""

import sys
import json
from pathlib import Path

# 프로젝트 경로 추가
sys.path.append('/home/pro301/git/en-zine/ocr_system/paddleocr_training')

try:
    from paddleocr import PaddleOCR
    import cv2
    import os
except ImportError as e:
    print(json.dumps({"error": f"Import error: {e}"}))
    sys.exit(1)

def main():
    if len(sys.argv) != 4:
        print(json.dumps({
            "error": "Usage: python ocr_service.py <det_model_path> <rec_model_path> <image_path>"
        }))
        sys.exit(1)

    det_model_path = sys.argv[1]
    rec_model_path = sys.argv[2]
    image_path = sys.argv[3]

    try:
        # 모델 경로 검증
        if not os.path.exists(det_model_path):
            print(json.dumps({"error": f"Detection model not found: {det_model_path}"}))
            sys.exit(1)

        if not os.path.exists(rec_model_path):
            print(json.dumps({"error": f"Recognition model not found: {rec_model_path}"}))
            sys.exit(1)

        if not os.path.exists(image_path):
            print(json.dumps({"error": f"Image file not found: {image_path}"}))
            sys.exit(1)

        # OCR 서비스 초기화
        ocr = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            det_model_dir=det_model_path,
            rec_model_dir=rec_model_path,
            show_log=False
        )

        # 이미지 처리
        results = ocr.ocr(image_path, cls=True)

        if not results or not results[0]:
            print(json.dumps({
                "text_boxes": [],
                "extracted_text": "",
                "total_boxes": 0
            }))
            sys.exit(0)

        # 결과 변환
        text_boxes = []
        all_text = []

        for line in results[0]:
            bbox = line[0]
            text_info = line[1]

            text_content = text_info[0]
            confidence = text_info[1]

            # 바운딩 박스 좌표
            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]

            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)

            text_box = {
                "text": text_content,
                "confidence": confidence,
                "x": x_min,
                "y": y_min,
                "width": x_max - x_min,
                "height": y_max - y_min
            }

            text_boxes.append(text_box)
            all_text.append(text_content)

        result = {
            "text_boxes": text_boxes,
            "extracted_text": " ".join(all_text),
            "total_boxes": len(text_boxes),
            "success": True
        }

        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": str(e), "success": False}))
        sys.exit(1)

if __name__ == "__main__":
    main()
'''

    # 스크립트 파일 생성
    script_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/ocr_service.py"
    with open(script_path, 'w') as f:
        f.write(service_script)

    # 실행 권한 부여
    os.chmod(script_path, 0o755)

    logger.info(f"OCR service script created at: {script_path}")
    return script_path

def main():
    parser = argparse.ArgumentParser(description='Create Python OCR service for C++ integration')
    parser.add_argument('--create-script', action='store_true',
                       help='Create OCR service script')
    parser.add_argument('--test', action='store_true',
                       help='Test the OCR service')

    args = parser.parse_args()

    if args.create_script:
        script_path = create_service_script()
        print(f"OCR service script created: {script_path}")

    if args.test:
        # 테스트 이미지로 서비스 테스트
        det_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/output/det_custom_web_inference"
        rec_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/output/rec_custom_web_inference"

        if os.path.exists(det_path) and os.path.exists(rec_path):
            service = PythonOCRService(det_path, rec_path)

            # 테스트 이미지 생성 및 테스트
            import cv2
            import numpy as np

            test_img = np.ones((200, 600, 3), dtype=np.uint8) * 255
            cv2.putText(test_img, "Test Fine-tuned PaddleOCR", (50, 100),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

            test_img_path = "/tmp/test_finetuned_ocr.png"
            cv2.imwrite(test_img_path, test_img)

            result = service.process_image(test_img_path)
            print("Test result:", json.dumps(result, indent=2))

            os.remove(test_img_path)
        else:
            print("Fine-tuned models not found. Please complete training first.")

if __name__ == "__main__":
    main()