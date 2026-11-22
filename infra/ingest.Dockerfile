FROM python:3.12-slim AS base
RUN pip install --no-cache-dir uv
WORKDIR /app/services/ingest
COPY services/ingest/pyproject.toml services/ingest/uv.lock* ./
RUN uv sync --frozen || uv sync
COPY services/ingest ./
CMD ["uv", "run", "python", "-m", "jobs.scheduler"]
