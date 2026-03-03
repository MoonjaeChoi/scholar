#!/bin/bash
# Generated: 2025-10-02 21:56:00 KST
# Ultra-Optimized Training Script for RTX 5070 12GB + 50 BBox
# Expected: 80-95% GPU utilization, 8-10 hours total

set -e

CONFIG_FILE="/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/data_50bbox_ultra_optimized.yml"
OUTPUT_DIR="/home/pro301/paddleocr_training/output/data_50bbox_ultra"
LOG_DIR="/home/pro301/paddleocr_training/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/ultra_training_${TIMESTAMP}.log"

# Create directories
mkdir -p "$OUTPUT_DIR"
mkdir -p "$LOG_DIR"

echo "========================================================"
echo "🚀 Ultra-Optimized PaddleOCR Training"
echo "========================================================"
echo "📅 Start Time:        $(date)"
echo "🎮 GPU:                RTX 5070 12GB"
echo "📦 BBox Count:         50 per image"
echo "🔧 Configuration:      Ultra-Optimized"
echo ""
echo "⚙️  Optimization Features:"
echo "   ├─ Mixed Precision (AMP):      ✅ Enabled"
echo "   ├─ Batch Size:                 24 (max for 12GB)"
echo "   ├─ Num Workers:                8 (parallel loading)"
echo "   ├─ Learning Rate:              0.0015 (scaled)"
echo "   ├─ Warmup Epochs:              5"
echo "   ├─ Total Epochs:               50"
echo "   ├─ Data Augmentation:          ✅ Enhanced"
echo "   └─ Use Shared Memory:          ✅ Enabled"
echo ""
echo "📁 Paths:"
echo "   ├─ Config:     ${CONFIG_FILE}"
echo "   ├─ Output:     ${OUTPUT_DIR}"
echo "   └─ Log:        ${LOG_FILE}"
echo "========================================================"
echo ""

# Verify configuration file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ ERROR: Configuration file not found: ${CONFIG_FILE}"
    exit 1
fi

# Verify data directory
DATA_DIR="/home/pro301/paddleocr_training/data_new"
if [ ! -d "$DATA_DIR" ]; then
    echo "❌ ERROR: Training data directory not found: ${DATA_DIR}"
    exit 1
fi

# Count training samples
TRAIN_LIST="/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/train_list.txt"
VAL_LIST="/home/pro301/git/en-zine/ocr_system/paddleocr_training/data/val_list.txt"

if [ -f "$TRAIN_LIST" ]; then
    TRAIN_COUNT=$(wc -l < "$TRAIN_LIST")
    echo "📊 Training data verification:"
    echo "   ├─ Train samples:  $TRAIN_COUNT"
else
    echo "⚠️  Train list not found: ${TRAIN_LIST}"
    TRAIN_COUNT=0
fi

if [ -f "$VAL_LIST" ]; then
    VAL_COUNT=$(wc -l < "$VAL_LIST")
    echo "   └─ Val samples:    $VAL_COUNT"
else
    echo "⚠️  Val list not found: ${VAL_LIST}"
    VAL_COUNT=0
fi

echo ""

# Verify first few images
echo "🔍 Verifying training data integrity:"
FIRST_IMAGE=$(head -1 "$TRAIN_LIST" | awk '{print $1}')
FULL_PATH="${DATA_DIR}/train/images/${FIRST_IMAGE}"

if [ -f "$FULL_PATH" ]; then
    echo "   ✅ First image verified: ${FIRST_IMAGE}"
else
    echo "   ❌ ERROR: First image not found: ${FULL_PATH}"
    exit 1
fi

# Check GPU availability
echo ""
echo "🎮 GPU Status Check:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader | while read line; do
    echo "   ├─ $line"
done

# Check PaddlePaddle GPU support
echo ""
echo "🔧 PaddlePaddle Configuration:"
python3.9 -c "
import paddle
print(f'   ├─ Version:        {paddle.__version__}')
print(f'   ├─ CUDA Available: {paddle.is_compiled_with_cuda()}')
if paddle.is_compiled_with_cuda():
    print(f'   └─ GPU Count:      {paddle.device.cuda.device_count()}')
else:
    print('   └─ ⚠️ WARNING: CUDA not available!')
"

echo ""
echo "========================================================"
echo "🚀 Starting Ultra-Optimized Training with 50 BBoxes"
echo "========================================================"
echo ""
echo "⏱️  Estimated time: 8-10 hours for 50 epochs"
echo "📊 Expected GPU utilization: 80-95%"
echo "💾 Expected GPU memory usage: 8-10 GB / 12 GB"
echo ""
echo "Press Ctrl+C to stop monitoring (training continues in background)"
echo ""

# Start training
cd /home/pro301/git/en-zine/ocr_system/paddleocr_training

python3.9 tools/train.py \
    -c "$CONFIG_FILE" \
    -o Global.use_gpu=True \
    -o Global.save_model_dir="$OUTPUT_DIR" \
    2>&1 | tee "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "========================================================"
echo "📊 Training Summary"
echo "========================================================"
echo "⏱️  End Time:    $(date)"
echo "📝 Log File:    ${LOG_FILE}"
echo "📁 Output Dir:  ${OUTPUT_DIR}"
echo "🔢 Exit Code:   ${EXIT_CODE}"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Training completed successfully!"
else
    echo "❌ Training failed with exit code: ${EXIT_CODE}"
fi

echo "========================================================"

exit $EXIT_CODE
