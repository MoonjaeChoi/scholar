#!/bin/bash
# Generated: 2025-10-02 22:58:00 KST
# Continuous Training System Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/ocr_system/paddleocr_training/config/continuous_training_config.json"
MAIN_SCRIPT="$PROJECT_ROOT/ocr_system/paddleocr_training/scripts/main_continuous_training.py"
LOG_DIR="/home/pro301/paddleocr_training/logs"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Continuous Training System - 무한 학습 자동화         ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Check prerequisites
echo -e "${YELLOW}[1/6] Checking prerequisites...${NC}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}✗ Configuration file not found: $CONFIG_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Configuration file found${NC}"

if [ ! -f "$MAIN_SCRIPT" ]; then
    echo -e "${RED}✗ Main script not found: $MAIN_SCRIPT${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Main script found${NC}"

# Check Python
if ! command -v python3.9 &> /dev/null; then
    echo -e "${RED}✗ Python 3.9 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3.9 available${NC}"

# Step 2: Create log directory
echo -e "\n${YELLOW}[2/6] Creating log directory...${NC}"
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✓ Log directory ready: $LOG_DIR${NC}"

# Step 3: Verify database connection
echo -e "\n${YELLOW}[3/6] Verifying database connection...${NC}"
python3.9 << 'PYEOF'
import cx_Oracle
import json
import sys

try:
    with open('/home/pro301/git/en-zine/ocr_system/paddleocr_training/config/continuous_training_config.json', 'r') as f:
        config = json.load(f)

    db_config = config['database']
    dsn = cx_Oracle.makedsn(
        db_config['host'],
        db_config['port'],
        service_name=db_config['service_name']
    )

    connection = cx_Oracle.connect(
        user=db_config['username'],
        password=db_config['password'],
        dsn=dsn
    )

    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM WEB_CAPTURE_DATA WHERE deleted_at IS NULL")
    count = cursor.fetchone()[0]

    print(f"✓ Database connected successfully")
    print(f"  Available data samples: {count}")

    connection.close()
    sys.exit(0)

except Exception as e:
    print(f"✗ Database connection failed: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF

if [ $? -ne 0 ]; then
    echo -e "${RED}Database connection failed. Please check configuration.${NC}"
    exit 1
fi

# Step 4: Check required database tables
echo -e "\n${YELLOW}[4/6] Checking required database tables...${NC}"
python3.9 << 'PYEOF'
import cx_Oracle
import json
import sys

try:
    with open('/home/pro301/git/en-zine/ocr_system/paddleocr_training/config/continuous_training_config.json', 'r') as f:
        config = json.load(f)

    db_config = config['database']
    dsn = cx_Oracle.makedsn(
        db_config['host'],
        db_config['port'],
        service_name=db_config['service_name']
    )

    connection = cx_Oracle.connect(
        user=db_config['username'],
        password=db_config['password'],
        dsn=dsn
    )

    cursor = connection.cursor()

    required_tables = [
        'DATA_QUALITY_METRICS',
        'TRAINING_HISTORY',
        'TRAINING_ITERATION_RESULTS'
    ]

    missing_tables = []
    for table_name in required_tables:
        cursor.execute(f"SELECT COUNT(*) FROM user_tables WHERE table_name = '{table_name}'")
        if cursor.fetchone()[0] == 0:
            missing_tables.append(table_name)

    connection.close()

    if missing_tables:
        print(f"⚠ Missing tables: {', '.join(missing_tables)}")
        print("Please run: ocr_system/paddleocr_training/sql/create_continuous_training_tables.sql")
        sys.exit(1)
    else:
        print("✓ All required tables exist")
        sys.exit(0)

except Exception as e:
    print(f"✗ Table check failed: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF

if [ $? -ne 0 ]; then
    echo -e "${RED}Required tables are missing. Please create them first.${NC}"
    exit 1
fi

# Step 5: Display configuration summary
echo -e "\n${YELLOW}[5/6] Configuration Summary${NC}"
python3.9 << 'PYEOF'
import json

with open('/home/pro301/git/en-zine/ocr_system/paddleocr_training/config/continuous_training_config.json', 'r') as f:
    config = json.load(f)

print(f"""
Training Settings:
  • Epochs per iteration: {config['training']['epochs_per_iteration']}
  • Training batch size: {config['training']['training_batch_size']}
  • Min bbox count: {config['training']['min_bbox_count']}
  • Iteration interval: {config['training']['iteration_interval_seconds']}s

Quality Settings:
  • Min quality score: {config['quality']['min_quality_score']}
  • Max training failures: {config['quality']['max_training_failures']}

Target Metrics:
  • Precision: {config['goals']['target_precision']:.2%}
  • Recall: {config['goals']['target_recall']:.2%}
  • Hmean: {config['goals']['target_hmean']:.2%}
  • FPS: {config['goals']['target_fps']}

Limits:
  • Max iterations: {config['limits']['max_total_iterations']}
  • Max training hours: {config['limits']['max_total_hours']} ({config['limits']['max_total_hours']/24:.1f} days)
""")
PYEOF

# Step 6: Start continuous training
echo -e "${YELLOW}[6/6] Starting Continuous Training Loop...${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}\n"

# Run the main training script
cd "$SCRIPT_DIR"
python3.9 "$MAIN_SCRIPT" --config "$CONFIG_FILE" 2>&1 | tee "$LOG_DIR/continuous_training_$(date +%Y%m%d_%H%M%S).log"

EXIT_CODE=$?

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}║  Continuous Training Completed Successfully                  ║${NC}"
else
    echo -e "${RED}║  Continuous Training Terminated with Errors                  ║${NC}"
fi
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"

exit $EXIT_CODE
