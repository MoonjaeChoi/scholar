#!/bin/bash
# Generated: 2025-10-02 21:15:00 KST
# PaddleOCR Detection Fine-tuning with Pre-trained Model

set -e

CONFIG_FILE="/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/data_new_pretrained.yml"
OUTPUT_DIR="/home/pro301/paddleocr_training/output/data_new_pretrained"
LOG_DIR="/home/pro301/paddleocr_training/logs"
PRETRAINED_MODEL="/home/pro301/git/en-zine/ocr_system/paddleocr_training/pretrained_models/ch_PP-OCRv3_det_distill_train"

echo "====================================="
echo "PaddleOCR Detection Fine-tuning"
echo "====================================="
echo "Config: $CONFIG_FILE"
echo "Output: $OUTPUT_DIR"
echo "Pre-trained Model: $PRETRAINED_MODEL"
echo "====================================="
echo

# Create directories
mkdir -p "$OUTPUT_DIR" "$LOG_DIR"

# Download pre-trained model if not exists
if [ ! -d "$PRETRAINED_MODEL" ]; then
    echo "Downloading PP-OCRv3 Detection pre-trained model..."
    mkdir -p /home/pro301/git/en-zine/ocr_system/paddleocr_training/pretrained_models
    cd /home/pro301/git/en-zine/ocr_system/paddleocr_training/pretrained_models

    wget https://paddleocr.bj.bcebos.com/PP-OCRv3/chinese/ch_PP-OCRv3_det_distill_train.tar
    tar -xf ch_PP-OCRv3_det_distill_train.tar

    echo "✅ Pre-trained model downloaded successfully!"
    ls -lh ch_PP-OCRv3_det_distill_train/
    echo
fi

# Verify pre-trained model exists
if [ ! -f "${PRETRAINED_MODEL}/best_accuracy.pdparams" ]; then
    echo "❌ ERROR: Pre-trained model not found: ${PRETRAINED_MODEL}/best_accuracy.pdparams"
    exit 1
fi

echo "✅ Pre-trained model found: ${PRETRAINED_MODEL}/best_accuracy.pdparams"
echo

# Verify training data
TRAIN_LIST="/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train_list.txt"
VAL_LIST="/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/val_list.txt"

if [ ! -f "$TRAIN_LIST" ]; then
    echo "❌ ERROR: Training list not found: $TRAIN_LIST"
    exit 1
fi

if [ ! -f "$VAL_LIST" ]; then
    echo "❌ ERROR: Validation list not found: $VAL_LIST"
    exit 1
fi

TRAIN_COUNT=$(wc -l < "$TRAIN_LIST")
VAL_COUNT=$(wc -l < "$VAL_LIST")

echo "Verifying training data..."
echo "Train samples: $TRAIN_COUNT"
echo "Val samples: $VAL_COUNT"
echo

# Verify first image
DATA_DIR="/home/pro301/paddleocr_training/data_new"
FIRST_IMAGE_REL=$(head -1 "$TRAIN_LIST" | awk '{print $1}')
FIRST_IMAGE="$DATA_DIR/$FIRST_IMAGE_REL"

if [ ! -f "$FIRST_IMAGE" ]; then
    echo "❌ ERROR: First training image not found: $FIRST_IMAGE"
    exit 1
fi

echo "✅ First image verified: $FIRST_IMAGE"
echo

# Log file with timestamp
LOG_FILE="$LOG_DIR/pretrained_training_$(date +%Y%m%d_%H%M%S).log"

echo "Starting fine-tuning with pre-trained model..."
echo "Log file: $LOG_FILE"
echo "Press Ctrl+C to stop training"
echo

# Start training with pre-trained model
cd /home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR

python3.9 tools/train.py \
    -c "$CONFIG_FILE" \
    -o Global.pretrained_model="${PRETRAINED_MODEL}/best_accuracy" \
    -o Global.use_gpu=True \
    -o Global.save_model_dir="$OUTPUT_DIR" \
    2>&1 | tee "$LOG_FILE"

echo
echo "====================================="
echo "Fine-tuning completed!"
echo "Output: $OUTPUT_DIR"
echo "Log: $LOG_FILE"
echo "====================================="
