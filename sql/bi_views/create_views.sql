-- ============================================================================
-- BI SEMANTIC LAYER — Pre-materialised views for Metabase / Power BI / Tableau
-- ============================================================================
--
-- These views flatten the star schema into 5 wide, denormalised tables
-- that a BI tool can consume directly without requiring the user to
-- configure any joins. Each view maps to one dashboard section.
--
-- Run this script against the clean SQLite database to create all views:
--   sqlite3 output/cleaned/ngo_impact_clean.db < sql/bi_views/create_views.sql
--
-- Compatible with: SQLite 3.35+, PostgreSQL 14+
-- ============================================================================


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ VIEW 1: v_cost_per_impact                                              │
-- │ Powers: KPI Scorecard #1 + Cost-per-Impact bar chart                   │
-- │ Grain: One row per program × IRIS+ indicator × fiscal year             │
-- └─────────────────────────────────────────────────────────────────────────┘
DROP VIEW IF EXISTS v_cost_per_impact;
CREATE VIEW v_cost_per_impact AS
WITH program_spend AS (
    SELECT
        e.program_id,
        e.fiscal_year,
        SUM(e.amount_inr)                                     AS total_spend_inr,
        SUM(CASE WHEN e.category = 'Personnel'
                 THEN e.amount_inr ELSE 0 END)                AS personnel_spend_inr,
        SUM(CASE WHEN e.category = 'Monitoring & Evaluation'
                 THEN e.amount_inr ELSE 0 END)                AS me_spend_inr
    FROM expenses e
    GROUP BY e.program_id, e.fiscal_year
),
program_outcomes AS (
    SELECT
        ot.program_id,
        ot.indicator_id,
        SUBSTR(ot.reporting_period, 4)                        AS fiscal_year,
        SUM(ot.target_value)                                  AS total_target,
        SUM(ot.actual_value)                                  AS total_actual,
        ROUND(SUM(ot.actual_value) * 100.0
              / NULLIF(SUM(ot.target_value), 0), 1)           AS achievement_pct
    FROM outcome_tracking ot
    WHERE ot.actual_value IS NOT NULL AND ot.actual_value > 0
    GROUP BY ot.program_id, ot.indicator_id, SUBSTR(ot.reporting_period, 4)
)
SELECT
    p.program_id,
    p.program_name,
    p.sector,
    p.status                                                  AS program_status,
    r.state,
    r.district,
    r.region_type,
    ii.iris_id,
    ii.indicator_name,
    ii.unit                                                   AS indicator_unit,
    ii.category                                               AS indicator_category,
    po.fiscal_year,
    po.total_target,
    po.total_actual,
    po.achievement_pct,
    ps.total_spend_inr,
    ROUND(ps.total_spend_inr / NULLIF(po.total_actual, 0), 2) AS cost_per_unit_inr,
    ROUND(ps.personnel_spend_inr * 100.0
          / NULLIF(ps.total_spend_inr, 0), 1)                 AS personnel_pct,
    ROUND(ps.me_spend_inr * 100.0
          / NULLIF(ps.total_spend_inr, 0), 1)                 AS me_investment_pct,
    DENSE_RANK() OVER (
        PARTITION BY ii.iris_id
        ORDER BY ps.total_spend_inr / NULLIF(po.total_actual, 0) ASC
    )                                                         AS efficiency_rank
FROM program_outcomes po
JOIN programs p       ON po.program_id = p.program_id
JOIN impact_indicators ii ON po.indicator_id = ii.indicator_id
LEFT JOIN program_spend ps
    ON po.program_id = ps.program_id AND po.fiscal_year = ps.fiscal_year
LEFT JOIN regions r   ON p.region_id = r.region_id
WHERE ps.total_spend_inr IS NOT NULL AND po.total_actual > 0;


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ VIEW 2: v_programme_progress                                           │
-- │ Powers: KPI Scorecard #2 + Quarterly trend line chart                  │
-- │ Grain: One row per program × indicator × quarter                       │
-- └─────────────────────────────────────────────────────────────────────────┘
DROP VIEW IF EXISTS v_programme_progress;
CREATE VIEW v_programme_progress AS
SELECT
    ot.outcome_id,
    p.program_id,
    p.program_name,
    p.sector,
    p.status                                                  AS program_status,
    r.state,
    r.region_type,
    ii.iris_id,
    ii.indicator_name,
    ii.category                                               AS indicator_category,
    ot.reporting_period,
    CAST(SUBSTR(ot.reporting_period, 2, 1) AS INTEGER)        AS quarter_num,
    SUBSTR(ot.reporting_period, 4)                            AS fiscal_year,
    ot.target_value,
    ot.actual_value,
    ROUND(ot.actual_value * 100.0
          / NULLIF(ot.target_value, 0), 1)                    AS achievement_pct,
    -- QoQ trend
    LAG(ot.actual_value, 1) OVER (
        PARTITION BY ot.program_id, ot.indicator_id
        ORDER BY SUBSTR(ot.reporting_period, 4), CAST(SUBSTR(ot.reporting_period, 2, 1) AS INTEGER)
    )                                                         AS prev_quarter_actual,
    -- Cumulative
    SUM(ot.actual_value) OVER (
        PARTITION BY ot.program_id, ot.indicator_id
        ORDER BY SUBSTR(ot.reporting_period, 4), CAST(SUBSTR(ot.reporting_period, 2, 1) AS INTEGER)
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                         AS cumulative_actual,
    SUM(ot.target_value) OVER (
        PARTITION BY ot.program_id, ot.indicator_id
        ORDER BY SUBSTR(ot.reporting_period, 4), CAST(SUBSTR(ot.reporting_period, 2, 1) AS INTEGER)
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                         AS cumulative_target,
    -- RAG
    CASE
        WHEN ot.actual_value * 100.0 / NULLIF(ot.target_value, 0) >= 90 THEN 'GREEN'
        WHEN ot.actual_value * 100.0 / NULLIF(ot.target_value, 0) >= 70 THEN 'AMBER'
        ELSE 'RED'
    END                                                       AS rag_status,
    -- Verification
    CASE WHEN ot.verified_by IS NOT NULL THEN 'Verified' ELSE 'Unverified' END
                                                              AS verification_status,
    ot.data_source,
    -- Recency
    ROW_NUMBER() OVER (
        PARTITION BY ot.program_id, ot.indicator_id
        ORDER BY SUBSTR(ot.reporting_period, 4) DESC, CAST(SUBSTR(ot.reporting_period, 2, 1) AS INTEGER) DESC
    )                                                         AS recency_rank
FROM outcome_tracking ot
JOIN programs p       ON ot.program_id = p.program_id
JOIN impact_indicators ii ON ot.indicator_id = ii.indicator_id
LEFT JOIN regions r   ON p.region_id = r.region_id
WHERE ot.actual_value IS NOT NULL;


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ VIEW 3: v_beneficiary_360                                              │
-- │ Powers: KPI Scorecard #3 + Demographic reach charts                    │
-- │ Grain: One row per beneficiary (with service/assessment aggregates)    │
-- └─────────────────────────────────────────────────────────────────────────┘
DROP VIEW IF EXISTS v_beneficiary_360;
CREATE VIEW v_beneficiary_360 AS
SELECT
    b.beneficiary_id,
    b.full_name,
    b.age,
    CASE
        WHEN b.age IS NULL        THEN 'Unknown'
        WHEN b.age < 6            THEN '0-5 (Early Childhood)'
        WHEN b.age BETWEEN 6  AND 14 THEN '6-14 (School Age)'
        WHEN b.age BETWEEN 15 AND 24 THEN '15-24 (Youth)'
        WHEN b.age BETWEEN 25 AND 44 THEN '25-44 (Working Age)'
        WHEN b.age BETWEEN 45 AND 59 THEN '45-59 (Middle Age)'
        ELSE '60+ (Senior)'
    END                                                       AS age_cohort,
    b.gender,
    b.education_level,
    b.income_bracket,
    b.household_size,
    CASE
        WHEN b.is_disabled = 1 THEN 'Person with Disability'
        WHEN b.is_disabled = 0 THEN 'No Disability'
        ELSE 'Not Recorded'
    END                                                       AS disability_status,
    b.registration_date,
    p.program_id,
    p.program_name,
    p.sector,
    r.state,
    r.district,
    r.region_type,
    -- Service aggregates
    COALESCE(svc.services_received, 0)                        AS services_received,
    COALESCE(svc.unique_interventions, 0)                     AS unique_interventions,
    CASE WHEN COALESCE(svc.services_received, 0) > 0
         THEN 'Active' ELSE 'Registered Only' END             AS beneficiary_status,
    -- Assessment aggregates
    COALESCE(asm.assessments_taken, 0)                        AS assessments_taken,
    asm.latest_score_pct
FROM beneficiaries b
LEFT JOIN programs p  ON b.program_id = p.program_id
LEFT JOIN regions r   ON b.region_id = r.region_id
LEFT JOIN (
    SELECT
        beneficiary_id,
        COUNT(delivery_id)                                    AS services_received,
        COUNT(DISTINCT intervention_id)                       AS unique_interventions
    FROM service_delivery
    GROUP BY beneficiary_id
) svc ON b.beneficiary_id = svc.beneficiary_id
LEFT JOIN (
    SELECT
        beneficiary_id,
        COUNT(assessment_id)                                  AS assessments_taken,
        ROUND(
            MAX(CASE WHEN score IS NOT NULL AND max_score > 0
                     THEN score * 100.0 / max_score END), 1
        )                                                     AS latest_score_pct
    FROM assessments
    GROUP BY beneficiary_id
) asm ON b.beneficiary_id = asm.beneficiary_id;


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ VIEW 4: v_outcome_effectiveness                                        │
-- │ Powers: KPI Scorecard #4 + Outcome heatmap table                       │
-- │ Grain: One row per beneficiary with matched pre/post scores            │
-- └─────────────────────────────────────────────────────────────────────────┘
DROP VIEW IF EXISTS v_outcome_effectiveness;
CREATE VIEW v_outcome_effectiveness AS
WITH pre AS (
    SELECT beneficiary_id, assessment_date AS pre_date,
           ROUND(score * 100.0 / NULLIF(max_score, 0), 1) AS pre_score_pct,
           ROW_NUMBER() OVER (PARTITION BY beneficiary_id ORDER BY assessment_date ASC) AS rn
    FROM assessments
    WHERE assessment_type = 'Pre-Test' AND score IS NOT NULL AND max_score > 0
),
post AS (
    SELECT beneficiary_id, assessment_date AS post_date,
           ROUND(score * 100.0 / NULLIF(max_score, 0), 1) AS post_score_pct,
           ROW_NUMBER() OVER (PARTITION BY beneficiary_id ORDER BY assessment_date DESC) AS rn
    FROM assessments
    WHERE assessment_type = 'Post-Test' AND score IS NOT NULL AND max_score > 0
)
SELECT
    pre.beneficiary_id,
    b.full_name,
    b.gender,
    b.age,
    b.income_bracket,
    CASE WHEN b.is_disabled = 1 THEN 'PwD' ELSE 'No' END    AS is_pwd,
    p.program_id,
    p.program_name,
    p.sector,
    r.state,
    r.region_type,
    pre.pre_date,
    pre.pre_score_pct,
    post.post_date,
    post.post_score_pct,
    ROUND(post.post_score_pct - pre.pre_score_pct, 1)        AS improvement_pct,
    ROUND((post.post_score_pct - pre.pre_score_pct) * 100.0
          / NULLIF(pre.pre_score_pct, 0), 1)                 AS effect_size_pct,
    CAST(JULIANDAY(post.post_date) - JULIANDAY(pre.pre_date)
         AS INTEGER)                                          AS days_between_tests,
    CASE
        WHEN post.post_score_pct > pre.pre_score_pct THEN 'Improved'
        WHEN post.post_score_pct = pre.pre_score_pct THEN 'No Change'
        ELSE 'Declined'
    END                                                       AS outcome_direction
FROM pre
JOIN post ON pre.beneficiary_id = post.beneficiary_id
JOIN beneficiaries b ON pre.beneficiary_id = b.beneficiary_id
LEFT JOIN programs p ON b.program_id = p.program_id
LEFT JOIN regions r  ON b.region_id = r.region_id
WHERE pre.rn = 1 AND post.rn = 1 AND post.post_date > pre.pre_date;


-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ VIEW 5: v_financial_overview                                           │
-- │ Powers: Funding vs Expense waterfall, burn rate analysis                │
-- │ Grain: One row per program × fiscal year                               │
-- └─────────────────────────────────────────────────────────────────────────┘
DROP VIEW IF EXISTS v_financial_overview;
CREATE VIEW v_financial_overview AS
SELECT
    p.program_id,
    p.program_name,
    p.sector,
    p.status                                                  AS program_status,
    r.state,
    r.region_type,
    fy.fiscal_year,
    COALESCE(fund.total_funding_inr, 0)                       AS total_funding_inr,
    COALESCE(fund.donor_count, 0)                             AS donor_count,
    COALESCE(exp.total_expense_inr, 0)                        AS total_expense_inr,
    COALESCE(fund.total_funding_inr, 0)
        - COALESCE(exp.total_expense_inr, 0)                  AS net_balance_inr,
    ROUND(COALESCE(exp.total_expense_inr, 0) * 100.0
          / NULLIF(COALESCE(fund.total_funding_inr, 0), 0), 1)
                                                              AS burn_rate_pct,
    -- Expense breakdown
    COALESCE(exp.personnel_inr, 0)                            AS personnel_inr,
    COALESCE(exp.field_inr, 0)                                AS field_inr,
    COALESCE(exp.me_inr, 0)                                   AS me_inr,
    COALESCE(exp.overhead_inr, 0)                             AS overhead_inr
FROM programs p
LEFT JOIN regions r ON p.region_id = r.region_id
CROSS JOIN (
    SELECT DISTINCT fiscal_year FROM expenses
    UNION
    SELECT DISTINCT fiscal_year FROM funding
) fy
LEFT JOIN (
    SELECT program_id, fiscal_year,
           SUM(amount_inr) AS total_funding_inr,
           COUNT(DISTINCT donor_id) AS donor_count
    FROM funding GROUP BY program_id, fiscal_year
) fund ON p.program_id = fund.program_id AND fy.fiscal_year = fund.fiscal_year
LEFT JOIN (
    SELECT program_id, fiscal_year,
           SUM(amount_inr) AS total_expense_inr,
           SUM(CASE WHEN category = 'Personnel' THEN amount_inr ELSE 0 END) AS personnel_inr,
           SUM(CASE WHEN category = 'Travel & Field' THEN amount_inr ELSE 0 END) AS field_inr,
           SUM(CASE WHEN category = 'Monitoring & Evaluation' THEN amount_inr ELSE 0 END) AS me_inr,
           SUM(CASE WHEN category = 'Administrative Overhead' THEN amount_inr ELSE 0 END) AS overhead_inr
    FROM expenses GROUP BY program_id, fiscal_year
) exp ON p.program_id = exp.program_id AND fy.fiscal_year = exp.fiscal_year;
