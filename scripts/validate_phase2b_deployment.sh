#!/bin/bash
# Generated: 2025-10-16 22:00:00 KST
# Phase 2B 배포 검증 스크립트

set -e

echo "=========================================="
echo "Phase 2B: Deployment Validation Checklist"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 검증 카운터
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# 함수: 체크 시작
check_start() {
    echo -ne "${BLUE}[CHECK]${NC} $1... "
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

# 함수: 체크 성공
check_pass() {
    echo -e "${GREEN}✓ PASS${NC}"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
}

# 함수: 체크 실패
check_fail() {
    echo -e "${RED}✗ FAIL${NC}"
    if [ ! -z "$1" ]; then
        echo -e "  ${YELLOW}→ $1${NC}"
    fi
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
}

# 함수: 체크 건너뛰기
check_skip() {
    echo -e "${YELLOW}⊘ SKIP${NC} $1"
}

# 함수: 헤더
header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# 프로젝트 루트
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHOLAR_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$SCHOLAR_ROOT"

# ==========================================
# 1. 파일 존재 검증
# ==========================================
header "1. File Existence Checks"

check_start "ScreenshotCrawler exists"
if [ -f "src/crawler/screenshot_crawler.py" ]; then
    check_pass
else
    check_fail "src/crawler/screenshot_crawler.py not found"
fi

check_start "ScreenshotStrategyRetriever exists"
if [ -f "src/crawler/screenshot_strategy_retriever.py" ]; then
    check_pass
else
    check_fail "src/crawler/screenshot_strategy_retriever.py not found"
fi

check_start "ImageCaptureManager exists"
if [ -f "src/database/image_capture_manager.py" ]; then
    check_pass
else
    check_fail "src/database/image_capture_manager.py not found"
fi

check_start "continuous_image_crawler.py exists"
if [ -f "src/continuous_image_crawler.py" ]; then
    check_pass
else
    check_fail "src/continuous_image_crawler.py not found"
fi

check_start "Kubernetes deployment YAML exists"
if [ -f "k8s/continuous-image-crawler-deployment.yaml" ]; then
    check_pass
else
    check_fail "k8s/continuous-image-crawler-deployment.yaml not found"
fi

# ==========================================
# 2. 테스트 파일 검증
# ==========================================
header "2. Test File Checks"

check_start "Unit test: screenshot_crawler"
if [ -f "tests/test_screenshot_crawler.py" ]; then
    check_pass
else
    check_fail "tests/test_screenshot_crawler.py not found"
fi

check_start "Unit test: strategy_retriever"
if [ -f "tests/test_screenshot_strategy_retriever.py" ]; then
    check_pass
else
    check_fail "tests/test_screenshot_strategy_retriever.py not found"
fi

check_start "Unit test: image_capture_manager"
if [ -f "tests/test_image_capture_manager.py" ]; then
    check_pass
else
    check_fail "tests/test_image_capture_manager.py not found"
fi

check_start "Integration test: image_collection"
if [ -f "tests/test_integration_image_collection.py" ]; then
    check_pass
else
    check_fail "tests/test_integration_image_collection.py not found"
fi

# ==========================================
# 3. Python 구문 검증
# ==========================================
header "3. Python Syntax Checks"

check_start "Syntax: ScreenshotCrawler"
if python3 -m py_compile src/crawler/screenshot_crawler.py 2>/dev/null; then
    check_pass
else
    check_fail "Syntax error in screenshot_crawler.py"
fi

check_start "Syntax: continuous_image_crawler"
if python3 -m py_compile src/continuous_image_crawler.py 2>/dev/null; then
    check_pass
else
    check_fail "Syntax error in continuous_image_crawler.py"
fi

# ==========================================
# 4. Import 검증
# ==========================================
header "4. Python Import Checks"

check_start "Import: ScreenshotCrawler"
if python3 -c "import sys; sys.path.insert(0, 'src'); from crawler.screenshot_crawler import ScreenshotCrawler" 2>/dev/null; then
    check_pass
else
    check_fail "Cannot import ScreenshotCrawler"
fi

check_start "Import: ScreenshotStrategyRetriever"
if python3 -c "import sys; sys.path.insert(0, 'src'); from crawler.screenshot_strategy_retriever import ScreenshotStrategyRetriever" 2>/dev/null; then
    check_pass
else
    check_fail "Cannot import ScreenshotStrategyRetriever"
fi

check_start "Import: ImageCaptureManager"
if python3 -c "import sys; sys.path.insert(0, 'src'); from database.image_capture_manager import ImageCaptureManager" 2>/dev/null; then
    check_pass
else
    check_fail "Cannot import ImageCaptureManager"
fi

# ==========================================
# 5. 디렉토리 구조 검증
# ==========================================
header "5. Directory Structure Checks"

check_start "Image storage directory writable"
IMAGE_DIR="/home/pro301/git/en-zine/scholar/training/data/images"
ALT_IMAGE_DIR="training/data/images"

if [ -w "$IMAGE_DIR" ] 2>/dev/null || [ -w "$ALT_IMAGE_DIR" ] 2>/dev/null; then
    check_pass
else
    check_fail "Image directory not writable"
fi

check_start "Logs directory writable"
LOG_DIR="/opt/scholar/logs"
ALT_LOG_DIR="logs"

if [ -w "$LOG_DIR" ] 2>/dev/null || [ -w "$ALT_LOG_DIR" ] 2>/dev/null || mkdir -p "$ALT_LOG_DIR" 2>/dev/null; then
    check_pass
else
    check_fail "Logs directory not writable"
fi

# ==========================================
# 6. 의존성 검증
# ==========================================
header "6. Dependency Checks"

check_start "Selenium installed"
if python3 -c "import selenium" 2>/dev/null; then
    check_pass
else
    check_fail "Selenium not installed (pip install selenium)"
fi

check_start "Pillow installed"
if python3 -c "from PIL import Image" 2>/dev/null; then
    check_pass
else
    check_fail "Pillow not installed (pip install Pillow)"
fi

check_start "loguru installed"
if python3 -c "from loguru import logger" 2>/dev/null; then
    check_pass
else
    check_fail "loguru not installed (pip install loguru)"
fi

check_start "prometheus_client installed"
if python3 -c "from prometheus_client import Counter" 2>/dev/null; then
    check_pass
else
    check_fail "prometheus_client not installed (pip install prometheus-client)"
fi

# ==========================================
# 7. Kubernetes YAML 검증
# ==========================================
header "7. Kubernetes Configuration Checks"

check_start "YAML syntax valid"
if command -v kubectl &> /dev/null; then
    if kubectl apply --dry-run=client -f k8s/continuous-image-crawler-deployment.yaml &>/dev/null; then
        check_pass
    else
        check_fail "Invalid Kubernetes YAML"
    fi
else
    check_skip "(kubectl not found)"
fi

# ==========================================
# 8. 환경 변수 검증
# ==========================================
header "8. Environment Variable Checks"

check_start "ORACLE_HOST defined"
if [ ! -z "$ORACLE_HOST" ]; then
    check_pass
else
    check_fail "ORACLE_HOST not set"
fi

check_start "ORACLE_USERNAME defined"
if [ ! -z "$ORACLE_USERNAME" ]; then
    check_pass
else
    check_fail "ORACLE_USERNAME not set"
fi

# ==========================================
# 결과 요약
# ==========================================
echo ""
echo "=========================================="
echo "Validation Summary"
echo "=========================================="
echo -e "Total Checks:  ${BLUE}$TOTAL_CHECKS${NC}"
echo -e "Passed:        ${GREEN}$PASSED_CHECKS${NC}"
echo -e "Failed:        ${RED}$FAILED_CHECKS${NC}"
echo "=========================================="

if [ $FAILED_CHECKS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! System is ready.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please fix the issues above.${NC}"
    exit 1
fi
