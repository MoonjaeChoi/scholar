# IT동아 크롤링 실행 가이드

**생성일시**: 2025-10-16 10:05:00 KST
**대상 서버**: 192.168.75.194 (Oracle Linux 9)

---

## 📋 사전 준비

### 1. 필요한 파일
```
scholar/scripts/
├── full_crawl_it_donga.py          # 크롤링 메인 스크립트
├── run_it_donga_crawling.sh        # 실행 스크립트
└── article_urls.json                # 42개 기사 URL 목록
```

### 2. 서버 환경 요구사항
- **OS**: Oracle Linux 9
- **Python**: 3.9+
- **Chrome/Chromium**: 설치 필요
- **ChromeDriver**: 설치 필요
- **Python 패키지**: selenium, loguru

---

## 🚀 서버 배포 및 실행

### Step 1: 서버 접속
```bash
ssh pro301@192.168.75.194
# 비밀번호 입력
```

### Step 2: ChromeDriver 설치 (최초 1회)
```bash
# Chromium 및 ChromeDriver 설치
sudo yum install -y chromium chromium-headless chromedriver

# 설치 확인
chromedriver --version
```

### Step 3: Python 패키지 설치 (최초 1회)
```bash
cd /home/pro301/git/en-zine/scholar

# 가상환경 활성화 (존재하는 경우)
source venv/bin/activate

# 필요한 패키지 설치
pip install selenium==4.15.2 loguru webdriver-manager

# 설치 확인
python3 -c "import selenium; from loguru import logger; print('OK')"
```

### Step 4: 파일 전송 (로컬에서 실행)
```bash
# 로컬 머신에서 실행
cd /Users/memmem/git/en-zine

# 크롤링 스크립트 전송
scp scholar/scripts/full_crawl_it_donga.py pro301@192.168.75.194:/home/pro301/git/en-zine/scholar/scripts/

# 실행 스크립트 전송
scp scholar/scripts/run_it_donga_crawling.sh pro301@192.168.75.194:/home/pro301/git/en-zine/scholar/scripts/

# URL 목록 전송
scp results/it_donga_57/article_urls.json pro301@192.168.75.194:/home/pro301/git/en-zine/scholar/scripts/

# 실행 권한 부여 (서버에서)
ssh pro301@192.168.75.194 'chmod +x /home/pro301/git/en-zine/scholar/scripts/run_it_donga_crawling.sh'
```

### Step 5: 크롤링 실행 (서버에서)
```bash
# 서버 접속
ssh pro301@192.168.75.194

# 디렉토리 이동
cd /home/pro301/git/en-zine/scholar/scripts

# 실행
./run_it_donga_crawling.sh article_urls.json
```

---

## 📊 실행 결과 확인

### 크롤링 완료 후
```bash
# 결과 디렉토리 확인 (예시)
ls -lh /tmp/it_donga_crawl_20251016_100500/screenshots/

# 스크린샷 개수 확인
ls -1 /tmp/it_donga_crawl_*/screenshots/*.png | wc -l

# 용량 확인
du -sh /tmp/it_donga_crawl_*/screenshots/

# 결과 JSON 확인
cat /tmp/it_donga_crawl_*/full_crawl_results.json | python3 -m json.tool | head -50
```

### 데이터베이스 확인
```bash
# Oracle 접속
sqlplus ocr_admin/admin_password@XEPDB1

# 저장된 데이터 확인
SELECT COUNT(*) FROM WEB_CAPTURE_DATA WHERE SOURCE_TYPE = 'IT동아';
SELECT TITLE, CAPTURED_AT FROM WEB_CAPTURE_DATA WHERE SOURCE_TYPE = 'IT동아' ORDER BY CAPTURED_AT DESC;
```

---

## 🔧 트러블슈팅

### 1. ChromeDriver 오류
```bash
# ChromeDriver 재설치
sudo yum remove -y chromedriver
sudo yum install -y chromedriver

# 수동 다운로드 (필요시)
wget https://chromedriver.storage.googleapis.com/120.0.6099.109/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/bin/
sudo chmod +x /usr/bin/chromedriver
```

### 2. 메모리 부족 오류
```bash
# 크롤링 개수 제한
python3 full_crawl_it_donga.py --urls article_urls.json --output /tmp/output --max 20
```

### 3. 데이터베이스 연결 오류
```bash
# 데이터베이스 저장 비활성화
python3 full_crawl_it_donga.py --urls article_urls.json --output /tmp/output --no-db
```

### 4. Selenium 오류
```bash
# 로그 확인
tail -f /tmp/it_donga_crawl_*/crawl.log

# Chrome 버전 확인
chromium-browser --version
chromedriver --version
```

---

## 📈 예상 소요 시간 및 리소스

### 42개 기사 기준
- **소요 시간**: 약 3-5분 (기사당 4-6초)
- **스크린샷 용량**: 약 100-150 MB
- **HTML 용량**: 약 10-15 MB
- **메모리 사용**: 약 500 MB
- **디스크 공간**: 약 200 MB

---

## 🎯 다음 단계 (크롤링 완료 후)

### 1. 학습 데이터 검증
```bash
# 스크린샷 품질 확인 (샘플)
ls -lh /tmp/it_donga_crawl_*/screenshots/*.png | head -5

# 데이터베이스 레코드 확인
sqlplus ocr_admin/admin_password@XEPDB1 <<EOF
SELECT COUNT(*), AVG(DBMS_LOB.GETLENGTH(IMAGE_DATA))/1024 as AVG_SIZE_KB
FROM WEB_CAPTURE_DATA
WHERE SOURCE_TYPE = 'IT동아';
EOF
```

### 2. PaddleOCR 학습 실행
```bash
cd /home/pro301/git/en-zine/scholar/training

# 학습 실행
python continuous_trainer.py --source it_donga --epochs 10

# 또는 Docker에서
docker exec -it scholar bash -c "cd /opt/scholar/training && python continuous_trainer.py"
```

---

## 💡 수동 실행 방법 (단계별)

### Python 직접 실행
```bash
cd /home/pro301/git/en-zine/scholar/scripts

python3 full_crawl_it_donga.py \
    --urls article_urls.json \
    --output /tmp/my_crawl_output \
    --max 42
```

### 백그라운드 실행
```bash
nohup ./run_it_donga_crawling.sh article_urls.json > crawl.log 2>&1 &

# 진행 상황 확인
tail -f crawl.log

# 프로세스 확인
ps aux | grep full_crawl
```

---

## 📞 문제 발생 시

**일반적인 문제**:
1. ChromeDriver 버전 불일치 → ChromeDriver 재설치
2. 메모리 부족 → `--max` 옵션으로 개수 제한
3. 네트워크 오류 → 재시도 또는 딜레이 증가

**로그 확인**:
```bash
# Python 스크립트 로그
cat /tmp/it_donga_crawl_*/full_crawl_results.json

# 시스템 로그
dmesg | tail -50
```

---

**작성자**: Claude Code (Scholar System Agent)
**최종 업데이트**: 2025-10-16 10:05:00 KST
