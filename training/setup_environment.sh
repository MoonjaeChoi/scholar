#!/bin/bash
# PaddleOCR 환경 구성 자동화 스크립트

set -e

WORK_DIR="/home/pro301/git/en-zine/ocr_system/paddleocr_training"
VENV_NAME="venv_paddleocr"

echo "=== PaddleOCR Environment Setup ==="
echo "Working directory: $WORK_DIR"

# 작업 디렉토리 존재 확인
if [ ! -d "$WORK_DIR" ]; then
    echo "Error: Working directory not found: $WORK_DIR"
    echo "Please ensure you are in the correct environment"
    exit 1
fi

cd $WORK_DIR

# 1. 시스템 의존성 설치
echo "1. Installing system dependencies..."
sudo dnf install -y gcc gcc-c++ cmake
sudo dnf install -y openblas-devel lapack-devel
sudo dnf install -y git wget

# 2. Python 가상환경 생성
echo "2. Creating Python virtual environment..."
if [ ! -d "$VENV_NAME" ]; then
    python3 -m venv $VENV_NAME
    echo "✓ Virtual environment created: $VENV_NAME"
else
    echo "✓ Virtual environment already exists: $VENV_NAME"
fi

# 가상환경 활성화
source $VENV_NAME/bin/activate

# 3. Python 패키지 설치
echo "3. Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. PaddleOCR 소스코드 다운로드
echo "4. Downloading PaddleOCR source code..."
if [ ! -d "PaddleOCR" ]; then
    git clone https://github.com/PaddlePaddle/PaddleOCR.git
    echo "✓ PaddleOCR source code downloaded"
else
    echo "✓ PaddleOCR source code already exists"
fi

cd PaddleOCR

# PaddleOCR 의존성 추가 설치
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

cd ..

# 5. 사전 학습된 모델 다운로드
echo "5. Downloading pretrained models..."
chmod +x download_pretrained_models.sh
./download_pretrained_models.sh

# 6. 환경 테스트
echo "6. Testing environment..."
python scripts/test_paddleocr_environment.py

if [ $? -eq 0 ]; then
    echo "✓ Environment setup completed successfully!"
    echo ""
    echo "To activate the environment:"
    echo "  cd $WORK_DIR"
    echo "  source $VENV_NAME/bin/activate"
    echo ""
    echo "To test the conversion script:"
    echo "  python scripts/convert_database_to_paddleocr.py"
else
    echo "✗ Environment test failed. Please check the logs."
    exit 1
fi