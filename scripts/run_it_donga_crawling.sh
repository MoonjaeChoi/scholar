#!/bin/bash
# Generated: 2025-10-16 10:05:00 KST
# IT동아 전체 크롤링 실행 스크립트

set -e

echo "================================================================================"
echo "IT동아 전체 크롤링 실행"
echo "================================================================================"
echo "시작 시간: $(date)"
echo ""

# 환경 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHOLAR_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="/tmp/it_donga_crawl_$(date +%Y%m%d_%H%M%S)"
URL_FILE="${1:-$SCRIPT_DIR/article_urls.json}"

echo "설정:"
echo "  Scholar 디렉토리: $SCHOLAR_DIR"
echo "  출력 디렉토리: $OUTPUT_DIR"
echo "  URL 파일: $URL_FILE"
echo ""

# URL 파일 존재 확인
if [ ! -f "$URL_FILE" ]; then
    echo "❌ URL 파일을 찾을 수 없습니다: $URL_FILE"
    echo ""
    echo "사용법:"
    echo "  $0 /path/to/article_urls.json"
    exit 1
fi

# ChromeDriver 확인
if ! command -v chromedriver &> /dev/null; then
    echo "⚠️  ChromeDriver를 찾을 수 없습니다"
    echo ""
    echo "설치 방법:"
    echo "  sudo yum install -y chromium chromium-headless chromedriver"
    exit 1
fi

# Python 가상환경 활성화 (존재하는 경우)
if [ -d "$SCHOLAR_DIR/venv" ]; then
    echo "✅ Python 가상환경 활성화"
    source "$SCHOLAR_DIR/venv/bin/activate"
fi

# Python 의존성 확인
python3 -c "import selenium; from loguru import logger" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  필요한 Python 패키지가 설치되지 않았습니다"
    echo ""
    echo "설치 명령:"
    echo "  pip install selenium loguru"
    exit 1
fi

# URL 개수 확인
URL_COUNT=$(python3 -c "import json; print(len(json.load(open('$URL_FILE'))['urls']))")
echo "✅ $URL_COUNT 개의 URL 로드됨"
echo ""

# 크롤링 실행
echo "================================================================================"
echo "크롤링 시작..."
echo "================================================================================"
echo ""

python3 "$SCRIPT_DIR/full_crawl_it_donga.py" \
    --urls "$URL_FILE" \
    --output "$OUTPUT_DIR" \
    --max 50

RESULT=$?

echo ""
echo "================================================================================"
if [ $RESULT -eq 0 ]; then
    echo "✅ 크롤링 완료"
else
    echo "❌ 크롤링 실패 (exit code: $RESULT)"
fi
echo "================================================================================"
echo ""

# 결과 확인
if [ -d "$OUTPUT_DIR/screenshots" ]; then
    SCREENSHOT_COUNT=$(ls -1 "$OUTPUT_DIR/screenshots"/*.png 2>/dev/null | wc -l)
    TOTAL_SIZE=$(du -sh "$OUTPUT_DIR/screenshots" | cut -f1)

    echo "결과:"
    echo "  스크린샷 개수: $SCREENSHOT_COUNT"
    echo "  총 용량: $TOTAL_SIZE"
    echo "  저장 위치: $OUTPUT_DIR"
fi

echo ""
echo "종료 시간: $(date)"
echo "================================================================================"

# 결과 파일 위치 출력
if [ -f "$OUTPUT_DIR/full_crawl_results.json" ]; then
    echo ""
    echo "📊 결과 파일:"
    echo "  $OUTPUT_DIR/full_crawl_results.json"
    echo ""
    echo "확인 방법:"
    echo "  cat $OUTPUT_DIR/full_crawl_results.json | python3 -m json.tool | head -50"
fi

exit $RESULT
