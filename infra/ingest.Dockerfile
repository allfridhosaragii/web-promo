FROM python:3.12-slim AS base
RUN pip install --no-cache-dir uv
WORKDIR /app/services/ingest
COPY services/ingest/pyproject.toml services/ingest/uv.lock ./
# uv sync --frozen MURNI (tanpa fallback `|| uv sync`): uv.lock WAJIB ada dan
# cocok dengan pyproject.toml, kalau tidak build GAGAL dengan jelas.
RUN uv sync --frozen
RUN uv run playwright install --with-deps chromium
COPY services/ingest ./
CMD ["uv", "run", "python", "-m", "jobs.scheduler"]
