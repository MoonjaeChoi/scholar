#!/usr/bin/env python3
"""
데이터베이스의 캡처 데이터를 PaddleOCR 학습 형식으로 변환
"""

import os
import json
import shutil
from typing import List, Dict, Tuple
from pathlib import Path
import cv2
import numpy as np
from loguru import logger
import random

# 데이터베이스 연결
import sys
sys.path.append('/home/pro301/git/en-zine/ocr_system/paddleocr_training')
from database_connection import DatabaseConnection

class PaddleOCRDatasetConverter:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.db_connection = DatabaseConnection()

        # 출력 디렉토리 생성
        self.train_dir = self.output_dir / "train"
        self.val_dir = self.output_dir / "val"

        for dir_path in [self.train_dir, self.val_dir]:
            (dir_path / "images").mkdir(parents=True, exist_ok=True)
            (dir_path / "labels").mkdir(parents=True, exist_ok=True)

    def get_quality_captures(self, min_quality_score: float = 0.7) -> List[Dict]:
        """고품질 캡처 데이터 조회"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()

                sql = """
                SELECT wcd.CAPTURE_ID, wcd.URL, wcd.IMAGE_PATH,
                       COUNT(tbb.BOX_ID) as bbox_count,
                       AVG(tbb.CONFIDENCE_SCORE) as avg_confidence
                FROM WEB_CAPTURE_DATA wcd
                JOIN TEXT_BOUNDING_BOXES tbb ON wcd.CAPTURE_ID = tbb.CAPTURE_ID
                WHERE wcd.PROCESSING_STATUS = 'completed'
                  AND wcd.IMAGE_PATH IS NOT NULL
                GROUP BY wcd.CAPTURE_ID, wcd.URL, wcd.IMAGE_PATH
                HAVING COUNT(tbb.BOX_ID) >= 5
                   AND AVG(tbb.CONFIDENCE_SCORE) >= :1
                ORDER BY COUNT(tbb.BOX_ID) DESC
                """

                cursor.execute(sql, (min_quality_score,))
                results = []

                for row in cursor.fetchall():
                    results.append({
                        'capture_id': row[0],
                        'source_url': row[1],
                        'image_path': row[2],
                        'bbox_count': row[3],
                        'avg_confidence': row[4]
                    })

                return results

        except Exception as e:
            logger.error(f"Error getting quality captures: {e}")
            return []

    def get_bounding_boxes(self, capture_id: int) -> List[Dict]:
        """특정 캡처의 바운딩 박스 정보 조회"""
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()

                sql = """
                SELECT TEXT_CONTENT, X_COORDINATE, Y_COORDINATE,
                       WIDTH, HEIGHT, CONFIDENCE_SCORE
                FROM TEXT_BOUNDING_BOXES
                WHERE CAPTURE_ID = :1
                  AND X_COORDINATE >= 0
                  AND Y_COORDINATE >= 0
                  AND WIDTH > 0
                  AND HEIGHT > 0
                ORDER BY Y_COORDINATE, X_COORDINATE
                """

                cursor.execute(sql, (capture_id,))
                boxes = []

                # Oracle LOB must be read before connection closes
                for row in cursor.fetchall():
                    # Immediately read LOB data (TEXT_CONTENT is CLOB)
                    text_content = row[0].read() if row[0] and hasattr(row[0], 'read') else (row[0] if row[0] else '')

                    boxes.append({
                        'text': text_content,
                        'x': float(row[1]) if row[1] else 0.0,
                        'y': float(row[2]) if row[2] else 0.0,
                        'width': float(row[3]) if row[3] else 0.0,
                        'height': float(row[4]) if row[4] else 0.0,
                        'confidence': float(row[5]) if row[5] else 0.0
                    })

                return boxes

        except Exception as e:
            logger.error(f"Error getting bounding boxes for capture {capture_id}: {e}")
            return []

    def convert_to_paddleocr_format(self, boxes: List[Dict], max_boxes: int = 100) -> List[Dict]:
        """PaddleOCR 형식으로 변환 (큰 bounding box만 선택)"""
        paddleocr_annotations = []

        # ⚠️ RecursionError 방지: 면적이 큰 bounding box만 선택
        # Shapely 1.8.5.post1 downgrade로 안정성 확보
        # 해결: 면적(width × height) 기준 상위 100개 선택
        # bbox 100개 초과 시 면적 기준 상위 100개만 학습에 사용
        sorted_boxes = sorted(boxes, key=lambda x: x.get('width', 0) * x.get('height', 0), reverse=True)
        limited_boxes = sorted_boxes[:max_boxes]

        if len(boxes) > max_boxes:
            logger.info(f"Selected top {max_boxes} bboxes (by area) from {len(boxes)} total (largest area first)")

        for box in limited_boxes:
            # PaddleOCR는 4개 모서리 좌표를 요구
            x, y, w, h = box['x'], box['y'], box['width'], box['height']

            # ⚠️ RecursionError 방지: 좌표를 정수로 변환 + 유효성 검증
            # shapely Polygon 객체 생성 시 소수점 좌표가 문제를 일으킬 수 있음
            try:
                x, y = int(round(x)), int(round(y))
                w, h = int(round(w)), int(round(h))

                # 너무 작은 bbox 제외 (min_size=3)
                if w < 3 or h < 3:
                    continue

                # 좌표 형식: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                points = [
                    [x, y],                    # 좌상단
                    [x + w, y],                # 우상단
                    [x + w, y + h],            # 우하단
                    [x, y + h]                 # 좌하단
                ]

                paddleocr_annotations.append({
                    "transcription": box['text'],
                    "points": points,
                    "difficult": False
                })
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid bbox coordinates: {box}, error: {e}")
                continue

        return paddleocr_annotations

    def copy_and_process_image(self, src_path: str, dst_path: str) -> bool:
        """이미지 복사 및 전처리"""
        try:
            # 이미지 로드
            img = cv2.imread(src_path)
            if img is None:
                logger.error(f"Cannot load image: {src_path}")
                return False

            # 이미지 크기 정규화 (선택사항)
            height, width = img.shape[:2]

            # 너무 큰 이미지는 리사이즈
            max_size = 2048
            if max(height, width) > max_size:
                if width > height:
                    new_width = max_size
                    new_height = int(height * max_size / width)
                else:
                    new_height = max_size
                    new_width = int(width * max_size / height)

                img = cv2.resize(img, (new_width, new_height))
                logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}")

            # 이미지 저장
            cv2.imwrite(dst_path, img)
            return True

        except Exception as e:
            logger.error(f"Error processing image {src_path}: {e}")
            return False

    def convert_dataset(self, train_ratio: float = 0.8, max_samples: int = 1000) -> Tuple[int, int]:
        """데이터셋 변환"""
        logger.info("Starting dataset conversion...")

        # 고품질 캡처 데이터 조회
        quality_captures = self.get_quality_captures()
        logger.info(f"Found {len(quality_captures)} quality captures")

        if len(quality_captures) > max_samples:
            quality_captures = random.sample(quality_captures, max_samples)
            logger.info(f"Limited to {max_samples} samples")

        # 학습/검증 분할
        random.shuffle(quality_captures)
        split_idx = int(len(quality_captures) * train_ratio)
        train_captures = quality_captures[:split_idx]
        val_captures = quality_captures[split_idx:]

        logger.info(f"Train samples: {len(train_captures)}, Val samples: {len(val_captures)}")

        # 변환 실행
        train_count = self._convert_samples(train_captures, self.train_dir)
        val_count = self._convert_samples(val_captures, self.val_dir)

        return train_count, val_count

    def _convert_samples(self, captures: List[Dict], output_dir: Path) -> int:
        """샘플 변환"""
        successful_count = 0

        for i, capture in enumerate(captures):
            try:
                capture_id = capture['capture_id']
                src_image_path = capture['image_path']

                # 이미지 파일명 생성
                image_filename = f"image_{capture_id}.jpg"
                label_filename = f"image_{capture_id}.txt"

                dst_image_path = output_dir / "images" / image_filename
                dst_label_path = output_dir / "labels" / label_filename

                # 이미지 복사 및 처리
                if not self.copy_and_process_image(src_image_path, str(dst_image_path)):
                    continue

                # 바운딩 박스 조회 및 변환
                boxes = self.get_bounding_boxes(capture_id)
                if not boxes:
                    continue

                # ⚠️ RecursionError 방지: 큰 박스만 선택 (기본값 50개)
                # 면적 기준 상위 50개로 학습 데이터 풍부화
                paddleocr_annotations = self.convert_to_paddleocr_format(boxes)

                # 라벨 파일 생성 (PaddleOCR Detection 형식 - 한 이미지당 하나의 라인)
                with open(dst_label_path, 'w', encoding='utf-8') as f:
                    # 모든 bbox를 하나의 JSON 배열로 작성
                    label_dicts = [
                        {
                            "transcription": ann['transcription'],
                            "points": ann['points']
                        }
                        for ann in paddleocr_annotations
                    ]
                    # 한 라인에 이미지 경로와 전체 bbox 배열 기록
                    f.write(f"images/{image_filename}\t{json.dumps(label_dicts, ensure_ascii=False)}\n")

                successful_count += 1

                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(captures)} samples")

            except Exception as e:
                logger.error(f"Error converting capture {capture.get('capture_id', 'unknown')}: {e}")
                continue

        logger.info(f"Successfully converted {successful_count}/{len(captures)} samples")
        return successful_count

    def create_file_lists(self):
        """PaddleOCR 학습용 파일 리스트 생성 (상대 경로 사용)"""
        # ⚠️ 파일 리스트는 PaddleOCR 기본 위치에 저장
        # PaddleOCR 학습 시 data/ 디렉토리에서 파일 리스트를 찾음
        base_data_dir = Path("/home/pro301/git/en-zine/ocr_system/paddleocr_training/data")
        base_data_dir.mkdir(parents=True, exist_ok=True)

        train_list_path = base_data_dir / "train_list.txt"
        val_list_path = base_data_dir / "val_list.txt"

        # 학습용 리스트 (상대 경로 사용)
        with open(train_list_path, 'w') as f:
            image_dir = self.train_dir / "images"
            for image_file in sorted(image_dir.glob("*.jpg")):
                # 상대 경로로 이미지 위치 지정 (data_dir 기준)
                # data_dir이 /home/pro301/paddleocr_training/data_new/ 이면
                # train/images/image_10.jpg 형식으로 저장
                image_path = f"train/images/{image_file.name}"

                # 대응하는 라벨 파일 읽기
                label_file = self.train_dir / "labels" / f"{image_file.stem}.txt"
                if label_file.exists():
                    with open(label_file, 'r', encoding='utf-8') as label_f:
                        label_content = label_f.read().strip()
                        # 라벨 내용에서 이미지 경로를 상대 경로로 변경
                        if label_content.startswith("images/"):
                            # images/xxx.jpg -> train/images/xxx.jpg
                            label_content = label_content.replace("images/", "train/images/", 1)
                        # 이미 절대 경로인 경우 상대 경로로 변환
                        elif "/" in label_content and label_content.split('\t')[0].startswith("/"):
                            parts = label_content.split('\t')
                            parts[0] = image_path
                            label_content = '\t'.join(parts)
                        f.write(label_content + "\n")

        # 검증용 리스트 (상대 경로 사용)
        with open(val_list_path, 'w') as f:
            image_dir = self.val_dir / "images"
            for image_file in sorted(image_dir.glob("*.jpg")):
                # 상대 경로로 이미지 위치 지정
                image_path = f"val/images/{image_file.name}"

                # 대응하는 라벨 파일 읽기
                label_file = self.val_dir / "labels" / f"{image_file.stem}.txt"
                if label_file.exists():
                    with open(label_file, 'r', encoding='utf-8') as label_f:
                        label_content = label_f.read().strip()
                        # 라벨 내용에서 이미지 경로를 상대 경로로 변경
                        if label_content.startswith("images/"):
                            # images/xxx.jpg -> val/images/xxx.jpg
                            label_content = label_content.replace("images/", "val/images/", 1)
                        # 이미 절대 경로인 경우 상대 경로로 변환
                        elif "/" in label_content and label_content.split('\t')[0].startswith("/"):
                            parts = label_content.split('\t')
                            parts[0] = image_path
                            label_content = '\t'.join(parts)
                        f.write(label_content + "\n")

        logger.info(f"Created file lists with relative paths: {train_list_path}, {val_list_path}")

def main():
    # ⚠️ 저장 공간 이슈로 인해 홈 디렉토리 사용
    # 이전 경로: /home/pro301/git/en-zine/ocr_system/paddleocr_training/data (루트 파티션 96% 사용)
    # 현재 경로: /home/pro301/paddleocr_training/ (홈 파티션 11% 사용)

    import argparse
    parser = argparse.ArgumentParser(description='Convert database to PaddleOCR format')
    parser.add_argument('--output-dir', type=str,
                       default='/home/pro301/paddleocr_training/data_new',
                       help='Output directory for converted dataset')
    parser.add_argument('--max-samples', type=int, default=500,
                       help='Maximum number of samples to convert')
    args = parser.parse_args()

    converter = PaddleOCRDatasetConverter(args.output_dir)

    # 데이터셋 변환
    train_count, val_count = converter.convert_dataset(max_samples=args.max_samples)

    # 파일 리스트 생성
    converter.create_file_lists()

    print(f"Dataset conversion completed!")
    print(f"Output directory: {args.output_dir}")
    print(f"Training samples: {train_count}")
    print(f"Validation samples: {val_count}")

if __name__ == "__main__":
    main()