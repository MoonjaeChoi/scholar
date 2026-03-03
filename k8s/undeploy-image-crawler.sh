#!/bin/bash
# Generated: 2025-10-16 21:45:00 KST
# Phase 2B: Continuous Image Crawler Kubernetes Undeployment Script

set -e

echo "=========================================="
echo "Phase 2B Image Crawler Undeployment"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 환경 변수
NAMESPACE="${NAMESPACE:-scholar}"
DELETE_PVC="${DELETE_PVC:-false}"  # PVC 삭제 여부 (기본: 보존)

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

# 확인 메시지
echo ""
warning "This will delete the continuous-image-crawler deployment."
if [ "$DELETE_PVC" = "true" ]; then
    warning "PVC will also be DELETED (data loss!)."
else
    info "PVC will be preserved (set DELETE_PVC=true to delete)."
fi

echo ""
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    info "Aborted."
    exit 0
fi

# 1. Deployment 삭제
info "Deleting deployment..."
kubectl delete deployment continuous-image-crawler -n "$NAMESPACE" --ignore-not-found=true
success "Deployment deleted"

# 2. Service 삭제
info "Deleting service..."
kubectl delete service continuous-image-crawler -n "$NAMESPACE" --ignore-not-found=true
success "Service deleted"

# 3. ConfigMap 삭제
info "Deleting ConfigMap..."
kubectl delete configmap image-crawler-config -n "$NAMESPACE" --ignore-not-found=true
success "ConfigMap deleted"

# 4. Secret 삭제
info "Deleting Secret..."
kubectl delete secret oracle-credentials -n "$NAMESPACE" --ignore-not-found=true
success "Secret deleted"

# 5. ServiceMonitor 삭제 (있는 경우)
info "Deleting ServiceMonitor (if exists)..."
kubectl delete servicemonitor continuous-image-crawler -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true

# 6. PVC 삭제 (옵션)
if [ "$DELETE_PVC" = "true" ]; then
    warning "Deleting PVC (DATA WILL BE LOST)..."
    kubectl delete pvc scholar-images-pvc -n "$NAMESPACE" --ignore-not-found=true
    kubectl delete pvc scholar-logs-pvc -n "$NAMESPACE" --ignore-not-found=true
    success "PVC deleted"
else
    info "PVC preserved (scholar-images-pvc, scholar-logs-pvc)"
fi

# 7. 상태 확인
echo ""
info "Remaining resources in namespace '$NAMESPACE':"
kubectl get all -n "$NAMESPACE" -l app=continuous-image-crawler

echo ""
success "Undeployment complete! 👋"
