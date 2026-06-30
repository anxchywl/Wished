FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system wished \
    && useradd --system --gid wished --home-dir /app wished \
    && pip install --no-cache-dir --upgrade pip

COPY backend/pyproject.toml ./
COPY backend/alembic.ini ./
COPY --chown=wished:wished backend/app ./app

RUN pip install --no-cache-dir .

USER wished

EXPOSE 8000

# Multiple workers so one CPU-bound request (image processing) can't stall others;
# WEB_CONCURRENCY is tunable per host (default 2 — matches a 2-core box). Access
# logging is disabled because Caddy already logs every request at the edge.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2} --no-access-log"]
