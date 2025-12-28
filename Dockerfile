FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    SEND_MESSAGES=True \
    UV_SYSTEM_PYTHON=1

RUN useradd -m appuser && chown -R appuser:appuser /app

COPY pyproject.toml uv.lock ./

RUN uv pip install --no-cache -r pyproject.toml

COPY cat_watcher cat_watcher
COPY settings.ini cat_watcher/settings.ini

RUN chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import cat_watcher.cat_watcher"

CMD ["python3", "-m", "cat_watcher.cat_watcher"]
