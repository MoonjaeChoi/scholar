# Phase 2B: Continuous Image Crawler - Kubernetes Deployment

## 개요

이 디렉토리는 PaddleOCR 학습용 이미지 수집 시스템의 Kubernetes 배포 설정을 포함합니다.

## 파일 구조

```
scholar/k8s/
├── continuous-image-crawler-deployment.yaml  # Kubernetes 리소스 정의
├── deploy-image-crawler.sh                   # 배포 스크립트
├── undeploy-image-crawler.sh                 # 언디플로이 스크립트
└── README.md                                  # 이 파일
```

## 배포 방법

### 1. 빠른 배포 (권장)

```bash
cd /Users/memmem/git/en-zine/scholar/k8s

# 기본 설정으로 배포
./deploy-image-crawler.sh
```

### 2. 환경 변수 커스터마이즈

```bash
# Oracle 연결 정보 수정
export ORACLE_HOST="your-oracle-host"
export ORACLE_PORT="1521"
export ORACLE_SERVICE_NAME="XEPDB1"
export ORACLE_USERNAME="ocr_admin"
export ORACLE_PASSWORD="your-password"
export NAMESPACE="scholar"

./deploy-image-crawler.sh
```

### 3. 수동 배포

```bash
# 1. Namespace 생성
kubectl create namespace scholar

# 2. Secret 생성
kubectl create secret generic oracle-credentials \
  --from-literal=ORACLE_HOST=zine-oracle-xe \
  --from-literal=ORACLE_PORT=1521 \
  --from-literal=ORACLE_SERVICE_NAME=XEPDB1 \
  --from-literal=ORACLE_USERNAME=ocr_admin \
  --from-literal=ORACLE_PASSWORD=admin_password \
  -n scholar

# 3. Deployment 적용
kubectl apply -f continuous-image-crawler-deployment.yaml

# 4. 상태 확인
kubectl get pods -n scholar
kubectl logs -f deployment/continuous-image-crawler -n scholar
```

## 리소스 구성

### Deployment

- **Replicas**: 1 (중복 크롤링 방지)
- **Resources**:
  - CPU: 1000m (request) ~ 4000m (limit)
  - Memory: 2Gi (request) ~ 8Gi (limit)
- **Image**: `scholar:latest`
- **Command**: `python src/continuous_image_crawler.py`

### Service

- **Type**: ClusterIP
- **Port**: 8005 (Prometheus metrics)

### ConfigMap

- `CRAWL_INTERVAL_SECONDS`: 300 (5분)
- `IMAGE_CRAWL_BATCH_SIZE`: 10
- `PROMETHEUS_METRICS_PORT`: 8005

### PersistentVolumeClaim

- `scholar-images-pvc`: 100Gi (이미지 저장)
- `scholar-logs-pvc`: 10Gi (로그 저장)

### Secret

- `oracle-credentials`: Oracle 데이터베이스 연결 정보

## 모니터링

### 로그 확인

```bash
# 실시간 로그
kubectl logs -f deployment/continuous-image-crawler -n scholar

# 최근 100줄
kubectl logs --tail=100 deployment/continuous-image-crawler -n scholar
```

### 메트릭 확인

```bash
# Port forwarding
kubectl port-forward -n scholar svc/continuous-image-crawler 8005:8005

# 브라우저에서 열기
open http://localhost:8005/metrics
```

### Pod 상태

```bash
# Pod 목록
kubectl get pods -n scholar -l app=continuous-image-crawler

# Pod 상세 정보
kubectl describe pod -n scholar -l app=continuous-image-crawler
```

## 언디플로이

### 1. PVC 보존 (기본)

```bash
./undeploy-image-crawler.sh
```

### 2. PVC 삭제 (데이터 손실 주의!)

```bash
DELETE_PVC=true ./undeploy-image-crawler.sh
```

### 3. 수동 삭제

```bash
kubectl delete -f continuous-image-crawler-deployment.yaml
kubectl delete secret oracle-credentials -n scholar
```

## 트러블슈팅

### Pod가 시작되지 않음

```bash
# Pod 이벤트 확인
kubectl describe pod -n scholar -l app=continuous-image-crawler

# 로그 확인
kubectl logs -n scholar -l app=continuous-image-crawler
```

### Oracle 연결 실패

```bash
# Secret 확인
kubectl get secret oracle-credentials -n scholar -o yaml

# 환경 변수 확인
kubectl exec -n scholar deployment/continuous-image-crawler -- env | grep ORACLE
```

### 이미지 저장 실패

```bash
# PVC 상태 확인
kubectl get pvc -n scholar

# PVC 마운트 확인
kubectl exec -n scholar deployment/continuous-image-crawler -- ls -la /home/pro301/git/en-zine/scholar/training/data/images
```

### Chrome/Selenium 에러

```bash
# Chrome 설치 확인
kubectl exec -n scholar deployment/continuous-image-crawler -- which google-chrome

# Headless 모드 확인
kubectl exec -n scholar deployment/continuous-image-crawler -- google-chrome --version
```

## 업데이트

### ConfigMap 수정

```bash
# ConfigMap 편집
kubectl edit configmap image-crawler-config -n scholar

# Pod 재시작 (ConfigMap 반영)
kubectl rollout restart deployment/continuous-image-crawler -n scholar
```

### Secret 수정

```bash
# Secret 삭제
kubectl delete secret oracle-credentials -n scholar

# 새로운 Secret 생성
kubectl create secret generic oracle-credentials \
  --from-literal=ORACLE_HOST=new-host \
  --from-literal=ORACLE_PORT=1521 \
  ... \
  -n scholar

# Pod 재시작
kubectl rollout restart deployment/continuous-image-crawler -n scholar
```

### 이미지 업데이트

```bash
# 새로운 이미지 빌드
docker build -t scholar:latest .

# Deployment 업데이트
kubectl set image deployment/continuous-image-crawler \
  image-crawler=scholar:latest \
  -n scholar

# 롤아웃 상태 확인
kubectl rollout status deployment/continuous-image-crawler -n scholar
```

## 스케일링

### Replica 수 증가 (권장하지 않음)

**주의**: 중복 크롤링 방지를 위해 replica를 1로 유지하는 것을 권장합니다.

```bash
# Replica 증가 (테스트 목적으로만)
kubectl scale deployment continuous-image-crawler --replicas=2 -n scholar
```

### 리소스 제한 조정

```bash
# Deployment 편집
kubectl edit deployment continuous-image-crawler -n scholar

# resources 섹션 수정:
# resources:
#   requests:
#     cpu: "2000m"
#     memory: "4Gi"
#   limits:
#     cpu: "8000m"
#     memory: "16Gi"
```

## Prometheus 연동

### ServiceMonitor 사용 (Prometheus Operator)

Deployment YAML에 이미 ServiceMonitor가 포함되어 있습니다:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: continuous-image-crawler
  namespace: scholar
spec:
  selector:
    matchLabels:
      app: continuous-image-crawler
  endpoints:
    - port: metrics
      interval: 30s
      path: /metrics
```

### Prometheus 쿼리 예제

```promql
# 총 캡처 수
screenshot_captures_total

# 성공률
rate(screenshot_captures_total{status="success"}[5m])
  / rate(screenshot_captures_total[5m])

# 평균 캡처 시간
rate(screenshot_capture_duration_seconds_sum[5m])
  / rate(screenshot_capture_duration_seconds_count[5m])

# 현재 활성 크롤 수
active_crawls
```

## 참고 문서

- [340_10: Phase 2B 전체 개요](../../docs/development/340_10_paddleocr_image_collection_system_overview.md)
- [340_50: Continuous Image Crawler](../../docs/development/340_50_continuous_image_crawler.md)
- [340_60: Kubernetes 배포](../../docs/development/340_60_kubernetes_deployment.md)

## 라이선스

This is part of the en-zine project.
