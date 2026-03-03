# Generated: 2025-10-12 00:10:00 KST
"""
잡지 특화 합성 데이터 생성 시스템
Magazine-specific Synthetic Dataset Builder

Features:
- 다양한 레이아웃 (1단/2단/3단/혼합)
- 장식 폰트 지원
- 실시간 데이터 증강
- Ground truth 자동 생성
"""

import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import cv2
import json
from typing import List, Tuple, Dict
from datetime import datetime
from loguru import logger


class MagazineDatasetBuilder:
    """잡지 특화 학습 데이터 생성기"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 이미지와 라벨을 별도 디렉토리로 관리
        self.images_dir = self.output_dir / "images"
        self.labels_dir = self.output_dir / "labels"
        self.images_dir.mkdir(exist_ok=True)
        self.labels_dir.mkdir(exist_ok=True)

        # 잡지에서 자주 사용되는 한글 폰트
        self.font_families = [
            ("Noto Sans KR", "고딕체", "gothic"),
            ("Noto Serif KR", "명조체", "serif"),
            ("Gmarket Sans", "상업용", "commercial"),
            ("배민 주아체", "장식체", "decorative"),
            ("경기천년바탕", "제목용", "title"),
        ]

        # 잡지 레이아웃 타입
        self.layout_types = [
            "single_column",      # 1단
            "two_column",         # 2단
            "three_column",       # 3단
            "magazine_mixed",     # 혼합 (제목+본문+캡션)
            "vertical_text",      # 세로쓰기
        ]

        # 텍스트 샘플 (잡지에서 흔한 문구)
        self.text_corpus = self._load_magazine_corpus()

        logger.info(f"MagazineDatasetBuilder initialized: {self.output_dir}")

    def _load_magazine_corpus(self) -> List[str]:
        """잡지에서 자주 사용되는 텍스트 로드"""
        corpus = [
            # 제목 스타일
            "특별 기획: 2025년 트렌드 분석",
            "문화 리포트: 현대 예술의 새로운 시각",
            "인터뷰: 업계 리더와의 대화",
            "심층 분석: 변화하는 시장 환경",
            "특집: 미래 기술의 현재",

            # 본문 스타일
            "최근 조사에 따르면 소비자들의 구매 패턴이 급격히 변화하고 있다.",
            "전문가들은 이러한 현상이 앞으로도 지속될 것으로 전망한다.",
            "새로운 기술의 도입으로 산업 전반에 혁신이 일어나고 있다.",
            "이번 조사는 전국 1,000명을 대상으로 실시되었으며 신뢰도가 높다.",
            "다양한 분야의 전문가들이 모여 심도 있는 논의를 진행했다.",

            # 캡션 스타일
            "사진: 김철수 기자",
            "자료 제공: OO 연구소",
            "출처: 통계청 2024년 자료",
            "그래픽: 디자인팀",
        ]

        return corpus

    def generate_single_column_layout(self, text: str, font_name: str,
                                     width: int = 800, height: int = 1200) -> Image.Image:
        """1단 레이아웃 생성"""
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        # 폰트 로드 (크기: 24pt)
        try:
            font_path = self._get_font_path(font_name)
            pil_font = ImageFont.truetype(font_path, 24)
        except Exception as e:
            logger.warning(f"Font load failed, using default: {e}")
            pil_font = ImageFont.load_default()

        # 텍스트 렌더링 (중앙 정렬, 여백 80px)
        x_margin = 80
        y_position = 100

        lines = self._wrap_text(text, width - 2*x_margin, pil_font)
        for line in lines:
            draw.text((x_margin, y_position), line, fill='black', font=pil_font)
            y_position += 40

        return img

    def generate_multi_column_layout(self, text: str, font_name: str,
                                     num_columns: int = 2,
                                     width: int = 1200, height: int = 1600) -> Image.Image:
        """다단 레이아웃 생성 (2단 또는 3단)"""
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        try:
            font_path = self._get_font_path(font_name)
            pil_font = ImageFont.truetype(font_path, 18)
        except Exception as e:
            logger.warning(f"Font load failed, using default: {e}")
            pil_font = ImageFont.load_default()

        # 단 너비 계산
        total_margin = 120
        column_gap = 40
        column_width = (width - total_margin - column_gap*(num_columns-1)) // num_columns

        # 텍스트를 단으로 분할
        lines = self._wrap_text(text, column_width, pil_font)
        lines_per_column = len(lines) // num_columns

        for col in range(num_columns):
            x_start = 60 + col * (column_width + column_gap)
            y_position = 100

            start_line = col * lines_per_column
            end_line = start_line + lines_per_column if col < num_columns-1 else len(lines)

            for line in lines[start_line:end_line]:
                draw.text((x_start, y_position), line, fill='black', font=pil_font)
                y_position += 30

                if y_position > height - 100:  # 페이지 끝 방지
                    break

        return img

    def generate_magazine_mixed_layout(self, width: int = 1200, height: int = 1600) -> Tuple[Image.Image, str]:
        """잡지 혼합 레이아웃 (제목 + 본문 + 이미지 캡션)"""
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        all_text = []

        # 1. 제목 (큰 폰트, 굵게)
        try:
            title_font = ImageFont.truetype(self._get_font_path("Noto Sans KR"), 48)
        except:
            title_font = ImageFont.load_default()

        title = random.choice([t for t in self.text_corpus if "특별" in t or "인터뷰" in t or "특집" in t])
        draw.text((80, 80), title, fill='black', font=title_font)
        all_text.append(title)

        # 2. 본문 (2단)
        body_texts = [t for t in self.text_corpus if "최근" in t or "전문가" in t or "새로운" in t]
        if len(body_texts) >= 2:
            body_text = " ".join(random.sample(body_texts, 2))
        else:
            body_text = " ".join(self.text_corpus[:3])

        try:
            body_font = ImageFont.truetype(self._get_font_path("Noto Serif KR"), 16)
        except:
            body_font = ImageFont.load_default()

        # 본문 렌더링 (간단한 2단 레이아웃)
        y_start = 180
        column_width = 500
        lines = self._wrap_text(body_text, column_width, body_font)

        for i, line in enumerate(lines[:20]):  # 최대 20줄
            col = 0 if i < 10 else 1
            x_pos = 80 + col * (column_width + 40)
            y_pos = y_start + (i % 10) * 25
            draw.text((x_pos, y_pos), line, fill='black', font=body_font)

        all_text.append(body_text)

        # 3. 이미지 영역 (회색 박스로 표시)
        draw.rectangle([80, 500, 580, 900], fill='lightgray', outline='black', width=2)
        draw.text((250, 680), "[이미지]", fill='gray', font=body_font)

        # 4. 캡션 (작은 폰트)
        try:
            caption_font = ImageFont.truetype(self._get_font_path("Noto Sans KR"), 14)
        except:
            caption_font = ImageFont.load_default()

        caption = random.choice([t for t in self.text_corpus if "사진:" in t or "자료" in t or "출처:" in t])
        draw.text((80, 920), caption, fill='gray', font=caption_font)
        all_text.append(caption)

        return img, " ".join(all_text)

    def apply_augmentation(self, image: Image.Image) -> Image.Image:
        """데이터 증강 (노이즈, 회전, 밝기 조정)"""
        img_array = np.array(image)

        # 1. 랜덤 회전 (±5도)
        if random.random() > 0.5:
            angle = random.uniform(-5, 5)
            center = (img_array.shape[1]//2, img_array.shape[0]//2)
            rot_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            img_array = cv2.warpAffine(img_array, rot_matrix,
                                      (img_array.shape[1], img_array.shape[0]),
                                      borderValue=(255,255,255))

        # 2. 노이즈 추가
        if random.random() > 0.5:
            noise = np.random.normal(0, 10, img_array.shape).astype(np.uint8)
            img_array = cv2.add(img_array, noise)

        # 3. 밝기/대비 조정
        if random.random() > 0.5:
            alpha = random.uniform(0.8, 1.2)  # 대비
            beta = random.randint(-20, 20)    # 밝기
            img_array = cv2.convertScaleAbs(img_array, alpha=alpha, beta=beta)

        # 4. 블러 효과 (가끔)
        if random.random() > 0.8:
            img_pil = Image.fromarray(img_array)
            img_pil = img_pil.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.5, 1.5)))
            img_array = np.array(img_pil)

        return Image.fromarray(img_array)

    def generate_dataset(self, num_samples: int = 10000):
        """대규모 합성 데이터 생성"""
        logger.info(f"생성 시작: {num_samples}개 샘플")
        print(f"🚀 생성 시작: {num_samples}개 샘플")
        print(f"📁 출력 경로: {self.output_dir}")

        generation_config = {
            "start_time": datetime.now().isoformat(),
            "num_samples": num_samples,
            "layout_types": self.layout_types,
            "font_families": [f[0] for f in self.font_families],
            "augmentation": ["rotation", "noise", "brightness", "blur"],
        }

        successful = 0
        failed = 0

        for i in range(num_samples):
            try:
                # 랜덤 선택
                layout = random.choice(self.layout_types)
                font_name = random.choice(self.font_families)[0]

                # 레이아웃에 따라 텍스트 생성
                if layout == "magazine_mixed":
                    img, text = self.generate_magazine_mixed_layout()
                else:
                    # 일반 레이아웃은 텍스트 샘플 조합
                    text = " ".join(random.sample(self.text_corpus, min(3, len(self.text_corpus))))

                    if layout == "single_column":
                        img = self.generate_single_column_layout(text, font_name)
                    elif layout in ["two_column", "three_column"]:
                        num_cols = 2 if layout == "two_column" else 3
                        img = self.generate_multi_column_layout(text, font_name, num_cols)
                    else:  # vertical_text
                        # TODO: 세로쓰기 구현 (현재는 1단으로 대체)
                        img = self.generate_single_column_layout(text, font_name)

                # 데이터 증강
                augmented = self.apply_augmentation(img)

                # 저장
                output_path = self.images_dir / f"synthetic_{i:06d}.jpg"
                augmented.save(output_path, quality=90)

                # Ground truth 저장
                gt_path = self.labels_dir / f"synthetic_{i:06d}.txt"
                gt_path.write_text(text, encoding='utf-8')

                successful += 1

                # 진행상황 출력
                if (i+1) % 100 == 0:
                    progress = (i+1) / num_samples * 100
                    logger.info(f"진행: {i+1}/{num_samples} ({progress:.1f}%)")
                    print(f"📊 진행: {i+1}/{num_samples} ({progress:.1f}%)")

            except Exception as e:
                failed += 1
                logger.error(f"샘플 {i} 생성 실패: {e}")
                if failed > 10:
                    logger.error("연속 실패 너무 많음, 중단")
                    break

        # 생성 정보 저장
        generation_config["end_time"] = datetime.now().isoformat()
        generation_config["successful"] = successful
        generation_config["failed"] = failed

        config_path = self.output_dir / "generation_config.json"
        config_path.write_text(json.dumps(generation_config, indent=2, ensure_ascii=False), encoding='utf-8')

        logger.info(f"✅ 생성 완료: {self.output_dir}")
        logger.info(f"성공: {successful}, 실패: {failed}")
        print(f"\n✅ 생성 완료!")
        print(f"  - 성공: {successful}개")
        print(f"  - 실패: {failed}개")
        print(f"  - 이미지: {self.images_dir}")
        print(f"  - 라벨: {self.labels_dir}")

    def _get_font_path(self, font_name: str) -> str:
        """폰트 파일 경로 반환"""
        # 폰트 경로 매핑 (Linux 기준)
        font_map = {
            "Noto Sans KR": "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf",
            "Noto Serif KR": "/usr/share/fonts/truetype/noto/NotoSerifKR-Regular.ttf",
            "Gmarket Sans": "/usr/share/fonts/truetype/gmarket/GmarketSansTTFMedium.ttf",
            "배민 주아체": "/usr/share/fonts/truetype/baemin/BMJua.ttf",
            "경기천년바탕": "/usr/share/fonts/truetype/gyeonggi/GyeonggiCheonnyeonBatang.ttf",
        }

        # 폰트가 없으면 Noto Sans KR 사용
        font_path = font_map.get(font_name, font_map["Noto Sans KR"])

        # 폰트 파일이 없으면 기본 경로 시도
        if not Path(font_path).exists():
            # Fallback to default font paths
            fallback_paths = [
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # macOS
            ]
            for fp in fallback_paths:
                if Path(fp).exists():
                    return fp

        return font_path

    def _wrap_text(self, text: str, max_width: int, font: ImageFont.FreeTypeFont) -> List[str]:
        """텍스트를 최대 너비에 맞게 줄바꿈"""
        lines = []
        words = text.split()
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            try:
                bbox = font.getbbox(test_line)
                text_width = bbox[2] - bbox[0]
            except:
                # Fallback for fonts without getbbox
                text_width = len(test_line) * 10

            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines if lines else [text]  # 최소 1줄 반환


# 실행 스크립트
if __name__ == "__main__":
    from pathlib import Path
    import sys

    # 출력 디렉토리 설정
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
    else:
        output_dir = Path("/home/pro301/git/en-zine/scholar/training/datasets/synthetic")

    # 샘플 수 설정
    if len(sys.argv) > 2:
        num_samples = int(sys.argv[2])
    else:
        num_samples = 10000

    print("=" * 60)
    print("🎨 Magazine Dataset Builder")
    print("=" * 60)
    print(f"출력 경로: {output_dir}")
    print(f"생성 개수: {num_samples}")
    print("=" * 60)

    builder = MagazineDatasetBuilder(output_dir)
    builder.generate_dataset(num_samples=num_samples)

    print("\n" + "=" * 60)
    print("✅ 작업 완료!")
    print("=" * 60)
