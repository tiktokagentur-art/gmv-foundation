FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PORT=8000

WORKDIR /srv

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations

RUN pip install --no-cache-dir . \
    && chown -R app:app /srv

USER app

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; port=os.environ.get('PORT', '8000'); urllib.request.urlopen('http://127.0.0.1:%s/health' % port, timeout=2)"]

# Railway injects PORT. The shell expands it; exec lets the process receive signals.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
