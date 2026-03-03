#!/usr/bin/env python3
# Generated: 2025-10-16 13:45:00 KST
"""
Database Query Tool - Interactive database exploration utility

Features:
1. List all database tables
2. Show table schema and overview
3. Query records by primary key
"""

import os
import sys
from typing import Optional, List, Tuple

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


class DatabaseQueryTool:
    """Interactive database query tool"""

    def __init__(self):
        self.db = CrawlDatabaseManager()

    def list_all_tables(self) -> List[Tuple[str, int, str]]:
        """
        1. 데이터베이스 테이블 전체 조회

        Returns:
            List of (table_name, num_rows, last_analyzed) tuples
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    TABLE_NAME,
                    NUM_ROWS,
                    TO_CHAR(LAST_ANALYZED, 'YYYY-MM-DD HH24:MI:SS') AS LAST_ANALYZED,
                    TABLESPACE_NAME
                FROM USER_TABLES
                ORDER BY TABLE_NAME
            """

            cursor.execute(query)
            results = cursor.fetchall()

            print("\n" + "="*100)
            print("📋 DATABASE TABLES (OCR_ADMIN Schema)")
            print("="*100)
            print(f"{'Table Name':<40} {'Rows':<12} {'Last Analyzed':<20} {'Tablespace':<20}")
            print("-"*100)

            for row in results:
                table_name = row[0] if row[0] else "N/A"
                num_rows = row[1] if row[1] is not None else 0
                last_analyzed = row[2] if row[2] else "Not analyzed"
                tablespace = row[3] if row[3] else "N/A"

                print(f"{table_name:<40} {num_rows:<12,} {last_analyzed:<20} {tablespace:<20}")

            print("-"*100)
            print(f"Total tables: {len(results)}\n")

            return results

    def show_table_overview(self, table_name: str) -> None:
        """
        2. 테이블명을 입력받아서 해당 테이블의 개요 조회

        Shows:
        - Column definitions (name, type, nullable, default)
        - Primary key constraints
        - Foreign key constraints
        - Indexes
        - Sample row count

        Args:
            table_name: Table name to inspect (case-insensitive)
        """
        table_name = table_name.upper()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Check if table exists
            cursor.execute("""
                SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = :1
            """, (table_name,))

            if cursor.fetchone()[0] == 0:
                print(f"\n❌ Table '{table_name}' not found in OCR_ADMIN schema.")
                return

            print("\n" + "="*100)
            print(f"📊 TABLE OVERVIEW: {table_name}")
            print("="*100)

            # 1. Column definitions
            print("\n📝 COLUMNS:")
            cursor.execute("""
                SELECT
                    COLUMN_NAME,
                    DATA_TYPE,
                    DATA_LENGTH,
                    DATA_PRECISION,
                    DATA_SCALE,
                    NULLABLE,
                    DATA_DEFAULT
                FROM USER_TAB_COLUMNS
                WHERE TABLE_NAME = :1
                ORDER BY COLUMN_ID
            """, (table_name,))

            print(f"{'Column Name':<30} {'Type':<20} {'Nullable':<10} {'Default':<20}")
            print("-"*100)

            for row in cursor:
                col_name = row[0]
                data_type = row[1]

                # Format data type with precision/scale
                if data_type == 'NUMBER':
                    if row[3] is not None:
                        if row[4] is not None and row[4] > 0:
                            type_str = f"NUMBER({row[3]},{row[4]})"
                        else:
                            type_str = f"NUMBER({row[3]})"
                    else:
                        type_str = "NUMBER"
                elif data_type in ('VARCHAR2', 'CHAR'):
                    type_str = f"{data_type}({row[2]})"
                else:
                    type_str = data_type

                nullable = "NULL" if row[5] == 'Y' else "NOT NULL"
                default_val = str(row[6]).strip() if row[6] else ""

                print(f"{col_name:<30} {type_str:<20} {nullable:<10} {default_val:<20}")

            # 2. Primary Key
            print("\n🔑 PRIMARY KEY:")
            cursor.execute("""
                SELECT
                    c.CONSTRAINT_NAME,
                    LISTAGG(cc.COLUMN_NAME, ', ') WITHIN GROUP (ORDER BY cc.POSITION) AS PK_COLUMNS
                FROM USER_CONSTRAINTS c
                JOIN USER_CONS_COLUMNS cc ON c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
                WHERE c.TABLE_NAME = :1
                  AND c.CONSTRAINT_TYPE = 'P'
                GROUP BY c.CONSTRAINT_NAME
            """, (table_name,))

            pk_row = cursor.fetchone()
            if pk_row:
                print(f"  Constraint: {pk_row[0]}")
                print(f"  Columns: {pk_row[1]}")
            else:
                print("  No primary key defined")

            # 3. Foreign Keys
            print("\n🔗 FOREIGN KEYS:")
            cursor.execute("""
                SELECT
                    c.CONSTRAINT_NAME,
                    LISTAGG(cc.COLUMN_NAME, ', ') WITHIN GROUP (ORDER BY cc.POSITION) AS FK_COLUMNS,
                    c.R_CONSTRAINT_NAME,
                    (SELECT TABLE_NAME FROM USER_CONSTRAINTS WHERE CONSTRAINT_NAME = c.R_CONSTRAINT_NAME) AS REF_TABLE
                FROM USER_CONSTRAINTS c
                JOIN USER_CONS_COLUMNS cc ON c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
                WHERE c.TABLE_NAME = :1
                  AND c.CONSTRAINT_TYPE = 'R'
                GROUP BY c.CONSTRAINT_NAME, c.R_CONSTRAINT_NAME
            """, (table_name,))

            fk_rows = cursor.fetchall()
            if fk_rows:
                for fk_row in fk_rows:
                    print(f"  {fk_row[0]}: {fk_row[1]} → {fk_row[3]}")
            else:
                print("  No foreign keys defined")

            # 4. Indexes
            print("\n📇 INDEXES:")
            cursor.execute("""
                SELECT
                    i.INDEX_NAME,
                    i.UNIQUENESS,
                    LISTAGG(ic.COLUMN_NAME, ', ') WITHIN GROUP (ORDER BY ic.COLUMN_POSITION) AS INDEX_COLUMNS
                FROM USER_INDEXES i
                JOIN USER_IND_COLUMNS ic ON i.INDEX_NAME = ic.INDEX_NAME
                WHERE i.TABLE_NAME = :1
                GROUP BY i.INDEX_NAME, i.UNIQUENESS
                ORDER BY i.INDEX_NAME
            """, (table_name,))

            idx_rows = cursor.fetchall()
            if idx_rows:
                for idx_row in idx_rows:
                    uniqueness = "UNIQUE" if idx_row[1] == 'UNIQUE' else "NON-UNIQUE"
                    print(f"  {idx_row[0]} ({uniqueness}): {idx_row[2]}")
            else:
                print("  No indexes defined")

            # 5. Row count
            print("\n📊 DATA STATISTICS:")
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            print(f"  Total rows: {row_count:,}")

            # 6. Table comments
            cursor.execute("""
                SELECT COMMENTS
                FROM USER_TAB_COMMENTS
                WHERE TABLE_NAME = :1
            """, (table_name,))

            comment_row = cursor.fetchone()
            if comment_row and comment_row[0]:
                print(f"\n💬 TABLE COMMENT:")
                print(f"  {comment_row[0]}")

            print("\n" + "="*100 + "\n")

    def query_by_primary_key(self, table_name: str, pk_value: str) -> None:
        """
        3. 테이블명과 PK를 입력받아서 그 내용을 조회

        Args:
            table_name: Table name (case-insensitive)
            pk_value: Primary key value to search
        """
        table_name = table_name.upper()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get primary key column name
            cursor.execute("""
                SELECT cc.COLUMN_NAME
                FROM USER_CONSTRAINTS c
                JOIN USER_CONS_COLUMNS cc ON c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
                WHERE c.TABLE_NAME = :1
                  AND c.CONSTRAINT_TYPE = 'P'
                ORDER BY cc.POSITION
            """, (table_name,))

            pk_columns = [row[0] for row in cursor.fetchall()]

            if not pk_columns:
                print(f"\n❌ No primary key found for table '{table_name}'")
                return

            if len(pk_columns) > 1:
                print(f"\n⚠️  Table has composite primary key: {', '.join(pk_columns)}")
                print(f"This tool currently supports single-column primary keys only.")
                return

            pk_column = pk_columns[0]

            # Get column data type
            cursor.execute("""
                SELECT DATA_TYPE
                FROM USER_TAB_COLUMNS
                WHERE TABLE_NAME = :1 AND COLUMN_NAME = :2
            """, (table_name, pk_column))

            data_type = cursor.fetchone()[0]

            # Build query
            query = f"SELECT * FROM {table_name} WHERE {pk_column} = :1"

            # Convert pk_value to appropriate type
            try:
                if data_type in ('NUMBER', 'FLOAT'):
                    pk_value_converted = float(pk_value) if '.' in pk_value else int(pk_value)
                else:
                    pk_value_converted = pk_value
            except ValueError:
                print(f"\n❌ Invalid primary key value '{pk_value}' for type {data_type}")
                return

            # Execute query
            cursor.execute(query, (pk_value_converted,))

            # Get column names
            columns = [desc[0] for desc in cursor.description]

            # Fetch result
            row = cursor.fetchone()

            if not row:
                print(f"\n❌ No record found with {pk_column} = {pk_value}")
                return

            # Display result
            print("\n" + "="*100)
            print(f"📄 RECORD FROM {table_name} (WHERE {pk_column} = {pk_value})")
            print("="*100)

            max_col_width = max(len(col) for col in columns)

            for col_name, col_value in zip(columns, row):
                # Format value for display
                if col_value is None:
                    display_value = "NULL"
                elif isinstance(col_value, (bytes, bytearray)):
                    display_value = f"<BLOB: {len(col_value)} bytes>"
                elif hasattr(col_value, 'read'):  # CLOB
                    clob_content = col_value.read()
                    if len(clob_content) > 200:
                        display_value = f"{clob_content[:200]}... (total: {len(clob_content)} chars)"
                    else:
                        display_value = clob_content
                else:
                    display_value = str(col_value)

                print(f"{col_name:<{max_col_width}}: {display_value}")

            print("\n" + "="*100 + "\n")

    def interactive_mode(self) -> None:
        """Run interactive CLI mode"""
        print("\n" + "="*100)
        print("🗄️  DATABASE QUERY TOOL")
        print("="*100)
        print(f"Connected to: {os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_SERVICE_NAME']}")
        print(f"Schema: {os.environ['DB_USERNAME']}")
        print("="*100)

        while True:
            print("\n📋 MENU:")
            print("  1. List all tables")
            print("  2. Show table overview")
            print("  3. Query record by primary key")
            print("  4. Exit")

            choice = input("\nSelect option (1-4): ").strip()

            if choice == '1':
                self.list_all_tables()

            elif choice == '2':
                table_name = input("\nEnter table name: ").strip()
                if table_name:
                    self.show_table_overview(table_name)
                else:
                    print("❌ Table name is required")

            elif choice == '3':
                table_name = input("\nEnter table name: ").strip()
                pk_value = input("Enter primary key value: ").strip()

                if table_name and pk_value:
                    self.query_by_primary_key(table_name, pk_value)
                else:
                    print("❌ Both table name and primary key value are required")

            elif choice == '4':
                print("\n👋 Goodbye!\n")
                break

            else:
                print("❌ Invalid option. Please select 1-4.")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Database Query Tool - Interactive database exploration utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python query_database.py

  # List all tables
  python query_database.py --list-tables

  # Show table overview
  python query_database.py --table CRAWL_TARGETS

  # Query by primary key
  python query_database.py --table CRAWL_TARGETS --pk 46
        """
    )

    parser.add_argument('--list-tables', action='store_true',
                       help='List all database tables')
    parser.add_argument('--table', type=str,
                       help='Table name to query')
    parser.add_argument('--pk', type=str,
                       help='Primary key value to query')

    args = parser.parse_args()

    tool = DatabaseQueryTool()

    # Non-interactive mode
    if args.list_tables:
        tool.list_all_tables()
    elif args.table and args.pk:
        tool.query_by_primary_key(args.table, args.pk)
    elif args.table:
        tool.show_table_overview(args.table)
    else:
        # Interactive mode
        tool.interactive_mode()


if __name__ == '__main__':
    main()
