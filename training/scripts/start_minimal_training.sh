#!/bin/bash
# Generated: 2025-10-02 17:39:00 KST
# Start PaddleOCR Detection Training with MINIMAL AUGMENTATION
# Purpose: Train with minimal data augmentation to avoid memory overflow

set -e

echo "====================================="
echo "PaddleOCR Detection Training - MINIMAL"
echo "====================================="

CONFIG_FILE="/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/data_new_training_minimal.yml"
OUTPUT_DIR="/home/pro301/paddleocr_training/output/data_new_minimal"
LOG_DIR="/home/pro301/paddleocr_training/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/training_minimal_${TIMESTAMP}.log"

echo "Config: ${CONFIG_FILE}"
echo "Output: ${OUTPUT_DIR}"
echo "Log: ${LOG_FILE}"
echo "====================================="
echo ""

# Create directories
mkdir -p "${OUTPUT_DIR}"
mkdir -p "${LOG_DIR}"

# Verify training data
echo "Verifying training data..."
TRAIN_LIST="/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train_list.txt"
VAL_LIST="/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/val_list.txt"

if [ ! -f "${TRAIN_LIST}" ]; then
    echo "ERROR: Training list not found: ${TRAIN_LIST}"
    exit 1
fi

if [ ! -f "${VAL_LIST}" ]; then
    echo "ERROR: Validation list not found: ${VAL_LIST}"
    exit 1
fi

TRAIN_COUNT=$(wc -l < "${TRAIN_LIST}")
VAL_COUNT=$(wc -l < "${VAL_LIST}")

echo "Train samples: ${TRAIN_COUNT}"
echo "Val samples: ${VAL_COUNT}"
echo ""

# Verify first image exists
DATA_DIR="/home/pro301/paddleocr_training/data_new"
FIRST_IMAGE_REL=$(head -1 "${TRAIN_LIST}" | awk '{print $1}')
FIRST_IMAGE="${DATA_DIR}/${FIRST_IMAGE_REL}"

if [ ! -f "${FIRST_IMAGE}" ]; then
    echo "ERROR: First training image not found: ${FIRST_IMAGE}"
    echo "Please check data paths in train_list.txt"
    exit 1
fi

echo "First image verified: ${FIRST_IMAGE}"
echo ""

# Start training
echo "Starting training with MINIMAL augmentation..."
echo "Press Ctrl+C to stop training"
echo ""

cd /home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR

python3.9 tools/train.py \
    -c "${CONFIG_FILE}" \
    2>&1 | tee "${LOG_FILE}"

echo ""
echo "Training completed or stopped."
echo "Check logs at: ${LOG_FILE}"
echo "Model saved to: ${OUTPUT_DIR}"
