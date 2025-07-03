FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    SEND_MESSAGES=True

RUN useradd -m appuser && chown -R appuser:appuser /app

COPY Pipfile Pipfile.lock ./

RUN pip install --no-cache-dir pipenv && \
    pipenv install --deploy --system

COPY cat_watcher cat_watcher
COPY settings.ini cat_watcher/settings.ini

RUN chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import cat_watcher.cat_watcher"

CMD ["python3", "-m", "cat_watcher.cat_watcher"]
