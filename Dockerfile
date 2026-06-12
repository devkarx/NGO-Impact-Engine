# ===========================================================================
# NGO Impact Dashboard — Multi-stage Dockerfile
# ===========================================================================
# Stage 1: Install dependencies in an isolated layer (cached across builds)
# Stage 2: Copy source code and run the pipeline
#
# Usage:
#   docker build -t ngo-impact-dashboard .
#   docker run -v $(pwd)/output:/app/output ngo-impact-dashboard
# ===========================================================================

# ── Stage 1: Dependency layer ──────────────────────────────────────────────
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install OS-level dependencies (sqlite3 CLI for debugging)
RUN apt-get update && \
    apt-get install -y --no-install-recommends sqlite3 make && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Application layer ────────────────────────────────────────────
FROM base AS app

WORKDIR /app

# Copy source code
COPY phase1_data_architecture/ ./phase1_data_architecture/
COPY phase2_cleaning/          ./phase2_cleaning/
COPY sql/                      ./sql/
COPY docs/                     ./docs/
COPY create_bi_views.py        .
COPY validate_kpis.py          .
COPY Makefile                  .

# Create output directories
RUN mkdir -p output/cleaned

# Default: run the full pipeline (generate → clean → views → validate)
CMD ["make", "run-all"]
