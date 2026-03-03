#!/bin/bash
# Generated: 2025-10-01 11:20:00 KST
# cuDNN 라이브러리 심볼릭 링크 생성 스크립트
# PaddlePaddle이 /usr/local/cuda/lib64/에서 cuDNN을 찾도록 설정

set -e

echo "=== cuDNN 심볼릭 링크 설정 시작 ==="

# cuDNN 라이브러리 위치 확인
CUDNN_SOURCE_DIR="/usr/lib/x86_64-linux-gnu"
CUDA_LIB_DIR="/usr/local/cuda/lib64"

echo "✓ cuDNN 소스 디렉토리: $CUDNN_SOURCE_DIR"
echo "✓ CUDA 라이브러리 디렉토리: $CUDA_LIB_DIR"

# cuDNN 라이브러리 파일 확인
if [ -f "$CUDNN_SOURCE_DIR/libcudnn.so.8" ]; then
    echo "✓ libcudnn.so.8 발견: $(ls -lh $CUDNN_SOURCE_DIR/libcudnn.so.8*)"
else
    echo "✗ libcudnn.so.8 파일을 찾을 수 없습니다!"
    exit 1
fi

# CUDA lib64 디렉토리 확인 및 생성
if [ ! -d "$CUDA_LIB_DIR" ]; then
    echo "! CUDA lib64 디렉토리가 없습니다. 생성합니다..."
    mkdir -p "$CUDA_LIB_DIR"
fi

# 기존 심볼릭 링크 제거
echo "기존 링크 정리..."
rm -f "$CUDA_LIB_DIR/libcudnn.so"*

# 심볼릭 링크 생성
echo "심볼릭 링크 생성 중..."
ln -sf "$CUDNN_SOURCE_DIR/libcudnn.so.8.9.6" "$CUDA_LIB_DIR/libcudnn.so.8.9.6"
ln -sf "$CUDNN_SOURCE_DIR/libcudnn.so.8" "$CUDA_LIB_DIR/libcudnn.so.8"
ln -sf "$CUDNN_SOURCE_DIR/libcudnn.so" "$CUDA_LIB_DIR/libcudnn.so"

# 추가 cuDNN 라이브러리 링크
for lib in libcudnn_ops_infer.so.8 libcudnn_cnn_infer.so.8 libcudnn_adv_infer.so.8; do
    if [ -f "$CUDNN_SOURCE_DIR/$lib" ]; then
        echo "링크 생성: $lib"
        ln -sf "$CUDNN_SOURCE_DIR/$lib" "$CUDA_LIB_DIR/$lib"
    fi
done

# 링크 확인
echo ""
echo "=== 생성된 cuDNN 심볼릭 링크 ==="
ls -lh "$CUDA_LIB_DIR/libcudnn"*

# ldconfig 업데이트 (필요시)
if command -v ldconfig &> /dev/null; then
    echo ""
    echo "ldconfig 캐시 업데이트 중..."
    ldconfig
fi

echo ""
echo "✓ cuDNN 심볼릭 링크 설정 완료!"
echo ""
echo "다음 명령어로 확인:"
echo "  ls -la /usr/local/cuda/lib64/libcudnn*"
echo "  ldd /usr/local/cuda/lib64/libcudnn.so"
