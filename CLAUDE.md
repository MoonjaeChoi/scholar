# Generated: 2025-10-07 15:00:00 KST

# Scholar System - Development Guide

This file provides guidance for working with the Scholar System (학습 시스템).

## System Overview

**Scholar System** - "The Scholar" - 끊임없이 학습하며 지식을 축적하는 시스템

Scholar is the Python-based web crawling and PaddleOCR training system responsible for:
- Automated web crawling from 22 Korean platforms
- Ground truth data generation from HTML parsing
- PaddleOCR custom model training with continuous learning
- Quality-driven data processing and validation
- Oracle database integration (INSERT/UPDATE operations)

## Development Commands

### Starting Scholar System

```bash
# Start Scholar system only
docker compose -f ../infrastructure/docker-compose/docker-compose.scholar.yml up -d

# Enter Scholar container
docker exec -it scholar bash
cd /opt/scholar && source venv/bin/activate

# Run web crawling
python src/main.py

# Run PaddleOCR training
cd training
python train_model.py

# Install/update dependencies
pip install -r requirements.txt
```

### Legacy Development (Deprecated)
```bash
# Old structure (use new structure above instead)
docker exec -it zine-python-server bash
cd /opt/ocr_system/crawling && source venv_crawling/bin/activate
```

## Architecture

### Key Components

1. **Web Crawling** (22 Korean websites)
   - Naver Blog, Naver Post, Naver News
   - Tistory, Namuwiki
   - And 17 more Korean content platforms

2. **Selenium WebDriver**
   - Chrome/Firefox support for webpage screenshots
   - High-quality screenshot capture
   - Dynamic content handling

3. **HTML Parsing**
   - BeautifulSoup and scrapy for ground truth extraction
   - Text position and styling information extraction

4. **Quality Validation**
   - BoundingBoxValidator: Validates text bounding boxes
   - DataOptimizer: Deduplication and optimization
   - Visualizer: Quality assurance visualization tools

5. **PaddleOCR Training**
   - Custom model training with EWC continuous learning
   - Catastrophic forgetting prevention
   - Model versioning and optimization

6. **Oracle Integration**
   - Connection pooling for performance
   - Data storage (INSERT/UPDATE operations)
   - Training history tracking

7. **Advanced Logging**
   - loguru with comprehensive error handling
   - Structured logging for debugging

### Directory Structure

```
scholar/
├── src/                    # Web crawling source code
│   ├── crawler/            # WebCrawler, ScreenshotService
│   ├── database/           # Oracle DB integration
│   ├── data_processing/    # Quality validation
│   └── utils/              # Utility functions
├── training/               # PaddleOCR training pipeline
│   ├── configs/            # Training configurations
│   ├── tools/              # Training utilities
│   ├── scripts/            # OCR service, continuous learning
│   └── sql/                # Training-related DB scripts
├── config/                 # Scholar-specific configurations
├── tests/                  # Python unit tests
├── docker/                 # Scholar Docker Compose
├── k8s/                    # Scholar Kubernetes manifests
├── Dockerfile              # Scholar container image
├── requirements.txt        # Python dependencies
├── CLAUDE.md               # This file
└── README.md               # Scholar system documentation
```

## Key Dependencies

**Python Dependencies** (see requirements.txt):
- **OCR Engine**: `paddlepaddle==2.5.2`, `paddleocr>=2.7.0`
- **Web Crawling**: `selenium==4.15.2`, `beautifulsoup4==4.12.2`, `scrapy==2.11.0`
- **Database**: `cx-Oracle==8.3.0` for Oracle connectivity
- **Data Processing**: `pandas==2.1.4`, `numpy==1.25.2`, `pydantic==2.5.0`
- **Image Processing**: `Pillow==10.1.0`, `opencv-python-headless==4.8.1.78`
- **Utilities**: `loguru==0.7.2`, `python-dotenv==1.0.0`, `webdriver-manager==4.0.1`

## Database Role

**Scholar writes data to Oracle Database:**
- **INSERT**: New crawled web pages and training data
- **UPDATE**: Training results, model versions, quality metrics
- **Tables Used**:
  - `WEB_CAPTURE_DATA`: Screenshot and HTML data
  - `TEXT_BOUNDING_BOXES`: Text position information
  - `OCR_MODEL_VERSIONS`: Model versioning
  - `TRAINING_HISTORY`: Training session records

**Database Configuration:**
```bash
ORACLE_HOST=zine-oracle-xe
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=XEPDB1
ORACLE_USERNAME=ocr_admin
ORACLE_PASSWORD=admin_password
```

## Testing

### Data Quality Validation
```bash
# In Scholar container
docker exec -it scholar bash
cd /opt/scholar && source venv/bin/activate

# Run quality tests
python scripts/test_data_quality.py

# Validate crawling results
python tests/test_crawler.py
```

### Python Unit Tests
```bash
# In Scholar container
cd /opt/scholar && source venv/bin/activate
python -m pytest tests/ -v
```

## Code Quality Standards

- **Python PEP 8**: Follow Python coding standards
- **Type Hints**: Use type hints for better code documentation
- **Error Handling**: Implement comprehensive error handling with loguru
- **Data Validation**: Use pydantic for data structure validation
- **Testing**: Write unit tests for new functionality

## Important Files

- [src/main.py](src/main.py): Main crawling entry point
- [training/train_model.py](training/train_model.py): PaddleOCR model training
- [src/crawler/web_crawler.py](src/crawler/web_crawler.py): Web crawling implementation
- [src/database/connection.py](src/database/connection.py): Oracle connection management
- [config/korean_blog_sites.json](config/korean_blog_sites.json): Crawling targets
- [README.md](README.md): Comprehensive Scholar documentation

## Data Flow

```
Web Pages → Selenium Screenshot → HTML Parser
     ↓              ↓                   ↓
Screenshot      Bounding Boxes    Ground Truth
     ↓              ↓                   ↓
Quality Validation → Oracle Database (INSERT/UPDATE)
     ↓
PaddleOCR Training → Trained Models → Oracle Database
     ↓
Shared Models (Read-only for Artisan)
```

## Environment Variables

Scholar-specific environment variables:
```bash
# Python Environment
PYTHONPATH=/opt/scholar
DATA_DIR=/opt/scholar/data
LOG_LEVEL=INFO
CRAWLING_INTERVAL=3600  # seconds

# ChromeDriver
CHROME_DRIVER_PATH=/usr/local/bin/chromedriver
HEADLESS_MODE=true

# Training
MODEL_VERSION=v1.0.0
TRAINING_EPOCHS=100
BATCH_SIZE=32
```

## Deployment

### Docker Deployment
```bash
# Scholar-only deployment
cd /Users/memmem/git/en-zine
docker compose -f infrastructure/docker-compose/docker-compose.scholar.yml up -d

# Check logs
docker logs -f scholar

# Stop
docker compose -f infrastructure/docker-compose/docker-compose.scholar.yml down
```

### Kubernetes Deployment
```bash
# Deploy Scholar to Kubernetes
kubectl apply -f k8s/

# Check status
kubectl get pods -l app=scholar

# View logs
kubectl logs -f deployment/scholar
```

## Common Tasks

### Adding New Crawling Target
1. Edit `../shared/config/korean_blog_sites.json`
2. Add website configuration (URL patterns, selectors)
3. Test crawling with single page
4. Validate data quality
5. Deploy to production

### Updating PaddleOCR Model
1. Prepare training data in Oracle database
2. Configure training parameters in `training/configs/`
3. Run training: `python training/train_model.py`
4. Evaluate model performance
5. Update model version in database
6. Deploy new model to shared storage

### Monitoring Crawling Status
```bash
# Check crawling logs
docker exec -it scholar bash
tail -f /opt/scholar/logs/crawling.log

# Check database records
sqlplus ocr_admin/admin_password@XEPDB1
SELECT COUNT(*) FROM WEB_CAPTURE_DATA WHERE created_at > SYSDATE - 1;
```

## Troubleshooting

### ChromeDriver Issues
```bash
# Update ChromeDriver
pip install --upgrade webdriver-manager

# Test ChromeDriver
python -c "from selenium import webdriver; driver = webdriver.Chrome(); driver.quit()"
```

### Oracle Connection Issues
- Check Oracle service status: `lsnrctl status`
- Verify connection string in `.env`
- Check firewall rules
- Review connection pool settings

### Training Performance Issues
- Monitor GPU usage: `nvidia-smi`
- Check training logs for errors
- Validate training data quality
- Adjust batch size and learning rate

## Related Documentation

- [Main CLAUDE.md](../CLAUDE.md): Overall project guide
- [Artisan CLAUDE.md](../artisan/CLAUDE.md): Artisan system guide
- [README.md](README.md): Scholar system overview
- [Shared Resources](../shared/README.md): Database schemas and models
- [Infrastructure](../infrastructure/README.md): Deployment guide
