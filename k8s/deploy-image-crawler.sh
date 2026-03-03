#!/bin/bash
# Generated: 2025-10-16 21:45:00 KST
# Phase 2B: Continuous Image Crawler Kubernetes Deployment Script

set -e

echo "=========================================="
echo "Phase 2B Image Crawler Deployment"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 환경 변수 (필요시 수정)
NAMESPACE="${NAMESPACE:-scholar}"
ORACLE_HOST="${ORACLE_HOST:-zine-oracle-xe}"
ORACLE_PORT="${ORACLE_PORT:-1521}"
ORACLE_SERVICE_NAME="${ORACLE_SERVICE_NAME:-XEPDB1}"
ORACLE_USERNAME="${ORACLE_USERNAME:-ocr_admin}"
ORACLE_PASSWORD="${ORACLE_PASSWORD:-admin_password}"

# 함수: 에러 메시지 출력
error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# 함수: 성공 메시지 출력
success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# 함수: 경고 메시지 출력
warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# 함수: 정보 메시지 출력
info() {
    echo -e "[INFO] $1"
}

# kubectl 명령 확인
if ! command -v kubectl &> /dev/null; then
    error "kubectl not found. Please install kubectl first."
fi

info "Using namespace: $NAMESPACE"

# 1. Namespace 생성
info "Creating namespace '$NAMESPACE'..."
if kubectl get namespace "$NAMESPACE" &> /dev/null; then
    warning "Namespace '$NAMESPACE' already exists"
else
    kubectl create namespace "$NAMESPACE"
    success "Namespace '$NAMESPACE' created"
fi

# 2. Oracle Credentials Secret 생성
info "Creating Oracle credentials secret..."
kubectl create secret generic oracle-credentials \
    --from-literal=ORACLE_HOST="$ORACLE_HOST" \
    --from-literal=ORACLE_PORT="$ORACLE_PORT" \
    --from-literal=ORACLE_SERVICE_NAME="$ORACLE_SERVICE_NAME" \
    --from-literal=ORACLE_USERNAME="$ORACLE_USERNAME" \
    --from-literal=ORACLE_PASSWORD="$ORACLE_PASSWORD" \
    -n "$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f -

success "Oracle credentials secret created/updated"

# 3. Deployment 적용
info "Applying continuous-image-crawler deployment..."
kubectl apply -f "$(dirname "$0")/continuous-image-crawler-deployment.yaml"

success "Deployment applied"

# 4. 배포 상태 확인
info "Waiting for deployment to be ready..."
kubectl rollout status deployment/continuous-image-crawler -n "$NAMESPACE" --timeout=5m

success "Deployment is ready"

# 5. Pod 상태 확인
echo ""
info "Current pods:"
kubectl get pods -n "$NAMESPACE" -l app=continuous-image-crawler

# 6. Service 확인
echo ""
info "Services:"
kubectl get svc -n "$NAMESPACE" -l app=continuous-image-crawler

# 7. PVC 확인
echo ""
info "Persistent Volume Claims:"
kubectl get pvc -n "$NAMESPACE" -l app=continuous-image-crawler

# 8. 로그 확인 옵션
echo ""
info "To view logs, run:"
echo "  kubectl logs -f deployment/continuous-image-crawler -n $NAMESPACE"

echo ""
info "To view metrics, run:"
echo "  kubectl port-forward -n $NAMESPACE svc/continuous-image-crawler 8005:8005"
echo "  Then open: http://localhost:8005/metrics"

echo ""
success "Deployment complete! 🎉"
