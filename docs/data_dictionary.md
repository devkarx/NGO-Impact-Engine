# NGO Impact Dashboard — Data Dictionary

> **Version**: 1.0  
> **Last Updated**: 2025-06-12  
> **Schema**: 13 tables mapped to the Theory of Change results chain  
> **Database**: PostgreSQL 14+ / SQLite (local dev)

---

## Table of Contents

1. [regions](#1-regions)
2. [donors](#2-donors)
3. [programs](#3-programs)
4. [staff](#4-staff)
5. [impact_indicators](#5-impact_indicators)
6. [funding](#6-funding)
7. [interventions](#7-interventions)
8. [beneficiaries](#8-beneficiaries)
9. [service_delivery](#9-service_delivery)
10. [assessments](#10-assessments)
11. [outcome_tracking](#11-outcome_tracking)
12. [expenses](#12-expenses)
13. [data_quality_log](#13-data_quality_log)

---

## Entity Relationship Overview

```
┌──────────┐     ┌──────────┐     ┌───────────────┐
│  DONORS  │────▶│ FUNDING  │◀────│   PROGRAMS    │
└──────────┘     └──────────┘     └───────┬───────┘
                                          │
                    ┌─────────────────────┼──────────────────┐
                    ▼                     ▼                  ▼
             ┌──────────────┐   ┌──────────────┐   ┌────────────────┐
             │INTERVENTIONS │   │   EXPENSES   │   │OUTCOME_TRACKING│
             └──────┬───────┘   └──────────────┘   └───────┬────────┘
                    │                                      │
          ┌────────┼────────┐                    ┌─────────▼─────────┐
          ▼                 ▼                    │ IMPACT_INDICATORS │
  ┌───────────────┐ ┌─────────────┐              └───────────────────┘
  │SERVICE_DELIVERY│ │ ASSESSMENTS │
  └───────┬───────┘ └──────┬──────┘
          │                │
          ▼                ▼
    ┌──────────────┐
    │ BENEFICIARIES│──────▶ REGIONS
    └──────────────┘
```

---

## Theory of Change Mapping

| ToC Level      | Tables                                 | Purpose                                    |
|----------------|----------------------------------------|--------------------------------------------|
| **Inputs**     | donors, funding, expenses              | Who funds what, and how money is spent      |
| **Activities** | programs, interventions, staff         | What the NGO does and who delivers it       |
| **Outputs**    | beneficiaries, service_delivery        | Who is reached and what services delivered  |
| **Outcomes**   | assessments, outcome_tracking          | What changed for beneficiaries              |
| **Impact**     | impact_indicators                      | Standardised IRIS+ metrics for reporting    |
| **Meta**       | data_quality_log                       | Audit trail of data issues                  |

---

## 1. `regions`

**Purpose**: Geographic reference table for all NGO operational areas.  
**ToC Level**: Cross-cutting dimension  
**Row Count**: ~25

| Column      | Type       | Nullable | Description                                     | Example             |
|-------------|------------|----------|-------------------------------------------------|---------------------|
| region_id   | VARCHAR(16)| No (PK)  | Unique identifier                                | `REG-001`           |
| state       | VARCHAR(64)| No       | Indian state name                                | `Rajasthan`         |
| district    | VARCHAR(64)| No       | District within the state                        | `Jaipur`            |
| block       | VARCHAR(64)| Yes      | Administrative block (sub-district)              | `Sanganer`          |
| region_type | VARCHAR(32)| No       | Urban / Semi-Urban / Rural / Tribal              | `Rural`             |
| latitude    | FLOAT      | Yes      | GPS latitude for mapping                         | `26.9124`           |
| longitude   | FLOAT      | Yes      | GPS longitude for mapping                        | `75.7873`           |

**Business Rules**:
- `region_type` must be one of: Urban, Semi-Urban, Rural, Tribal
- Latitude range: 8.0 – 37.0 (Indian subcontinent)
- Longitude range: 68.0 – 97.0 (Indian subcontinent)

---

## 2. `donors`

**Purpose**: Registry of all funding sources (bilateral agencies, CSR, foundations, government).  
**ToC Level**: Input  
**Row Count**: ~30

| Column         | Type        | Nullable | Description                          | Example                        |
|----------------|-------------|----------|--------------------------------------|--------------------------------|
| donor_id       | VARCHAR(16) | No (PK)  | Unique identifier                     | `DON-001`                      |
| donor_name     | VARCHAR(128)| No       | Full name of donor entity             | `Tata Trusts CSR`              |
| donor_type     | VARCHAR(64) | No       | Category of donor                     | `Corporate CSR`                |
| country        | VARCHAR(64) | No       | Country of origin                     | `India`                        |
| contact_email  | VARCHAR(128)| Yes      | Primary contact email                 | `grants@tata.org`              |
| onboarded_date | DATE        | Yes      | Date the donor was first registered   | `2019-06-15`                   |

**Business Rules**:
- `donor_type` values: Bilateral Agency, Multilateral Agency, Corporate CSR, Private Foundation, Individual (HNI), Government Scheme, Crowdfunding

---

## 3. `programs`

**Purpose**: High-level development programs aligned to the NGO's strategic plan.  
**ToC Level**: Activity  
**Row Count**: ~12

| Column               | Type        | Nullable | Description                          | Example                          |
|----------------------|-------------|----------|--------------------------------------|----------------------------------|
| program_id           | VARCHAR(16) | No (PK)  | Unique identifier                     | `PRG-001`                        |
| program_name         | VARCHAR(128)| No       | Descriptive program name              | `Pragati Education Programme`    |
| sector               | VARCHAR(64) | No       | Thematic sector                       | `Education`                      |
| start_date           | DATE        | No       | Program launch date                   | `2021-07-01`                     |
| end_date             | DATE        | Yes      | Planned end date (NULL if ongoing)    | `2024-03-31`                     |
| target_beneficiaries | INTEGER     | Yes      | Planned beneficiary count             | `300`                            |
| region_id            | VARCHAR(16) | Yes (FK) | Primary operating region → regions    | `REG-005`                        |
| status               | VARCHAR(32) | No       | Active / Completed / Suspended        | `Active`                         |

**Business Rules**:
- `sector` values: Education, Healthcare, Livelihoods, WASH, Women Empowerment, Agriculture, Financial Inclusion, Child Protection, Nutrition, Governance & Advocacy
- `end_date` is NULL for ongoing programs

---

## 4. `staff`

**Purpose**: Field workers, coordinators, M&E officers, and support staff.  
**ToC Level**: Activity  
**Row Count**: ~60

| Column    | Type        | Nullable | Description                     | Example              |
|-----------|-------------|----------|---------------------------------|----------------------|
| staff_id  | VARCHAR(16) | No (PK)  | Unique identifier                | `STF-001`            |
| full_name | VARCHAR(128)| No       | Staff member's full name         | `Priya Sharma`       |
| role      | VARCHAR(64) | No       | Job title / role                 | `Field Coordinator`  |
| region_id | VARCHAR(16) | Yes (FK) | Assigned region → regions        | `REG-003`            |
| hire_date | DATE        | Yes      | Date of joining                  | `2020-01-15`         |
| phone     | VARCHAR(20) | Yes      | Contact phone number             | `+91-9876543210`     |
| email     | VARCHAR(128)| Yes      | Work email address               | `priya@ngo.org`      |
| is_active | INTEGER     | No       | 1 = active, 0 = inactive        | `1`                  |

---

## 5. `impact_indicators`

**Purpose**: IRIS+ standardised impact metrics from the GIIN catalog.  
**ToC Level**: Impact  
**Row Count**: ~20

| Column         | Type        | Nullable | Description                          | Example                       |
|----------------|-------------|----------|--------------------------------------|-------------------------------|
| indicator_id   | VARCHAR(16) | No (PK)  | Internal identifier                   | `IND-001`                     |
| iris_id        | VARCHAR(16) | No       | IRIS+ catalog metric ID               | `PI4060`                      |
| indicator_name | VARCHAR(128)| No       | Human-readable name                   | `Client Individuals: Total`   |
| category       | VARCHAR(32) | No       | Output / Outcome                      | `Output`                      |
| unit           | VARCHAR(32) | No       | Unit of measurement                   | `Count`                       |
| sector         | VARCHAR(64) | No       | Thematic sector covered               | `Cross-sector`                |

**Business Rules**:
- IRIS+ IDs sourced from the [GIIN IRIS+ Catalog](https://iris.thegiin.org/)
- `category` maps to the ToC level: Output-level indicators vs. Outcome-level indicators

---

## 6. `funding`

**Purpose**: Financial inflows from donors to programs.  
**ToC Level**: Input  
**Row Count**: ~80

| Column            | Type          | Nullable | Description                        | Example         |
|-------------------|---------------|----------|------------------------------------|-----------------|
| funding_id        | VARCHAR(16)   | No (PK)  | Unique identifier                   | `FND-001`       |
| donor_id          | VARCHAR(16)   | No (FK)  | Source donor → donors               | `DON-005`       |
| program_id        | VARCHAR(16)   | No (FK)  | Receiving program → programs        | `PRG-002`       |
| amount_inr        | NUMERIC(15,2) | No       | Grant amount in Indian Rupees       | `1500000.00`    |
| currency          | VARCHAR(8)    | No       | Original currency code              | `INR`           |
| disbursement_date | DATE          | Yes      | Date funds were disbursed           | `2022-10-01`    |
| fiscal_year       | VARCHAR(12)   | No       | Indian FY label                     | `FY2022-23`     |
| grant_type        | VARCHAR(32)   | Yes      | Restricted / Unrestricted / Project-Tied | `Restricted` |

---

## 7. `interventions`

**Purpose**: Specific activities delivered under a program (workshops, health camps, etc.).  
**ToC Level**: Activity  
**Row Count**: ~150

| Column             | Type        | Nullable | Description                          | Example                              |
|--------------------|-------------|----------|--------------------------------------|--------------------------------------|
| intervention_id    | VARCHAR(16) | No (PK)  | Unique identifier                     | `INT-001`                            |
| program_id         | VARCHAR(16) | No (FK)  | Parent program → programs             | `PRG-003`                            |
| intervention_type  | VARCHAR(64) | No       | Type of activity                      | `Workshop`                           |
| title              | VARCHAR(256)| No       | Descriptive title                     | `Workshop — Education (Pragati...)`  |
| scheduled_date     | DATE        | No       | Planned delivery date                 | `2022-11-15`                         |
| actual_date        | DATE        | Yes      | Actual delivery date (NULL if pending)| `2022-11-18`                         |
| staff_id           | VARCHAR(16) | Yes (FK) | Lead facilitator → staff              | `STF-012`                            |
| region_id          | VARCHAR(16) | Yes (FK) | Delivery location → regions           | `REG-007`                            |
| planned_attendance | INTEGER     | Yes      | Expected number of attendees          | `50`                                 |
| actual_attendance  | INTEGER     | Yes      | Recorded number of attendees          | `43`                                 |

---

## 8. `beneficiaries`

**Purpose**: Individuals receiving services from the NGO.  
**ToC Level**: Output  
**Row Count**: ~2,000

| Column            | Type        | Nullable | Description                             | Example                  |
|-------------------|-------------|----------|-----------------------------------------|--------------------------|
| beneficiary_id    | VARCHAR(16) | No (PK)  | Unique identifier                        | `BEN-00001`              |
| full_name         | VARCHAR(128)| No       | Beneficiary's full name                  | `Anita Kumari`           |
| age               | INTEGER     | Yes      | Age in years at registration             | `34`                     |
| gender            | VARCHAR(32) | Yes      | Male / Female / Non-Binary / etc.        | `Female`                 |
| phone             | VARCHAR(20) | Yes      | Contact phone number                     | `+91-7654321098`         |
| education_level   | VARCHAR(64) | Yes      | Highest education attained               | `Primary (1-5)`          |
| income_bracket    | VARCHAR(64) | Yes      | Annual household income bracket          | `BPL (Below ₹1 lakh)`   |
| region_id         | VARCHAR(16) | Yes (FK) | Home region → regions                    | `REG-012`                |
| registration_date | DATE        | Yes      | Date registered in the system            | `2022-03-10`             |
| program_id        | VARCHAR(16) | Yes (FK) | Primary program enrolled in → programs   | `PRG-001`                |
| household_size    | INTEGER     | Yes      | Number of household members              | `5`                      |
| is_disabled       | INTEGER     | Yes      | 1 = yes, 0 = no, NULL = not recorded    | `0`                      |

**Business Rules**:
- `age` valid range: 0–110
- `income_bracket` values: BPL (Below ₹1 lakh), LIG (₹1-3 lakh), MIG (₹3-6 lakh), HIG (Above ₹6 lakh)
- `education_level` values: No Formal Education, Primary (1-5), Upper Primary (6-8), Secondary (9-10), Higher Secondary (11-12), Graduate, Post-Graduate

---

## 9. `service_delivery`

**Purpose**: Records of individual services delivered to beneficiaries.  
**ToC Level**: Output  
**Row Count**: ~2,500

| Column          | Type        | Nullable | Description                          | Example                           |
|-----------------|-------------|----------|--------------------------------------|------------------------------------|
| delivery_id     | VARCHAR(16) | No (PK)  | Unique identifier                     | `DEL-00001`                        |
| beneficiary_id  | VARCHAR(16) | No (FK)  | Recipient → beneficiaries             | `BEN-00042`                        |
| intervention_id | VARCHAR(16) | No (FK)  | Activity → interventions              | `INT-015`                          |
| delivery_date   | DATE        | No       | Date of service delivery              | `2023-01-20`                       |
| status          | VARCHAR(32) | No       | Completed / Partially Completed / etc.| `Completed`                        |
| dosage          | INTEGER     | Yes      | Number of sessions/units received     | `3`                                |
| notes           | TEXT        | Yes      | Field worker's free-text notes        | `Beneficiary engaged well.`       |

---

## 10. `assessments`

**Purpose**: Pre/post tests and surveys measuring beneficiary outcome changes.  
**ToC Level**: Outcome  
**Row Count**: ~1,800

| Column            | Type        | Nullable | Description                          | Example                       |
|-------------------|-------------|----------|--------------------------------------|-------------------------------|
| assessment_id     | VARCHAR(16) | No (PK)  | Unique identifier                     | `ASM-00001`                   |
| beneficiary_id    | VARCHAR(16) | No (FK)  | Assessed beneficiary → beneficiaries  | `BEN-00100`                   |
| intervention_id   | VARCHAR(16) | Yes (FK) | Related intervention → interventions  | `INT-030`                     |
| assessment_type   | VARCHAR(64) | No       | Type of assessment                    | `Post-Test`                   |
| assessment_date   | DATE        | No       | Date conducted                        | `2023-06-15`                  |
| score             | FLOAT       | Yes      | Numeric score                         | `72.5`                        |
| max_score         | FLOAT       | Yes      | Maximum possible score                | `100.0`                       |
| assessor_staff_id | VARCHAR(16) | Yes (FK) | Assessor → staff                      | `STF-008`                     |
| remarks           | TEXT        | Yes      | Qualitative notes                     | `Significant improvement.`    |

**Business Rules**:
- `score` must be ≥ 0 and ≤ `max_score`
- `assessment_type` values: Pre-Test, Post-Test, Midline Survey, Endline Survey, Spot Check, Follow-Up Interview

---

## 11. `outcome_tracking`

**Purpose**: Periodic tracking of program outcomes against IRIS+ indicators.  
**ToC Level**: Outcome  
**Row Count**: ~200

| Column           | Type        | Nullable | Description                          | Example              |
|------------------|-------------|----------|--------------------------------------|----------------------|
| outcome_id       | VARCHAR(16) | No (PK)  | Unique identifier                     | `OUT-001`            |
| program_id       | VARCHAR(16) | No (FK)  | Program → programs                    | `PRG-001`            |
| indicator_id     | VARCHAR(16) | No (FK)  | Indicator → impact_indicators         | `IND-003`            |
| reporting_period | VARCHAR(16) | No       | Quarter label                         | `Q2-FY2023-24`       |
| target_value     | FLOAT       | Yes      | Planned target                        | `250.0`              |
| actual_value     | FLOAT       | Yes      | Achieved value                        | `210.5`              |
| status           | VARCHAR(32) | No       | On Track / At Risk / Achieved / etc.  | `On Track`           |
| data_source      | VARCHAR(128)| Yes      | Data collection source                | `Field Survey`       |
| verified_by      | VARCHAR(16) | Yes (FK) | Verifier → staff                      | `STF-003`            |

---

## 12. `expenses`

**Purpose**: Financial outflows / expenditures against programs.  
**ToC Level**: Input  
**Row Count**: ~300

| Column            | Type          | Nullable | Description                          | Example             |
|-------------------|---------------|----------|--------------------------------------|---------------------|
| expense_id        | VARCHAR(16)   | No (PK)  | Unique identifier                     | `EXP-001`           |
| program_id        | VARCHAR(16)   | No (FK)  | Program → programs                    | `PRG-004`           |
| category          | VARCHAR(64)   | No       | Expense category                      | `Personnel`         |
| amount_inr        | NUMERIC(15,2) | No       | Amount in Indian Rupees               | `45000.00`          |
| expense_date      | DATE          | No       | Date incurred                         | `2023-03-15`        |
| fiscal_year       | VARCHAR(12)   | No       | Indian FY label                       | `FY2022-23`         |
| approved_by       | VARCHAR(16)   | Yes (FK) | Approver → staff                      | `STF-002`           |
| receipt_available | INTEGER       | Yes      | 1 = yes, 0 = no                       | `1`                 |

**Business Rules**:
- `category` values: Personnel, Travel & Field, Materials & Supplies, Training & Capacity Building, Infrastructure, Monitoring & Evaluation, Administrative Overhead, Communication & Outreach

---

## 13. `data_quality_log`

**Purpose**: Audit trail of data quality issues detected during cleaning.  
**ToC Level**: Meta  
**Row Count**: ~100

| Column        | Type        | Nullable | Description                          | Example                    |
|---------------|-------------|----------|--------------------------------------|-----------------------------|
| log_id        | VARCHAR(16) | No (PK)  | Unique identifier                     | `DQL-001`                   |
| table_name    | VARCHAR(64) | No       | Table where issue was found           | `beneficiaries`             |
| column_name   | VARCHAR(64) | Yes      | Specific column affected              | `gender`                    |
| record_id     | VARCHAR(16) | Yes      | ID of affected record                 | `BEN-00042`                 |
| issue_type    | VARCHAR(64) | No       | Type of data quality issue            | `inconsistent_casing`       |
| description   | TEXT        | Yes      | Human-readable description            | `'male' → 'Male'`          |
| detected_date | DATE        | No       | Date the issue was logged             | `2025-06-12`                |
| resolved      | INTEGER     | No       | 1 = resolved, 0 = open               | `0`                         |

**Issue Types**: missing_value, inconsistent_date_format, duplicate_entry, transliteration_variant, inconsistent_casing, outlier, orphan_reference

---

## Foreign Key Relationships

| Child Table       | FK Column         | Parent Table       | Parent PK      |
|-------------------|-------------------|--------------------|----------------|
| programs          | region_id         | regions            | region_id      |
| staff             | region_id         | regions            | region_id      |
| funding           | donor_id          | donors             | donor_id       |
| funding           | program_id        | programs           | program_id     |
| interventions     | program_id        | programs           | program_id     |
| interventions     | staff_id          | staff              | staff_id       |
| interventions     | region_id         | regions            | region_id      |
| beneficiaries     | region_id         | regions            | region_id      |
| beneficiaries     | program_id        | programs           | program_id     |
| service_delivery  | beneficiary_id    | beneficiaries      | beneficiary_id |
| service_delivery  | intervention_id   | interventions      | intervention_id|
| assessments       | beneficiary_id    | beneficiaries      | beneficiary_id |
| assessments       | intervention_id   | interventions      | intervention_id|
| assessments       | assessor_staff_id | staff              | staff_id       |
| outcome_tracking  | program_id        | programs           | program_id     |
| outcome_tracking  | indicator_id      | impact_indicators  | indicator_id   |
| outcome_tracking  | verified_by       | staff              | staff_id       |
| expenses          | program_id        | programs           | program_id     |
| expenses          | approved_by       | staff              | staff_id       |
