-- ============================================================================
-- KPI 1: COST-PER-IMPACT BY PROGRAM & IRIS+ INDICATOR
-- ============================================================================
--
-- THE #1 METRIC FOR ANY EXECUTIVE DIRECTOR
--
-- What it answers:
--   "For every ₹1 we spend on Program X, how many units of outcome Y do we
--    produce?"  This is the single number the ED should check every Monday.
--
-- Theory of Change mapping:
--   Inputs (expenses) ÷ Outcomes (outcome_tracking × impact_indicators)
--   = Cost per unit of social impact
--
-- Performance notes:
--   - 3 CTEs prevent repeated table scans
--   - Pre-aggregation in CTEs reduces join cardinality
--   - Final join is on program_id (small dimension, ~12 rows)
--   - Expected execution: < 50ms on our dataset, < 500ms on 100K+ rows
--
-- Compatible with: PostgreSQL 14+, SQLite 3.35+, Metabase, Power BI, Tableau
-- ============================================================================

WITH
-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ CTE 1: Total expenditure per program, per fiscal year                  │
-- │                                                                        │
-- │ Why pre-aggregate: Expenses table can grow to 100K+ rows in a real     │
-- │ NGO. Aggregating first reduces the join surface to ~48 rows            │
-- │ (12 programs × 4 fiscal years).                                        │
-- └─────────────────────────────────────────────────────────────────────────┘
program_spend AS (
    SELECT
        e.program_id,
        e.fiscal_year,
        SUM(e.amount_inr)                         AS total_spend_inr,
        COUNT(e.expense_id)                       AS expense_count,
        SUM(CASE WHEN e.category = 'Personnel'
                 THEN e.amount_inr ELSE 0 END)    AS personnel_spend_inr,
        SUM(CASE WHEN e.category = 'Monitoring & Evaluation'
                 THEN e.amount_inr ELSE 0 END)    AS me_spend_inr
    FROM expenses e
    GROUP BY e.program_id, e.fiscal_year
),

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ CTE 2: Achieved outcomes per program × indicator × fiscal year         │
-- │                                                                        │
-- │ Extracts the fiscal year from the reporting_period string              │
-- │ (e.g., 'Q2-FY2023-24' → 'FY2023-24') to enable the cost join.        │
-- │                                                                        │
-- │ Only counts outcomes where actual_value > 0 to avoid division by zero. │
-- └─────────────────────────────────────────────────────────────────────────┘
program_outcomes AS (
    SELECT
        ot.program_id,
        ot.indicator_id,
        -- Extract fiscal year: 'Q2-FY2023-24' → 'FY2023-24'
        SUBSTR(ot.reporting_period, 4)            AS fiscal_year,
        SUM(ot.target_value)                      AS total_target,
        SUM(ot.actual_value)                      AS total_actual,
        COUNT(ot.outcome_id)                      AS quarters_reported,
        -- Achievement rate as a percentage
        ROUND(
            SUM(ot.actual_value) * 100.0
            / NULLIF(SUM(ot.target_value), 0),
            1
        )                                         AS achievement_pct
    FROM outcome_tracking ot
    WHERE ot.actual_value IS NOT NULL
      AND ot.actual_value > 0
    GROUP BY ot.program_id, ot.indicator_id, SUBSTR(ot.reporting_period, 4)
),

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ CTE 3: Enrich with program name, sector, and IRIS+ metadata           │
-- └─────────────────────────────────────────────────────────────────────────┘
enriched AS (
    SELECT
        p.program_id,
        p.program_name,
        p.sector,
        ii.iris_id,
        ii.indicator_name,
        ii.unit                                   AS indicator_unit,
        po.fiscal_year,
        po.total_target,
        po.total_actual,
        po.achievement_pct,
        po.quarters_reported,
        ps.total_spend_inr,
        ps.personnel_spend_inr,
        ps.me_spend_inr,
        ps.expense_count
    FROM program_outcomes po
    INNER JOIN programs p
        ON po.program_id = p.program_id
    INNER JOIN impact_indicators ii
        ON po.indicator_id = ii.indicator_id
    LEFT JOIN program_spend ps
        ON po.program_id = ps.program_id
       AND po.fiscal_year = ps.fiscal_year
)

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ FINAL SELECT: Cost-per-impact with ranking                             │
-- │                                                                        │
-- │ The cost_per_unit tells you: "It costs ₹X to produce one unit of       │
-- │ this IRIS+ indicator."  Lower is better.                               │
-- │                                                                        │
-- │ efficiency_rank uses DENSE_RANK so that programs with the same         │
-- │ cost-per-unit get the same rank (ties are common in small datasets).   │
-- └─────────────────────────────────────────────────────────────────────────┘
SELECT
    program_name,
    sector,
    fiscal_year,
    iris_id,
    indicator_name,
    indicator_unit,
    total_target,
    total_actual,
    achievement_pct,
    total_spend_inr,

    -- THE KEY METRIC: cost per unit of outcome
    ROUND(
        total_spend_inr / NULLIF(total_actual, 0),
        2
    )                                             AS cost_per_unit_inr,

    -- Personnel cost as % of total (overhead indicator)
    ROUND(
        personnel_spend_inr * 100.0
        / NULLIF(total_spend_inr, 0),
        1
    )                                             AS personnel_pct,

    -- M&E cost as % of total (data quality investment indicator)
    ROUND(
        me_spend_inr * 100.0
        / NULLIF(total_spend_inr, 0),
        1
    )                                             AS me_investment_pct,

    -- Rank programs by cost-efficiency within each indicator
    DENSE_RANK() OVER (
        PARTITION BY iris_id
        ORDER BY total_spend_inr / NULLIF(total_actual, 0) ASC
    )                                             AS efficiency_rank

FROM enriched
WHERE total_spend_inr IS NOT NULL
  AND total_actual > 0
ORDER BY
    iris_id,
    efficiency_rank,
    fiscal_year;
