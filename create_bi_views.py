import sqlite3

DB_PATH = "output/cleaned/ngo_impact_clean.db"
SQL_PATH = "sql/bi_views/create_views.sql"

conn = sqlite3.connect(DB_PATH)

# Create views
with open(SQL_PATH, "r", encoding="utf-8") as f:
    conn.executescript(f.read())

print("Views created successfully.\n")

# Validate each view
views = [
    "v_cost_per_impact",
    "v_programme_progress",
    "v_beneficiary_360",
    "v_outcome_effectiveness",
    "v_financial_overview",
]

for v in views:
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {v}")
    count = cursor.fetchone()[0]
    cursor.execute(f"PRAGMA table_info({v})")
    cols = len(cursor.fetchall())
    print(f"  {v:30s}  {count:>5} rows  x  {cols:>2} cols")

conn.close()
