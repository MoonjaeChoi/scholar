#!/usr/bin/env python3
"""
자동 텍스트 블록 라벨링 시스템
Oracle DB의 기존 bounding box 데이터를 활용하여 자동으로 텍스트 블록 annotation 생성
"""

import os
import sys
import json
import cv2
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from sklearn.cluster import DBSCAN
from loguru import logger
import sqlite3
from collections import defaultdict

# Oracle DB 연결을 위한 임포트
sys.path.append('/home/pro301/git/en-zine/ocr_system/crawling/src')
try:
    from database_connection import DatabaseConnection
except ImportError:
    logger.warning("Oracle DB 연결을 사용할 수 없습니다. SQLite로 대체합니다.")
    DatabaseConnection = None

@dataclass
class BoundingBox:
    """바운딩 박스 데이터 클래스"""
    x: float
    y: float
    width: float
    height: float
    text: str
    confidence: float
    page_id: str

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    @property
    def area(self) -> float:
        return self.width * self.height

@dataclass
class TextBlock:
    """텍스트 블록 데이터 클래스"""
    boxes: List[BoundingBox]
    block_id: int
    block_type: str  # "paragraph", "title", "list", "table"
    confidence: float

    @property
    def bounding_rect(self) -> Tuple[float, float, float, float]:
        """블록 전체를 포함하는 최소 바운딩 박스"""
        if not self.boxes:
            return (0, 0, 0, 0)

        min_x = min(box.x for box in self.boxes)
        min_y = min(box.y for box in self.boxes)
        max_x = max(box.x + box.width for box in self.boxes)
        max_y = max(box.y + box.height for box in self.boxes)

        return (min_x, min_y, max_x - min_x, max_y - min_y)

    @property
    def text_content(self) -> str:
        """블록의 전체 텍스트"""
        return " ".join(box.text for box in self.boxes)

class AutoTextBlockLabeler:
    """자동 텍스트 블록 라벨링 클래스"""

    def __init__(self,
                 min_samples: int = 2,
                 eps_distance: float = 50.0,
                 min_block_area: float = 100.0):
        """
        초기화

        Args:
            min_samples: DBSCAN 최소 샘플 수
            eps_distance: DBSCAN 클러스터링 거리 임계값
            min_block_area: 최소 블록 면적
        """
        self.min_samples = min_samples
        self.eps_distance = eps_distance
        self.min_block_area = min_block_area

        # 데이터베이스 연결 초기화
        self.db_connection = None
        if DatabaseConnection:
            try:
                self.db_connection = DatabaseConnection()
                logger.info("Oracle DB 연결 성공")
            except Exception as e:
                logger.warning(f"Oracle DB 연결 실패: {e}")

        # SQLite fallback 준비
        self.sqlite_db_path = "/tmp/text_blocks_cache.db"
        self._init_sqlite_fallback()

    def _init_sqlite_fallback(self):
        """SQLite fallback 데이터베이스 초기화"""
        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS text_bounding_boxes (
                id INTEGER PRIMARY KEY,
                page_id TEXT,
                x REAL, y REAL, width REAL, height REAL,
                text TEXT, confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS text_blocks (
                id INTEGER PRIMARY KEY,
                page_id TEXT,
                block_id INTEGER,
                x REAL, y REAL, width REAL, height REAL,
                block_type TEXT,
                confidence REAL,
                text_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        logger.info("SQLite fallback 데이터베이스 초기화 완료")

    def load_bounding_boxes(self, limit: int = 1000) -> List[BoundingBox]:
        """
        데이터베이스에서 바운딩 박스 데이터 로드

        Args:
            limit: 로드할 최대 레코드 수

        Returns:
            바운딩 박스 리스트
        """
        boxes = []

        # Oracle DB 시도
        if self.db_connection:
            try:
                query = """
                    SELECT page_id, x_coordinate, y_coordinate, width, height,
                           extracted_text, confidence_score
                    FROM TEXT_BOUNDING_BOXES
                    WHERE confidence_score > 0.3
                    AND ROWNUM <= :limit
                    ORDER BY page_id, y_coordinate, x_coordinate
                """

                with self.db_connection.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query, {"limit": limit})

                    for row in cursor.fetchall():
                        boxes.append(BoundingBox(
                            page_id=str(row[0]),
                            x=float(row[1]),
                            y=float(row[2]),
                            width=float(row[3]),
                            height=float(row[4]),
                            text=str(row[5]) if row[5] else "",
                            confidence=float(row[6])
                        ))

                logger.info(f"Oracle DB에서 {len(boxes)}개 바운딩 박스 로드")
                return boxes

            except Exception as e:
                logger.warning(f"Oracle DB 로드 실패: {e}, SQLite로 대체")

        # SQLite fallback
        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        # 샘플 데이터가 없으면 생성
        cursor.execute("SELECT COUNT(*) FROM text_bounding_boxes")
        count = cursor.fetchone()[0]

        if count == 0:
            self._create_sample_data(cursor)
            conn.commit()

        cursor.execute("""
            SELECT page_id, x, y, width, height, text, confidence
            FROM text_bounding_boxes
            WHERE confidence > 0.3
            ORDER BY page_id, y, x
            LIMIT ?
        """, (limit,))

        for row in cursor.fetchall():
            boxes.append(BoundingBox(
                page_id=str(row[0]),
                x=float(row[1]),
                y=float(row[2]),
                width=float(row[3]),
                height=float(row[4]),
                text=str(row[5]) if row[5] else "",
                confidence=float(row[6])
            ))

        conn.close()
        logger.info(f"SQLite에서 {len(boxes)}개 바운딩 박스 로드")
        return boxes

    def _create_sample_data(self, cursor):
        """샘플 데이터 생성 (테스트용)"""
        sample_data = [
            # 페이지 1: 뉴스 기사 레이아웃
            ("page_001", 50, 50, 500, 40, "Breaking News: Technology Advances", 0.95),
            ("page_001", 50, 100, 240, 20, "By John Smith | March 15, 2024", 0.88),
            ("page_001", 50, 140, 480, 80, "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt.", 0.92),
            ("page_001", 50, 240, 480, 60, "Ut labore et dolore magna aliqua. Enim ad minim veniam quis nostrud.", 0.89),
            ("page_001", 300, 100, 200, 120, "Advertisement Space", 0.85),

            # 페이지 2: 학술 논문 레이아웃
            ("page_002", 70, 70, 400, 30, "Research Paper Title", 0.96),
            ("page_002", 70, 110, 180, 15, "Authors: A. Smith, B. Jones", 0.91),
            ("page_002", 70, 140, 60, 25, "Abstract", 0.93),
            ("page_002", 70, 170, 400, 100, "This paper presents a novel approach to machine learning applications...", 0.88),
            ("page_002", 70, 290, 400, 200, "Introduction paragraph with detailed explanation of the methodology...", 0.87),

            # 페이지 3: 표 형태 레이아웃
            ("page_003", 50, 50, 100, 30, "Product", 0.94),
            ("page_003", 160, 50, 100, 30, "Price", 0.95),
            ("page_003", 270, 50, 100, 30, "Stock", 0.93),
            ("page_003", 50, 90, 100, 25, "Laptop", 0.92),
            ("page_003", 160, 90, 100, 25, "$999", 0.96),
            ("page_003", 270, 90, 100, 25, "15", 0.89),
            ("page_003", 50, 120, 100, 25, "Mouse", 0.91),
            ("page_003", 160, 120, 100, 25, "$29", 0.94),
            ("page_003", 270, 120, 100, 25, "156", 0.87),
        ]

        cursor.executemany(
            "INSERT INTO text_bounding_boxes (page_id, x, y, width, height, text, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
            sample_data
        )

    def cluster_boxes_into_blocks(self, boxes: List[BoundingBox]) -> Dict[str, List[TextBlock]]:
        """
        바운딩 박스들을 DBSCAN 클러스터링으로 텍스트 블록으로 그룹화

        Args:
            boxes: 바운딩 박스 리스트

        Returns:
            페이지별 텍스트 블록 딕셔너리
        """
        page_blocks = defaultdict(list)

        # 페이지별로 처리
        for page_id in set(box.page_id for box in boxes):
            page_boxes = [box for box in boxes if box.page_id == page_id]

            if len(page_boxes) < 2:
                # 박스가 너무 적으면 각각을 개별 블록으로 처리
                for i, box in enumerate(page_boxes):
                    block = TextBlock(
                        boxes=[box],
                        block_id=i,
                        block_type=self._classify_block_type([box]),
                        confidence=box.confidence
                    )
                    page_blocks[page_id].append(block)
                continue

            # 클러스터링을 위한 좌표 준비 (중심점 기준)
            coordinates = np.array([[box.center_x, box.center_y] for box in page_boxes])

            # DBSCAN 클러스터링
            clustering = DBSCAN(eps=self.eps_distance, min_samples=self.min_samples).fit(coordinates)

            # 클러스터별로 텍스트 블록 생성
            cluster_boxes = defaultdict(list)

            for box, label in zip(page_boxes, clustering.labels_):
                cluster_boxes[label].append(box)

            # 각 클러스터를 텍스트 블록으로 변환
            block_id = 0
            for cluster_id, cluster_box_list in cluster_boxes.items():
                if cluster_id == -1:  # 노이즈 (이상치)
                    # 노이즈는 각각을 개별 블록으로 처리
                    for box in cluster_box_list:
                        if box.area >= self.min_block_area:
                            block = TextBlock(
                                boxes=[box],
                                block_id=block_id,
                                block_type=self._classify_block_type([box]),
                                confidence=box.confidence
                            )
                            page_blocks[page_id].append(block)
                            block_id += 1
                else:
                    # 정상 클러스터
                    block = TextBlock(
                        boxes=cluster_box_list,
                        block_id=block_id,
                        block_type=self._classify_block_type(cluster_box_list),
                        confidence=np.mean([box.confidence for box in cluster_box_list])
                    )

                    # 최소 면적 조건 확인
                    if block.bounding_rect[2] * block.bounding_rect[3] >= self.min_block_area:
                        page_blocks[page_id].append(block)
                        block_id += 1

        logger.info(f"총 {sum(len(blocks) for blocks in page_blocks.values())}개 텍스트 블록 생성")
        return dict(page_blocks)

    def _classify_block_type(self, boxes: List[BoundingBox]) -> str:
        """
        바운딩 박스들을 분석하여 블록 타입 분류

        Args:
            boxes: 바운딩 박스 리스트

        Returns:
            블록 타입 ("title", "paragraph", "list", "table")
        """
        if not boxes:
            return "paragraph"

        # 특징 추출
        avg_height = np.mean([box.height for box in boxes])
        total_text = " ".join(box.text for box in boxes)
        text_length = len(total_text)

        # 폰트 크기 추정 (높이 기준)
        if avg_height > 30:
            return "title"  # 큰 텍스트 -> 제목

        # 텍스트 길이 기준
        if text_length < 50:
            return "title"  # 짧은 텍스트 -> 제목 가능성

        # 여러 박스가 정렬되어 있으면 표 가능성
        if len(boxes) > 3:
            x_positions = [box.x for box in boxes]
            if len(set(x_positions)) > 2:  # X 좌표가 다양하면 표
                return "table"

        # 기본은 문단
        return "paragraph"

    def save_paddleocr_annotations(self, page_blocks: Dict[str, List[TextBlock]], output_dir: str):
        """
        PaddleOCR 형식으로 annotation 저장

        Args:
            page_blocks: 페이지별 텍스트 블록
            output_dir: 출력 디렉토리
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 훈련/검증 데이터 분할
        all_pages = list(page_blocks.keys())
        train_pages = all_pages[:int(len(all_pages) * 0.8)]  # 80% 훈련
        val_pages = all_pages[int(len(all_pages) * 0.8):]    # 20% 검증

        # 훈련 데이터 저장
        train_list_path = output_path / "train_text_blocks_list.txt"
        with open(train_list_path, 'w', encoding='utf-8') as f:
            for page_id in train_pages:
                blocks = page_blocks[page_id]
                if blocks:
                    annotation_file = f"annotations/text_blocks_{page_id}.txt"
                    image_file = f"images/{page_id}.jpg"
                    f.write(f"{image_file}\t{annotation_file}\n")

                    # Annotation 파일 생성
                    ann_path = output_path / "annotations"
                    ann_path.mkdir(exist_ok=True)

                    with open(ann_path / f"text_blocks_{page_id}.txt", 'w', encoding='utf-8') as ann_f:
                        for block in blocks:
                            x, y, w, h = block.bounding_rect
                            # PaddleOCR 형식: x1,y1,x2,y2,x3,y3,x4,y4,text
                            points = f"{x},{y},{x+w},{y},{x+w},{y+h},{x},{y+h}"
                            ann_f.write(f"{points}\t{block.text_content}\n")

        # 검증 데이터 저장
        val_list_path = output_path / "val_text_blocks_list.txt"
        with open(val_list_path, 'w', encoding='utf-8') as f:
            for page_id in val_pages:
                blocks = page_blocks[page_id]
                if blocks:
                    annotation_file = f"annotations/text_blocks_{page_id}.txt"
                    image_file = f"images/{page_id}.jpg"
                    f.write(f"{image_file}\t{annotation_file}\n")

                    with open(output_path / "annotations" / f"text_blocks_{page_id}.txt", 'w', encoding='utf-8') as ann_f:
                        for block in blocks:
                            x, y, w, h = block.bounding_rect
                            points = f"{x},{y},{x+w},{y},{x+w},{y+h},{x},{y+h}"
                            ann_f.write(f"{points}\t{block.text_content}\n")

        # 통계 저장
        stats = {
            "total_pages": len(all_pages),
            "train_pages": len(train_pages),
            "val_pages": len(val_pages),
            "total_blocks": sum(len(blocks) for blocks in page_blocks.values()),
            "avg_blocks_per_page": np.mean([len(blocks) for blocks in page_blocks.values()]),
            "block_types": {}
        }

        # 블록 타입별 통계
        for blocks in page_blocks.values():
            for block in blocks:
                stats["block_types"][block.block_type] = stats["block_types"].get(block.block_type, 0) + 1

        with open(output_path / "labeling_stats.json", 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        logger.info(f"PaddleOCR annotation 저장 완료: {output_path}")
        logger.info(f"통계: {stats}")

    def visualize_blocks(self, page_blocks: Dict[str, List[TextBlock]], output_dir: str):
        """
        텍스트 블록 시각화 (디버깅용)

        Args:
            page_blocks: 페이지별 텍스트 블록
            output_dir: 출력 디렉토리
        """
        output_path = Path(output_dir) / "visualizations"
        output_path.mkdir(parents=True, exist_ok=True)

        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
                 (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 165, 0)]

        for page_id, blocks in page_blocks.items():
            # 가상의 이미지 생성 (실제로는 원본 이미지 사용)
            img_height, img_width = 800, 600
            img = np.ones((img_height, img_width, 3), dtype=np.uint8) * 255

            for i, block in enumerate(blocks):
                x, y, w, h = block.bounding_rect
                color = colors[i % len(colors)]

                # 블록 경계 그리기
                cv2.rectangle(img, (int(x), int(y)), (int(x+w), int(y+h)), color, 2)

                # 블록 타입 텍스트 추가
                cv2.putText(img, f"{block.block_type}_{block.block_id}",
                           (int(x), int(y-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                # 개별 바운딩 박스 그리기 (회색)
                for box in block.boxes:
                    cv2.rectangle(img, (int(box.x), int(box.y)),
                                (int(box.x+box.width), int(box.y+box.height)),
                                (128, 128, 128), 1)

            # 이미지 저장
            cv2.imwrite(str(output_path / f"{page_id}_blocks.png"), img)

        logger.info(f"시각화 이미지 저장 완료: {output_path}")

def main():
    """메인 실행 함수"""
    logger.info("=== 자동 텍스트 블록 라벨링 시스템 시작 ===")

    # 출력 디렉토리 설정
    output_dir = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/text_blocks"

    # 라벨러 초기화
    labeler = AutoTextBlockLabeler(
        min_samples=2,      # 최소 2개 박스로 블록 형성
        eps_distance=50.0,  # 50픽셀 이내 박스들을 같은 블록으로 묶기
        min_block_area=100.0 # 최소 100픽셀² 면적
    )

    try:
        # 1. 바운딩 박스 데이터 로드
        logger.info("바운딩 박스 데이터 로드 중...")
        boxes = labeler.load_bounding_boxes(limit=1000)

        if not boxes:
            logger.error("바운딩 박스 데이터가 없습니다.")
            return 1

        # 2. 텍스트 블록 클러스터링
        logger.info("텍스트 블록 클러스터링 중...")
        page_blocks = labeler.cluster_boxes_into_blocks(boxes)

        # 3. PaddleOCR 형식 저장
        logger.info("PaddleOCR 형식 annotation 생성 중...")
        labeler.save_paddleocr_annotations(page_blocks, output_dir)

        # 4. 시각화 생성 (디버깅용)
        logger.info("시각화 생성 중...")
        labeler.visualize_blocks(page_blocks, output_dir)

        logger.info("🎉 자동 텍스트 블록 라벨링 완료!")
        logger.info(f"결과 위치: {output_dir}")

        return 0

    except Exception as e:
        logger.error(f"라벨링 중 오류 발생: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())