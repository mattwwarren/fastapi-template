FROM ghcr.io/astral-sh/uv:0.12.19-python3.13-alpine@sha256:686f1f0ca752b28d29f1a946a429572565a40900d894ee10ed06a4efc81febdd

ENV PYTHONUNBUFFERED=1 \
    UV_NO_DEV=1 \
    UV_PYTHON_INSTALL_DIR=/app/.python

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked -n --no-progress
COPY scripts ./scripts
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY fastapi_template ./fastapi_template/

RUN addgroup -g 1000 -S app && adduser -u 1000 -S app -G app \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["sh", "scripts/start.sh"]
