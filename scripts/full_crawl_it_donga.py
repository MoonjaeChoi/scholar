#!/usr/bin/env python3
# Generated: 2025-10-16 10:05:00 KST
"""
IT동아 전체 크롤링 스크립트 (스크린샷 + 데이터베이스 저장)

사용법:
    python full_crawl_it_donga.py --urls /path/to/article_urls.json --max 50
"""

import sys
import os
import json
import time
import hashlib
import argparse
from datetime import datetime
from pathlib import Path

# Add scholar src to path
script_dir = Path(__file__).parent
scholar_src = script_dir.parent / 'src'
sys.path.insert(0, str(scholar_src))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger

# Try to import database manager
try:
    from database.crawl_db_manager import CrawlDatabaseManager
    DB_AVAILABLE = True
except ImportError:
    logger.warning("Database manager not available - will save to files only")
    DB_AVAILABLE = False


class FullCrawler:
    """Full-featured crawler with screenshot capture and DB storage"""

    def __init__(self, output_dir: str, save_to_db: bool = True):
        self.output_dir = Path(output_dir)
        self.screenshots_dir = self.output_dir / 'screenshots'
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        self.save_to_db = save_to_db and DB_AVAILABLE
        self.driver = None
        self.db_manager = None

        self.results = []
        self.db_saved_count = 0

    def setup_driver(self):
        """Setup Chrome driver for screenshot capture"""
        logger.info("Setting up Chrome driver...")

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # Use system chromedriver
        service = Service('/usr/bin/chromedriver')
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)

        logger.success("✅ Chrome driver ready")

    def setup_database(self):
        """Setup database connection"""
        if not self.save_to_db:
            logger.info("Database saving disabled")
            return

        try:
            self.db_manager = CrawlDatabaseManager()
            logger.success("✅ Database connection ready")
        except Exception as e:
            logger.error(f"Failed to setup database: {e}")
            self.save_to_db = False

    def crawl_article(self, url: str, index: int, total: int) -> dict:
        """Crawl single article with screenshot"""
        logger.info(f"[{index}/{total}] Crawling: {url}")

        result = {
            'url': url,
            'index': index,
            'crawled_at': datetime.now().isoformat(),
            'success': False
        }

        try:
            # Load page
            self.driver.get(url)
            time.sleep(3)  # Wait for page to fully load

            # Extract title
            title = None
            try:
                title_elem = self.driver.find_element(By.TAG_NAME, 'h1')
                title = title_elem.text
            except:
                title = self.driver.title

            # Extract content
            content = None
            try:
                article_elem = self.driver.find_element(By.TAG_NAME, 'article')
                content = article_elem.text
            except:
                content = self.driver.find_element(By.TAG_NAME, 'body').text

            # Get page source
            html_content = self.driver.page_source

            # Generate unique filename
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"it_donga_{timestamp}_{url_hash}"

            # Save screenshot
            screenshot_path = self.screenshots_dir / f"{filename}.png"
            self.driver.save_screenshot(str(screenshot_path))

            # Save HTML
            html_path = self.screenshots_dir / f"{filename}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            # Calculate image hash for deduplication
            with open(screenshot_path, 'rb') as f:
                image_hash = hashlib.md5(f.read()).hexdigest()

            result.update({
                'title': title,
                'content_length': len(content) if content else 0,
                'screenshot_path': str(screenshot_path),
                'screenshot_relative': str(screenshot_path.relative_to(self.output_dir)),
                'html_path': str(html_path),
                'screenshot_size': screenshot_path.stat().st_size,
                'html_size': html_path.stat().st_size,
                'image_hash': image_hash,
                'success': True
            })

            logger.success(f"✅ Screenshot: {filename}.png ({result['screenshot_size']:,} bytes)")
            logger.info(f"   Title: {title[:60] if title else 'N/A'}...")
            logger.info(f"   Content: {result['content_length']} chars")

            # Save to database if enabled
            if self.save_to_db:
                try:
                    self.save_to_database(result)
                    result['db_saved'] = True
                    self.db_saved_count += 1
                except Exception as e:
                    logger.error(f"Failed to save to DB: {e}")
                    result['db_saved'] = False
                    result['db_error'] = str(e)

            return result

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            result['error'] = str(e)
            return result

    def save_to_database(self, result: dict):
        """Save crawled data to database"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Read image file as binary
            with open(result['screenshot_path'], 'rb') as f:
                image_data = f.read()

            # Insert into WEB_CAPTURE_DATA
            cursor.execute("""
                INSERT INTO WEB_CAPTURE_DATA (
                    CAPTURE_ID, URL, IMAGE_PATH, IMAGE_DATA, IMAGE_HASH,
                    HTML_CONTENT, TITLE, SOURCE_TYPE, CAPTURED_AT
                ) VALUES (
                    CAPTURE_SEQ.NEXTVAL, :url, :image_path, :image_data, :image_hash,
                    :html_content, :title, :source_type, SYSTIMESTAMP
                )
            """, {
                'url': result['url'],
                'image_path': result['screenshot_relative'],
                'image_data': image_data,
                'image_hash': result['image_hash'],
                'html_content': open(result['html_path'], 'r', encoding='utf-8').read()[:4000],  # Oracle CLOB limit
                'title': result.get('title', '')[:500],
                'source_type': 'IT동아'
            })

            conn.commit()
            logger.success(f"   💾 Saved to database")

    def run(self, urls: list, max_articles: int = None):
        """Run full crawling"""
        logger.info("=" * 80)
        logger.info(f"Starting Full Crawling - IT동아")
        logger.info("=" * 80)

        if max_articles:
            urls = urls[:max_articles]

        logger.info(f"Total URLs to crawl: {len(urls)}")
        logger.info(f"Save to database: {'YES' if self.save_to_db else 'NO'}")

        try:
            self.setup_driver()
            self.setup_database()

            # Crawl articles
            for i, url in enumerate(urls, 1):
                result = self.crawl_article(url, i, len(urls))
                self.results.append(result)

                # Delay between requests
                if i < len(urls):
                    delay = 3
                    logger.info(f"Waiting {delay}s...")
                    time.sleep(delay)

        except KeyboardInterrupt:
            logger.warning("Interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Chrome driver closed")

        # Save results
        self.save_results()
        self.print_summary()

    def save_results(self):
        """Save crawling results to JSON"""
        output_file = self.output_dir / 'full_crawl_results.json'

        data = {
            'site': 'IT동아',
            'crawled_at': datetime.now().isoformat(),
            'total_articles': len(self.results),
            'successful_articles': sum(1 for r in self.results if r.get('success')),
            'db_saved_count': self.db_saved_count,
            'results': self.results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.success(f"Results saved to: {output_file}")

    def print_summary(self):
        """Print crawling summary"""
        logger.info("\n" + "=" * 80)
        logger.info("Full Crawling Summary")
        logger.info("=" * 80)

        successful = sum(1 for r in self.results if r.get('success'))
        failed = len(self.results) - successful

        logger.info(f"Total articles: {len(self.results)}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Success rate: {successful/len(self.results)*100:.1f}%")

        if self.save_to_db:
            logger.info(f"Saved to database: {self.db_saved_count}")

        if successful > 0:
            total_size = sum(r.get('screenshot_size', 0) for r in self.results if r.get('success'))
            avg_size = total_size / successful
            logger.info(f"Total screenshots: {total_size/1024/1024:.2f} MB")
            logger.info(f"Avg screenshot size: {avg_size/1024:.1f} KB")

        logger.info("\n" + "=" * 80)
        if successful >= len(self.results) * 0.8:
            logger.success("🎉 CRAWLING SUCCESSFUL")
        else:
            logger.warning("⚠️  Success rate below 80%")
        logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='IT동아 전체 크롤링')
    parser.add_argument('--urls', required=True, help='URL JSON 파일 경로')
    parser.add_argument('--output', default='/tmp/it_donga_crawl', help='출력 디렉토리')
    parser.add_argument('--max', type=int, help='최대 크롤링 개수')
    parser.add_argument('--no-db', action='store_true', help='데이터베이스 저장 비활성화')

    args = parser.parse_args()

    # Load URLs
    with open(args.urls, 'r', encoding='utf-8') as f:
        url_data = json.load(f)
        urls = url_data.get('urls', [])

    logger.info(f"Loaded {len(urls)} URLs from {args.urls}")

    # Run crawler
    crawler = FullCrawler(
        output_dir=args.output,
        save_to_db=not args.no_db
    )

    crawler.run(urls, max_articles=args.max)


if __name__ == '__main__':
    main()
