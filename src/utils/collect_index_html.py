# Generated: 2025-10-14 09:40:00 KST
"""
Index HTML Collector - Phase 1 프로토타입용 HTML 수집 도구

Tistory 블로그 3개의 index.html을 수집하여 Site-Analyzer 입력으로 사용
"""

import os
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from loguru import logger

# Selenium 없이 requests만 사용 (간단한 GET 요청)
import requests
from bs4 import BeautifulSoup


class IndexHTMLCollector:
    """Index HTML 수집기"""

    def __init__(self, output_dir: str = None):
        """
        Args:
            output_dir: HTML 파일 저장 디렉토리 (기본: scholar/data/phase1_samples)
        """
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / 'data' / 'phase1_samples'

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # User-Agent 설정 (정상적인 브라우저처럼 보이도록)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        logger.info(f"IndexHTMLCollector initialized, output_dir: {self.output_dir}")

    def collect_single_page(self, url: str, name: str) -> Dict:
        """
        단일 페이지 HTML 수집

        Args:
            url: 수집할 URL
            name: 파일명에 사용할 이름 (예: 'notice_tistory')

        Returns:
            dict: {
                'success': bool,
                'url': str,
                'file_path': str,
                'size': int,
                'timestamp': str,
                'error': Optional[str]
            }
        """
        logger.info(f"Collecting HTML from: {url}")

        try:
            # HTTP GET 요청
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            # HTML 내용 가져오기
            html_content = response.text

            # 파일명 생성 (타임스탬프 포함)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{name}_{timestamp}.html"
            file_path = self.output_dir / filename

            # HTML 파일 저장
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            file_size = os.path.getsize(file_path)

            logger.info(f"✅ Saved HTML: {file_path} ({file_size:,} bytes)")

            # 메타데이터도 저장 (분석용)
            metadata_path = file_path.with_suffix('.meta.json')
            import json
            metadata = {
                'url': url,
                'name': name,
                'timestamp': timestamp,
                'file_size': file_size,
                'status_code': response.status_code,
                'content_type': response.headers.get('Content-Type'),
                'collected_at': datetime.now().isoformat()
            }
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            return {
                'success': True,
                'url': url,
                'file_path': str(file_path),
                'size': file_size,
                'timestamp': timestamp,
                'error': None
            }

        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {e}"
            logger.error(f"❌ Failed to collect {url}: {error_msg}")
            return {
                'success': False,
                'url': url,
                'file_path': None,
                'size': 0,
                'timestamp': None,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(f"❌ Failed to collect {url}: {error_msg}")
            return {
                'success': False,
                'url': url,
                'file_path': None,
                'size': 0,
                'timestamp': None,
                'error': error_msg
            }

    def collect_tistory_samples(self) -> List[Dict]:
        """
        Phase 1용 Tistory 블로그 3개 샘플 수집

        Returns:
            List[Dict]: 수집 결과 목록
        """
        target_blogs = [
            {
                'url': 'https://notice.tistory.com',
                'name': 'notice_tistory',
                'description': '공식 블로그, 표준 테마'
            },
            {
                'url': 'https://coding-factory.tistory.com',
                'name': 'coding_factory',
                'description': '개발 블로그, 커스텀 테마'
            },
            {
                'url': 'https://inpa.tistory.com',
                'name': 'inpa_tistory',
                'description': '인기 블로그, 복잡한 레이아웃'
            }
        ]

        logger.info(f"Starting collection of {len(target_blogs)} Tistory blogs")
        results = []

        for i, blog in enumerate(target_blogs, 1):
            logger.info(f"[{i}/{len(target_blogs)}] Collecting: {blog['name']} - {blog['description']}")

            result = self.collect_single_page(blog['url'], blog['name'])
            result['description'] = blog['description']
            results.append(result)

            # 요청 간 지연 (서버 부담 최소화)
            if i < len(target_blogs):
                time.sleep(3)

        # 결과 요약
        success_count = sum(1 for r in results if r['success'])
        logger.info(f"Collection completed: {success_count}/{len(target_blogs)} successful")

        # 결과 요약 파일 저장
        summary_path = self.output_dir / f'collection_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        import json
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump({
                'total': len(results),
                'successful': success_count,
                'failed': len(results) - success_count,
                'results': results,
                'collected_at': datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)

        logger.info(f"Summary saved: {summary_path}")

        return results


def main():
    """메인 실행 함수"""
    logger.info("="*80)
    logger.info("Index HTML Collector - Phase 1 Prototype")
    logger.info("="*80)

    collector = IndexHTMLCollector()
    results = collector.collect_tistory_samples()

    # 결과 출력
    print("\n" + "="*80)
    print("Collection Results:")
    print("="*80)

    for i, result in enumerate(results, 1):
        status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
        print(f"{i}. {status}")
        print(f"   URL: {result['url']}")
        print(f"   Description: {result.get('description', 'N/A')}")
        if result['success']:
            print(f"   File: {result['file_path']}")
            print(f"   Size: {result['size']:,} bytes")
        else:
            print(f"   Error: {result['error']}")
        print()

    success_count = sum(1 for r in results if r['success'])
    print(f"Total: {success_count}/{len(results)} successful")
    print("="*80)


if __name__ == '__main__':
    main()
