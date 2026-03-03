# PaddleOCR 훈련 데이터 저장 위치 변경 안내

## 📋 변경 사유

**저장 공간 부족 문제 해결**

- **루트 파티션** (`/dev/mapper/ol-root`): 50GB 중 48GB 사용 (**96% 사용**)
- **홈 파티션** (`/dev/mapper/ol-home`): 730GB 중 76GB 사용 (**11% 사용**)

PaddleOCR 훈련 데이터 및 모델을 저장할 공간이 부족하여, 홈 디렉토리로 데이터 저장 위치를 변경하였습니다.

---

## 🔄 경로 변경 내역

### 이전 경로 (사용 안 함)
```
/home/pro301/git/en-zine/data/paddleocr_data/
├── train/
│   ├── images/
│   └── labels/
└── val/
    ├── images/
    └── labels/
```

### 현재 경로 (권장)
```
/home/pro301/paddleocr_training/
├── data_100/          # 100개 샘플 (41MB)
├── data_full/         # 163개 샘플 (89MB)
├── data_test_10/      # 10개 샘플 (2.6MB)
├── data_test/         # 2개 샘플 (500KB)
├── models/            # 사전 학습 모델 (266MB)
├── output/            # 학습 결과 (29MB)
└── logs/              # 로그 파일
```

---

## 🚀 사용 방법

### 1. 데이터베이스에서 훈련 데이터 변환

```bash
# 컨테이너 접속
docker exec -it zine-paddleocr-training bash

# 홈 디렉토리로 데이터 변환
cd /home/pro301/git/en-zine/ocr_system/paddleocr_training
python3.9 scripts/convert_database_to_paddleocr.py \
  --output-dir /home/pro301/paddleocr_training/data_new \
  --max-samples 500
```

### 2. 훈련 설정 파일 사용

**홈 디렉토리 경로를 사용하는 설정 파일 예시:**
```yaml
# configs/det/home_directory.yml
Train:
  dataset:
    data_dir: /home/pro301/paddleocr_training/data_100/train/
    label_file_list:
      - /home/pro301/paddleocr_training/data_100/train_list.txt

Global:
  save_model_dir: /home/pro301/paddleocr_training/output/
  pretrained_model: /home/pro301/paddleocr_training/models/en_PP-OCRv3_det_distill_train/best_accuracy
```

### 3. 훈련 시작

```bash
# 홈 디렉토리 경로를 사용하는 설정으로 훈련
python3.9 PaddleOCR/tools/train.py -c configs/det/test_2_samples_home.yml
```

---

## 📊 데이터셋 정보

| 데이터셋 | 샘플 수 | 용량 | 위치 | 용도 |
|---------|--------|------|-----|-----|
| data_100 | 100 | 41MB | /home/pro301/paddleocr_training/data_100/ | 기본 학습 (권장) |
| data_full | 163 | 89MB | /home/pro301/paddleocr_training/data_full/ | 전체 데이터 학습 |
| data_test_10 | 10 | 2.6MB | /home/pro301/paddleocr_training/data_test_10/ | 빠른 테스트 |
| data_test | 2 | 500KB | /home/pro301/paddleocr_training/data_test/ | 최소 테스트 |

---

## ⚠️ 주의사항

### 1. 컨테이너 마운트 확인

홈 디렉토리가 컨테이너에 마운트되어 있어야 합니다:
```bash
docker inspect zine-paddleocr-training | grep -A 10 Mounts
```

### 2. 권한 문제

홈 디렉토리의 파일 권한을 확인하세요:
```bash
ls -la /home/pro301/paddleocr_training/
# 필요 시 권한 변경
sudo chown -R pro301:pro301 /home/pro301/paddleocr_training/
```

### 3. 컨테이너 내부 경로 사용 금지

**절대 사용하지 마세요:**
- `/home/pro301/git/en-zine/ocr_system/paddleocr_training/data_validated/`
- `/home/pro301/git/en-zine/ocr_system/paddleocr_training/data_safe/`
- `/home/pro301/git/en-zine/data/paddleocr_data/`

이 경로들은 루트 파티션에 위치하여 저장 공간이 부족합니다.

---

## 🔧 문제 해결

### 이미지 디코딩 오류 발생 시

**증상:**
```
cv2.error: OpenCV(4.10.0) :-1: error: (-5:Bad argument) in function 'imdecode'
```

**원인:** 잘못된 경로 사용

**해결:**
1. 설정 파일의 경로가 `/home/pro301/paddleocr_training/`으로 시작하는지 확인
2. 실제 이미지 파일이 존재하는지 확인:
   ```bash
   ls -la /home/pro301/paddleocr_training/data_100/train/images/ | head -5
   ```

### 디스크 공간 부족 시

**확인:**
```bash
df -h | grep -E "Filesystem|home|opt"
```

**정리:**
```bash
# 홈 디렉토리의 불필요한 파일 삭제
rm -rf /home/pro301/paddleocr_training/data_old/
```

---

## 📝 관련 문서

- [012_PaddleOCR_학습환경_구축.md](../../docs/operation/012_PaddleOCR_학습환경_구축.md)
- [CLAUDE.md](../../CLAUDE.md)

---

**작성일:** 2025-10-02
**작성자:** Claude Code
**버전:** 1.0
