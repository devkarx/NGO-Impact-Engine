# Phase 4: BI Dashboard Blueprint — Architectural Specification

> **Audience**: BI developer implementing this in Metabase, Power BI, or Tableau  
> **Database**: `output/cleaned/ngo_impact_clean.db` (SQLite) with 5 pre-built views  
> **Target user**: NGO Executive Director, Programme Manager, M&E Officer

---

## 1. Data Modeling Rules

### 1.1 Star Schema Classification

The clean database has **13 base tables**. For BI modeling, classify them as follows:

```
                    ┌─────────────┐
                    │   regions   │ DIM
                    └──────┬──────┘
                           │
    ┌──────────┐    ┌──────┴──────┐    ┌──────────────────┐
    │  donors  │────│  programs   │────│ impact_indicators │
    │   DIM    │    │    DIM      │    │       DIM         │
    └────┬─────┘    └──────┬──────┘    └────────┬──────────┘
         │                 │                    │
    ┌────┴─────┐    ┌──────┴──────┐    ┌────────┴──────────┐
    │ funding  │    │  expenses   │    │ outcome_tracking   │
    │   FACT   │    │    FACT     │    │       FACT         │
    └──────────┘    └─────────────┘    └───────────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
    ┌─────────┴──┐  ┌──────┴──────┐  ┌──┴───────────┐
    │interventions│  │beneficiaries│  │    staff     │
    │    FACT     │  │    DIM      │  │     DIM      │
    └─────────┬──┘  └──────┬──────┘  └──────────────┘
              │            │
    ┌─────────┴──────────┬─┘
    │                    │
    ┌────────────────┐  ┌┴──────────────┐
    │service_delivery│  │  assessments  │
    │     FACT       │  │     FACT      │
    └────────────────┘  └───────────────┘
```

| Table              | Type       | Grain                                    | BI Role                          |
|--------------------|------------|------------------------------------------|----------------------------------|
| `regions`          | Dimension  | One row per geographic region             | Geographic filter / slicer       |
| `donors`           | Dimension  | One row per funding source                | Funding source filter            |
| `programs`         | Dimension  | One row per program                       | Primary filter / slicer          |
| `staff`            | Dimension  | One row per staff member                  | Assessor / facilitator lookup    |
| `impact_indicators`| Dimension  | One row per IRIS+ metric                  | Indicator selector               |
| `beneficiaries`    | Dimension  | One row per individual                    | Demographic analysis pivot       |
| `funding`          | Fact       | One row per funding transaction           | Financial inflows                |
| `expenses`         | Fact       | One row per expense transaction           | Financial outflows               |
| `interventions`    | Fact       | One row per activity delivered            | Activity tracking                |
| `service_delivery` | Fact       | One row per beneficiary × intervention    | Service output counting          |
| `assessments`      | Fact       | One row per assessment event              | Outcome measurement              |
| `outcome_tracking` | Fact       | One row per program × indicator × quarter | IRIS+ reporting                  |
| `data_quality_log` | Meta       | One row per issue                         | Data governance tab              |

### 1.2 Join Rules (Exact Relationships)

Configure these **exact relationships** in your BI tool's semantic model:

| Relationship                              | Join Type  | Left Table        | Left Key          | Right Table        | Right Key        | Cardinality |
|-------------------------------------------|-----------|-------------------|-------------------|--------------------|------------------|-------------|
| Programs operate in Regions               | Left Outer | `programs`        | `region_id`       | `regions`          | `region_id`      | Many → One  |
| Staff assigned to Regions                 | Left Outer | `staff`           | `region_id`       | `regions`          | `region_id`      | Many → One  |
| Beneficiaries live in Regions             | Left Outer | `beneficiaries`   | `region_id`       | `regions`          | `region_id`      | Many → One  |
| Beneficiaries enroll in Programs          | Left Outer | `beneficiaries`   | `program_id`      | `programs`         | `program_id`     | Many → One  |
| Funding links Donors to Programs          | Inner      | `funding`         | `donor_id`        | `donors`           | `donor_id`       | Many → One  |
| Funding goes to Programs                  | Inner      | `funding`         | `program_id`      | `programs`         | `program_id`     | Many → One  |
| Expenses charged to Programs              | Inner      | `expenses`        | `program_id`      | `programs`         | `program_id`     | Many → One  |
| Interventions belong to Programs          | Inner      | `interventions`   | `program_id`      | `programs`         | `program_id`     | Many → One  |
| Interventions facilitated by Staff        | Left Outer | `interventions`   | `staff_id`        | `staff`            | `staff_id`       | Many → One  |
| Service Delivery to Beneficiaries         | Inner      | `service_delivery`| `beneficiary_id`  | `beneficiaries`    | `beneficiary_id` | Many → One  |
| Service Delivery via Interventions        | Inner      | `service_delivery`| `intervention_id` | `interventions`    | `intervention_id`| Many → One  |
| Assessments of Beneficiaries              | Inner      | `assessments`     | `beneficiary_id`  | `beneficiaries`    | `beneficiary_id` | Many → One  |
| Outcome Tracking for Programs             | Inner      | `outcome_tracking`| `program_id`      | `programs`         | `program_id`     | Many → One  |
| Outcome Tracking measures Indicators      | Inner      | `outcome_tracking`| `indicator_id`    | `impact_indicators`| `indicator_id`   | Many → One  |

> **CRITICAL**: Use **Left Outer** joins for `region_id`, `staff_id`, and `program_id` on beneficiaries/staff — these can be NULL after cleaning. Inner joins would silently drop rows.

### 1.3 The Shortcut: Pre-built Views (Recommended)

Instead of configuring 14 joins manually, **use the 5 pre-built SQL views** in `sql/bi_views/create_views.sql`. These are already denormalised and require **zero joins** in the BI tool:

| View                       | Rows  | Cols | Dashboard Section                  | Grain                           |
|----------------------------|-------|------|------------------------------------|---------------------------------|
| `v_cost_per_impact`        | 50    | 20   | KPI #1 card + bar chart            | Program × Indicator × FY        |
| `v_programme_progress`     | 200   | 23   | KPI #2 card + trend line           | Program × Indicator × Quarter   |
| `v_beneficiary_360`        | 2,000 | 21   | KPI #3 card + demographic charts   | One row per beneficiary          |
| `v_outcome_effectiveness`  | 12    | 19   | KPI #4 card + heatmap              | One row per matched pre/post    |
| `v_financial_overview`     | 48    | 16   | Financial sidebar / supplementary  | Program × Fiscal Year            |

**Metabase**: Add the SQLite file as a database → the views appear as queryable tables.  
**Power BI**: Import via ODBC/SQLite connector → views auto-detected.  
**Tableau**: Connect to SQLite → drag views to canvas.

---

## 2. Calculated Fields

### 2.1 DAX Formulas (Power BI)

```dax
// ─── KPI #1: Weighted Average Cost per Impact (Scorecard) ───
Cost per Impact =
DIVIDE(
    SUM(v_cost_per_impact[total_spend_inr]),
    SUM(v_cost_per_impact[total_actual]),
    BLANK()
)

// ─── KPI #2: Overall Achievement % (Scorecard) ───
Programme Achievement % =
DIVIDE(
    SUM(v_programme_progress[actual_value]),
    SUM(v_programme_progress[target_value]),
    0
) * 100

// ─── KPI #2: Quarter-over-Quarter Growth ───
QoQ Growth % =
VAR _current = SUM(v_programme_progress[actual_value])
VAR _previous = CALCULATE(
    SUM(v_programme_progress[actual_value]),
    DATEADD(v_programme_progress[reporting_period], -1, QUARTER)
)
RETURN DIVIDE(_current - _previous, _previous, BLANK()) * 100

// ─── KPI #3: Activation Rate (Scorecard) ───
Activation Rate % =
DIVIDE(
    COUNTROWS(FILTER(v_beneficiary_360, v_beneficiary_360[beneficiary_status] = "Active")),
    COUNTROWS(v_beneficiary_360),
    0
) * 100

// ─── KPI #3: Total Beneficiaries Reached (Active only) ───
Beneficiaries Reached =
COUNTROWS(FILTER(v_beneficiary_360, v_beneficiary_360[beneficiary_status] = "Active"))

// ─── KPI #4: % Beneficiaries Improved (Scorecard) ───
% Improved =
DIVIDE(
    COUNTROWS(FILTER(v_outcome_effectiveness, v_outcome_effectiveness[outcome_direction] = "Improved")),
    COUNTROWS(v_outcome_effectiveness),
    0
) * 100

// ─── KPI #4: Average Score Improvement ───
Avg Improvement =
AVERAGE(v_outcome_effectiveness[improvement_pct])

// ─── Financial: Burn Rate ───
Burn Rate % =
DIVIDE(
    SUM(v_financial_overview[total_expense_inr]),
    SUM(v_financial_overview[total_funding_inr]),
    0
) * 100

// ─── RAG Status Color ───
RAG Color =
SWITCH(
    TRUE(),
    [Programme Achievement %] >= 90, "#22c55e",   // Green
    [Programme Achievement %] >= 70, "#f59e0b",   // Amber
    "#ef4444"                                      // Red
)
```

### 2.2 Metabase Custom Expressions (SQL)

Metabase supports custom columns via its expression editor or native SQL queries. Use the views directly — they already contain all calculated columns:

| Metric                   | View Column                     | Type           |
|--------------------------|---------------------------------|----------------|
| Cost per Impact          | `v_cost_per_impact.cost_per_unit_inr` | Pre-computed |
| Achievement %            | `v_programme_progress.achievement_pct` | Pre-computed |
| RAG Status               | `v_programme_progress.rag_status` | Pre-computed |
| QoQ Trend                | `v_programme_progress.prev_quarter_actual` | Use for custom formula |
| Activation Rate          | `v_beneficiary_360.beneficiary_status` | Count where = 'Active' |
| Improvement %            | `v_outcome_effectiveness.improvement_pct` | Pre-computed |
| Outcome Direction        | `v_outcome_effectiveness.outcome_direction` | Pre-computed |
| Burn Rate                | `v_financial_overview.burn_rate_pct` | Pre-computed |

**No additional Metabase custom expressions needed** — all heavy computation lives in the SQL views.

### 2.3 Tableau Calculated Fields

```
// Cost per Impact
SUM([Total Spend Inr]) / SUM([Total Actual])

// RAG Status Color
IF [Achievement Pct] >= 90 THEN "Green"
ELSEIF [Achievement Pct] >= 70 THEN "Amber"
ELSE "Red"
END

// Beneficiary Activation
COUNTD(IF [Beneficiary Status] = "Active" THEN [Beneficiary Id] END)
/ COUNTD([Beneficiary Id])
```

---

## 3. Dashboard Wireframe — Exact Layout Specification

### 3.1 Visual Reference

![Dashboard wireframe](C:\Users\Aradhy\.gemini\antigravity-ide\brain\57f22532-21ff-451b-afa0-76c7db8479d4\dashboard_wireframe_1781248324015.png)

### 3.2 Page Structure

The dashboard is a **single-page layout** with 5 horizontal rows. Reading order follows the M&E results chain: Inputs → Activities → Outputs → Outcomes → Impact.

```
┌──────────────────────────────────────────────────────────────────────┐
│  ROW 0: GLOBAL FILTER BAR                                            │
├──────────┬──────────┬──────────────┬─────────────────────────────────┤
│  ROW 1   │  KPI #1  │    KPI #2   │   KPI #3    │     KPI #4        │
│ SCORECARDS│         │             │             │                   │
├──────────┴──────────┼─────────────┴─────────────────────────────────┤
│  ROW 2 (60%)        │  ROW 2 (40%)                                  │
│  Cost per Impact    │  Quarterly Progress Trend                      │
│  BAR CHART          │  LINE CHART                                    │
├─────────────────────┼───────────────────────────────────────────────┤
│  ROW 3 (40%)        │  ROW 3 (60%)                                  │
│  Demographic Reach  │  Outcome Effectiveness                        │
│  STACKED BAR        │  HEATMAP TABLE                                │
├─────────────────────┴───────────────────────────────────────────────┤
│  ROW 4: DETAILED DATA TABLE (drill-through)                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 3.3 ROW 0 — Global Filter Bar

**Position**: Sticky top bar, full width  
**Background**: Slightly darker than dashboard body

| Filter         | Type         | Source View                | Default Value  | Wired To             |
|----------------|-------------|----------------------------|----------------|----------------------|
| Fiscal Year    | Dropdown     | `v_cost_per_impact.fiscal_year` | Latest FY | All 5 views (fiscal_year) |
| Program        | Multi-select | `programs.program_name`     | All            | All 5 views (program_id / program_name) |
| Region / State | Dropdown     | `regions.state`             | All            | All views with state column |
| Sector         | Dropdown     | `programs.sector`           | All            | All views with sector column |

**Metabase**: Dashboard filters → map to each card's column.  
**Power BI**: Slicers with "Sync slicers" across all visuals.  
**Tableau**: Dashboard filter actions applied to all sheets.

---

### 3.4 ROW 1 — KPI Scorecards (4 × Big Number Cards)

Each card follows the same anatomy:

```
┌─────────────────────────┐
│  ● GREEN                │  ← RAG indicator dot
│                         │
│  ₹287                   │  ← Big number (hero metric)
│  Cost per Impact        │  ← Label
│                         │
│  ▲ 12% vs last FY      │  ← Trend annotation (small text)
└─────────────────────────┘
```

| Card | Hero Metric | Source | Big Number Formula | Trend Annotation | RAG Logic |
|------|-------------|--------|-------------------|------------------|-----------|
| **KPI #1** | Cost per Impact | `v_cost_per_impact` | `SUM(total_spend_inr) / SUM(total_actual)` | `% change vs prior FY` | ≤₹200 GREEN, ≤₹500 AMBER, >₹500 RED |
| **KPI #2** | Programme Achievement | `v_programme_progress` | `SUM(actual_value) / SUM(target_value) * 100` | `+/- pp vs prior quarter` | ≥90% GREEN, ≥70% AMBER, <70% RED |
| **KPI #3** | Beneficiaries Reached | `v_beneficiary_360` | `COUNT WHERE beneficiary_status = 'Active'` | `of N registered (X% activation)` | ≥80% activation GREEN, ≥60% AMBER, <60% RED |
| **KPI #4** | % Showed Improvement | `v_outcome_effectiveness` | `COUNT(Improved) / COUNT(*) * 100` | `avg +X pp improvement` | ≥70% GREEN, ≥50% AMBER, <50% RED |

**Chart type**: `Big Number` (Metabase) / `Card` (Power BI) / `Text Table with BAN` (Tableau)

---

### 3.5 ROW 2 — Efficiency & Trends

#### LEFT (60% width): Cost per Impact by Program — Horizontal Bar Chart

| Property       | Value |
|----------------|-------|
| **Chart type** | Horizontal bar chart |
| **Source view** | `v_cost_per_impact` |
| **Y-axis**     | `program_name` (sorted by cost_per_unit_inr ascending — most efficient at top) |
| **X-axis**     | `cost_per_unit_inr` (₹) |
| **Color by**   | `sector` (categorical palette) |
| **Data labels** | Show ₹ value at end of each bar |
| **Reference line** | Vertical line at the portfolio-wide average cost |
| **Tooltip**    | Program name, sector, fiscal year, total_spend, total_actual, achievement_pct |
| **Filter**     | `WHERE fiscal_year = [selected FY]` (from global filter) |
| **Interaction** | Click bar → filter ROW 4 detail table to that program |

#### RIGHT (40% width): Quarterly Progress Trend — Multi-line Chart

| Property       | Value |
|----------------|-------|
| **Chart type** | Line chart with markers |
| **Source view** | `v_programme_progress` |
| **X-axis**     | `reporting_period` (ordered chronologically) |
| **Y-axis**     | `achievement_pct` (%) |
| **Lines**      | One line per `program_name` (top 5 by total_actual, others grouped as "Other") |
| **Reference line** | Horizontal dashed line at 90% (GREEN threshold) and 70% (AMBER threshold) |
| **Color**      | By program — consistent with bar chart palette |
| **Tooltip**    | Program, quarter, target, actual, achievement %, QoQ growth %, momentum |
| **Annotations** | RAG dots on each data point (GREEN/AMBER/RED based on `rag_status`) |

---

### 3.6 ROW 3 — Equity & Outcomes

#### LEFT (40% width): Demographic Reach — Horizontal 100% Stacked Bar Chart

| Property       | Value |
|----------------|-------|
| **Chart type** | Horizontal 100% stacked bar |
| **Source view** | `v_beneficiary_360` |
| **Y-axis categories** | 4 rows: `gender`, `income_bracket`, `region_type`, `disability_status` |
| **Segments**   | Category values within each demographic dimension |
| **Color palette** | Consistent across dimensions (e.g., Female=teal, Male=slate, Unknown=gray) |
| **Data labels** | Show percentage within each segment |
| **Tooltip**    | Total count, % of total, activation rate for that segment |
| **Interaction** | Click segment → cross-filter KPI cards and detail table |

**How to build in Metabase**: Create 4 separate bar cards stacked vertically, each querying `v_beneficiary_360` with a GROUP BY on the relevant column. Alternatively, use the SQL query from KPI 3 which produces the UNION ALL format ready for pivoting.

**How to build in Power BI**: Matrix visual with `dimension` on rows, `dimension_value` as column groups, `total_registered` as values. Conditional formatting on `activation_rate_pct`.

#### RIGHT (60% width): Outcome Effectiveness — Conditional Heatmap Table

| Property       | Value |
|----------------|-------|
| **Chart type** | Table / Matrix with conditional cell coloring |
| **Source view** | `v_outcome_effectiveness` — aggregated by `program_name, sector` |
| **Rows**       | `program_name` |
| **Columns**    | See below |
| **Sort**       | By `improvement_pct` descending (best-performing programs at top) |

| Column Header          | Field                         | Format    | Conditional Color                     |
|------------------------|-------------------------------|-----------|---------------------------------------|
| Sector                 | `sector`                      | Text      | —                                     |
| Matched Pairs          | `COUNT(*)`                    | Integer   | — (sample size indicator)             |
| Baseline Score         | `AVG(pre_score_pct)`          | 0.0%      | White → light blue gradient           |
| Endline Score          | `AVG(post_score_pct)`         | 0.0%      | White → dark blue gradient            |
| Improvement            | `AVG(improvement_pct)`        | +0.0 pp   | Red (≤0) → Yellow (0-10) → Green (>10) |
| % Improved             | `COUNT(Improved)/COUNT(*)`    | 0%        | Red (<50%) → Amber (50-70%) → Green (>70%) |
| Avg Days Exposure      | `AVG(days_between_tests)`     | Integer   | — (context)                           |

---

### 3.7 ROW 4 — Detail Table (Drill-Through)

| Property       | Value |
|----------------|-------|
| **Chart type** | Paginated data table with search |
| **Source view** | `v_beneficiary_360` |
| **Columns**    | `beneficiary_id`, `full_name`, `age_cohort`, `gender`, `income_bracket`, `region_type`, `program_name`, `sector`, `services_received`, `beneficiary_status` |
| **Page size**  | 20 rows per page |
| **Sort**       | Default: `services_received` DESC (most engaged first) |
| **Search**     | Enable full-text search on `full_name` |
| **Export**      | CSV download button |
| **Cross-filter** | Responds to all ROW 2/3 click interactions |

---

### 3.8 Color Palette

```
// Primary palette (program sectors)
Education:           #3b82f6  (Blue)
Healthcare:          #10b981  (Emerald)
Livelihoods:         #f59e0b  (Amber)
WASH:                #06b6d4  (Cyan)
Women Empowerment:   #ec4899  (Pink)
Agriculture:         #84cc16  (Lime)
Financial Inclusion:  #8b5cf6  (Violet)
Child Protection:    #f97316  (Orange)
Nutrition:           #14b8a6  (Teal)
Governance:          #6366f1  (Indigo)

// RAG status
GREEN:   #22c55e
AMBER:   #f59e0b
RED:     #ef4444

// Neutral
Background:  #0f172a  (Dark navy)
Card bg:     #1e293b  (Slate-800)
Text:        #f8fafc  (Slate-50)
Muted:       #94a3b8  (Slate-400)
Border:      #334155  (Slate-700)
```

---

## 4. Metabase-Specific Setup Instructions

### 4.1 Connect the Database

1. **Admin → Databases → Add Database**
2. Database type: **SQLite**
3. Database file path: `/home/kirmada/ngo-impact-dashboard/output/cleaned/ngo_impact_clean.db`
4. Name: `NGO Impact Dashboard`
5. Click **Save**

### 4.2 Create the Dashboard

1. **New → Dashboard** → Name: "Impact Measurement Dashboard"
2. Add **4 Saved Questions** (one per KPI scorecard):

| Question Name | Type | Source | Query |
|--------------|------|--------|-------|
| KPI 1: Cost per Impact | Native query | `SELECT ROUND(SUM(total_spend_inr)/SUM(total_actual),0) AS cost_per_impact FROM v_cost_per_impact WHERE fiscal_year = {{fiscal_year}}` | Big Number |
| KPI 2: Achievement | Native query | `SELECT ROUND(SUM(actual_value)*100.0/SUM(target_value),1) AS achievement_pct FROM v_programme_progress WHERE fiscal_year = {{fiscal_year}}` | Big Number |
| KPI 3: Reached | Native query | `SELECT COUNT(*) AS reached FROM v_beneficiary_360 WHERE beneficiary_status = 'Active'` | Big Number |
| KPI 4: % Improved | Native query | `SELECT ROUND(SUM(CASE WHEN outcome_direction='Improved' THEN 1 ELSE 0 END)*100.0/COUNT(*),1) FROM v_outcome_effectiveness` | Big Number |

3. Add **4 chart cards** (one per ROW 2/3 visual) using simple questions against the views.
4. Add **dashboard filters** and wire them to each card.

### 4.3 Filter Wiring Matrix

| Filter Name | Maps to (per card) |
|-------------|-------------------|
| Fiscal Year | `v_cost_per_impact.fiscal_year`, `v_programme_progress.fiscal_year`, `v_financial_overview.fiscal_year` |
| Program     | `*.program_name` on all cards |
| State       | `*.state` on all cards |
| Sector      | `*.sector` on all cards |

---

## 5. Power BI–Specific Setup Instructions

### 5.1 Import Data

1. **Get Data → ODBC** (or use the SQLite connector via Power Query)
2. Import all 5 views as separate tables
3. No relationships needed — views are pre-denormalised

### 5.2 Create Measures Table

Create a disconnected measures table for the DAX formulas in Section 2.1:

```
Measures Table:
  - Cost per Impact
  - Programme Achievement %
  - Activation Rate %
  - % Improved
  - Burn Rate %
  - RAG Color
```

### 5.3 Page Layout

1. Set canvas size to **16:9 (1920×1080)**
2. Use **Dark theme** with the palette from Section 3.8
3. Add 4 Card visuals (ROW 1), 2 charts (ROW 2), 2 charts (ROW 3), 1 Table (ROW 4)
4. Add 4 Slicers (ROW 0) and sync them across all visuals

---

## 6. File Deliverables (Phase 4)

| File | Purpose |
|------|---------|
| `sql/bi_views/create_views.sql` | 5 SQL views forming the BI semantic layer |
| `docs/bi_dashboard_blueprint.md` | This document |
| `create_bi_views.py` | Script to materialise views in the SQLite DB |
| Views are already materialised in `output/cleaned/ngo_impact_clean.db` | Ready for BI tool connection |
