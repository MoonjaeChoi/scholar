#!/usr/bin/env python3
# Generated: 2025-10-14 17:55:00 KST
"""
크롤링 관리 데이터베이스 매니저
7개의 CRAWL_ 테이블에 대한 Python 인터페이스 제공
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
import os
from loguru import logger

# 환경 변수로 Oracle 라이브러리 선택
# 로컬 개발: USE_PYTHON_ORACLEDB=true (python-oracledb Thin Mode)
# 서버 프로덕션: USE_PYTHON_ORACLEDB=false 또는 미설정 (cx_Oracle)
USE_PYTHON_ORACLEDB = os.getenv('USE_PYTHON_ORACLEDB', 'false').lower() == 'true'

if USE_PYTHON_ORACLEDB:
    import oracledb as oracle_lib
    logger.info("✅ CrawlDatabaseManager: Using python-oracledb (Thin Mode)")
else:
    import cx_Oracle as oracle_lib
    logger.info("✅ CrawlDatabaseManager: Using cx_Oracle")


class CrawlDatabaseManager:
    """크롤링 관리 데이터베이스 매니저"""

    def __init__(self):
        """데이터베이스 연결 초기화"""
        self.host = os.getenv('DB_HOST', '192.168.75.194')
        self.port = os.getenv('DB_PORT', '1521')
        self.service_name = os.getenv('DB_SERVICE_NAME', 'XEPDB1')
        self.username = os.getenv('DB_USERNAME', 'ocr_admin')
        self.password = os.getenv('DB_PASSWORD', 'admin_password')

        # DSN 생성 (라이브러리별 처리)
        if USE_PYTHON_ORACLEDB:
            # python-oracledb: 간단한 DSN 형식
            self.dsn = f"{self.host}:{self.port}/{self.service_name}"
        else:
            # cx_Oracle: makedsn 함수 사용
            self.dsn = oracle_lib.makedsn(self.host, self.port, service_name=self.service_name)

    @contextmanager
    def get_connection(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        connection = None
        try:
            connection = oracle_lib.connect(
                user=self.username,
                password=self.password,
                dsn=self.dsn
            )
            logger.debug("Database connection established")
            yield connection
        except oracle_lib.DatabaseError as e:
            logger.error(f"Database connection failed: {e}")
            raise
        finally:
            if connection:
                connection.close()
                logger.debug("Database connection closed")

    # =========================================================================
    # CRAWL_TARGETS 관리
    # =========================================================================

    def insert_target_site(self, site_url: str, site_name: str, **kwargs) -> int:
        """
        새로운 크롤링 대상 사이트 등록

        Args:
            site_url: 사이트 URL
            site_name: 사이트 이름
            **kwargs: site_type, priority, phase 등

        Returns:
            target_id: 생성된 대상 사이트 ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            target_id = cursor.var(oracle_lib.NUMBER)

            sql = """
            INSERT INTO CRAWL_TARGETS (
                target_id, site_url, site_name, site_type, priority,
                phase, status, created_by
            ) VALUES (
                crawl_targets_seq.NEXTVAL, :site_url, :site_name, :site_type,
                :priority, :phase, 'pending', :created_by
            ) RETURNING target_id INTO :target_id
            """

            cursor.execute(sql, {
                'site_url': site_url,
                'site_name': site_name,
                'site_type': kwargs.get('site_type'),
                'priority': kwargs.get('priority', 5),
                'phase': kwargs.get('phase', 1),
                'created_by': kwargs.get('created_by', 'system'),
                'target_id': target_id
            })

            conn.commit()

            result_id = int(target_id.getvalue()[0])
            logger.info(f"Target site registered: {site_name} (ID: {result_id})")

            return result_id

    def get_target_site(self, target_id: int) -> Optional[Dict]:
        """대상 사이트 정보 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            sql = """
            SELECT target_id, site_url, site_name, site_type, priority, status,
                   phase, last_step_completed, current_strategy_version,
                   current_success_rate, created_at, updated_at
            FROM CRAWL_TARGETS
            WHERE target_id = :target_id
            """

            cursor.execute(sql, {'target_id': target_id})
            row = cursor.fetchone()

            if not row:
                return None

            return {
                'target_id': row[0],
                'site_url': row[1],
                'site_name': row[2],
                'site_type': row[3],
                'priority': row[4],
                'status': row[5],
                'phase': row[6],
                'last_step_completed': row[7],
                'current_strategy_version': row[8],
                'current_success_rate': float(row[9]) if row[9] else None,
                'created_at': row[10],
                'updated_at': row[11]
            }

    def update_target_progress(self, target_id: int, last_step: int,
                              strategy_version: str = None,
                              success_rate: float = None,
                              status: str = None):
        """대상 사이트 진행 상황 업데이트"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            sql = """
            UPDATE CRAWL_TARGETS
            SET last_step_completed = :last_step,
                current_strategy_version = NVL(:strategy_version, current_strategy_version),
                current_success_rate = NVL(:success_rate, current_success_rate),
                status = NVL(:status, status),
                updated_at = CURRENT_TIMESTAMP
            WHERE target_id = :target_id
            """

            cursor.execute(sql, {
                'target_id': target_id,
                'last_step': last_step,
                'strategy_version': strategy_version,
                'success_rate': success_rate,
                'status': status
            })

            conn.commit()
            logger.info(f"Target {target_id} progress updated: step {last_step}")

    # =========================================================================
    # CRAWL_SITE_ANALYSIS 관리 (Step 1 결과)
    # =========================================================================

    def insert_site_analysis(self, target_id: int, analysis_data: Dict,
                           version: str = "1.0") -> int:
        """
        Step 1 사이트 분석 결과 저장

        Args:
            target_id: 대상 사이트 ID
            analysis_data: Step 1 JSON 출력
            version: 분석 버전

        Returns:
            analysis_id: 생성된 분석 ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            analysis_id = cursor.var(oracle_lib.NUMBER)

            # JSON에서 주요 정보 추출
            rendering_type = analysis_data.get('rendering', {}).get('detected_type')
            framework = analysis_data.get('rendering', {}).get('framework')
            requires_js = 1 if analysis_data.get('rendering', {}).get('requires_javascript') else 0
            overall_conf = analysis_data.get('overall_confidence', 0.0)

            article_selector = None
            article_conf = None
            if 'article_list' in analysis_data:
                article_selector = analysis_data['article_list'].get('primary_selector')
                article_conf = analysis_data['article_list'].get('confidence', 0.0)

            pagination_type = None
            if 'pagination' in analysis_data:
                pagination_type = analysis_data['pagination'].get('type')

            sql = """
            INSERT INTO CRAWL_SITE_ANALYSIS (
                analysis_id, target_id, analysis_version, analysis_json,
                rendering_type, framework_detected, requires_javascript,
                overall_confidence, article_list_selector, article_list_confidence,
                pagination_type, analyzed_by
            ) VALUES (
                crawl_site_analysis_seq.NEXTVAL, :target_id, :version, :analysis_json,
                :rendering_type, :framework, :requires_js, :overall_conf,
                :article_selector, :article_conf, :pagination_type, 'system'
            ) RETURNING analysis_id INTO :analysis_id
            """

            cursor.execute(sql, {
                'target_id': target_id,
                'version': version,
                'analysis_json': json.dumps(analysis_data, ensure_ascii=False),
                'rendering_type': rendering_type,
                'framework': framework,
                'requires_js': requires_js,
                'overall_conf': overall_conf,
                'article_selector': article_selector,
                'article_conf': article_conf,
                'pagination_type': pagination_type,
                'analysis_id': analysis_id
            })

            conn.commit()

            result_id = int(analysis_id.getvalue()[0])
            logger.info(f"Site analysis saved: target_id={target_id}, analysis_id={result_id}")

            return result_id

    def get_site_analysis(self, target_id: int, version: str = None) -> Optional[Dict]:
        """사이트 분석 결과 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if version:
                sql = """
                SELECT analysis_id, analysis_json, analyzed_at
                FROM CRAWL_SITE_ANALYSIS
                WHERE target_id = :target_id AND analysis_version = :version
                ORDER BY analyzed_at DESC
                """
                cursor.execute(sql, {'target_id': target_id, 'version': version})
            else:
                sql = """
                SELECT analysis_id, analysis_json, analyzed_at
                FROM CRAWL_SITE_ANALYSIS
                WHERE target_id = :target_id
                ORDER BY analyzed_at DESC
                """
                cursor.execute(sql, {'target_id': target_id})

            row = cursor.fetchone()

            if not row:
                return None

            # CLOB 읽기
            analysis_json = row[1].read() if hasattr(row[1], 'read') else row[1]

            return {
                'analysis_id': row[0],
                'analysis_data': json.loads(analysis_json),
                'analyzed_at': row[2]
            }

    # =========================================================================
    # CRAWL_STRATEGIES 관리 (Step 2, 5 결과)
    # =========================================================================

    def insert_strategy(self, target_id: int, strategy_data: Dict,
                       version: str, refinement_step: int = 2) -> int:
        """
        크롤링 전략 저장

        Args:
            target_id: 대상 사이트 ID
            strategy_data: Step 2 or Step 5 JSON 출력
            version: 전략 버전 (1.0, 2.0, ...)
            refinement_step: 2 (initial) or 5 (refined)

        Returns:
            strategy_id: 생성된 전략 ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            strategy_id = cursor.var(oracle_lib.NUMBER)

            tool_selected = strategy_data.get('tool_recommendation', {}).get('primary_tool')
            estimated_rate = strategy_data.get('expected_outcomes', {}).get('estimated_success_rate', 0.0)

            # 이전 버전 찾기
            prev_version = None
            if version != "1.0":
                major = int(version.split('.')[0])
                prev_version = f"{major-1}.0" if major > 1 else None

            sql = """
            INSERT INTO CRAWL_STRATEGIES (
                strategy_id, target_id, strategy_version, strategy_json,
                tool_selected, estimated_success_rate, previous_version,
                refinement_step, status, created_by
            ) VALUES (
                crawl_strategies_seq.NEXTVAL, :target_id, :version, :strategy_json,
                :tool_selected, :estimated_rate, :prev_version,
                :refinement_step, 'draft', 'system'
            ) RETURNING strategy_id INTO :strategy_id
            """

            cursor.execute(sql, {
                'target_id': target_id,
                'version': version,
                'strategy_json': json.dumps(strategy_data, ensure_ascii=False),
                'tool_selected': tool_selected,
                'estimated_rate': estimated_rate,
                'prev_version': prev_version,
                'refinement_step': refinement_step,
                'strategy_id': strategy_id
            })

            conn.commit()

            result_id = int(strategy_id.getvalue()[0])
            logger.info(f"Strategy saved: target_id={target_id}, version={version}, strategy_id={result_id}")

            return result_id

    def get_strategy(self, target_id: int, version: str) -> Optional[Dict]:
        """크롤링 전략 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            sql = """
            SELECT strategy_id, strategy_json, tool_selected,
                   estimated_success_rate, status, created_at
            FROM CRAWL_STRATEGIES
            WHERE target_id = :target_id AND strategy_version = :version
            """

            cursor.execute(sql, {'target_id': target_id, 'version': version})
            row = cursor.fetchone()

            if not row:
                return None

            strategy_json = row[1].read() if hasattr(row[1], 'read') else row[1]

            return {
                'strategy_id': row[0],
                'strategy_data': json.loads(strategy_json),
                'tool_selected': row[2],
                'estimated_success_rate': float(row[3]) if row[3] else None,
                'status': row[4],
                'created_at': row[5]
            }

    def update_strategy_status(self, strategy_id: int, status: str):
        """전략 상태 업데이트 (draft -> testing -> validated -> active)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            sql = """
            UPDATE CRAWL_STRATEGIES
            SET status = :status
            WHERE strategy_id = :strategy_id
            """

            cursor.execute(sql, {'strategy_id': strategy_id, 'status': status})
            conn.commit()

            logger.info(f"Strategy {strategy_id} status updated: {status}")

    # =========================================================================
    # CRAWL_VALIDATIONS 관리 (Step 3 결과)
    # =========================================================================

    def insert_validation(self, strategy_id: int, validation_data: Dict) -> int:
        """
        Step 3 검증 결과 저장

        Args:
            strategy_id: 전략 ID
            validation_data: Step 3 JSON 출력

        Returns:
            validation_id: 생성된 검증 ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            validation_id = cursor.var(oracle_lib.NUMBER)

            summary = validation_data.get('summary', {})
            total_tests = summary.get('total_tests', 0)
            successful = summary.get('successful_tests', 0)
            failed = summary.get('failed_tests', 0)
            success_rate = summary.get('success_rate', 0.0)

            issues = validation_data.get('issues', {})
            critical = len(issues.get('critical', []))
            high = len(issues.get('high', []))
            medium = len(issues.get('medium', []))
            low = len(issues.get('low', []))

            test_urls = json.dumps(validation_data.get('test_urls', []))
            sample_size = validation_data.get('sample_size', 0)
            duration = validation_data.get('test_duration_seconds', 0)

            sql = """
            INSERT INTO CRAWL_VALIDATIONS (
                validation_id, strategy_id, validation_json,
                total_tests, successful_tests, failed_tests, actual_success_rate,
                test_urls, sample_size, critical_issues, high_issues,
                medium_issues, low_issues, test_duration_seconds
            ) VALUES (
                crawl_validations_seq.NEXTVAL, :strategy_id, :validation_json,
                :total_tests, :successful, :failed, :success_rate,
                :test_urls, :sample_size, :critical, :high, :medium, :low, :duration
            ) RETURNING validation_id INTO :validation_id
            """

            cursor.execute(sql, {
                'strategy_id': strategy_id,
                'validation_json': json.dumps(validation_data, ensure_ascii=False),
                'total_tests': total_tests,
                'successful': successful,
                'failed': failed,
                'success_rate': success_rate,
                'test_urls': test_urls,
                'sample_size': sample_size,
                'critical': critical,
                'high': high,
                'medium': medium,
                'low': low,
                'duration': duration,
                'validation_id': validation_id
            })

            conn.commit()

            result_id = int(validation_id.getvalue()[0])
            logger.info(f"Validation result saved: strategy_id={strategy_id}, success_rate={success_rate}%")

            return result_id

    def get_validation(self, validation_id: int) -> Optional[Dict]:
        """검증 결과 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            sql = """
            SELECT validation_id, strategy_id, validation_json,
                   actual_success_rate, validated_at
            FROM CRAWL_VALIDATIONS
            WHERE validation_id = :validation_id
            """

            cursor.execute(sql, {'validation_id': validation_id})
            row = cursor.fetchone()

            if not row:
                return None

            validation_json = row[2].read() if hasattr(row[2], 'read') else row[2]

            return {
                'validation_id': row[0],
                'strategy_id': row[1],
                'validation_data': json.loads(validation_json),
                'actual_success_rate': float(row[3]) if row[3] else None,
                'validated_at': row[4]
            }

    # =========================================================================
    # CRAWL_EVALUATIONS 관리 (Step 4 결과)
    # =========================================================================

    def insert_evaluation(self, validation_id: int, evaluation_data: Dict) -> int:
        """
        Step 4 평가 결과 저장

        Args:
            validation_id: 검증 ID
            evaluation_data: Step 4 JSON 출력

        Returns:
            evaluation_id: 생성된 평가 ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            evaluation_id = cursor.var(oracle_lib.NUMBER)

            overall = evaluation_data.get('overall_assessment', 'FAIL')

            fixes = evaluation_data.get('fix_instructions', [])
            total_fixes = len(fixes)
            critical = len([f for f in fixes if f.get('severity') == 'Critical'])
            high = len([f for f in fixes if f.get('severity') == 'High'])
            medium = len([f for f in fixes if f.get('severity') == 'Medium'])
            low = len([f for f in fixes if f.get('severity') == 'Low'])

            estimated_rate = evaluation_data.get('estimated_success_rate_after_fixes', 0.0)

            sql = """
            INSERT INTO CRAWL_EVALUATIONS (
                evaluation_id, validation_id, evaluation_json,
                overall_assessment, total_fixes_needed, critical_fixes,
                high_fixes, medium_fixes, low_fixes,
                estimated_success_rate_after_fixes
            ) VALUES (
                crawl_evaluations_seq.NEXTVAL, :validation_id, :evaluation_json,
                :overall, :total_fixes, :critical, :high, :medium, :low,
                :estimated_rate
            ) RETURNING evaluation_id INTO :evaluation_id
            """

            cursor.execute(sql, {
                'validation_id': validation_id,
                'evaluation_json': json.dumps(evaluation_data, ensure_ascii=False),
                'overall': overall,
                'total_fixes': total_fixes,
                'critical': critical,
                'high': high,
                'medium': medium,
                'low': low,
                'estimated_rate': estimated_rate,
                'evaluation_id': evaluation_id
            })

            conn.commit()

            result_id = int(evaluation_id.getvalue()[0])
            logger.info(f"Evaluation saved: validation_id={validation_id}, assessment={overall}")

            return result_id

    def get_evaluation(self, evaluation_id: int) -> Optional[Dict]:
        """평가 결과 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            sql = """
            SELECT evaluation_id, validation_id, evaluation_json,
                   overall_assessment, estimated_success_rate_after_fixes
            FROM CRAWL_EVALUATIONS
            WHERE evaluation_id = :evaluation_id
            """

            cursor.execute(sql, {'evaluation_id': evaluation_id})
            row = cursor.fetchone()

            if not row:
                return None

            evaluation_json = row[2].read() if hasattr(row[2], 'read') else row[2]

            return {
                'evaluation_id': row[0],
                'validation_id': row[1],
                'evaluation_data': json.loads(evaluation_json),
                'overall_assessment': row[3],
                'estimated_success_rate_after_fixes': float(row[4]) if row[4] else None
            }

    # =========================================================================
    # CRAWL_STRATEGY_CHANGES 관리 (Step 5 변경 이력)
    # =========================================================================

    def insert_strategy_changes(self, strategy_id: int, evaluation_id: int,
                               changes: List[Dict]):
        """
        Step 5 전략 변경 이력 저장

        Args:
            strategy_id: 새 전략 ID (v2.0)
            evaluation_id: 평가 ID
            changes: 변경 이력 리스트
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            for idx, change in enumerate(changes, 1):
                sql = """
                INSERT INTO CRAWL_STRATEGY_CHANGES (
                    change_id, strategy_id, evaluation_id, change_sequence,
                    change_category, target_location, change_description,
                    value_before, value_after, rationale, expected_impact,
                    related_fix_id, priority
                ) VALUES (
                    crawl_strategy_changes_seq.NEXTVAL, :strategy_id, :evaluation_id, :sequence,
                    :category, :location, :description,
                    :value_before, :value_after, :rationale, :impact,
                    :fix_id, :priority
                )
                """

                cursor.execute(sql, {
                    'strategy_id': strategy_id,
                    'evaluation_id': evaluation_id,
                    'sequence': idx,
                    'category': change.get('category'),
                    'location': change.get('target_location'),
                    'description': change.get('description'),
                    'value_before': json.dumps(change.get('value_before')),
                    'value_after': json.dumps(change.get('value_after')),
                    'rationale': change.get('rationale'),
                    'impact': change.get('expected_impact'),
                    'fix_id': change.get('related_fix_id'),
                    'priority': change.get('priority', 5)
                })

            conn.commit()
            logger.info(f"Strategy changes saved: {len(changes)} changes for strategy_id={strategy_id}")

    # =========================================================================
    # CRAWL_EXECUTIONS 관리 (실제 크롤링 실행)
    # =========================================================================

    def insert_execution(self, target_id: int, strategy_id: int,
                        execution_type: str = 'production') -> int:
        """크롤링 실행 시작"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            execution_id = cursor.var(oracle_lib.NUMBER)

            sql = """
            INSERT INTO CRAWL_EXECUTIONS (
                execution_id, target_id, strategy_id, execution_type,
                status, start_time, triggered_by
            ) VALUES (
                crawl_executions_seq.NEXTVAL, :target_id, :strategy_id, :exec_type,
                'running', CURRENT_TIMESTAMP, 'system'
            ) RETURNING execution_id INTO :execution_id
            """

            cursor.execute(sql, {
                'target_id': target_id,
                'strategy_id': strategy_id,
                'exec_type': execution_type,
                'execution_id': execution_id
            })

            conn.commit()

            result_id = int(execution_id.getvalue()[0])
            logger.info(f"Execution started: execution_id={result_id}")

            return result_id

    def update_execution(self, execution_id: int, status: str, **kwargs):
        """크롤링 실행 결과 업데이트"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            sql = """
            UPDATE CRAWL_EXECUTIONS
            SET status = :status,
                pages_crawled = NVL(:pages_crawled, pages_crawled),
                pages_failed = NVL(:pages_failed, pages_failed),
                articles_extracted = NVL(:articles_extracted, articles_extracted),
                actual_success_rate = NVL(:success_rate, actual_success_rate),
                end_time = CASE WHEN :status IN ('completed', 'failed', 'cancelled')
                                THEN CURRENT_TIMESTAMP ELSE end_time END,
                duration_seconds = NVL(:duration, duration_seconds),
                error_summary = NVL(:error_summary, error_summary)
            WHERE execution_id = :execution_id
            """

            cursor.execute(sql, {
                'execution_id': execution_id,
                'status': status,
                'pages_crawled': kwargs.get('pages_crawled'),
                'pages_failed': kwargs.get('pages_failed'),
                'articles_extracted': kwargs.get('articles_extracted'),
                'success_rate': kwargs.get('success_rate'),
                'duration': kwargs.get('duration_seconds'),
                'error_summary': json.dumps(kwargs.get('error_summary')) if kwargs.get('error_summary') else None
            })

            conn.commit()
            logger.info(f"Execution {execution_id} updated: status={status}")

    # =========================================================================
    # 유틸리티 메서드
    # =========================================================================

    def get_crawl_status(self, target_id: int = None) -> List[Dict]:
        """v_crawl_status 뷰를 통한 현황 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if target_id:
                sql = "SELECT * FROM v_crawl_status WHERE target_id = :target_id"
                cursor.execute(sql, {'target_id': target_id})
            else:
                sql = "SELECT * FROM v_crawl_status"
                cursor.execute(sql)

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(dict(zip(columns, row)))

            return results


if __name__ == '__main__':
    # 테스트 코드
    db = CrawlDatabaseManager()

    # 테스트 사이트 등록
    target_id = db.insert_target_site(
        site_url='https://notice.tistory.com',
        site_name='Notice Tistory',
        site_type='blog',
        priority=1,
        phase=1
    )

    print(f"✅ Test site registered: target_id={target_id}")

    # 사이트 정보 조회
    target_info = db.get_target_site(target_id)
    print(f"📊 Site info: {target_info}")

    # 현황 조회
    status = db.get_crawl_status(target_id)
    print(f"📈 Crawl status: {status}")
