#!/usr/bin/env python3
# Generated: 2025-10-16 12:40:00 KST
"""
Pipeline Artifact Manager - Dual Storage Implementation

This module manages the storage and retrieval of Sonic Koi 5-step pipeline artifacts
using BOTH normalized CRAWL_* tables AND hybrid CRAWL_PIPELINE_* tables.

DUAL STORAGE STRATEGY:
- Normalized tables (CRAWL_*): Fast queries, filtering, referential integrity
- Hybrid tables (CRAWL_PIPELINE_*): Complete audit trail, full JSON artifacts

Tables managed:
- CRAWL_PIPELINE_EXECUTIONS (main table with all CLOBs + extracted metrics)
- CRAWL_PIPELINE_TESTS (Step 3 test details)
- CRAWL_PIPELINE_FIXES (Step 4 fix details)
- CRAWL_PIPELINE_REFINEMENTS (Step 5 refinement details)
- CRAWL_SITE_ANALYSIS (Step 1 normalized data)
- CRAWL_STRATEGIES (Step 2 & 5 normalized strategies)
- CRAWL_VALIDATIONS (Step 3 normalized validation)
- CRAWL_EVALUATIONS (Step 4 normalized evaluation)
- CRAWL_STRATEGY_CHANGES (Step 5 normalized changes)
- CRAWL_EXECUTIONS (overall execution tracking)
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
from loguru import logger

# Use the same Oracle library selection as CrawlDatabaseManager
USE_PYTHON_ORACLEDB = os.getenv('USE_PYTHON_ORACLEDB', 'false').lower() == 'true'

if USE_PYTHON_ORACLEDB:
    import oracledb as oracle_lib
    logger.info("✅ PipelineArtifactManager: Using python-oracledb (Thin Mode)")
else:
    import cx_Oracle as oracle_lib
    logger.info("✅ PipelineArtifactManager: Using cx_Oracle")


class PipelineArtifactManager:
    """
    Manager for storing and retrieving pipeline artifacts in Oracle database.
    Handles all CLOB operations including Step 0 HTML storage.
    """

    def __init__(self):
        """Initialize database connection for artifact storage"""
        self.host = os.getenv('DB_HOST', '192.168.75.194')
        self.port = os.getenv('DB_PORT', '1521')
        self.service_name = os.getenv('DB_SERVICE_NAME', 'XEPDB1')
        self.username = os.getenv('DB_USERNAME', 'ocr_admin')
        self.password = os.getenv('DB_PASSWORD', 'admin_password')

        # DSN generation (library-specific)
        if USE_PYTHON_ORACLEDB:
            self.dsn = f"{self.host}:{self.port}/{self.service_name}"
        else:
            self.dsn = oracle_lib.makedsn(self.host, self.port, service_name=self.service_name)

    @contextmanager
    def get_connection(self):
        """Database connection context manager"""
        connection = None
        try:
            connection = oracle_lib.connect(
                user=self.username,
                password=self.password,
                dsn=self.dsn
            )
            logger.debug("Pipeline artifact database connection established")
            yield connection
        except oracle_lib.DatabaseError as e:
            logger.error(f"Pipeline artifact database connection failed: {e}")
            raise
        finally:
            if connection:
                connection.close()
                logger.debug("Pipeline artifact database connection closed")

    # =========================================================================
    # CRAWL_PIPELINE_EXECUTIONS Management
    # =========================================================================

    def create_execution(self, target_id: int, triggered_by: str = 'auto') -> int:
        """
        Create new pipeline execution record

        Args:
            target_id: CRAWL_TARGETS.TARGET_ID
            triggered_by: Execution trigger source ('auto', 'manual', 'scheduled')

        Returns:
            New EXECUTION_ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            execution_id_var = cursor.var(oracle_lib.NUMBER)

            sql = """
                INSERT INTO CRAWL_PIPELINE_EXECUTIONS (
                    EXECUTION_ID,
                    TARGET_ID,
                    EXECUTION_STATUS,
                    PIPELINE_VERSION,
                    TRIGGERED_BY,
                    STARTED_AT
                ) VALUES (
                    SEQ_CRAWL_PIPELINE_EXECUTIONS.NEXTVAL,
                    :target_id,
                    'in_progress',
                    '1.0',
                    :triggered_by,
                    SYSTIMESTAMP
                )
                RETURNING EXECUTION_ID INTO :exec_id
            """

            cursor.execute(sql, {
                'target_id': target_id,
                'triggered_by': triggered_by,
                'exec_id': execution_id_var
            })

            conn.commit()

            execution_id = int(execution_id_var.getvalue()[0])
            logger.info(f"✅ Created pipeline execution: {execution_id} for target {target_id}")

            return execution_id

    def save_step0_html(self, execution_id: int, html_content: str,
                        file_path: str, duration_sec: float) -> bool:
        """
        Save Step 0 HTML content to database

        Args:
            execution_id: Pipeline execution ID
            html_content: Full HTML content (may be 100-500 KB)
            file_path: File path for reference
            duration_sec: Collection duration

        Returns:
            True if successful
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            try:
                sql = """
                    UPDATE CRAWL_PIPELINE_EXECUTIONS
                    SET STEP0_STATUS = 'success',
                        STEP0_HTML_CONTENT = :html_content,
                        STEP0_HTML_SIZE = :html_size,
                        STEP0_HTML_FILE_PATH = :file_path,
                        STEP0_COLLECTED_AT = SYSTIMESTAMP,
                        STEP0_DURATION_SEC = :duration_sec
                    WHERE EXECUTION_ID = :exec_id
                """

                cursor.execute(sql, {
                    'exec_id': execution_id,
                    'html_content': html_content,
                    'html_size': len(html_content),
                    'file_path': file_path,
                    'duration_sec': duration_sec
                })

                conn.commit()
                logger.info(f"✅ Step 0 HTML saved: execution={execution_id}, size={len(html_content):,} bytes")
                return True

            except Exception as e:
                logger.error(f"❌ Error saving Step 0 HTML: {e}")
                conn.rollback()
                return False

    def save_step1_analysis(self, execution_id: int, analysis: Dict[str, Any],
                           duration_sec: float, target_id: int) -> Optional[int]:
        """
        Save Step 1 analysis with DUAL STORAGE:
        1. CRAWL_SITE_ANALYSIS (normalized data for queries)
        2. CRAWL_PIPELINE_EXECUTIONS (full JSON CLOB)

        Args:
            execution_id: Pipeline execution ID
            analysis: Complete analysis dictionary
            duration_sec: Analysis duration
            target_id: CRAWL_TARGETS.TARGET_ID

        Returns:
            ANALYSIS_ID if successful, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            try:
                analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2)

                # Extract metadata
                confidence = analysis.get('overall_confidence')
                rendering_type = analysis.get('structure_analysis', {}).get('rendering_type')
                js_required = 1 if analysis.get('javascript_analysis', {}).get('required') else 0
                framework = analysis.get('javascript_analysis', {}).get('framework')
                anti_scraping_detected = 'Y' if analysis.get('anti_scraping', {}).get('detected') else 'N'

                # Extract selector information
                article_list_selector = analysis.get('extraction_points', {}).get('article_list', {}).get('primary_selector')
                article_list_confidence = analysis.get('extraction_points', {}).get('article_list', {}).get('confidence')
                pagination_type = analysis.get('pagination_analysis', {}).get('pagination_type')

                # === 1. Write to CRAWL_SITE_ANALYSIS (normalized) ===
                analysis_id_var = cursor.var(oracle_lib.NUMBER)

                sql_normalized = """
                    INSERT INTO CRAWL_SITE_ANALYSIS (
                        ANALYSIS_ID,
                        TARGET_ID,
                        ANALYSIS_VERSION,
                        ANALYSIS_JSON,
                        RENDERING_TYPE,
                        FRAMEWORK_DETECTED,
                        REQUIRES_JAVASCRIPT,
                        OVERALL_CONFIDENCE,
                        ARTICLE_LIST_SELECTOR,
                        ARTICLE_LIST_CONFIDENCE,
                        PAGINATION_TYPE,
                        ANALYZED_AT,
                        ANALYZED_BY
                    ) VALUES (
                        SEQ_CRAWL_SITE_ANALYSIS.NEXTVAL,
                        :target_id,
                        '1.0',
                        :analysis_json,
                        :rendering_type,
                        :framework,
                        :js_required,
                        :confidence,
                        :article_selector,
                        :article_confidence,
                        :pagination_type,
                        SYSTIMESTAMP,
                        'PipelineArtifactManager'
                    )
                    RETURNING ANALYSIS_ID INTO :analysis_id
                """

                cursor.execute(sql_normalized, {
                    'target_id': target_id,
                    'analysis_json': analysis_json,
                    'rendering_type': rendering_type,
                    'framework': framework,
                    'js_required': js_required,
                    'confidence': confidence,
                    'article_selector': article_list_selector,
                    'article_confidence': article_list_confidence,
                    'pagination_type': pagination_type,
                    'analysis_id': analysis_id_var
                })

                analysis_id = int(analysis_id_var.getvalue()[0])

                # === 2. Write to CRAWL_PIPELINE_EXECUTIONS (full JSON) ===
                sql_pipeline = """
                    UPDATE CRAWL_PIPELINE_EXECUTIONS
                    SET STEP1_STATUS = 'success',
                        STEP1_ANALYSIS_JSON = :analysis_json,
                        STEP1_COMPLETED_AT = SYSTIMESTAMP,
                        STEP1_DURATION_SEC = :duration_sec,
                        ANALYSIS_CONFIDENCE = :confidence,
                        RENDERING_TYPE = :rendering_type,
                        JS_REQUIRED = :js_required_char,
                        FRAMEWORK_DETECTED = :framework,
                        ANTI_SCRAPING_DETECTED = :anti_scraping
                    WHERE EXECUTION_ID = :exec_id
                """

                cursor.execute(sql_pipeline, {
                    'exec_id': execution_id,
                    'analysis_json': analysis_json,
                    'duration_sec': duration_sec,
                    'confidence': confidence,
                    'rendering_type': rendering_type,
                    'js_required_char': 'Y' if js_required == 1 else 'N',
                    'framework': framework,
                    'anti_scraping': anti_scraping_detected
                })

                conn.commit()
                logger.info(f"✅ Step 1 analysis saved (DUAL): execution={execution_id}, analysis_id={analysis_id}, confidence={confidence}")
                return analysis_id

            except Exception as e:
                logger.error(f"❌ Error saving Step 1 analysis (DUAL): {e}")
                conn.rollback()
                return None

    def save_step2_strategy(self, execution_id: int, strategy: Dict[str, Any],
                           duration_sec: float, target_id: int) -> Optional[int]:
        """
        Save Step 2 strategy with DUAL STORAGE:
        1. CRAWL_STRATEGIES (normalized strategy for queries)
        2. CRAWL_PIPELINE_EXECUTIONS (full JSON CLOB)

        Args:
            execution_id: Pipeline execution ID
            strategy: Complete strategy dictionary
            duration_sec: Strategy generation duration
            target_id: CRAWL_TARGETS.TARGET_ID

        Returns:
            STRATEGY_ID if successful, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            try:
                strategy_json = json.dumps(strategy, ensure_ascii=False, indent=2)

                # Extract metadata
                tool_selected = strategy.get('approach', {}).get('tool')
                estimated_rate = strategy.get('estimated_success_rate')
                version = strategy.get('strategy_version', '1.0')

                # === 1. Write to CRAWL_STRATEGIES (normalized) ===
                # Try to insert, if UNIQUE constraint violated, use existing strategy_id
                strategy_id = None

                try:
                    strategy_id_var = cursor.var(oracle_lib.NUMBER)

                    sql_normalized = """
                        INSERT INTO CRAWL_STRATEGIES (
                            STRATEGY_ID,
                            TARGET_ID,
                            STRATEGY_VERSION,
                            STRATEGY_JSON,
                            TOOL_SELECTED,
                            ESTIMATED_SUCCESS_RATE,
                            STATUS,
                            REFINEMENT_STEP,
                            CREATED_AT,
                            CREATED_BY
                        ) VALUES (
                            SEQ_CRAWL_STRATEGIES.NEXTVAL,
                            :target_id,
                            :version,
                            :strategy_json,
                            :tool_selected,
                            :estimated_rate,
                            'active',
                            0,
                            SYSTIMESTAMP,
                            'PipelineArtifactManager'
                        )
                        RETURNING STRATEGY_ID INTO :strategy_id
                    """

                    cursor.execute(sql_normalized, {
                        'target_id': target_id,
                        'version': version,
                        'strategy_json': strategy_json,
                        'tool_selected': tool_selected,
                        'estimated_rate': estimated_rate,
                        'strategy_id': strategy_id_var
                    })

                    strategy_id = int(strategy_id_var.getvalue()[0])

                except Exception as insert_error:
                    # Check if it's a UNIQUE constraint violation (ORA-00001)
                    if 'ORA-00001' in str(insert_error):
                        # Strategy with this version already exists, fetch existing STRATEGY_ID
                        cursor.execute("""
                            SELECT STRATEGY_ID
                            FROM CRAWL_STRATEGIES
                            WHERE TARGET_ID = :target_id AND STRATEGY_VERSION = :version
                        """, {'target_id': target_id, 'version': version})

                        row = cursor.fetchone()
                        if row:
                            strategy_id = int(row[0])
                            logger.warning(f"⚠️ Strategy version {version} already exists for target {target_id}, using existing STRATEGY_ID={strategy_id}")
                        else:
                            # Unexpected error
                            raise insert_error
                    else:
                        # Not a UNIQUE constraint error, re-raise
                        raise insert_error

                if strategy_id is None:
                    raise Exception("Failed to get STRATEGY_ID")

                # === 2. Write to CRAWL_PIPELINE_EXECUTIONS ===
                sql_pipeline = """
                    UPDATE CRAWL_PIPELINE_EXECUTIONS
                    SET STEP2_STATUS = 'success',
                        STEP2_STRATEGY_JSON = :strategy_json,
                        STEP2_COMPLETED_AT = SYSTIMESTAMP,
                        STEP2_DURATION_SEC = :duration_sec,
                        TOOL_SELECTED = :tool_selected,
                        ESTIMATED_SUCCESS_RATE = :estimated_rate,
                        STRATEGY_VERSION = :version,
                        INITIAL_STRATEGY_ID = :strategy_id
                    WHERE EXECUTION_ID = :exec_id
                """

                cursor.execute(sql_pipeline, {
                    'exec_id': execution_id,
                    'strategy_json': strategy_json,
                    'duration_sec': duration_sec,
                    'tool_selected': tool_selected,
                    'estimated_rate': estimated_rate,
                    'version': version,
                    'strategy_id': strategy_id
                })

                conn.commit()
                logger.info(f"✅ Step 2 strategy saved (DUAL): execution={execution_id}, strategy_id={strategy_id}, estimated_rate={estimated_rate}")
                return strategy_id

            except Exception as e:
                logger.error(f"❌ Error saving Step 2 strategy (DUAL): {e}")
                conn.rollback()
                return None

    def save_step3_validation(self, execution_id: int, validation_results: Dict[str, Any],
                              duration_sec: float, target_id: int, strategy_id: int) -> Optional[int]:
        """
        Save Step 3 validation with DUAL STORAGE:
        1. CRAWL_VALIDATIONS (normalized validation metrics)
        2. CRAWL_PIPELINE_EXECUTIONS (full JSON CLOB)
        3. CRAWL_PIPELINE_TESTS (individual test details)

        Args:
            execution_id: Pipeline execution ID
            validation_results: Complete validation results
            duration_sec: Validation duration
            target_id: CRAWL_TARGETS.TARGET_ID
            strategy_id: CRAWL_STRATEGIES.STRATEGY_ID being validated

        Returns:
            VALIDATION_ID if successful, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            try:
                # Handle nested structure {'validation_results': {...}}
                vr = validation_results.get('validation_results', validation_results)
                validation_json = json.dumps(validation_results, ensure_ascii=False, indent=2)

                # Extract summary metrics - support THREE JSON formats
                # Format 1 (old): passed_tests, success_rate, tests
                # Format 2 (new): successful_tests, failed_tests, actual_success_rate, test_details
                # Format 3 (summary): summary.total_tests, summary.success_rate, test_results

                # Check for Format 3 (summary-based)
                summary = vr.get('summary', {})
                has_summary = bool(summary)

                # Success rate: try all formats
                if has_summary:
                    success_rate = summary.get('success_rate')
                else:
                    success_rate = vr.get('actual_success_rate') or vr.get('success_rate')

                # Ensure success_rate is not None (default to 0.0 if missing)
                if success_rate is None:
                    success_rate = 0.0

                # Total tests
                if has_summary:
                    total_tests = summary.get('total_tests', 0)
                else:
                    total_tests = vr.get('total_tests', 0)

                # Passed tests: support all formats
                if has_summary:
                    passed_tests = summary.get('successful_tests', 0)
                else:
                    passed_tests = vr.get('successful_tests')
                    if passed_tests is None:
                        passed_tests = vr.get('passed_tests')
                    if passed_tests is None:
                        passed_tests = 0

                # Failed tests: calculate if not provided
                if has_summary:
                    failed_tests = summary.get('failed_tests', 0)
                else:
                    failed_tests = vr.get('failed_tests')
                    if failed_tests is None and total_tests and passed_tests is not None:
                        failed_tests = total_tests - passed_tests
                    if failed_tests is None:
                        failed_tests = 0

                # Count critical issues (new format uses 'issues_found', old format uses 'issues')
                issues_list = vr.get('issues_found', []) or vr.get('issues', [])
                critical_issues = len([issue for issue in issues_list
                                      if issue.get('severity') == 'critical'])

                # === 1. Write to CRAWL_VALIDATIONS (normalized) ===
                validation_id_var = cursor.var(oracle_lib.NUMBER)

                sql_normalized = """
                    INSERT INTO CRAWL_VALIDATIONS (
                        VALIDATION_ID,
                        TARGET_ID,
                        STRATEGY_ID,
                        VALIDATION_JSON,
                        ACTUAL_SUCCESS_RATE,
                        TOTAL_TESTS,
                        SUCCESSFUL_TESTS,
                        FAILED_TESTS,
                        CRITICAL_ISSUES,
                        VALIDATED_AT
                    ) VALUES (
                        SEQ_CRAWL_VALIDATIONS.NEXTVAL,
                        :target_id,
                        :strategy_id,
                        :validation_json,
                        :success_rate,
                        :total_tests,
                        :passed_tests,
                        :failed_tests,
                        :critical_issues,
                        SYSTIMESTAMP
                    )
                    RETURNING VALIDATION_ID INTO :validation_id
                """

                cursor.execute(sql_normalized, {
                    'target_id': target_id,
                    'strategy_id': strategy_id,
                    'validation_json': validation_json,
                    'success_rate': success_rate,
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'failed_tests': failed_tests,
                    'critical_issues': critical_issues,
                    'validation_id': validation_id_var
                })

                validation_id = int(validation_id_var.getvalue()[0])

                # === 2. Write to CRAWL_PIPELINE_EXECUTIONS ===
                sql_pipeline = """
                    UPDATE CRAWL_PIPELINE_EXECUTIONS
                    SET STEP3_STATUS = 'success',
                        STEP3_VALIDATION_JSON = :validation_json,
                        STEP3_COMPLETED_AT = SYSTIMESTAMP,
                        STEP3_DURATION_SEC = :duration_sec,
                        ACTUAL_SUCCESS_RATE = :success_rate,
                        TOTAL_TESTS = :total_tests,
                        PASSED_TESTS = :passed_tests,
                        FAILED_TESTS = :failed_tests,
                        CRITICAL_ISSUES = :critical_issues
                    WHERE EXECUTION_ID = :exec_id
                """

                cursor.execute(sql_pipeline, {
                    'exec_id': execution_id,
                    'validation_json': validation_json,
                    'duration_sec': duration_sec,
                    'success_rate': success_rate,
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'failed_tests': failed_tests,
                    'critical_issues': critical_issues
                })

                # Save individual test details (support THREE formats)
                # Format 1 (old): 'tests', Format 2 (new): 'test_details', Format 3: 'test_results'
                test_details = vr.get('test_details', []) or vr.get('tests', []) or vr.get('test_results', [])
                for seq, test in enumerate(test_details, 1):
                    # Extract test name (support all formats)
                    # Format 1 (old): 'test', Format 2 (new): 'test_name', Format 3: 'test_name'
                    test_name = test.get('test_name') or test.get('test', 'unknown_test')

                    test_type = self._infer_test_type(test_name)

                    # Extract test status (support all formats)
                    # Format 1 (old): 'passed' (boolean)
                    # Format 2 (new): 'status' (string)
                    # Format 3: 'success' (boolean)
                    status = test.get('status')
                    if status is None:
                        # Format 1 uses 'passed' boolean
                        passed = test.get('passed')
                        if passed is not None:
                            status = 'success' if passed else 'failed'
                        else:
                            # Format 3 uses 'success' boolean
                            success = test.get('success')
                            if success is not None:
                                status = 'success' if success else 'failed'
                            else:
                                status = 'skipped'  # Default if no status found

                    # Normalize test status to match CHK_TEST_STATUS constraint
                    normalized_status = self._normalize_test_status(status)

                    sql_test = """
                        INSERT INTO CRAWL_PIPELINE_TESTS (
                            TEST_ID,
                            EXECUTION_ID,
                            TEST_NAME,
                            TEST_TYPE,
                            TEST_SEQUENCE,
                            TEST_STATUS,
                            TEST_URL,
                            TIME_TAKEN_SEC,
                            RESULT_DATA,
                            LINKS_FOUND,
                            FALLBACK_USED,
                            ERROR_MESSAGE,
                            SEVERITY
                        ) VALUES (
                            SEQ_CRAWL_PIPELINE_TESTS.NEXTVAL,
                            :exec_id,
                            :test_name,
                            :test_type,
                            :test_seq,
                            :test_status,
                            :test_url,
                            :time_taken,
                            :result_data,
                            :links_found,
                            :fallback_used,
                            :error_msg,
                            :severity
                        )
                    """

                    cursor.execute(sql_test, {
                        'exec_id': execution_id,
                        'test_name': test_name,
                        'test_type': test_type,
                        'test_seq': seq,
                        'test_status': normalized_status,
                        'test_url': test.get('url'),
                        'time_taken': test.get('time_taken'),
                        'result_data': json.dumps(test, ensure_ascii=False),
                        'links_found': test.get('links_found'),
                        'fallback_used': 'Y' if test.get('fallback_used') else 'N',
                        'error_msg': test.get('error') or test.get('details'),  # Old format uses 'details'
                        'severity': 'critical' if normalized_status == 'failed' else 'low'
                    })

                conn.commit()
                logger.info(f"✅ Step 3 validation saved (DUAL): execution={execution_id}, validation_id={validation_id}, success_rate={success_rate}, tests={len(test_details)}")
                return validation_id

            except Exception as e:
                logger.error(f"❌ Error saving Step 3 validation (DUAL): {e}")
                conn.rollback()
                return None

    def save_step4_evaluation(self, execution_id: int, evaluation: Dict[str, Any],
                              duration_sec: float, target_id: int, validation_id: int) -> Optional[int]:
        """
        Save Step 4 evaluation with DUAL STORAGE:
        1. CRAWL_EVALUATIONS (normalized evaluation metrics)
        2. CRAWL_PIPELINE_EXECUTIONS (full JSON CLOB)
        3. CRAWL_PIPELINE_FIXES (individual fix details)

        Args:
            execution_id: Pipeline execution ID
            evaluation: Complete evaluation dictionary
            duration_sec: Evaluation duration
            target_id: CRAWL_TARGETS.TARGET_ID
            validation_id: CRAWL_VALIDATIONS.VALIDATION_ID being evaluated

        Returns:
            EVALUATION_ID if successful, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            try:
                evaluation_json = json.dumps(evaluation, ensure_ascii=False, indent=2)

                # Extract fix summary
                fix_summary = evaluation.get('fix_summary', {})
                total_fixes = fix_summary.get('total_fixes_needed', 0)
                critical_fixes = fix_summary.get('critical_fixes', 0)
                high_fixes = fix_summary.get('high_fixes', 0)
                medium_fixes = fix_summary.get('medium_fixes', 0)
                low_fixes = fix_summary.get('low_fixes', 0)
                estimated_rate = fix_summary.get('estimated_success_rate_after_fixes')
                expected_improvement = evaluation.get('validation_summary', {}).get('gap_to_target')

                # === 1. Write to CRAWL_EVALUATIONS (normalized) ===
                evaluation_id_var = cursor.var(oracle_lib.NUMBER)

                sql_normalized = """
                    INSERT INTO CRAWL_EVALUATIONS (
                        EVALUATION_ID,
                        TARGET_ID,
                        VALIDATION_ID,
                        EVALUATION_JSON,
                        TOTAL_FIXES_NEEDED,
                        CRITICAL_FIXES,
                        HIGH_FIXES,
                        MEDIUM_FIXES,
                        LOW_FIXES,
                        ESTIMATED_SUCCESS_RATE_AFTER_FIXES,
                        EVALUATED_AT
                    ) VALUES (
                        SEQ_CRAWL_EVALUATIONS.NEXTVAL,
                        :target_id,
                        :validation_id,
                        :evaluation_json,
                        :total_fixes,
                        :critical_fixes,
                        :high_fixes,
                        :medium_fixes,
                        :low_fixes,
                        :expected_improvement,
                        SYSTIMESTAMP
                    )
                    RETURNING EVALUATION_ID INTO :evaluation_id
                """

                cursor.execute(sql_normalized, {
                    'target_id': target_id,
                    'validation_id': validation_id,
                    'evaluation_json': evaluation_json,
                    'total_fixes': total_fixes,
                    'critical_fixes': critical_fixes,
                    'high_fixes': high_fixes,
                    'medium_fixes': medium_fixes,
                    'low_fixes': low_fixes,
                    'expected_improvement': abs(expected_improvement) if expected_improvement else None,
                    'evaluation_id': evaluation_id_var
                })

                evaluation_id = int(evaluation_id_var.getvalue()[0])

                # === 2. Write to CRAWL_PIPELINE_EXECUTIONS ===
                sql_pipeline = """
                    UPDATE CRAWL_PIPELINE_EXECUTIONS
                    SET STEP4_STATUS = 'success',
                        STEP4_EVALUATION_JSON = :evaluation_json,
                        STEP4_COMPLETED_AT = SYSTIMESTAMP,
                        STEP4_DURATION_SEC = :duration_sec,
                        TOTAL_FIXES_NEEDED = :total_fixes,
                        CRITICAL_FIXES = :critical_fixes,
                        HIGH_FIXES = :high_fixes,
                        MEDIUM_FIXES = :medium_fixes,
                        LOW_FIXES = :low_fixes,
                        EXPECTED_IMPROVEMENT = :expected_improvement
                    WHERE EXECUTION_ID = :exec_id
                """

                cursor.execute(sql_pipeline, {
                    'exec_id': execution_id,
                    'evaluation_json': evaluation_json,
                    'duration_sec': duration_sec,
                    'total_fixes': total_fixes,
                    'critical_fixes': critical_fixes,
                    'high_fixes': high_fixes,
                    'medium_fixes': medium_fixes,
                    'low_fixes': low_fixes,
                    'expected_improvement': abs(expected_improvement) if expected_improvement else None
                })

                # Save individual fix details
                fixes = evaluation.get('valid_issues', [])
                for fix in fixes:
                    sql_fix = """
                        INSERT INTO CRAWL_PIPELINE_FIXES (
                            FIX_ID,
                            EXECUTION_ID,
                            FIX_CODE,
                            FIX_PRIORITY,
                            FIX_TITLE,
                            FIX_DESCRIPTION,
                            ROOT_CAUSE,
                            SEVERITY,
                            AFFECTED_TEST_COUNT,
                            PERCENTAGE_IMPACT,
                            EXPECTED_IMPROVEMENT,
                            FIX_TYPE,
                            TARGET_LOCATION,
                            SPECIFIC_CHANGE,
                            IMPLEMENTATION_JSON,
                            TEST_URLS,
                            VERIFIED_SELECTORS
                        ) VALUES (
                            SEQ_CRAWL_PIPELINE_FIXES.NEXTVAL,
                            :exec_id,
                            :fix_code,
                            :priority,
                            :title,
                            :description,
                            :root_cause,
                            :severity,
                            :affected_count,
                            :impact_pct,
                            :expected_improvement,
                            :fix_type,
                            :target_location,
                            :specific_change,
                            :implementation_json,
                            :test_urls,
                            :verified_selectors
                        )
                    """

                    recommended_fix = fix.get('recommended_fix', {})

                    cursor.execute(sql_fix, {
                        'exec_id': execution_id,
                        'fix_code': fix.get('issue_id'),
                        'priority': fix.get('fix_priority', 5),
                        'title': fix.get('title'),
                        'description': fix.get('description'),
                        'root_cause': fix.get('root_cause'),
                        'severity': fix.get('severity'),
                        'affected_count': fix.get('frequency'),
                        'impact_pct': fix.get('percentage_impact'),
                        'expected_improvement': recommended_fix.get('expected_improvement'),
                        'fix_type': recommended_fix.get('fix_type'),
                        'target_location': recommended_fix.get('target_location'),
                        'specific_change': recommended_fix.get('specific_change'),
                        'implementation_json': json.dumps(recommended_fix.get('implementation', {}), ensure_ascii=False),
                        'test_urls': json.dumps(fix.get('testing_verification', {}).get('test_urls', []), ensure_ascii=False),
                        'verified_selectors': json.dumps(fix.get('testing_verification', {}).get('verified_selectors', {}), ensure_ascii=False)
                    })

                conn.commit()
                logger.info(f"✅ Step 4 evaluation saved (DUAL): execution={execution_id}, evaluation_id={evaluation_id}, fixes={len(fixes)}")
                return evaluation_id

            except Exception as e:
                logger.error(f"❌ Error saving Step 4 evaluation (DUAL): {e}")
                conn.rollback()
                return None

    def save_step5_refinement(self, execution_id: int, refinement: Dict[str, Any],
                              duration_sec: float, target_id: int, old_strategy_id: int,
                              evaluation_id: int) -> Optional[int]:
        """
        Save Step 5 refinement with DUAL STORAGE:
        1. CRAWL_STRATEGIES (new refined strategy - normalized)
        2. CRAWL_STRATEGY_CHANGES (change log - normalized)
        3. CRAWL_PIPELINE_EXECUTIONS (full JSON + final_strategy_id)
        4. CRAWL_PIPELINE_REFINEMENTS (individual change details)

        Args:
            execution_id: Pipeline execution ID
            refinement: Complete refinement dictionary with refined_strategy
            duration_sec: Refinement duration
            target_id: CRAWL_TARGETS.TARGET_ID
            old_strategy_id: Previous CRAWL_STRATEGIES.STRATEGY_ID (from Step 2/4)
            evaluation_id: CRAWL_EVALUATIONS.EVALUATION_ID (from Step 4)

        Returns:
            New STRATEGY_ID for refined strategy, or None on error
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            try:
                # Serialize full refinement JSON
                refinement_json = json.dumps(refinement, ensure_ascii=False, indent=2)

                # Extract metadata
                refined_strategy = refinement.get('refined_strategy', {})
                refined_strategy_json = json.dumps(refined_strategy, ensure_ascii=False, indent=2)

                final_success_rate = refinement.get('final_success_rate')
                refinement_cycle = refinement.get('refinement_cycle', 1)
                changes_applied = refinement.get('changes_applied', 0)
                final_version = refinement.get('final_strategy_version', 'v1.1')
                old_version = refinement.get('old_strategy_version', 'v1.0')

                tool_selected = refined_strategy.get('tool_selected')
                estimated_success_rate = refined_strategy.get('estimated_success_rate')

                # === 1. Write new refined strategy to CRAWL_STRATEGIES (normalized) ===
                new_strategy_id_var = cursor.var(oracle_lib.NUMBER)

                sql_new_strategy = """
                    INSERT INTO CRAWL_STRATEGIES (
                        STRATEGY_ID,
                        TARGET_ID,
                        STRATEGY_VERSION,
                        STRATEGY_JSON,
                        TOOL_SELECTED,
                        ESTIMATED_SUCCESS_RATE,
                        STATUS,
                        PREVIOUS_VERSION,
                        REFINEMENT_STEP,
                        CREATED_AT,
                        CREATED_BY
                    ) VALUES (
                        SEQ_CRAWL_STRATEGIES.NEXTVAL,
                        :target_id,
                        :final_version,
                        :refined_strategy_json,
                        :tool_selected,
                        :estimated_success_rate,
                        'active',
                        :old_version,
                        :refinement_cycle,
                        SYSTIMESTAMP,
                        'PipelineArtifactManager'
                    )
                    RETURNING STRATEGY_ID INTO :new_strategy_id
                """

                cursor.execute(sql_new_strategy, {
                    'target_id': target_id,
                    'final_version': final_version,
                    'refined_strategy_json': refined_strategy_json,
                    'tool_selected': tool_selected,
                    'estimated_success_rate': estimated_success_rate,
                    'old_version': old_version,
                    'refinement_cycle': refinement_cycle,
                    'new_strategy_id': new_strategy_id_var
                })

                new_strategy_id = int(new_strategy_id_var.getvalue()[0])

                # === 2. Write to CRAWL_STRATEGY_CHANGES (individual changes) ===
                changes = refinement.get('changes', [])

                for seq, change in enumerate(changes, 1):
                    sql_strategy_change = """
                        INSERT INTO CRAWL_STRATEGY_CHANGES (
                            CHANGE_ID,
                            STRATEGY_ID,
                            EVALUATION_ID,
                            CHANGE_SEQUENCE,
                            CHANGE_CATEGORY,
                            TARGET_LOCATION,
                            CHANGE_DESCRIPTION,
                            VALUE_BEFORE,
                            VALUE_AFTER,
                            RATIONALE,
                            EXPECTED_IMPACT,
                            RELATED_FIX_ID,
                            PRIORITY
                        ) VALUES (
                            SEQ_CRAWL_STRATEGY_CHANGES.NEXTVAL,
                            :new_strategy_id,
                            :evaluation_id,
                            :sequence,
                            :category,
                            :target_location,
                            :description,
                            :value_before,
                            :value_after,
                            :rationale,
                            :expected_impact,
                            :related_fix_id,
                            :priority
                        )
                    """

                    cursor.execute(sql_strategy_change, {
                        'new_strategy_id': new_strategy_id,
                        'evaluation_id': evaluation_id,
                        'sequence': seq,
                        'category': change.get('change_type', 'selector_update'),
                        'target_location': change.get('location', change.get('target_location')),
                        'description': json.dumps(change.get('description', ''), ensure_ascii=False),
                        'value_before': json.dumps(change.get('before_value', {}), ensure_ascii=False),
                        'value_after': json.dumps(change.get('after_value', {}), ensure_ascii=False),
                        'rationale': json.dumps(change.get('rationale', ''), ensure_ascii=False),
                        'expected_impact': change.get('expected_impact', 'medium'),
                        'related_fix_id': change.get('change_code', f'CHG-{seq:03d}'),
                        'priority': change.get('priority', seq)
                    })

                # === 3. Write to CRAWL_PIPELINE_EXECUTIONS (full JSON) ===
                sql_pipeline = """
                    UPDATE CRAWL_PIPELINE_EXECUTIONS
                    SET STEP5_STATUS = 'success',
                        STEP5_REFINEMENT_JSON = :refinement_json,
                        STEP5_COMPLETED_AT = SYSTIMESTAMP,
                        STEP5_DURATION_SEC = :duration_sec,
                        FINAL_SUCCESS_RATE = :final_success_rate,
                        REFINEMENT_CYCLE = :refinement_cycle,
                        CHANGES_APPLIED = :changes_applied,
                        FINAL_STRATEGY_VERSION = :final_version,
                        FINAL_STRATEGY_ID = :new_strategy_id,
                        EXECUTION_STATUS = 'completed',
                        COMPLETED_AT = SYSTIMESTAMP
                    WHERE EXECUTION_ID = :exec_id
                """

                cursor.execute(sql_pipeline, {
                    'exec_id': execution_id,
                    'refinement_json': refinement_json,
                    'duration_sec': duration_sec,
                    'final_success_rate': final_success_rate,
                    'refinement_cycle': refinement_cycle,
                    'changes_applied': changes_applied,
                    'final_version': final_version,
                    'new_strategy_id': new_strategy_id
                })

                # === 4. Write to CRAWL_PIPELINE_REFINEMENTS (individual changes) ===
                changes = refinement.get('changes', [])
                for seq, change in enumerate(changes, 1):
                    sql_refinement = """
                        INSERT INTO CRAWL_PIPELINE_REFINEMENTS (
                            REFINEMENT_ID,
                            EXECUTION_ID,
                            CHANGE_CODE,
                            CHANGE_SEQUENCE,
                            CHANGE_TYPE,
                            CHANGE_CATEGORY,
                            CHANGE_DESCRIPTION,
                            BEFORE_VALUE,
                            AFTER_VALUE,
                            DIFF_SUMMARY,
                            STRATEGY_SECTION,
                            EXPECTED_IMPACT,
                            EXPECTED_IMPROVEMENT
                        ) VALUES (
                            SEQ_CRAWL_PIPELINE_REFINEMENTS.NEXTVAL,
                            :exec_id,
                            :change_code,
                            :sequence,
                            :change_type,
                            :category,
                            :description,
                            :before_value,
                            :after_value,
                            :diff_summary,
                            :strategy_section,
                            :expected_impact,
                            :expected_improvement
                        )
                    """

                    cursor.execute(sql_refinement, {
                        'exec_id': execution_id,
                        'change_code': change.get('change_code', f'CHG-{seq:03d}'),
                        'sequence': seq,
                        'change_type': change.get('change_type'),
                        'category': change.get('category'),
                        'description': change.get('description'),
                        'before_value': json.dumps(change.get('before_value', {}), ensure_ascii=False),
                        'after_value': json.dumps(change.get('after_value', {}), ensure_ascii=False),
                        'diff_summary': change.get('diff_summary'),
                        'strategy_section': change.get('strategy_section'),
                        'expected_impact': change.get('expected_impact'),
                        'expected_improvement': change.get('expected_improvement')
                    })

                # === 5. Commit all writes atomically ===
                conn.commit()
                logger.info(f"✅ Step 5 saved (DUAL): execution={execution_id}, new_strategy_id={new_strategy_id}, changes={len(changes)}")
                return new_strategy_id

            except Exception as e:
                logger.error(f"❌ Error saving Step 5 (DUAL): {e}")
                conn.rollback()
                return None

    def mark_execution_failed(self, execution_id: int, step: int, error_message: str):
        """
        Mark execution as failed at a specific step

        Args:
            execution_id: Pipeline execution ID
            step: Failed step number (0-5)
            error_message: Error description
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            sql = f"""
                UPDATE CRAWL_PIPELINE_EXECUTIONS
                SET STEP{step}_STATUS = 'failed',
                    STEP{step}_ERROR_MESSAGE = :error_message,
                    EXECUTION_STATUS = 'failed',
                    COMPLETED_AT = SYSTIMESTAMP
                WHERE EXECUTION_ID = :exec_id
            """

            cursor.execute(sql, {
                'exec_id': execution_id,
                'error_message': error_message[:1000]  # Truncate to 1000 chars
            })

            conn.commit()
            logger.warning(f"⚠️ Execution {execution_id} marked as failed at step {step}")

    # =========================================================================
    # Retrieval Methods
    # =========================================================================

    def get_execution_summary(self, execution_id: int) -> Optional[Dict[str, Any]]:
        """
        Get execution summary without loading large CLOBs

        Args:
            execution_id: Pipeline execution ID

        Returns:
            Execution summary dictionary
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            sql = """
                SELECT
                    EXECUTION_ID,
                    TARGET_ID,
                    EXECUTION_STATUS,
                    STEP0_STATUS, STEP0_HTML_SIZE,
                    STEP1_STATUS, ANALYSIS_CONFIDENCE,
                    STEP2_STATUS, ESTIMATED_SUCCESS_RATE,
                    STEP3_STATUS, ACTUAL_SUCCESS_RATE, TOTAL_TESTS, PASSED_TESTS,
                    STEP4_STATUS, TOTAL_FIXES_NEEDED,
                    STEP5_STATUS, FINAL_SUCCESS_RATE,
                    STARTED_AT, COMPLETED_AT,
                    TOTAL_DURATION_SEC
                FROM CRAWL_PIPELINE_EXECUTIONS
                WHERE EXECUTION_ID = :exec_id
            """

            cursor.execute(sql, {'exec_id': execution_id})
            row = cursor.fetchone()

            if not row:
                return None

            return {
                'execution_id': row[0],
                'target_id': row[1],
                'execution_status': row[2],
                'step0': {'status': row[3], 'html_size': row[4]},
                'step1': {'status': row[5], 'confidence': float(row[6]) if row[6] else None},
                'step2': {'status': row[7], 'estimated_rate': float(row[8]) if row[8] else None},
                'step3': {'status': row[9], 'actual_rate': float(row[10]) if row[10] else None,
                         'total_tests': row[11], 'passed_tests': row[12]},
                'step4': {'status': row[13], 'total_fixes': row[14]},
                'step5': {'status': row[15], 'final_rate': float(row[16]) if row[16] else None},
                'started_at': row[17],
                'completed_at': row[18],
                'duration_sec': float(row[19]) if row[19] else None
            }

    def read_step0_html(self, execution_id: int) -> Optional[str]:
        """
        Read Step 0 HTML content (may be large)

        Args:
            execution_id: Pipeline execution ID

        Returns:
            Complete HTML content or None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            sql = """
                SELECT STEP0_HTML_CONTENT
                FROM CRAWL_PIPELINE_EXECUTIONS
                WHERE EXECUTION_ID = :exec_id
            """

            cursor.execute(sql, {'exec_id': execution_id})
            row = cursor.fetchone()

            if not row or not row[0]:
                return None

            # Handle CLOB reading (python-oracledb automatically converts to string)
            html_content = row[0].read() if hasattr(row[0], 'read') else row[0]

            return html_content

    def read_step_json(self, execution_id: int, step: int) -> Optional[Dict[str, Any]]:
        """
        Read JSON artifact from a specific step

        Args:
            execution_id: Pipeline execution ID
            step: Step number (1, 2, 3, 4, or 5)

        Returns:
            Parsed JSON dictionary or None
        """
        column_map = {
            1: 'STEP1_ANALYSIS_JSON',
            2: 'STEP2_STRATEGY_JSON',
            3: 'STEP3_VALIDATION_JSON',
            4: 'STEP4_EVALUATION_JSON',
            5: 'STEP5_REFINEMENT_JSON'
        }

        if step not in column_map:
            raise ValueError(f"Invalid step number: {step}. Must be 1-5.")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            sql = f"""
                SELECT {column_map[step]}
                FROM CRAWL_PIPELINE_EXECUTIONS
                WHERE EXECUTION_ID = :exec_id
            """

            cursor.execute(sql, {'exec_id': execution_id})
            row = cursor.fetchone()

            if not row or not row[0]:
                return None

            # Handle CLOB reading
            json_content = row[0].read() if hasattr(row[0], 'read') else row[0]

            return json.loads(json_content)

    @staticmethod
    def _infer_test_type(test_name: str) -> str:
        """Infer test type from test name"""
        if 'page_load' in test_name:
            return 'page_load'
        elif 'list_extraction' in test_name:
            return 'extraction'
        elif 'content_extraction' in test_name:
            return 'content'
        else:
            return 'other'

    @staticmethod
    def _normalize_test_status(status: Optional[str]) -> str:
        """
        Normalize test status to match CHK_TEST_STATUS constraint

        Allowed values: 'success', 'failed', 'skipped', 'timeout'

        Args:
            status: Raw status value from JSON

        Returns:
            Normalized status value
        """
        if not status:
            return 'skipped'

        status_lower = status.lower().strip()

        # Map common variations to standard values
        status_map = {
            # Success variants
            'success': 'success',
            'passed': 'success',
            'pass': 'success',
            'ok': 'success',
            'warning': 'success',  # Warning but succeeded
            'warn': 'success',

            # Failed variants
            'failed': 'failed',
            'fail': 'failed',
            'error': 'failed',
            'failure': 'failed',

            # Skipped variants
            'skipped': 'skipped',
            'skip': 'skipped',
            'ignored': 'skipped',

            # Timeout variants
            'timeout': 'timeout',
            'timedout': 'timeout',
        }

        normalized = status_map.get(status_lower, 'failed')  # Default to 'failed' for unknown

        if status_lower not in status_map:
            logger.warning(f"⚠️ Unknown test status '{status}' normalized to '{normalized}'")

        return normalized


if __name__ == '__main__':
    # Test code
    import os
    os.environ['USE_PYTHON_ORACLEDB'] = 'true'

    manager = PipelineArtifactManager()

    # Test execution creation
    execution_id = manager.create_execution(target_id=56, triggered_by='test')
    print(f"✅ Created test execution: {execution_id}")

    # Test Step 0 HTML save
    test_html = "<html><body><h1>Test HTML</h1></body></html>"
    success = manager.save_step0_html(
        execution_id=execution_id,
        html_content=test_html,
        file_path='/tmp/test.html',
        duration_sec=1.0
    )
    print(f"✅ Step 0 HTML saved: {success}")

    # Test retrieval
    summary = manager.get_execution_summary(execution_id)
    print(f"✅ Execution summary: {summary}")

    # Test HTML retrieval
    html = manager.read_step0_html(execution_id)
    print(f"✅ Retrieved HTML: {len(html)} bytes")
