#!/usr/bin/env python3
# Generated: 2025-10-16 13:56:00 KST
"""
Pipeline Results Importer - Import JSON files from results/ folder to database

Scans results/ folder for pipeline execution artifacts and imports them to:
- CRAWL_TARGETS (site information)
- CRAWL_PIPELINE_EXECUTIONS (Step 0-5 results in wide table format)
- CRAWL_STRATEGIES (Step 2: normalized strategy metadata)
- CRAWL_VALIDATIONS (Step 3: normalized validation metadata)
- CRAWL_EVALUATIONS (Step 4: normalized evaluation metadata)
- CRAWL_STRATEGY_CHANGES (Step 5: normalized refinement metadata)

Note: Uses PipelineArtifactManager for dual storage pattern (wide + normalized tables)
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add scholar/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Set Oracle environment
os.environ['USE_PYTHON_ORACLEDB'] = 'true'
os.environ['DB_HOST'] = os.getenv('DB_HOST', '192.168.75.194')
os.environ['DB_PORT'] = os.getenv('DB_PORT', '1521')
os.environ['DB_SERVICE_NAME'] = os.getenv('DB_SERVICE_NAME', 'XEPDB1')
os.environ['DB_USERNAME'] = os.getenv('DB_USERNAME', 'ocr_admin')
os.environ['DB_PASSWORD'] = os.getenv('DB_PASSWORD', 'admin_password')

from database.crawl_db_manager import CrawlDatabaseManager
from database.pipeline_artifact_manager import PipelineArtifactManager


class PipelineResultsImporter:
    """Import pipeline results from JSON files to database"""

    def __init__(self, results_dir: str = "/Users/memmem/git/en-zine/results"):
        self.results_dir = Path(results_dir)
        self.db = CrawlDatabaseManager()
        self.artifact_manager = PipelineArtifactManager()

        # Statistics
        self.stats = {
            'sites_found': 0,
            'sites_created': 0,
            'sites_skipped': 0,
            'executions_created': 0,
            'steps_imported': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            'errors': []
        }

    def scan_results_folder(self) -> List[Tuple[str, Path]]:
        """
        Scan results/ folder for site-specific result folders

        Returns:
            List of (site_name, folder_path) tuples
        """
        site_folders = []

        if not self.results_dir.exists():
            print(f"❌ Results directory not found: {self.results_dir}")
            return []

        for item in self.results_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Extract site name and ID from folder name
                # Format: "사이트명_ID" or "사이트명"
                site_folders.append((item.name, item))

        return sorted(site_folders)

    def parse_folder_name(self, folder_name: str) -> Tuple[str, Optional[int]]:
        """
        Parse folder name to extract site name and target ID

        Examples:
            "하이닥_46" -> ("하이닥", 46)
            "경향신문_9" -> ("경향신문", 9)

        Returns:
            (site_name, target_id or None)
        """
        match = re.match(r'^(.+?)_(\d+)$', folder_name)
        if match:
            return match.group(1), int(match.group(2))
        else:
            return folder_name, None

    def find_json_files(self, folder: Path) -> Dict[str, Path]:
        """
        Find all pipeline JSON files in a folder

        Returns:
            Dict of {step_name: file_path}
        """
        files = {}

        file_patterns = {
            'html_meta': 'step0_html.meta.json',
            'analysis': 'step1_analysis.json',
            'strategy': 'step2_strategy.json',
            'validation': 'step3_validation.json',
            'evaluation': 'step4_evaluation.json',
            'refinement': 'step5_refinement.json',
        }

        for key, pattern in file_patterns.items():
            for file in folder.glob(pattern):
                files[key] = file
                break

        return files

    def ensure_target_exists(self, site_name: str, target_id: Optional[int] = None,
                            site_url: Optional[str] = None) -> int:
        """
        Ensure CRAWL_TARGETS record exists, create if not

        Args:
            site_name: Site name
            target_id: Existing target ID (if known)
            site_url: Site URL (if available)

        Returns:
            target_id
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # If target_id provided, check if exists
            if target_id:
                cursor.execute("""
                    SELECT TARGET_ID, SITE_URL FROM CRAWL_TARGETS WHERE TARGET_ID = :1
                """, (target_id,))
                row = cursor.fetchone()
                if row:
                    print(f"  ✓ Found existing target: {site_name} (ID={target_id})")
                    return target_id

            # Try to find by site_name
            cursor.execute("""
                SELECT TARGET_ID, SITE_URL FROM CRAWL_TARGETS WHERE SITE_NAME = :1
            """, (site_name,))
            row = cursor.fetchone()
            if row:
                print(f"  ✓ Found existing target by name: {site_name} (ID={row[0]})")
                return row[0]

            # Try to find by site_url (if provided)
            if site_url:
                cursor.execute("""
                    SELECT TARGET_ID, SITE_NAME FROM CRAWL_TARGETS WHERE SITE_URL = :1
                """, (site_url,))
                row = cursor.fetchone()
                if row:
                    print(f"  ✓ Found existing target by URL: {site_url} (ID={row[0]}, Name={row[1]})")
                    return row[0]

            # Create new target
            if not site_url:
                site_url = f"https://example.com/{site_name}"  # Placeholder

            new_id_var = cursor.var(int)
            cursor.execute("""
                INSERT INTO CRAWL_TARGETS (
                    TARGET_ID, SITE_URL, SITE_NAME, STATUS, PRIORITY, CREATED_AT, UPDATED_AT
                ) VALUES (
                    CRAWL_TARGETS_SEQ.NEXTVAL,
                    :site_url,
                    :site_name,
                    'pending',
                    5,
                    SYSTIMESTAMP,
                    SYSTIMESTAMP
                )
                RETURNING TARGET_ID INTO :new_id
            """, {
                'site_url': site_url,
                'site_name': site_name,
                'new_id': new_id_var
            })
            new_id = new_id_var.getvalue()[0]
            conn.commit()

            print(f"  ✓ Created new target: {site_name} (ID={new_id})")
            self.stats['sites_created'] += 1
            return new_id

    def ensure_execution_exists(self, target_id: int) -> int:
        """
        Ensure CRAWL_PIPELINE_EXECUTIONS record exists, create if not

        Returns:
            execution_id
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Check if execution exists for this target
            cursor.execute("""
                SELECT EXECUTION_ID FROM CRAWL_PIPELINE_EXECUTIONS
                WHERE TARGET_ID = :1
                ORDER BY CREATED_AT DESC
                FETCH FIRST 1 ROWS ONLY
            """, (target_id,))
            row = cursor.fetchone()

            if row:
                print(f"  ✓ Found existing execution: {row[0]}")
                return row[0]

            # Create new execution
            new_id_var = cursor.var(int)
            cursor.execute("""
                INSERT INTO CRAWL_PIPELINE_EXECUTIONS (
                    EXECUTION_ID,
                    TARGET_ID,
                    EXECUTION_STATUS,
                    CREATED_AT
                ) VALUES (
                    SEQ_CRAWL_PIPELINE_EXECUTIONS.NEXTVAL,
                    :target_id,
                    'in_progress',
                    SYSTIMESTAMP
                )
                RETURNING EXECUTION_ID INTO :new_id
            """, {
                'target_id': target_id,
                'new_id': new_id_var
            })
            new_id = new_id_var.getvalue()[0]
            conn.commit()

            print(f"  ✓ Created new execution: {new_id}")
            self.stats['executions_created'] += 1
            return new_id

    def check_step_exists(self, execution_id: int, step_number: int) -> bool:
        """
        Check if a step has already been imported

        Checks CRAWL_PIPELINE_EXECUTIONS.STEP*_STATUS column
        Returns True if status is not 'pending' (i.e., completed/failed/in_progress)
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Map step number to column name
            status_column = f"STEP{step_number}_STATUS"

            cursor.execute(f"""
                SELECT {status_column}
                FROM CRAWL_PIPELINE_EXECUTIONS
                WHERE EXECUTION_ID = :1
            """, (execution_id,))

            row = cursor.fetchone()
            if not row:
                return False

            status = row[0]
            # Consider step as existing if status is not 'pending'
            return status is not None and status != 'pending'

    def import_step0_html(self, execution_id: int, target_id: int, meta_file: Path) -> bool:
        """Import Step 0 HTML collection metadata"""
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            # Check if already imported
            if self.check_step_exists(execution_id, 0):
                print(f"    ⊘ Step 0 already imported")
                return False

            # Read HTML content from file
            html_path = meta.get('html_path', '')
            html_content = ''
            if html_path and os.path.exists(html_path):
                with open(html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()

            # Import using artifact manager
            # Signature: save_step0_html(execution_id, html_content, file_path, duration_sec)
            self.artifact_manager.save_step0_html(
                execution_id=execution_id,
                html_content=html_content,
                file_path=html_path,
                duration_sec=meta.get('duration_sec', 0.0)
            )

            print(f"    ✓ Imported Step 0: HTML collection")
            self.stats['steps_imported'][0] += 1
            return True

        except Exception as e:
            error_msg = f"Error importing Step 0: {e}"
            print(f"    ✗ {error_msg}")
            self.stats['errors'].append(error_msg)
            return False

    def import_step1_analysis(self, execution_id: int, target_id: int, analysis_file: Path) -> bool:
        """Import Step 1 site analysis"""
        try:
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis = json.load(f)

            # Check if already imported
            if self.check_step_exists(execution_id, 1):
                print(f"    ⊘ Step 1 already imported")
                return False

            # Import using artifact manager
            # Signature: save_step1_analysis(execution_id, analysis, duration_sec, target_id)
            self.artifact_manager.save_step1_analysis(
                execution_id=execution_id,
                analysis=analysis,
                duration_sec=analysis.get('metadata', {}).get('analysis_duration_seconds', 0.0),
                target_id=target_id
            )

            print(f"    ✓ Imported Step 1: Site analysis")
            self.stats['steps_imported'][1] += 1
            return True

        except Exception as e:
            error_msg = f"Error importing Step 1: {e}"
            print(f"    ✗ {error_msg}")
            self.stats['errors'].append(error_msg)
            return False

    def import_step2_strategy(self, execution_id: int, target_id: int, strategy_file: Path) -> bool:
        """Import Step 2 crawling strategy"""
        try:
            with open(strategy_file, 'r', encoding='utf-8') as f:
                strategy = json.load(f)

            # Check if already imported
            if self.check_step_exists(execution_id, 2):
                print(f"    ⊘ Step 2 already imported")
                return False

            # Import using artifact manager
            # Signature: save_step2_strategy(execution_id, strategy, duration_sec, target_id)
            self.artifact_manager.save_step2_strategy(
                execution_id=execution_id,
                strategy=strategy,
                duration_sec=strategy.get('metadata', {}).get('generation_duration_seconds', 0.0),
                target_id=target_id
            )

            print(f"    ✓ Imported Step 2: Crawling strategy")
            self.stats['steps_imported'][2] += 1
            return True

        except Exception as e:
            error_msg = f"Error importing Step 2: {e}"
            print(f"    ✗ {error_msg}")
            self.stats['errors'].append(error_msg)
            return False

    def import_step3_validation(self, execution_id: int, target_id: int, validation_file: Path) -> bool:
        """Import Step 3 validation results"""
        try:
            with open(validation_file, 'r', encoding='utf-8') as f:
                validation = json.load(f)

            # Check if already imported
            if self.check_step_exists(execution_id, 3):
                print(f"    ⊘ Step 3 already imported")
                return False

            # Get latest strategy_id for this target
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(STRATEGY_ID) FROM CRAWL_STRATEGIES WHERE TARGET_ID = :1
                """, (target_id,))
                strategy_id = cursor.fetchone()[0]

            if not strategy_id:
                print(f"    ⚠ No strategy found for target {target_id}, skipping validation")
                return False

            # Import using artifact manager
            # Signature: save_step3_validation(execution_id, validation_results, duration_sec, target_id, strategy_id)
            self.artifact_manager.save_step3_validation(
                execution_id=execution_id,
                validation_results=validation,
                duration_sec=0.0,  # Not available in file
                target_id=target_id,
                strategy_id=strategy_id
            )

            print(f"    ✓ Imported Step 3: Validation results")
            self.stats['steps_imported'][3] += 1
            return True

        except Exception as e:
            error_msg = f"Error importing Step 3: {e}"
            print(f"    ✗ {error_msg}")
            self.stats['errors'].append(error_msg)
            return False

    def import_step4_evaluation(self, execution_id: int, target_id: int, evaluation_file: Path) -> bool:
        """Import Step 4 issue evaluation"""
        try:
            with open(evaluation_file, 'r', encoding='utf-8') as f:
                evaluation = json.load(f)

            # Check if already imported
            if self.check_step_exists(execution_id, 4):
                print(f"    ⊘ Step 4 already imported")
                return False

            # Get latest validation_id
            # CRAWL_VALIDATIONS now has TARGET_ID (denormalized)
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(VALIDATION_ID)
                    FROM CRAWL_VALIDATIONS
                    WHERE TARGET_ID = :1
                """, (target_id,))
                validation_id = cursor.fetchone()[0]

            if not validation_id:
                print(f"    ⚠ No validation found for target {target_id}, skipping evaluation")
                return False

            # Import using artifact manager
            # Signature: save_step4_evaluation(execution_id, evaluation, duration_sec, target_id, validation_id)
            self.artifact_manager.save_step4_evaluation(
                execution_id=execution_id,
                evaluation=evaluation,
                duration_sec=evaluation.get('metadata', {}).get('evaluation_duration_seconds', 0.0),
                target_id=target_id,
                validation_id=validation_id
            )

            print(f"    ✓ Imported Step 4: Issue evaluation")
            self.stats['steps_imported'][4] += 1
            return True

        except Exception as e:
            error_msg = f"Error importing Step 4: {e}"
            print(f"    ✗ {error_msg}")
            self.stats['errors'].append(error_msg)
            return False

    def import_step5_refinement(self, execution_id: int, target_id: int, refinement_file: Path) -> bool:
        """Import Step 5 strategy refinement"""
        try:
            with open(refinement_file, 'r', encoding='utf-8') as f:
                refinement = json.load(f)

            # Check if already imported
            if self.check_step_exists(execution_id, 5):
                print(f"    ⊘ Step 5 already imported")
                return False

            # Get old_strategy_id and evaluation_id
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(STRATEGY_ID) FROM CRAWL_STRATEGIES WHERE TARGET_ID = :1
                """, (target_id,))
                old_strategy_id = cursor.fetchone()[0]

                # CRAWL_EVALUATIONS now has TARGET_ID (denormalized)
                cursor.execute("""
                    SELECT MAX(EVALUATION_ID)
                    FROM CRAWL_EVALUATIONS
                    WHERE TARGET_ID = :1
                """, (target_id,))
                evaluation_id = cursor.fetchone()[0]

            if not old_strategy_id:
                print(f"    ⚠ No strategy found for target {target_id}, skipping refinement")
                return False

            # Import using artifact manager
            # Signature: save_step5_refinement(execution_id, refinement, duration_sec, target_id, old_strategy_id, evaluation_id)
            self.artifact_manager.save_step5_refinement(
                execution_id=execution_id,
                refinement=refinement,
                duration_sec=refinement.get('metadata', {}).get('refinement_duration_seconds', 0.0),
                target_id=target_id,
                old_strategy_id=old_strategy_id,
                evaluation_id=evaluation_id
            )

            print(f"    ✓ Imported Step 5: Strategy refinement")
            self.stats['steps_imported'][5] += 1
            return True

        except Exception as e:
            error_msg = f"Error importing Step 5: {e}"
            print(f"    ✗ {error_msg}")
            self.stats['errors'].append(error_msg)
            return False

    def import_site_results(self, site_name: str, folder: Path, skip_existing: bool = True) -> None:
        """
        Import all pipeline results for a single site

        Args:
            site_name: Site name from folder
            folder: Path to results folder
            skip_existing: Skip already imported steps
        """
        print(f"\n📁 Processing: {site_name}")

        # Parse folder name
        parsed_name, target_id = self.parse_folder_name(site_name)

        # Find JSON files
        json_files = self.find_json_files(folder)

        if not json_files:
            print(f"  ⊘ No JSON files found, skipping")
            self.stats['sites_skipped'] += 1
            return

        print(f"  Found {len(json_files)} JSON file(s): {', '.join(json_files.keys())}")

        # Extract site URL from strategy or analysis
        site_url = None
        if 'strategy' in json_files:
            with open(json_files['strategy'], 'r', encoding='utf-8') as f:
                strategy = json.load(f)
                site_url = strategy.get('site_url')
        elif 'analysis' in json_files:
            with open(json_files['analysis'], 'r', encoding='utf-8') as f:
                analysis = json.load(f)
                site_url = analysis.get('site_url')

        # Ensure target exists
        target_id = self.ensure_target_exists(parsed_name, target_id, site_url)

        # Ensure execution exists
        execution_id = self.ensure_execution_exists(target_id)

        # Import each step
        if 'html_meta' in json_files:
            self.import_step0_html(execution_id, target_id, json_files['html_meta'])

        if 'analysis' in json_files:
            self.import_step1_analysis(execution_id, target_id, json_files['analysis'])

        if 'strategy' in json_files:
            self.import_step2_strategy(execution_id, target_id, json_files['strategy'])

        if 'validation' in json_files:
            self.import_step3_validation(execution_id, target_id, json_files['validation'])

        if 'evaluation' in json_files:
            self.import_step4_evaluation(execution_id, target_id, json_files['evaluation'])

        if 'refinement' in json_files:
            self.import_step5_refinement(execution_id, target_id, json_files['refinement'])

        self.stats['sites_found'] += 1

    def import_all(self, skip_existing: bool = True, site_filter: Optional[str] = None) -> None:
        """
        Import all pipeline results from results/ folder

        Args:
            skip_existing: Skip already imported steps
            site_filter: Only import sites matching this name (optional)
        """
        print("="*80)
        print("🚀 PIPELINE RESULTS IMPORTER")
        print("="*80)
        print(f"Results directory: {self.results_dir}")
        print(f"Skip existing: {skip_existing}")
        if site_filter:
            print(f"Site filter: {site_filter}")
        print("="*80)

        # Scan folders
        site_folders = self.scan_results_folder()

        if not site_folders:
            print("\n❌ No site folders found in results directory")
            return

        print(f"\nFound {len(site_folders)} site folder(s)")

        # Import each site
        for site_name, folder in site_folders:
            if site_filter and site_filter not in site_name:
                continue

            try:
                self.import_site_results(site_name, folder, skip_existing)
            except Exception as e:
                error_msg = f"Failed to import {site_name}: {e}"
                print(f"  ✗ {error_msg}")
                self.stats['errors'].append(error_msg)

        # Print summary
        self.print_summary()

    def print_summary(self) -> None:
        """Print import statistics summary"""
        print("\n" + "="*80)
        print("📊 IMPORT SUMMARY")
        print("="*80)
        print(f"Sites found:          {self.stats['sites_found']}")
        print(f"Sites created:        {self.stats['sites_created']}")
        print(f"Sites skipped:        {self.stats['sites_skipped']}")
        print(f"Executions created:   {self.stats['executions_created']}")
        print("\nSteps imported:")
        for step_num, count in self.stats['steps_imported'].items():
            print(f"  Step {step_num}: {count}")

        total_steps = sum(self.stats['steps_imported'].values())
        print(f"\nTotal steps imported: {total_steps}")

        if self.stats['errors']:
            print(f"\n⚠️  Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more")

        print("="*80 + "\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Pipeline Results Importer - Import JSON files to database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import all results
  python import_pipeline_results.py

  # Import specific site
  python import_pipeline_results.py --site "하이닥"

  # Force re-import (overwrite existing)
  python import_pipeline_results.py --force

  # Custom results directory
  python import_pipeline_results.py --results-dir /path/to/results
        """
    )

    parser.add_argument('--results-dir', type=str,
                       default='/Users/memmem/git/en-zine/results',
                       help='Results directory path')
    parser.add_argument('--site', type=str,
                       help='Only import specific site (partial name match)')
    parser.add_argument('--force', action='store_true',
                       help='Force re-import even if already exists')

    args = parser.parse_args()

    # Create importer
    importer = PipelineResultsImporter(results_dir=args.results_dir)

    # Run import
    importer.import_all(
        skip_existing=not args.force,
        site_filter=args.site
    )


if __name__ == '__main__':
    main()
