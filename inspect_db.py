import sqlite3

conn = sqlite3.connect("output/cleaned/ngo_impact_clean.db")
c = conn.cursor()

# List tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("Tables:", tables)

# Check key columns and sample data
for t in [
    "beneficiaries",
    "assessments",
    "outcome_tracking",
    "expenses",
    "programs",
    "impact_indicators",
]:
    if t in tables:
        c.execute(f"PRAGMA table_info({t})")
        cols = [r[1] for r in c.fetchall()]
        c.execute(f"SELECT COUNT(*) FROM {t}")
        count = c.fetchone()[0]
        print(f"\n{t} ({count} rows): {cols}")

# Check sample assessment types
c.execute("SELECT DISTINCT assessment_type FROM assessments LIMIT 10")
print("\nAssessment types:", [r[0] for r in c.fetchall()])

# Check sample fiscal years in outcome tracking
c.execute("SELECT DISTINCT reporting_period FROM outcome_tracking LIMIT 10")
print("Reporting periods:", [r[0] for r in c.fetchall()])

# Check sample IRIS indicators
c.execute(
    "SELECT indicator_id, iris_id, indicator_name, sector FROM impact_indicators LIMIT 5"
)
for r in c.fetchall():
    print(f"  {r}")

conn.close()
