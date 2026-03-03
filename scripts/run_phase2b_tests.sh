#!/bin/bash
# Generated: 2025-10-16 21:55:00 KST
# Phase 2B 테스트 실행 스크립트

set -e

echo "=========================================="
echo "Phase 2B: Image Collection System Tests"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수: 에러 메시지
error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# 함수: 성공 메시지
success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# 함수: 정보 메시지
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# 함수: 헤더 출력
header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# 프로젝트 루트 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHOLAR_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$SCHOLAR_ROOT"

info "Scholar root: $SCHOLAR_ROOT"

# Python 가상환경 확인
if [ -d "venv" ]; then
    info "Activating virtual environment..."
    source venv/bin/activate
elif [ -d "../venv" ]; then
    info "Activating parent virtual environment..."
    source ../venv/bin/activate
else
    info "No virtual environment found (using system Python)"
fi

# pytest 설치 확인
if ! command -v pytest &> /dev/null; then
    error "pytest not found. Install with: pip install pytest pytest-cov"
fi

# 테스트 타입 선택
TEST_TYPE="${1:-all}"

case "$TEST_TYPE" in
    "unit")
        header "Running Unit Tests Only"
        info "Testing individual components..."
        pytest tests/test_screenshot_crawler.py \
               tests/test_screenshot_strategy_retriever.py \
               tests/test_image_capture_manager.py \
               -v --tb=short
        ;;

    "integration")
        header "Running Integration Tests Only"
        info "Testing end-to-end workflow..."
        pytest tests/test_integration_image_collection.py \
               -v --tb=short --log-cli-level=INFO
        ;;

    "performance")
        header "Running Performance Tests Only"
        info "Measuring system performance..."
        pytest tests/test_integration_image_collection.py::TestPerformance \
               -v --tb=short --log-cli-level=INFO
        ;;

    "validation")
        header "Running Data Validation Tests Only"
        info "Validating data integrity..."
        pytest tests/test_integration_image_collection.py::TestDataValidation \
               -v --tb=short --log-cli-level=INFO
        ;;

    "coverage")
        header "Running Tests with Coverage"
        info "Generating coverage report..."
        pytest tests/ \
               --cov=src/crawler \
               --cov=src/database \
               --cov-report=html \
               --cov-report=term \
               -v --tb=short

        if [ -d "htmlcov" ]; then
            success "Coverage report generated: htmlcov/index.html"
            info "Open with: open htmlcov/index.html"
        fi
        ;;

    "all")
        header "Running All Tests"

        # 1. Unit Tests
        info "1/3 Unit Tests..."
        pytest tests/test_screenshot_crawler.py \
               tests/test_screenshot_strategy_retriever.py \
               tests/test_image_capture_manager.py \
               -v --tb=line -q

        # 2. Integration Tests
        info "2/3 Integration Tests..."
        pytest tests/test_integration_image_collection.py \
               -v --tb=line -q --log-cli-level=WARNING

        # 3. Performance Tests
        info "3/3 Performance Tests..."
        pytest tests/test_integration_image_collection.py::TestPerformance \
               -v --tb=line -q --log-cli-level=WARNING

        success "All tests completed!"
        ;;

    "quick")
        header "Running Quick Tests (Unit Only)"
        info "Fast unit tests for rapid feedback..."
        pytest tests/test_screenshot_crawler.py::TestScreenshotCrawler::test_a4_constants \
               tests/test_screenshot_strategy_retriever.py::TestScreenshotStrategyRetriever::test_clear_cache \
               tests/test_image_capture_manager.py::TestImageCaptureManager::test_calculate_hash \
               -v --tb=short
        ;;

    "help"|"-h"|"--help")
        echo "Usage: $0 [TEST_TYPE]"
        echo ""
        echo "Test Types:"
        echo "  all           - Run all tests (default)"
        echo "  unit          - Run unit tests only"
        echo "  integration   - Run integration tests only"
        echo "  performance   - Run performance tests only"
        echo "  validation    - Run data validation tests only"
        echo "  coverage      - Run all tests with coverage report"
        echo "  quick         - Run quick unit tests only"
        echo "  help          - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                  # Run all tests"
        echo "  $0 unit             # Run unit tests"
        echo "  $0 integration      # Run integration tests"
        echo "  $0 coverage         # Generate coverage report"
        exit 0
        ;;

    *)
        error "Unknown test type: $TEST_TYPE (use 'help' for options)"
        ;;
esac

echo ""
success "Test run complete! 🎉"
