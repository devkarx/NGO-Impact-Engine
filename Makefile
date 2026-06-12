# ===========================================================================
# NGO Impact Dashboard — Makefile
# ===========================================================================
# Standard automation for Linux/macOS/WSL environments.
#
# Usage:
#   make install        — Create venv and install dependencies
#   make generate-data  — Run Phase 1 (synthetic data generation)
#   make clean-data     — Run Phase 2 (cleaning pipeline)
#   make create-views   — Run Phase 4 (BI semantic layer views)
#   make validate       — Run Phase 3 (KPI query validation)
#   make run-all        — Execute the full pipeline end-to-end
#   make lint           — Run ruff + flake8
#   make docker-up      — Build and run via Docker Compose
#   make wipe           — Delete all generated output
# ===========================================================================

.PHONY: help install generate-data clean-data create-views validate \
        run-all lint docker-up docker-down wipe

# Default Python interpreter
PYTHON ?= python
PIP    ?= pip

# Directories
OUTPUT_DIR     := output
CLEAN_DIR      := output/cleaned
CLEAN_DB       := $(CLEAN_DIR)/ngo_impact_clean.db

# ── Help (default target) ─────────────────────────────────────────────────
help:
	@echo ""
	@echo "  NGO Impact Dashboard — Makefile Commands"
	@echo "  ========================================="
	@echo ""
	@echo "  make install        Install Python dependencies"
	@echo "  make generate-data  Phase 1: Generate synthetic data"
	@echo "  make clean-data     Phase 2: Clean the data"
	@echo "  make create-views   Phase 4: Create BI views"
	@echo "  make validate       Phase 3: Validate KPI queries"
	@echo "  make run-all        Run the full pipeline"
	@echo "  make lint           Run linters (ruff + flake8)"
	@echo "  make docker-up      Build & run via Docker Compose"
	@echo "  make docker-down    Stop Docker containers"
	@echo "  make wipe           Delete all generated output"
	@echo ""

# ── Setup ──────────────────────────────────────────────────────────────────
install:
	@echo "[1/2] Upgrading pip..."
	$(PIP) install --upgrade pip
	@echo "[2/2] Installing dependencies..."
	$(PIP) install -r requirements.txt
	@echo "Done. Dependencies installed."

# ── Phase 1: Synthetic Data Generation ─────────────────────────────────────
generate-data:
	@echo "=== Phase 1: Generating synthetic data ==="
	$(PYTHON) -m phase1_data_architecture.main
	@echo "=== Phase 1 complete: output/ populated ==="

# ── Phase 2: Data Cleaning ─────────────────────────────────────────────────
clean-data: $(OUTPUT_DIR)/beneficiaries.csv
	@echo "=== Phase 2: Cleaning data ==="
	$(PYTHON) -m phase2_cleaning.main
	@echo "=== Phase 2 complete: output/cleaned/ populated ==="

$(OUTPUT_DIR)/beneficiaries.csv:
	@echo "Dirty data not found. Running Phase 1 first..."
	$(MAKE) generate-data

# ── Phase 4: BI Views ──────────────────────────────────────────────────────
create-views: $(CLEAN_DB)
	@echo "=== Phase 4: Creating BI views ==="
	$(PYTHON) create_bi_views.py
	@echo "=== Phase 4 complete: 5 views materialised ==="

$(CLEAN_DB):
	@echo "Clean database not found. Running Phase 2 first..."
	$(MAKE) clean-data

# ── Phase 3: KPI Validation ───────────────────────────────────────────────
validate: $(CLEAN_DB)
	@echo "=== Phase 3: Validating KPI queries ==="
	$(PYTHON) validate_kpis.py
	@echo "=== Phase 3 complete: all KPIs validated ==="

# ── Full Pipeline ──────────────────────────────────────────────────────────
run-all:
	@echo "=========================================="
	@echo "  NGO Impact Dashboard — Full Pipeline"
	@echo "=========================================="
	$(MAKE) generate-data
	$(MAKE) clean-data
	$(MAKE) create-views
	$(MAKE) validate
	@echo ""
	@echo "=========================================="
	@echo "  Pipeline complete."
	@echo "  Clean database: $(CLEAN_DB)"
	@echo "  Audit report:   $(CLEAN_DIR)/cleaning_audit_report.csv"
	@echo "=========================================="

# ── Linting ────────────────────────────────────────────────────────────────
lint:
	@echo "=== Running ruff ==="
	-$(PYTHON) -m ruff check . --output-format=concise
	@echo ""
	@echo "=== Running flake8 ==="
	-$(PYTHON) -m flake8 . \
		--max-line-length=120 \
		--max-complexity=15 \
		--exclude=__pycache__,.venv,output \
		--ignore=E501,W503,E203 \
		--statistics
	@echo "=== Lint complete ==="

# ── Docker ─────────────────────────────────────────────────────────────────
docker-up:
	docker compose up --build pipeline

docker-down:
	docker compose down

docker-metabase:
	@echo "Starting Metabase on http://localhost:3000 ..."
	docker compose up --build

# ── Cleanup ────────────────────────────────────────────────────────────────
wipe:
	@echo "Removing generated output..."
	rm -rf $(OUTPUT_DIR)
	@echo "Done. Run 'make run-all' to regenerate."
