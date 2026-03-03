import os
import json
import random
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Dict, Optional
from loguru import logger

class BoundingBoxVisualizer:
    def __init__(self, output_dir: str, data_root_path: str = '/opt/ocr_system/crawling/data'):
        self.output_dir = output_dir
        self.data_root_path = data_root_path
        os.makedirs(output_dir, exist_ok=True)
        
        # 색상 팔레트
        self.colors = [
            'red', 'blue', 'green', 'orange', 'purple', 
            'brown', 'pink', 'gray', 'olive', 'cyan'
        ]

    def load_capture_data(self, capture_file: str) -> Optional[Tuple[Dict, List[Dict]]]:
        """캡처 데이터와 바운딩 박스 로드"""
        try:
            # 캡처 메타데이터 로드
            with open(capture_file, 'r') as f:
                capture_data = json.load(f)
            
            # 바운딩 박스 데이터 로드
            bbox_file = capture_file.replace('capture_', 'bounding_boxes_')
            if not os.path.exists(bbox_file):
                logger.warning(f'Bounding boxes file not found: {bbox_file}')
                return None
            
            with open(bbox_file, 'r') as f:
                bounding_boxes = json.load(f)
            
            return capture_data, bounding_boxes
            
        except Exception as e:
            logger.error(f'Error loading capture data from {capture_file}: {e}')
            return None

    def get_font(self, size: int = 12):
        """시스템 폰트 로드"""
        try:
            # 다양한 폰트 경로 시도
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/TTF/DejaVuSans.ttf',
                '/usr/share/fonts/dejavu/DejaVuSans.ttf',
                '/System/Library/Fonts/Arial.ttf',  # macOS
                '/usr/share/fonts/liberation/LiberationSans-Regular.ttf'
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size)
            
            # 기본 폰트 사용
            return ImageFont.load_default()
            
        except Exception as e:
            logger.warning(f'Failed to load font: {e}. Using default font.')
            return ImageFont.load_default()

    def create_placeholder_for_visualization(self, width: int, height: int) -> Image.Image:
        """시각화용 placeholder 이미지 생성"""
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)
        
        # 격자 그리기
        grid_size = 50
        for x in range(0, width, grid_size):
            draw.line([(x, 0), (x, height)], fill='lightgray', width=1)
        for y in range(0, height, grid_size):
            draw.line([(0, y), (width, y)], fill='lightgray', width=1)
        
        # 중앙에 텍스트
        font = self.get_font(16)
        text = 'Visualization Placeholder'
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        draw.text(
            ((width - text_width) // 2, (height - text_height) // 2),
            text, fill='gray', font=font
        )
        
        return img

    def visualize_single_capture(self, capture_file: str, show_text: bool = True, max_text_length: int = 30) -> Optional[str]:
        """단일 캡처 데이터 시각화"""
        try:
            data = self.load_capture_data(capture_file)
            if not data:
                return None
            
            capture_data, bounding_boxes = data
            capture_id = capture_data.get('capture_id', 0)
            image_path = capture_data.get('image_file_path', '')
            source_url = capture_data.get('source_url', 'Unknown')
            
            # 이미지 로드 또는 placeholder 생성
            try:
                if os.path.exists(image_path):
                    img = Image.open(image_path).convert('RGB')
                else:
                    # placeholder 이미지 생성
                    width = capture_data.get('viewport_width', 1920)
                    height = capture_data.get('viewport_height', 1080)
                    img = self.create_placeholder_for_visualization(width, height)
                    logger.info(f'Using placeholder image for {capture_file}')
            except Exception as e:
                logger.warning(f'Failed to load image {image_path}: {e}. Using placeholder.')
                width = capture_data.get('viewport_width', 1920)
                height = capture_data.get('viewport_height', 1080)
                img = self.create_placeholder_for_visualization(width, height)
            
            draw = ImageDraw.Draw(img)
            font = self.get_font(10)
            
            # 통계 정보
            total_boxes = len(bounding_boxes)
            title_boxes = len([box for box in bounding_boxes if box.get('isTitle', False)])
            
            # 바운딩 박스 그리기
            for i, box in enumerate(bounding_boxes):
                text_content = box.get('text', '')
                x = int(box.get('x', 0))
                y = int(box.get('y', 0))
                width = int(box.get('width', 0))
                height = int(box.get('height', 0))
                is_title = box.get('isTitle', False)
                
                # 박스 색상 선택
                if is_title:
                    box_color = 'red'
                    text_color = 'red'
                    line_width = 3
                else:
                    color_index = i % len(self.colors)
                    box_color = self.colors[color_index]
                    text_color = box_color
                    line_width = 2
                
                # 바운딩 박스 그리기
                draw.rectangle(
                    [x, y, x + width, y + height],
                    outline=box_color, width=line_width
                )
                
                # 텍스트 표시 (옵션)
                if show_text and len(text_content.strip()) > 0:
                    # 텍스트 자르기
                    display_text = text_content[:max_text_length]
                    if len(text_content) > max_text_length:
                        display_text += '...'
                    
                    # 텍스트 배경 박스
                    text_bbox = draw.textbbox((0, 0), display_text, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                    
                    # 텍스트 위치 조정 (박스 위쪽)
                    text_y = max(0, y - text_height - 2)
                    text_x = x
                    
                    # 텍스트 배경
                    draw.rectangle(
                        [text_x - 2, text_y - 1, text_x + text_width + 2, text_y + text_height + 1],
                        fill='white', outline=text_color, width=1
                    )
                    
                    # 텍스트
                    draw.text(
                        (text_x, text_y),
                        display_text,
                        fill=text_color,
                        font=font
                    )
            
            # 정보 오버레이 추가
            info_font = self.get_font(14)
            info_text = f'Capture ID: {capture_id} | Boxes: {total_boxes} | Titles: {title_boxes}'
            draw.rectangle([10, 10, 500, 35], fill='white', outline='black', width=2)
            draw.text((15, 15), info_text, fill='black', font=info_font)
            
            # URL 정보 추가 (하단)
            url_text = f'Source: {source_url[:80]}...' if len(source_url) > 80 else f'Source: {source_url}'
            img_width, img_height = img.size
            draw.rectangle([10, img_height - 35, img_width - 10, img_height - 10], fill='white', outline='black', width=2)
            draw.text((15, img_height - 30), url_text, fill='black', font=font)
            
            # 결과 이미지 저장
            output_filename = f'visualized_capture_{capture_id}.png'
            output_path = os.path.join(self.output_dir, output_filename)
            img.save(output_path, 'PNG')
            
            logger.info(f'Saved visualization: {output_path}')
            return output_path
            
        except Exception as e:
            logger.error(f'Error visualizing {capture_file}: {e}')
            return None

    def create_sample_visualizations(self, sample_count: int = 5) -> List[str]:
        """샘플 시각화 생성"""
        try:
            metadata_dir = os.path.join(self.data_root_path, 'metadata')
            
            if not os.path.exists(metadata_dir):
                logger.error(f'Metadata directory not found: {metadata_dir}')
                return []
            
            # 캡처 파일들 찾기
            capture_files = [f for f in os.listdir(metadata_dir) 
                           if f.startswith('capture_') and f.endswith('.json')]
            
            if not capture_files:
                logger.warning('No capture files found for visualization')
                return []
            
            # 랜덤 샘플 선택
            sample_files = random.sample(capture_files, min(sample_count, len(capture_files)))
            
            visualized_files = []
            for capture_file in sample_files:
                file_path = os.path.join(metadata_dir, capture_file)
                output_path = self.visualize_single_capture(file_path, show_text=True)
                if output_path:
                    visualized_files.append(output_path)
            
            logger.info(f'Created {len(visualized_files)} visualizations')
            return visualized_files
            
        except Exception as e:
            logger.error(f'Error creating sample visualizations: {e}')
            return []

    def create_comparison_visualization(self, capture_file: str, before_file: str = None) -> Optional[str]:
        """최적화 전후 비교 시각화"""
        try:
            # 현재(최적화 후) 데이터 로드
            current_data = self.load_capture_data(capture_file)
            if not current_data:
                return None
            
            capture_data, current_boxes = current_data
            capture_id = capture_data.get('capture_id', 0)
            
            # 이전 데이터가 있으면 로드 (백업 파일)
            before_boxes = []
            if before_file and os.path.exists(before_file):
                with open(before_file, 'r') as f:
                    before_boxes = json.load(f)
            
            # 이미지 생성 (가로로 나란히 배치)
            img_width = capture_data.get('viewport_width', 1920)
            img_height = capture_data.get('viewport_height', 1080)
            
            # 전체 이미지 크기 (좌우 비교 + 간격)
            total_width = img_width * 2 + 60  # 좌우 이미지 + 중앙 간격
            total_height = img_height + 100   # 상하 여백
            
            comparison_img = Image.new('RGB', (total_width, total_height), color='white')
            draw = ImageDraw.Draw(comparison_img)
            
            # 제목 추가
            title_font = self.get_font(18)
            title = f'Bounding Box Optimization Comparison - Capture {capture_id}'
            draw.text((30, 20), title, fill='black', font=title_font)
            
            # 왼쪽: 이전 버전 (또는 현재 버전)
            left_boxes = before_boxes if before_boxes else current_boxes
            left_title = f'Before: {len(left_boxes)} boxes' if before_boxes else f'Current: {len(current_boxes)} boxes'
            
            font = self.get_font(12)
            draw.text((30, 50), left_title, fill='blue', font=font)
            
            # 왼쪽 영역에 박스 그리기
            for i, box in enumerate(left_boxes):
                x = int(box.get('x', 0)) + 30
                y = int(box.get('y', 0)) + 80
                width = int(box.get('width', 0))
                height = int(box.get('height', 0))
                
                draw.rectangle([x, y, x + width, y + height], outline='blue', width=1)
            
            # 오른쪽: 현재 버전
            right_title = f'After: {len(current_boxes)} boxes'
            draw.text((img_width + 60, 50), right_title, fill='red', font=font)
            
            # 오른쪽 영역에 박스 그리기
            for i, box in enumerate(current_boxes):
                x = int(box.get('x', 0)) + img_width + 60
                y = int(box.get('y', 0)) + 80
                width = int(box.get('width', 0))
                height = int(box.get('height', 0))
                
                draw.rectangle([x, y, x + width, y + height], outline='red', width=2)
            
            # 구분선
            draw.line([(img_width + 30, 80), (img_width + 30, img_height + 80)], fill='gray', width=2)
            
            # 저장
            output_filename = f'comparison_capture_{capture_id}.png'
            output_path = os.path.join(self.output_dir, output_filename)
            comparison_img.save(output_path, 'PNG')
            
            logger.info(f'Saved comparison visualization: {output_path}')
            return output_path
            
        except Exception as e:
            logger.error(f'Error creating comparison visualization: {e}')
            return None
