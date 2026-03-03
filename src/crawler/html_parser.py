import requests
from bs4 import BeautifulSoup
from loguru import logger
from typing import Optional, List, Dict, Any
import re
import random

class HTMLParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Chrome WebDriver 사용 가능성 확인
        self.chrome_available = False
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            self.chrome_available = True
        except Exception as e:
            logger.warning(f'Selenium WebDriver not available for coordinate extraction: {e}')

    def fetch_html_source(self, url: str) -> Optional[str]:
        """웹페이지의 HTML 소스코드 가져오기"""
        try:
            logger.info(f'Fetching HTML source from: {url}')
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            logger.info(f'Successfully fetched HTML from {url} ({len(response.text)} characters)')
            return response.text
        except Exception as e:
            logger.error(f'Error fetching HTML from {url}: {e}')
            return None

    def extract_text_content(self, html_source: str) -> str:
        """HTML에서 순수 텍스트 콘텐츠 추출"""
        try:
            soup = BeautifulSoup(html_source, 'lxml')

            # 불필요한 태그 제거
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()

            # 메인 콘텐츠 영역 찾기
            main_content = (
                soup.find('main') or
                soup.find('article') or
                soup.find('div', class_=re.compile(r'content|main|article', re.I)) or
                soup.find('body')
            )

            if main_content:
                # 텍스트 추출 및 정리
                text = main_content.get_text(separator=' ', strip=True)
                # 연속된 공백 제거
                text = re.sub(r'\s+', ' ', text)
                extracted_text = text.strip()
                logger.info(f'Extracted {len(extracted_text)} characters of text content')
                return extracted_text

            return ''

        except Exception as e:
            logger.error(f'Error extracting text from HTML: {e}')
            return ''

    def generate_mock_bounding_boxes(self, text_content: str, viewport_width: int = 1920) -> List[Dict[str, Any]]:
        """텍스트 콘텐츠를 기반으로 가상의 바운딩 박스 생성 (Chrome 없을 때)"""
        if not text_content:
            return []

        # 텍스트를 문장 단위로 분할
        sentences = re.split(r'[.!?]\s+', text_content)
        bounding_boxes = []
        
        y_position = 50  # 시작 Y 좌표
        line_height = 25  # 라인 높이
        
        for i, sentence in enumerate(sentences[:50]):  # 최대 50개 문장
            if len(sentence.strip()) < 5:  # 너무 짧은 문장 제외
                continue
                
            # 가상의 좌표와 크기 생성
            x = random.randint(20, 100)
            width = min(len(sentence) * 8, viewport_width - x - 20)  # 글자당 평균 8픽셀
            height = random.randint(18, 28)
            
            # 제목 여부 판단 (첫 번째 문장이거나 짧은 문장)
            is_title = i < 3 and len(sentence.strip()) < 100
            
            bounding_boxes.append({
                'text': sentence.strip(),
                'x': x,
                'y': y_position,
                'width': width,
                'height': height,
                'fontSize': 24 if is_title else 16,
                'color': 'rgb(0, 0, 0)',
                'isTitle': is_title
            })
            
            y_position += line_height * (2 if is_title else 1)

        logger.info(f'Generated {len(bounding_boxes)} mock bounding boxes')
        return bounding_boxes

    def extract_text_with_coordinates(self, url: str) -> List[Dict[str, Any]]:
        """JavaScript를 사용하여 텍스트와 좌표 정보 추출"""
        if not self.chrome_available:
            logger.info(f'Chrome not available, generating mock bounding boxes for {url}')
            # HTML을 가져와서 텍스트 추출 후 가상 바운딩 박스 생성
            html_source = self.fetch_html_source(url)
            if html_source:
                text_content = self.extract_text_content(html_source)
                return self.generate_mock_bounding_boxes(text_content)
            return []

        # Chrome이 사용 가능한 경우 실제 좌표 추출
        driver = None
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')

            driver = webdriver.Chrome(options=options)
            driver.get(url)

            # JavaScript로 텍스트 바운딩 박스 추출
            script = '''
            function getTextBoundingBoxes() {
                const textNodes = [];
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    {
                        acceptNode: function(node) {
                            if (node.parentElement.tagName.match(/SCRIPT|STYLE|NAV|HEADER|FOOTER/i)) {
                                return NodeFilter.FILTER_REJECT;
                            }
                            if (node.nodeValue.trim().length > 2) {
                                return NodeFilter.FILTER_ACCEPT;
                            }
                            return NodeFilter.FILTER_REJECT;
                        }
                    },
                    false
                );

                let node;
                while (node = walker.nextNode()) {
                    try {
                        const range = document.createRange();
                        range.selectNode(node);
                        const rect = range.getBoundingClientRect();

                        if (rect.width > 0 && rect.height > 0) {
                            const parentStyle = window.getComputedStyle(node.parentElement);

                            textNodes.push({
                                text: node.nodeValue.trim(),
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height),
                                fontSize: parseInt(parentStyle.fontSize) || 14,
                                color: parentStyle.color || 'rgb(0, 0, 0)',
                                isTitle: node.parentElement.tagName.match(/H[1-6]/i) ? true : false
                            });
                        }
                    } catch (e) {
                        continue;
                    }
                }
                return textNodes;
            }
            return getTextBoundingBoxes();
            '''

            bounding_boxes = driver.execute_script(script)
            logger.info(f'Extracted {len(bounding_boxes)} bounding boxes from {url}')
            return bounding_boxes

        except Exception as e:
            logger.error(f'Error extracting coordinates from {url}: {e}')
            # 실패 시 가상 바운딩 박스로 대체
            html_source = self.fetch_html_source(url)
            if html_source:
                text_content = self.extract_text_content(html_source)
                return self.generate_mock_bounding_boxes(text_content)
            return []
        finally:
            if driver:
                driver.quit()
