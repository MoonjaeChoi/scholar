#!/bin/bash

BASE_DIR="/home/pro301/git/en-zine/ocr_system/paddleocr_training/models"

echo "Downloading pretrained models..."

# 텍스트 검출 모델 (Detection)
cd ${BASE_DIR}/detection
wget -c https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar
tar -xf en_PP-OCRv3_det_infer.tar

wget -c https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_distill_train.tar
tar -xf en_PP-OCRv3_det_distill_train.tar

# 텍스트 인식 모델 (Recognition)
cd ${BASE_DIR}/recognition
wget -c https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_rec_infer.tar
tar -xf en_PP-OCRv3_rec_infer.tar

wget -c https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_rec_train.tar
tar -xf en_PP-OCRv3_rec_train.tar

echo "Pretrained models downloaded successfully!"