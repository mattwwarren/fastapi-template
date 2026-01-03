FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir uv
RUN uv pip install --system --no-cache-dir .
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

EXPOSE 8000

CMD ["bash", "scripts/start.sh"]
