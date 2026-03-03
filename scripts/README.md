# Scholar Scripts

Generated: 2025-10-16 14:20:00 KST
Updated: 2025-10-16 14:45:00 KST (TARGET_ID 반정규화 반영)

이 폴더에는 Scholar 시스템 관련 유틸리티 스크립트가 포함되어 있습니다.

## 주요 스크립트

### query_database.py
Oracle 데이터베이스 조회 도구 (대화형 CLI)

**Quick Start:**
```bash
# 대화형 모드
python3 scholar/scripts/query_database.py

# 테이블 목록 조회
python3 scholar/scripts/query_database.py --list-tables

# 테이블 구조 확인
python3 scholar/scripts/query_database.py --table CRAWL_TARGETS

# 레코드 조회
python3 scholar/scripts/query_database.py --table CRAWL_TARGETS --pk 46
```

**상세 문서**: [docs/operation/059_database_query_tool_guide.md](../../docs/operation/059_database_query_tool_guide.md)

### import_pipeline_results.py
파이프라인 실행 결과 JSON 파일을 데이터베이스로 일괄 import

**Quick Start:**
```bash
# 전체 사이트 import
python3 scholar/scripts/import_pipeline_results.py

# 특정 사이트만 import
python3 scholar/scripts/import_pipeline_results.py --site "하이닥"

# 강제 재import
python3 scholar/scripts/import_pipeline_results.py --site "하이닥" --force
```

**상세 문서**: [docs/operation/060_pipeline_results_import_guide.md](../../docs/operation/060_pipeline_results_import_guide.md)

## 관련 문서

- [Scholar System Guide](../CLAUDE.md)
- [Database Schema](../../shared/database/schema/)
- [Database Integration Strategy](../../docs/operation/052_database_integration_strategy.md)

---

**Last Updated**: 2025-10-16 14:20:00 KST
