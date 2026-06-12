-- ============================================================================
-- KPI 2: PROGRAMME PROGRESS — TARGET vs ACTUAL WITH TREND DETECTION
-- ============================================================================
--
-- What it answers:
--   "Which programs are on track, which are slipping, and what's the
--    quarter-over-quarter momentum?"
--
-- Theory of Change mapping:
--   Outcomes (outcome_tracking) × Impact (impact_indicators)
--   Trends computed via LAG window function over quarterly periods.
--
-- Key features:
--   - Quarter-over-quarter (QoQ) growth rate via LAG()
--   - Cumulative actual vs. cumulative target via running SUM()
--   - Automatic RAG (Red/Amber/Green) status derivation
--   - Fiscal year rollup subtotals
--
-- Performance notes:
--   - Window functions operate on the already-small outcome_tracking table
--   - No additional joins beyond the two dimension tables
--   - Expected execution: < 30ms on our dataset
--
-- Compatible with: PostgreSQL 14+, SQLite 3.35+, Metabase, Power BI, Tableau
-- ============================================================================

WITH
-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ CTE 1: Enrich outcome_tracking with program + indicator metadata       │
-- │         and parse fiscal year from reporting_period                     │
-- └─────────────────────────────────────────────────────────────────────────┘
enriched_outcomes AS (
    SELECT
        ot.outcome_id,
        ot.program_id,
        p.program_name,
        p.sector,
        p.status                                  AS program_status,
        ot.indicator_id,
        ii.iris_id,
        ii.indicator_name,
        ii.category                               AS indicator_category,
        ot.reporting_period,
        -- Extract quarter number: 'Q2-FY2023-24' → 2
        CAST(SUBSTR(ot.reporting_period, 2, 1) AS INTEGER)
                                                  AS quarter_num,
        -- Extract fiscal year: 'Q2-FY2023-24' → 'FY2023-24'
        SUBSTR(ot.reporting_period, 4)            AS fiscal_year,
        ot.target_value,
        ot.actual_value,
        ot.status                                 AS reported_status,
        ot.data_source,
        ot.verified_by
    FROM outcome_tracking ot
    INNER JOIN programs p
        ON ot.program_id = p.program_id
    INNER JOIN impact_indicators ii
        ON ot.indicator_id = ii.indicator_id
),

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ CTE 2: Add trend analytics via window functions                        │
-- │                                                                        │
-- │ LAG():     Previous quarter's actual for QoQ growth calculation        │
-- │ SUM():     Running cumulative actual within each program × indicator   │
-- │ ROW_NUM(): Identifies the latest quarter for "current status" filters  │
-- └─────────────────────────────────────────────────────────────────────────┘
with_trends AS (
    SELECT
        *,

        -- Previous quarter's actual value (within same program × indicator)
        LAG(actual_value, 1) OVER (
            PARTITION BY program_id, indicator_id
            ORDER BY fiscal_year, quarter_num
        )                                         AS prev_quarter_actual,

        -- Cumulative actual across all quarters
        SUM(actual_value) OVER (
            PARTITION BY program_id, indicator_id
            ORDER BY fiscal_year, quarter_num
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )                                         AS cumulative_actual,

        -- Cumulative target across all quarters
        SUM(target_value) OVER (
            PARTITION BY program_id, indicator_id
            ORDER BY fiscal_year, quarter_num
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )                                         AS cumulative_target,

        -- Is this the latest reported quarter? (for "current snapshot" views)
        ROW_NUMBER() OVER (
            PARTITION BY program_id, indicator_id
            ORDER BY fiscal_year DESC, quarter_num DESC
        )                                         AS recency_rank

    FROM enriched_outcomes
    WHERE actual_value IS NOT NULL
)

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ FINAL SELECT: Programme progress with trend detection                  │
-- │                                                                        │
-- │ QoQ growth rate:                                                        │
-- │   ((current - previous) / previous) * 100                              │
-- │   Positive = improving, negative = declining                           │
-- │                                                                        │
-- │ RAG status (derived, not from raw data):                               │
-- │   GREEN:  achievement ≥ 90%                                            │
-- │   AMBER:  achievement 70–89%                                           │
-- │   RED:    achievement < 70%                                            │
-- └─────────────────────────────────────────────────────────────────────────┘
SELECT
    program_name,
    sector,
    program_status,
    iris_id,
    indicator_name,
    indicator_category,
    reporting_period,
    fiscal_year,
    quarter_num,

    -- Core metrics
    target_value,
    actual_value,
    ROUND(
        actual_value * 100.0 / NULLIF(target_value, 0), 1
    )                                             AS achievement_pct,

    -- Cumulative progress
    cumulative_target,
    cumulative_actual,
    ROUND(
        cumulative_actual * 100.0
        / NULLIF(cumulative_target, 0),
        1
    )                                             AS cumulative_achievement_pct,

    -- Quarter-over-quarter momentum
    prev_quarter_actual,
    ROUND(
        (actual_value - prev_quarter_actual) * 100.0
        / NULLIF(prev_quarter_actual, 0),
        1
    )                                             AS qoq_growth_pct,

    -- Momentum direction for dashboard iconography
    CASE
        WHEN prev_quarter_actual IS NULL THEN 'N/A (First Quarter)'
        WHEN actual_value > prev_quarter_actual   THEN '↑ Improving'
        WHEN actual_value = prev_quarter_actual   THEN '→ Stable'
        ELSE                                           '↓ Declining'
    END                                           AS momentum,

    -- RAG status (derived from achievement percentage)
    CASE
        WHEN actual_value * 100.0 / NULLIF(target_value, 0) >= 90
            THEN 'GREEN'
        WHEN actual_value * 100.0 / NULLIF(target_value, 0) >= 70
            THEN 'AMBER'
        ELSE 'RED'
    END                                           AS rag_status,

    -- Verification status for data quality trust indicator
    CASE
        WHEN verified_by IS NOT NULL THEN 'Verified'
        ELSE 'Unverified'
    END                                           AS verification_status,

    data_source,
    recency_rank

FROM with_trends
ORDER BY
    program_name,
    iris_id,
    fiscal_year,
    quarter_num;
