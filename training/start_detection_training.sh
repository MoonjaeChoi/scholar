#!/bin/bash
# Generated: 2025-10-01 11:20:00 KST
# Phase 3: Detection 모델 학습 시작 스크립트

set -e

WORK_DIR="/home/pro301/git/en-zine/ocr_system/paddleocr_training"
cd $WORK_DIR

echo "=== Phase 3: Detection 모델 학습 시작 ==="
echo ""

# 0. cuDNN 심볼릭 링크 설정 (최초 1회)
echo "0. cuDNN 라이브러리 설정 중..."
if [ ! -L "/usr/local/cuda/lib64/libcudnn.so.8" ]; then
    echo "   cuDNN 심볼릭 링크 생성..."
    bash setup_cudnn_links.sh
else
    echo "   cuDNN 이미 설정됨 - 스킵"
fi

# cuDNN 라이브러리 경로 설정
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu:/opt/oracle/instantclient_21_15:$LD_LIBRARY_PATH
echo "   LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
echo ""

# 1. PaddleOCR 클론 (없는 경우)
if [ ! -d "PaddleOCR" ]; then
    echo "1. PaddleOCR 레포지토리 클론 중..."
    git clone https://github.com/PaddlePaddle/PaddleOCR.git
    cd PaddleOCR
    git checkout release/2.7
    cd ..
else
    echo "1. PaddleOCR 이미 존재 - 스킵"
fi

# 2. 사전 학습 모델 다운로드
echo "2. PP-OCRv3 Detection 사전 학습 모델 다운로드 중..."
mkdir -p models/detection

if [ ! -f "models/detection/en_PP-OCRv3_det_distill_train.tar" ]; then
    wget -O models/detection/en_PP-OCRv3_det_distill_train.tar \
        https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_distill_train.tar

    cd models/detection
    tar -xf en_PP-OCRv3_det_distill_train.tar
    cd ../..
else
    echo "   사전 학습 모델 이미 존재 - 스킵"
fi

# 3. 학습 데이터 확인
echo "3. 학습 데이터 확인 중..."
echo "   Train images: $(ls data/train/images/ | wc -l)"
echo "   Val images: $(ls data/val/images/ | wc -l)"
echo "   Train list: $(wc -l < data/train_list.txt) lines"
echo "   Val list: $(wc -l < data/val_list.txt) lines"

# 4. GPU 확인
echo "4. GPU 확인 중..."
python3.9 -c "import paddle; print(f'PaddlePaddle GPU available: {paddle.is_compiled_with_cuda()}')"
python3.9 -c "import paddle; print(f'GPU count: {paddle.device.cuda.device_count()}')" || echo "GPU not available"

# 5. Detection 학습 시작
echo ""
echo "5. Detection 모델 학습 시작..."
echo "   설정 파일: configs/det/custom_web_detection.yml"
echo "   예상 소요 시간: 2-4시간 (RTX 5070 12GB 기준)"
echo "   에포크: 500 (Early stopping 적용)"
echo "   배치 크기: 8"
echo ""
echo "학습을 시작합니다..."
sleep 3

cd PaddleOCR

python3.9 tools/train.py \
    -c ../configs/det/custom_web_detection.yml \
    -o Global.use_gpu=True \
       Global.epoch_num=100 \
       Global.save_model_dir=../output/detection \
       Train.loader.batch_size_per_card=4 \
       Global.print_batch_step=10 \
       Global.save_epoch_step=10

echo ""
echo "✓ Detection 모델 학습 완료!"
echo ""
echo "학습 결과 위치: ${WORK_DIR}/output/detection"
echo "최고 성능 모델: ${WORK_DIR}/output/detection/best_accuracy.pdparams"
