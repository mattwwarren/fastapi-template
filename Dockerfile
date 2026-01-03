FROM ghcr.io/astral-sh/uv:alpine

ENV PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_NO_DEV=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked -n --no-progress
COPY scripts ./scripts
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY app ./app

EXPOSE 8000

CMD ["sh", "scripts/start.sh"]
