#!/bin/bash
# Generated: 2025-10-02 21:35:00 KST
# PaddleOCR Detection Fine-tuning with 50 BBoxes - Optimized Training Script

set -e

CONFIG_FILE="/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/data_50bbox_optimized.yml"
OUTPUT_DIR="/home/pro301/paddleocr_training/output/data_50bbox_optimized"
LOG_DIR="/home/pro301/paddleocr_training/logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/50bbox_training_${TIMESTAMP}.log"

echo "====================================="
echo "PaddleOCR Detection Fine-tuning"
echo "====================================="
echo "BBox Count: 50 per image"
echo "Config: $CONFIG_FILE"
echo "Output: $OUTPUT_DIR"
echo "Log File: $LOG_FILE"
echo "====================================="
echo ""

# Create directories
mkdir -p "$OUTPUT_DIR"
mkdir -p "$LOG_DIR"

# Verify training data exists
if [ ! -f "/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train_list.txt" ]; then
    echo "❌ ERROR: Training list not found!"
    echo "Please run data conversion first:"
    echo "  python3.9 scripts/convert_database_to_paddleocr.py"
    exit 1
fi

TRAIN_COUNT=$(wc -l < /home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train_list.txt)
VAL_COUNT=$(wc -l < /home/pro301/git/en-zine/ocr_system/paddleocr_training/data/val_list.txt)

echo "Training data verification:"
echo "  Train samples: $TRAIN_COUNT"
echo "  Val samples: $VAL_COUNT"
echo ""

# Verify first image exists
FIRST_IMAGE=$(head -1 /home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train_list.txt | awk '{print $1}')
FIRST_IMAGE_PATH="/home/pro301/paddleocr_training/data_50bbox/${FIRST_IMAGE}"

if [ -f "$FIRST_IMAGE_PATH" ]; then
    echo "✅ First image verified: $FIRST_IMAGE_PATH"
else
    echo "❌ ERROR: First image not found: $FIRST_IMAGE_PATH"
    exit 1
fi

echo ""
echo "Starting training with 50 bboxes..."
echo "Optimizations applied:"
echo "  - Batch size: 2"
echo "  - Num workers: 2"
echo "  - Learning rate: 0.0001"
echo "  - Warmup epochs: 2"
echo "  - Total epochs: 50"
echo "  - GPU: RTX 5070 (CUDA 12.9)"
echo ""

# Start training
cd /home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR

python3.9 tools/train.py \
    -c "$CONFIG_FILE" \
    -o Global.use_gpu=True \
    -o Global.save_model_dir="$OUTPUT_DIR" \
    2>&1 | tee "$LOG_FILE"

echo ""
echo "====================================="
echo "Training completed!"
echo "Log file: $LOG_FILE"
echo "Model output: $OUTPUT_DIR"
echo "====================================="
