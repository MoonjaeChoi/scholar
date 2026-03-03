#!/bin/bash
# Generated: 2025-10-01 07:38:00 KST
# PaddleOCR Training Environment Build and Run Script

set -e

echo "=== PaddleOCR Training Environment Setup ==="
echo ""

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 작업 디렉토리
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# /home/pro301/git/en-zine/ocr_system/paddleocr_training -> /home/pro301/git/en-zine
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DOCKER_DIR="$PROJECT_ROOT/ocr_system/docker"

echo -e "${BLUE}Project Root: ${NC}$PROJECT_ROOT"
echo -e "${BLUE}Docker Config: ${NC}$DOCKER_DIR"
echo ""

# Step 1: 네트워크 생성 (이미 있으면 무시)
echo -e "${YELLOW}[1/5]${NC} Creating Docker network..."
docker network create zine-network 2>/dev/null || echo "  Network already exists"
echo ""

# Step 2: Oracle Database 시작 (이미 실행 중이면 무시)
echo -e "${YELLOW}[2/5]${NC} Starting Oracle Database..."
cd "$DOCKER_DIR"
if ! docker ps | grep -q oracle-xe; then
    docker compose -f docker-compose.production.yml up -d oracle-xe
    echo "  Waiting for Oracle to be healthy..."
    sleep 10
else
    echo "  Oracle already running"
fi
echo ""

# Step 3: 데이터 디렉토리 생성
echo -e "${YELLOW}[3/5]${NC} Creating data directories..."
# ⚠️ 저장 공간 이슈로 인해 홈 디렉토리 사용
# 이전: /home/pro301/git/en-zine/data (루트 파티션 96% 사용)
# 현재: /home/pro301/paddleocr_training (홈 파티션 11% 사용)
mkdir -p /home/pro301/paddleocr_training/data_new/train/images
mkdir -p /home/pro301/paddleocr_training/data_new/val/images
mkdir -p /home/pro301/paddleocr_training/models
mkdir -p /home/pro301/paddleocr_training/output
mkdir -p "$PROJECT_ROOT/logs"
echo -e "${GREEN}  ✓ Directories created in /home/pro301/paddleocr_training/${NC}"
echo ""

# Step 4: Docker 이미지 빌드
echo -e "${YELLOW}[4/5]${NC} Building PaddleOCR Docker image..."
cd "$DOCKER_DIR"
docker compose -f docker-compose.paddleocr.yml build
echo -e "${GREEN}  ✓ Image built successfully${NC}"
echo ""

# Step 5: 컨테이너 시작
echo -e "${YELLOW}[5/5]${NC} Starting PaddleOCR container..."
docker compose -f docker-compose.paddleocr.yml up -d
echo -e "${GREEN}  ✓ Container started${NC}"
echo ""

# 상태 확인
echo -e "${BLUE}=== Container Status ===${NC}"
docker ps | grep -E "CONTAINER|paddleocr|oracle"
echo ""

# 헬스체크 대기
echo -e "${YELLOW}Waiting for container to be healthy...${NC}"
sleep 5

if docker ps | grep -q "zine-paddleocr-training.*healthy"; then
    echo -e "${GREEN}✓ PaddleOCR container is healthy!${NC}"
else
    echo -e "${YELLOW}⚠ Container started but health check pending...${NC}"
fi
echo ""

# 다음 단계 안내
echo -e "${BLUE}=== Next Steps ===${NC}"
echo ""
echo -e "⚠️  ${YELLOW}Note: Training data is stored in /home/pro301/paddleocr_training/${NC}"
echo ""
echo -e "1. Enter the container:"
echo -e "   ${GREEN}docker exec -it zine-paddleocr-training bash${NC}"
echo ""
echo -e "2. Convert database to training data (with custom path):"
echo -e "   ${GREEN}python3.9 scripts/convert_database_to_paddleocr.py --output-dir /home/pro301/paddleocr_training/data_new${NC}"
echo ""
echo -e "3. Download pretrained models:"
echo -e "   ${GREEN}./download_pretrained_models.sh${NC}"
echo ""
echo -e "4. Start training (use config with home directory paths):"
echo -e "   ${GREEN}python3.9 PaddleOCR/tools/train.py -c configs/det/test_2_samples_home.yml${NC}"
echo ""
echo -e "5. View logs:"
echo -e "   ${GREEN}docker logs -f zine-paddleocr-training${NC}"
echo ""
echo -e "${GREEN}Setup completed successfully!${NC}"
echo -e "${YELLOW}Data location: /home/pro301/paddleocr_training/${NC}"
