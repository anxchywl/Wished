FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system wished \
    && useradd --system --gid wished --home-dir /app wished \
    && pip install --no-cache-dir --upgrade pip

COPY pyproject.toml ./
COPY alembic.ini ./
COPY --chown=wished:wished app ./app

RUN pip install --no-cache-dir .

USER wished

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
