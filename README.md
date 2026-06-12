<div align="center">

# 🏛️ NGO Impact Engine

### An Open-Source M&E KPI Framework for Social Impact Measurement

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)](https://python.org)
[![pandas](https://img.shields.io/badge/pandas-2.0%2B-150458?logo=pandas)](https://pandas.pydata.org)
[![SQLite](https://img.shields.io/badge/SQLite-3.35%2B-003B57?logo=sqlite)](https://sqlite.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![IRIS+](https://img.shields.io/badge/IRIS%2B-GIIN%20Aligned-blue)](https://iris.thegiin.org)

*A production-ready, reusable data pipeline that transforms raw NGO field data into*  
*actionable impact KPIs — designed to be forked by any small-to-medium NGO.*

---

**[Architecture](#architecture) · [Quick Start](#quick-start) · [Pipeline Walkthrough](#pipeline-walkthrough) · [KPI Queries](#kpi-queries) · [BI Integration](#bi-integration) · [User Guide](#user-guide) · [Contributing](#contributing)**

</div>

---

## The Problem

The vast majority of Indian NGOs measure **activity** (events held, beneficiaries registered) rather than **outcomes** (lives changed, behaviours shifted). This gap weakens fundraising, prevents course-correction, and obscures what's actually working.

The problem isn't BI software — it's the **missing translation layer** between field data and decision-relevant KPIs.

## The Solution

This repository provides that translation layer: a **complete, end-to-end data pipeline** from messy field data to clean, BI-ready KPIs mapped to the [IRIS+ standard](https://iris.thegiin.org) — the global benchmark for impact measurement used by institutional donors and impact investors.

**Fork this repo. Plug in your data. Get a working impact dashboard.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NGO FIELD DATA                               │
│         (Paper forms, Google Sheets, KoBoToolbox, MIS)              │
└──────────────────────────┬──────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 1: DATA ARCHITECTURE & SYNTHETIC GENERATION                  │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────────────┐   │
│  │ 13-Table     │  │ Synthetic   │  │ Noise Injector           │   │
│  │ Star Schema  │  │ Generator   │  │ (7 real-world issues)    │   │
│  │ (ToC-mapped) │  │ (Faker)     │  │                          │   │
│  └──────────────┘  └─────────────┘  └──────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 2: DATA CLEANING PIPELINE                                    │
│  ┌────────┐ ┌──────┐ ┌───────┐ ┌────────┐ ┌──────┐ ┌────┐ ┌────┐ │
│  │Dedup   │→│Dates │→│Categ. │→│Outliers│→│Impute│→│ FK │→│Type│ │
│  └────────┘ └──────┘ └───────┘ └────────┘ └──────┘ └────┘ └────┘ │
│                     7-Step Cleaning Waterfall                       │
│                     + Full Audit Trail (CSV)                        │
└──────────────────────────┬──────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 3: SQL KPI EXTRACTION                                       │
│  ┌────────────────┐ ┌──────────────┐ ┌──────────┐ ┌─────────────┐ │
│  │Cost per Impact │ │Programme     │ │Demographic│ │Outcome      │ │
│  │(IRIS+ linked)  │ │Progress+Trend│ │Reach ×8   │ │Effectiveness│ │
│  └────────────────┘ └──────────────┘ └──────────┘ └─────────────┘ │
│              All 4 queries: 27ms combined (<3s target)             │
└──────────────────────────┬──────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 4: BI SEMANTIC LAYER                                         │
│  5 pre-built SQL views (zero-join for BI tools)                     │
│  + DAX / Metabase / Tableau calculated fields                       │
│  + Dashboard wireframe with chart types & color palette             │
└──────────────────────────┬──────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  METABASE  /  POWER BI  /  TABLEAU  /  LOOKER STUDIO               │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                              │
│  │KPI 1 │ │KPI 2 │ │KPI 3 │ │KPI 4 │  ← Executive Dashboard      │
│  └──────┘ └──────┘ └──────┘ └──────┘                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Language | Python 3.10+ | Pipeline orchestration, data manipulation |
| Data Processing | pandas 2.0+, NumPy | DataFrame operations, type handling |
| Synthetic Data | Faker (en_IN locale) | Realistic Indian NGO field data generation |
| Database | SQLite 3.35+ | Portable, zero-config analytical database |
| Schema | SQLAlchemy 2.0 | Schema definitions, DDL generation |
| KPI Queries | SQL (CTE + Window Functions) | Cost-per-impact, trends, demographics, outcomes |
| BI Layer | Metabase / Power BI / Tableau | Dashboard visualisation (any tool works) |
| M&E Framework | IRIS+ (GIIN), Theory of Change | 20 legitimate impact indicators |

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

### 1. Clone and Set Up

```bash
git clone https://github.com/devkarx/NGO-Impact-Engine.git
cd NGO-Impact-Engine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Generate Synthetic Data (Phase 1)

```bash
# Generate messy data with noise injection (default seed: 42)
python -m phase1_data_architecture.main

# Options:
python -m phase1_data_architecture.main --seed 123          # Different seed
python -m phase1_data_architecture.main --no-noise           # Clean data only
python -m phase1_data_architecture.main --output-dir ./data  # Custom output path
python -m phase1_data_architecture.main --help               # All options
```

**Output**: 13 CSV files + SQLite database in `./output/`

### 3. Clean the Data (Phase 2)

```bash
# Clean from existing dirty CSVs
python -m phase2_cleaning.main

# Or generate + clean in one step
python -m phase2_cleaning.main --generate --seed 42

# Options:
python -m phase2_cleaning.main --input-dir ./data            # Custom input
python -m phase2_cleaning.main --output-dir ./data/cleaned   # Custom output
python -m phase2_cleaning.main --verbose                     # Debug logging
python -m phase2_cleaning.main --help                        # All options
```

**Output**: 13 clean CSVs + clean SQLite + `cleaning_audit_report.csv` in `./output/cleaned/`

### 4. Create BI Views (Phase 4)

```bash
python create_bi_views.py
```

**Output**: 5 denormalised views materialised in `./output/cleaned/ngo_impact_clean.db`

### 5. Validate KPI Queries (Phase 3)

```bash
python validate_kpis.py
```

**Expected output**: All 4 queries pass with < 3,000ms execution time.

### 6. Connect Your BI Tool

**Metabase**: Admin → Databases → Add → SQLite → point to `output/cleaned/ngo_impact_clean.db`  
**Power BI**: Get Data → ODBC → SQLite connector → import the 5 views  
**Tableau**: Connect → SQLite → drag views to canvas

---

## Pipeline Walkthrough

### Phase 1: Data Architecture

The relational schema maps directly to the **Theory of Change** results chain:

| ToC Level | Tables | What They Track |
|-----------|--------|----------------|
| **Inputs** | `donors`, `funding`, `expenses` | Who funds what, how money flows |
| **Activities** | `programs`, `interventions`, `staff` | What the NGO does |
| **Outputs** | `beneficiaries`, `service_delivery` | Who is reached |
| **Outcomes** | `assessments`, `outcome_tracking` | What changed |
| **Impact** | `impact_indicators` | IRIS+ standardised metrics |

The synthetic generator produces **7,400+ rows** with 7 categories of intentional data quality issues:

| Issue | Example | Rate |
|-------|---------|------|
| Missing values | NULL phone, age, income | 12% |
| Inconsistent dates | DD/MM/YYYY mixed with MM-DD-YYYY | 20% |
| Duplicates | Same person registered twice with typos | 3% |
| Name transliterations | "Sharma" → "Sharmaa" | 5% |
| Outliers | Age = 999, negative attendance | 2% |
| Casing chaos | "Male", "male", "MALE", "M" | 10% |
| Orphan references | FK pointing to non-existent ID | 1% |

### Phase 2: Data Cleaning

A **7-step waterfall** executed in topological order (parents before children):

1. **Deduplication** — Two-pass: synthetic `-DUP` removal + fuzzy demographic matching
2. **Date Normalisation** — All formats → ISO 8601 (`dayfirst=True` for Indian convention)
3. **Categorical Standardisation** — Canonical value maps (`'male'` → `'Male'`)
4. **Outlier Treatment** — Domain-justified bounds → nullification (not clamping)
5. **Imputation** — `'Unknown'` for demographics (avoids bias), `median` for numerics
6. **FK Integrity** — Orphan references → NULL (preserve the row, mark the gap)
7. **Type Casting** — Nullable `Int64`, `float64`, whitespace stripping

Every step produces a structured `CleaningReport` → aggregated into `cleaning_audit_report.csv`.

---

## KPI Queries

4 SQL queries mapped to the Problem Statement requirements:

| # | KPI | File | Key SQL Technique | Execution Time |
|---|-----|------|-------------------|---------------|
| 1 | **Cost per Impact** | `sql/kpi_queries/kpi1_cost_per_impact.sql` | CTE pre-aggregation, `DENSE_RANK()` | 2.2 ms |
| 2 | **Programme Progress** | `sql/kpi_queries/kpi2_programme_progress.sql` | `LAG()`, running `SUM()`, `ROW_NUMBER()` | 3.6 ms |
| 3 | **Demographic Reach** | `sql/kpi_queries/kpi3_demographic_reach.sql` | `UNION ALL` pivot, conditional aggregation | 20 ms |
| 4 | **Outcome Effectiveness** | `sql/kpi_queries/kpi4_outcome_effectiveness.sql` | Matched pre/post pairs, `ROW_NUMBER()` | 3.8 ms |

**Combined: 27ms — 111× under the 3-second page load target.**

---

## BI Integration

The `sql/bi_views/create_views.sql` script creates **5 denormalised views** that require **zero joins** in any BI tool:

| View | Rows | Dashboard Section |
|------|------|-------------------|
| `v_cost_per_impact` | 50 | KPI #1 scorecard + bar chart |
| `v_programme_progress` | 200 | KPI #2 scorecard + trend line |
| `v_beneficiary_360` | 2,000 | KPI #3 scorecard + demographics |
| `v_outcome_effectiveness` | 12 | KPI #4 scorecard + heatmap |
| `v_financial_overview` | 48 | Funding vs. expense analysis |

See `docs/bi_dashboard_blueprint.md` for the exact dashboard wireframe, chart types, filter wiring, DAX formulas, and colour palette.

---

## Project Structure

```
NGO-Impact-Engine/
├── requirements.txt                      # Python dependencies
├── create_bi_views.py                    # Materialise BI views in SQLite
├── validate_kpis.py                      # KPI query performance validator
│
├── phase1_data_architecture/             # PHASE 1: Schema + Generation
│   ├── config.py                         #   Constants, IRIS+ indicators, distributions
│   ├── schema.py                         #   13-table SQLAlchemy schema
│   ├── main.py                           #   Generation orchestrator + CLI
│   └── generators/
│       ├── base.py                       #   Abstract generator with utilities
│       ├── dimension_generators.py       #   Regions, donors, programs, staff, IRIS+
│       ├── fact_generators.py            #   Beneficiaries, services, assessments
│       └── noise_injector.py             #   7 data quality degradation methods
│
├── phase2_cleaning/                      # PHASE 2: Cleaning Pipeline
│   ├── config.py                         #   Externalised cleaning rules
│   ├── cleaners.py                       #   7 pure cleaning functions
│   ├── pipeline.py                       #   Topological orchestrator
│   └── main.py                           #   Cleaning CLI entry point
│
├── sql/
│   ├── kpi_queries/                      # PHASE 3: KPI SQL
│   │   ├── kpi1_cost_per_impact.sql
│   │   ├── kpi2_programme_progress.sql
│   │   ├── kpi3_demographic_reach.sql
│   │   └── kpi4_outcome_effectiveness.sql
│   └── bi_views/                         # PHASE 4: BI Semantic Layer
│       └── create_views.sql              #   5 denormalised views
│
├── docs/
│   ├── data_dictionary.md                # Column-level documentation (13 tables)
│   ├── bi_dashboard_blueprint.md         # Star schema, wireframe, DAX formulas
│   └── user_guide.md                     # Non-technical guide for NGO staff
│
└── output/                               # Generated data (gitignored)
    ├── *.csv                             #   Dirty CSVs
    ├── ngo_impact_dirty.db               #   Dirty SQLite
    └── cleaned/
        ├── *.csv                         #   Clean CSVs
        ├── ngo_impact_clean.db           #   Clean SQLite (with BI views)
        └── cleaning_audit_report.csv     #   Audit trail
```

---

## IRIS+ Indicators

The framework includes **20 legitimate IRIS+ metrics** from the [GIIN catalog](https://iris.thegiin.org):

| IRIS+ ID | Indicator | Sector |
|----------|-----------|--------|
| PI4060 | Client Individuals: Total | Cross-sector |
| PI2345 | Educational Attainment | Education |
| PI1479 | Earnings/Wage Improvement | Livelihoods |
| PI9468 | Health Improvements | Healthcare |
| PI3468 | Access to Clean Water | WASH |
| PI6298 | Women Empowered | Women Empowerment |
| PI5532 | Children Enrolled in School | Education |
| PI2201 | Malnutrition Cases Reduced | Nutrition |
| *...and 12 more* | | |

---

## Forking This Repo for Your NGO

This framework is designed to be **forked and customised**:

1. **Replace synthetic data** with your real data (match the CSV schemas in `docs/data_dictionary.md`)
2. **Modify `phase1_data_architecture/config.py`** to update sectors, regions, and indicator mappings for your context
3. **Adjust `phase2_cleaning/config.py`** to add your domain-specific cleaning rules (e.g., add new canonical value maps for your categorical fields)
4. **Run the pipeline** — your clean database and KPI views are ready
5. **Connect your BI tool** and use `docs/bi_dashboard_blueprint.md` as the build spec

---

## Success Metrics (from Problem Statement)

| Metric | Target | Status |
|--------|--------|--------|
| Stakeholder usability rating | ≥ 8/10 | User guide + wireframe delivered |
| Page load time | < 3 seconds | **27ms** (111× under target) |
| KPI tree validated by M&E expert | 1 expert | IRIS+ aligned, ToC mapped |

---

## User Guide

A jargon-free, empathetic user guide for non-technical NGO staff is available at `docs/user_guide.md`. It explains:

- What each KPI means in the context of daily impact work
- How to read RAG (Red/Amber/Green) status indicators
- How to use filters to find specific data
- What to do when a KPI shows RED
- A printable quick reference card

---

## License

MIT — fork freely, build dashboards, measure impact.

---

<div align="center">

*Built with ❤️ for the development sector.*  
*Better measurement → better programmes → better funding outcomes.*

</div>
