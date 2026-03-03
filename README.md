# Generated: 2025-10-07 13:10:00 KST

# Scholar - Web Crawling and OCR Training System

**"The Scholar"** - 끊임없이 학습하며 지식을 축적하는 시스템

## 개요

Scholar는 한국어 웹 콘텐츠를 자동으로 수집하고, 고품질 OCR 학습 데이터를 생성하여 PaddleOCR 모델을 지속적으로 개선하는 시스템입니다.

## 주요 기능

- 🌐 **자동 웹 크롤링**: 22개 한국 블로그/뉴스 플랫폼에서 콘텐츠 수집
- 📸 **스크린샷 캡처**: Selenium 기반 고품질 이미지 생성
- 🎯 **Ground Truth 생성**: HTML 파싱을 통한 텍스트 위치 자동 추출
- ✅ **데이터 품질 관리**: 중복 제거, 플레이스홀더 필터링, 품질 점수 계산
- 🧠 **지속적 학습**: EWC 알고리즘 기반 catastrophic forgetting 방지
- 📊 **성능 추적**: 학습 이력 관리 및 모델 버전 관리

## 기술 스택

- **Language**: Python 3.11
- **Web Scraping**: Selenium, BeautifulSoup, Scrapy
- **OCR Training**: PaddleOCR, Elastic Weight Consolidation (EWC)
- **Database**: Oracle Database (XEPDB1)
- **Logging**: Loguru

## 디렉토리 구조

```
scholar/
├── src/              # Python 소스 코드
│   ├── crawler/      # 웹 크롤링
│   ├── data_processing/  # 품질 검증
│   ├── database/     # Oracle 연동
│   └── utils/        # 유틸리티
├── training/         # PaddleOCR 학습
├── config/           # 설정 파일
├── docker/           # Docker 설정
├── k8s/              # Kubernetes 배포
├── tests/            # 테스트
└── scripts/          # 스크립트
```

## 빠른 시작

### 로컬 실행

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일 편집

# 실행
python src/main.py
```

### Docker 실행

```bash
# 단독 실행
cd scholar/docker
docker-compose up -d

# 로그 확인
docker logs -f scholar-server

# 중지
docker-compose down
```

### Kubernetes 배포

```bash
# 배포
kubectl apply -f k8s/

# 상태 확인
kubectl get pods -n en-zine -l app=scholar

# 로그 확인
kubectl logs -f -n en-zine -l app=scholar
```

## 환경 변수

```bash
# Oracle Database (Production - Remote Server)
# 서버: 58.227.121.8:1521
# 접속 방법: docs/operation/008_외부접속정보.md 참조
ORACLE_HOST=oracle-xe          # Docker 네트워크 내부: oracle-xe
ORACLE_PORT=1521               # 외부 접속: 58.227.121.8:1521
ORACLE_SERVICE=XEPDB1
ORACLE_USER=ocr_admin
ORACLE_PASSWORD=admin_password

# Python
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
DATA_DIR=/home/pro301/git/en-zine/scholar/training/data
```

## 개발 가이드

### 테스트 실행

```bash
# 단위 테스트
pytest tests/unit -v

# 통합 테스트
pytest tests/integration -v

# 커버리지
pytest --cov=src tests/
```

### 크롤링 실행

```bash
# 전체 크롤링
python src/main.py --mode crawling

# 특정 플랫폼만
python src/main.py --mode crawling --platform naver_blog

# Dry run (테스트)
python src/main.py --mode crawling --dry-run
```

### 학습 실행

```bash
# 연속 학습 시작
python training/scripts/continuous_learning.py

# 단일 학습
python training/scripts/train.py --config training/configs/det/korean.yml
```

## 모니터링

### 성능 지표

```bash
# 크롤링 통계
python scripts/check_crawling_stats.py

# 학습 이력
python scripts/check_training_history.py
```

### 데이터 품질

```bash
# 품질 분석
python scripts/analyze_data_quality.py

# 중복 확인
python scripts/check_duplicates.py
```

## 문제 해결

### Oracle 연결 실패

```bash
# 연결 테스트
python -c "from src.database.connection import test_connection; test_connection()"

# Oracle 서비스 확인
docker ps | grep oracle

# 원격 서버 Oracle 접속
# 참조: docs/operation/008_외부접속정보.md
ssh -p 29022 pro301@58.227.121.8
docker exec -it oracle-xe sqlplus ocr_admin/admin_password@XEPDB1
```

### 메모리 부족

```bash
# 배치 크기 조정
# config/production.json에서 batch_size 감소
```

## 관련 문서

- [1001_웹크롤링_학습_시스템_개요.md](../docs/development/1001_웹크롤링_학습_시스템_개요.md)
- [1000_시스템_전체_흐름_개요.md](../docs/development/1000_시스템_전체_흐름_개요.md)
- [CLAUDE.md](../CLAUDE.md)

## 라이센스

Copyright (c) 2025 en-zine OCR Team

## 기여

Scholar 시스템은 Artisan 시스템과 독립적으로 개발됩니다.
변경 사항은 `scholar/` 디렉토리 내에서만 작업해주세요.
