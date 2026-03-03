#!/bin/bash
# Generated: 2025-10-16 22:10:00 KST
# Phase 2B 일일 점검 스크립트

set -e

echo "=========================================="
echo "Phase 2B: Daily Health Check"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 카운터
TOTAL_CHECKS=0
PASSED=0
WARNINGS=0
FAILURES=0

# 함수
check() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo -n "$1... "
}

pass() {
    echo -e "${GREEN}✓ PASS${NC}"
    PASSED=$((PASSED + 1))
}

warn() {
    echo -e "${YELLOW}⚠ WARNING${NC}: $1"
    WARNINGS=$((WARNINGS + 1))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    FAILURES=$((FAILURES + 1))
}

# ==========================================
# 1. Kubernetes Pod 상태
# ==========================================
echo ""
echo "1. Kubernetes Status"
echo "----------------------------------------"

if command -v kubectl &> /dev/null; then
    check "Pod running status"
    POD_STATUS=$(kubectl get pods -n scholar -l app=continuous-image-crawler -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
    
    if [ "$POD_STATUS" = "Running" ]; then
        pass
    else
        fail "Pod status: $POD_STATUS"
    fi
    
    check "Pod restart count"
    RESTARTS=$(kubectl get pods -n scholar -l app=continuous-image-crawler -o jsonpath='{.items[0].status.containerStatuses[0].restartCount}' 2>/dev/null)
    
    if [ "$RESTARTS" -lt 5 ]; then
        pass
    else
        warn "Restart count: $RESTARTS (threshold: 5)"
    fi
else
    echo "kubectl not found (skipping Kubernetes checks)"
fi

# ==========================================
# 2. Prometheus 메트릭
# ==========================================
echo ""
echo "2. Prometheus Metrics"
echo "----------------------------------------"

METRICS_URL="${METRICS_URL:-http://localhost:8005/metrics}"

check "Metrics endpoint accessible"
if curl -s -f "$METRICS_URL" > /dev/null 2>&1; then
    pass
    
    # 캡처 성공률 확인
    check "Screenshot capture success rate"
    SUCCESS=$(curl -s "$METRICS_URL" | grep 'screenshot_captures_total{.*status="success"}' | awk '{print $2}' | awk '{s+=$1} END {print s}')
    TOTAL=$(curl -s "$METRICS_URL" | grep 'screenshot_captures_total' | awk '{print $2}' | awk '{s+=$1} END {print s}')
    
    if [ -n "$SUCCESS" ] && [ -n "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
        SUCCESS_RATE=$(awk "BEGIN {printf \"%.1f\", ($SUCCESS/$TOTAL)*100}")
        
        if (( $(echo "$SUCCESS_RATE >= 80" | bc -l) )); then
            pass
            echo "  Success rate: $SUCCESS_RATE%"
        else
            warn "Success rate: $SUCCESS_RATE% (threshold: 80%)"
        fi
    else
        warn "Unable to calculate success rate"
    fi
else
    fail "Cannot access $METRICS_URL"
fi

# ==========================================
# 3. 로그 확인
# ==========================================
echo ""
echo "3. Log Analysis"
echo "----------------------------------------"

LOG_FILE="${LOG_FILE:-/opt/scholar/logs/continuous_image_crawler.log}"
ALT_LOG_FILE="logs/continuous_image_crawler.log"

if [ -f "$LOG_FILE" ] || [ -f "$ALT_LOG_FILE" ]; then
    ACTUAL_LOG=$([ -f "$LOG_FILE" ] && echo "$LOG_FILE" || echo "$ALT_LOG_FILE")
    
    check "Recent ERROR logs"
    ERROR_COUNT=$(grep -c "ERROR" "$ACTUAL_LOG" 2>/dev/null | tail -1000 || echo 0)
    
    if [ "$ERROR_COUNT" -lt 10 ]; then
        pass
        echo "  Error count: $ERROR_COUNT"
    else
        warn "Error count: $ERROR_COUNT (threshold: 10)"
    fi
else
    echo "Log file not found (skipping log checks)"
fi

# ==========================================
# 4. 데이터베이스 확인
# ==========================================
echo ""
echo "4. Database Checks"
echo "----------------------------------------"

if [ -n "$ORACLE_HOST" ] && [ -n "$ORACLE_USERNAME" ]; then
    check "Oracle connectivity"
    
    # sqlplus 사용 가능한 경우
    if command -v sqlplus &> /dev/null; then
        CONN_TEST=$(echo "SELECT 1 FROM DUAL;" | sqlplus -S "$ORACLE_USERNAME/$ORACLE_PASSWORD@$ORACLE_HOST:$ORACLE_PORT/$ORACLE_SERVICE_NAME" 2>&1 | grep -c "^1$")
        
        if [ "$CONN_TEST" -eq 1 ]; then
            pass
        else
            fail "Cannot connect to Oracle"
        fi
    else
        echo "sqlplus not found (skipping DB checks)"
    fi
else
    echo "Oracle credentials not set (skipping DB checks)"
fi

# ==========================================
# 결과 요약
# ==========================================
echo ""
echo "=========================================="
echo "Health Check Summary"
echo "=========================================="
echo "Total Checks: $TOTAL_CHECKS"
echo -e "Passed:       ${GREEN}$PASSED${NC}"
echo -e "Warnings:     ${YELLOW}$WARNINGS${NC}"
echo -e "Failures:     ${RED}$FAILURES${NC}"
echo "=========================================="

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✓ System health is good${NC}"
    exit 0
elif [ $FAILURES -le 2 ]; then
    echo -e "${YELLOW}⚠ System has minor issues${NC}"
    exit 1
else
    echo -e "${RED}✗ System has critical issues${NC}"
    exit 2
fi
