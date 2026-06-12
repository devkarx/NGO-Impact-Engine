"""
Phase 3: KPI Query Validator

Executes all 4 KPI queries against the clean SQLite database,
measures execution time, and prints sample results to validate
correctness and performance.
"""

import sqlite3
import time
from pathlib import Path

DB_PATH = "output/cleaned/ngo_impact_clean.db"
QUERY_DIR = Path("sql/kpi_queries")


def run_query(conn: sqlite3.Connection, filepath: Path) -> None:
    """Execute a SQL file and print results with timing."""
    query = filepath.read_text(encoding="utf-8")

    # Strip comment-only lines for cleaner execution
    cursor = conn.cursor()

    print(f"\n{'='*70}")
    print(f"  {filepath.stem}")
    print(f"{'='*70}")

    start = time.perf_counter()
    cursor.execute(query)
    rows = cursor.fetchall()
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Get column names
    col_names = [desc[0] for desc in cursor.description]

    print(f"  Execution time: {elapsed_ms:.1f} ms")
    print(f"  Rows returned:  {len(rows)}")
    print(f"  Columns:        {len(col_names)}")
    print(f"\n  Columns: {', '.join(col_names)}")

    # Print first 5 rows
    print("\n  Sample rows (first 5):")
    for i, row in enumerate(rows[:5]):
        print(f"    [{i+1}] {dict(zip(col_names, row))}")

    # Performance check
    if elapsed_ms < 3000:
        print(f"\n  [PASS] {elapsed_ms:.1f}ms < 3000ms page load target")
    else:
        print(f"\n  [FAIL] {elapsed_ms:.1f}ms >= 3000ms page load target")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)

    print("NGO Impact Dashboard — KPI Query Validation")
    print(f"Database: {DB_PATH}")

    query_files = sorted(QUERY_DIR.glob("kpi*.sql"))
    print(f"Queries found: {len(query_files)}")

    total_ms = 0.0
    for qf in query_files:
        try:
            start = time.perf_counter()
            run_query(conn, qf)
            total_ms += (time.perf_counter() - start) * 1000
        except Exception as e:
            print(f"\n  [ERROR] in {qf.stem}: {e}")

    print(f"\n{'='*70}")
    print(f"  TOTAL execution time: {total_ms:.1f} ms")
    print(f"  Average per query:    {total_ms / max(len(query_files), 1):.1f} ms")
    print(f"{'='*70}")

    conn.close()


if __name__ == "__main__":
    main()
