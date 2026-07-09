# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# AgentLeak Cloud — production image (web platform + API).
#
# Stage 1 builds the React/Vite frontend into agentleak/web/static.
# Stage 2 is a slim Python runtime that installs the package and serves the
# built bundle + API with uvicorn.
#
# Build:  docker build -t agentleak:latest .
#   Optional Presidio hybrid detection (heavier — pulls spaCy):
#         docker build --build-arg EXTRAS=full -t agentleak:full .
#
# The CLI still works: `docker run --rm agentleak python -m agentleak run ...`.
# ---------------------------------------------------------------------------

FROM node:20-alpine AS frontend
WORKDIR /app/agentleak/web/frontend
# Install deps first for layer caching.
COPY agentleak/web/frontend/package*.json ./
RUN npm ci
# Build — Vite emits to ../static (agentleak/web/static), consumed by stage 2.
COPY agentleak/web/frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    AGENTLEAK_HOME=/data

ARG EXTRAS=gui
WORKDIR /app

# System deps: curl for the container healthcheck only.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install the package. Copy metadata first for caching, then the source.
COPY pyproject.toml README.md ./
COPY agentleak/ ./agentleak/
# Bring in the freshly-built frontend bundle from stage 1.
COPY --from=frontend /app/agentleak/web/static/ ./agentleak/web/static/
RUN pip install ".[${EXTRAS}]"

# Persisted SQLite database lives here (mount a volume).
RUN mkdir -p /data && useradd -r -u 10001 agentleak && chown -R agentleak /data /app
USER agentleak

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=4s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/readyz || exit 1

# Bind on all interfaces inside the container; the reverse proxy terminates TLS.
CMD ["python", "-m", "agentleak", "serve", "--host", "0.0.0.0", "--port", "8000", "--no-browser"]
