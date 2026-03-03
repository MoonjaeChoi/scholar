# PaddleOCR Training Environment

이 디렉토리는 웹페이지 텍스트 인식에 최적화된 PaddleOCR 모델 학습을 위한 환경입니다.

## 디렉토리 구조

```
paddleocr_training/
├── PaddleOCR/                 # PaddleOCR 소스코드 (자동 다운로드)
├── data/
│   ├── train/                 # 학습 데이터
│   │   ├── images/
│   │   └── labels/
│   ├── val/                   # 검증 데이터
│   │   ├── images/
│   │   └── labels/
│   └── test/                  # 테스트 데이터
├── configs/                   # 학습 설정 파일
├── models/                    # 사전 학습된 모델
│   ├── detection/
│   └── recognition/
├── logs/                      # 학습 로그
├── output/                    # 학습 결과
├── scripts/                   # 실행 스크립트
├── requirements.txt           # Python 의존성
├── setup_environment.sh       # 환경 구성 스크립트
└── README.md                 # 이 파일
```

## 설치 및 환경 구성

### 1. Oracle Linux 9 컨테이너 접속
```bash
docker exec -it oracle-linux9-container bash
cd /opt/ocr_system/paddleocr_training
```

### 2. 자동 환경 구성
```bash
# 전체 환경 자동 구성
./setup_environment.sh
```

### 3. 수동 설치 (옵션)
```bash
# Python 가상환경 생성
python3 -m venv venv_paddleocr
source venv_paddleocr/bin/activate

# 의존성 설치
pip install -r requirements.txt

# PaddleOCR 소스코드 다운로드
git clone https://github.com/PaddlePaddle/PaddleOCR.git

# 사전 학습된 모델 다운로드
./download_pretrained_models.sh
```

## 데이터 준비

### 데이터베이스에서 PaddleOCR 형식으로 변환
```bash
# 가상환경 활성화
source venv_paddleocr/bin/activate

# 데이터셋 변환 실행
python scripts/convert_database_to_paddleocr.py
```

## 환경 테스트

### 전체 환경 테스트
```bash
python scripts/test_paddleocr_environment.py
```

테스트 항목:
- PaddlePaddle 설치 확인
- PaddleOCR 기본 기능 테스트
- 사전 학습된 모델 존재 확인
- 데이터셋 구조 검증

## 주요 스크립트

- `setup_environment.sh`: 전체 환경 자동 구성
- `download_pretrained_models.sh`: 사전 학습된 모델 다운로드
- `scripts/convert_database_to_paddleocr.py`: 데이터베이스 데이터를 PaddleOCR 형식으로 변환
- `scripts/test_paddleocr_environment.py`: 환경 설정 검증
- `database_connection.py`: Oracle 데이터베이스 연결 모듈

## 환경 변수

다음 환경 변수들이 필요합니다:

```bash
# Oracle Database 연결
DB_HOST=localhost
DB_PORT=1521
DB_SERVICE_NAME=pdb_ocr_system
DB_USERNAME=ocr_admin
DB_PASSWORD=SecurePassword123!

# Oracle Client 경로
ORACLE_HOME=/usr/lib/oracle/21/client64
LD_LIBRARY_PATH=$ORACLE_HOME/lib:$LD_LIBRARY_PATH
```

## 다음 단계

환경 구성이 완료되면:
1. 201번 문서: PaddleOCR Fine-tuning 설정 및 실행
2. 202번 문서: 모델 최적화 및 배포 준비

## 문제 해결

### 일반적인 문제들
1. **Oracle 클라이언트 오류**: ORACLE_HOME 환경 변수 확인
2. **PaddlePaddle 설치 오류**: Python 버전 및 가상환경 확인
3. **모델 다운로드 실패**: 네트워크 연결 확인

### 로그 확인
- 환경 테스트 로그: 콘솔 출력
- 데이터 변환 로그: loguru를 통한 로그 출력