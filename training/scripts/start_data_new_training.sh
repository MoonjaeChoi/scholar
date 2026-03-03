#!/bin/bash
# Generated: 2025-10-02 12:38:00 KST
# Start PaddleOCR detection training for data_new dataset

set -e  # Exit on error

CONFIG_FILE="/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/data_new_training.yml"
OUTPUT_DIR="/home/pro301/paddleocr_training/output/data_new"
LOG_DIR="/home/pro301/paddleocr_training/logs"

# Create directories
mkdir -p "$OUTPUT_DIR"
mkdir -p "$LOG_DIR"

# Log file with timestamp
LOG_FILE="$LOG_DIR/training_$(date +%Y%m%d_%H%M%S).log"

echo "====================================="
echo "PaddleOCR Detection Training"
echo "====================================="
echo "Config: $CONFIG_FILE"
echo "Output: $OUTPUT_DIR"
echo "Log: $LOG_FILE"
echo "====================================="
echo ""

# Verify data files exist
echo "Verifying training data..."
TRAIN_LIST="/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train_list.txt"
VAL_LIST="/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/val_list.txt"

if [ ! -f "$TRAIN_LIST" ]; then
    echo "ERROR: Train list not found: $TRAIN_LIST"
    exit 1
fi

if [ ! -f "$VAL_LIST" ]; then
    echo "ERROR: Validation list not found: $VAL_LIST"
    exit 1
fi

TRAIN_COUNT=$(wc -l < "$TRAIN_LIST")
VAL_COUNT=$(wc -l < "$VAL_LIST")

echo "Train samples: $TRAIN_COUNT"
echo "Val samples: $VAL_COUNT"
echo ""

# Verify first image exists
DATA_DIR="/home/pro301/paddleocr_training/data_new"
FIRST_IMAGE_REL=$(head -1 "$TRAIN_LIST" | awk '{print $1}')
FIRST_IMAGE="$DATA_DIR/$FIRST_IMAGE_REL"
if [ ! -f "$FIRST_IMAGE" ]; then
    echo "ERROR: First training image not found: $FIRST_IMAGE"
    echo "Please check data paths in train_list.txt"
    exit 1
fi
echo "First image verified: $FIRST_IMAGE"
echo ""

# Start training
echo "Starting training..."
echo "Press Ctrl+C to stop training"
echo ""

cd /home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR

# Run training with Python 3.9
python3.9 tools/train.py \
    -c "$CONFIG_FILE" \
    -o Global.use_gpu=True \
    -o Global.save_model_dir="$OUTPUT_DIR" \
    2>&1 | tee "$LOG_FILE"

echo ""
echo "Training completed or stopped."
echo "Check logs at: $LOG_FILE"
echo "Model saved to: $OUTPUT_DIR"
