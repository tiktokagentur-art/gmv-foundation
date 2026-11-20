# Tag: python:3.12-slim
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PORT=8000

WORKDIR /srv

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app

COPY requirements.txt pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations

# Hashes come from requirements.txt. The project itself is installed without
# dependencies and without build isolation, so nothing is resolved from the index.
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: --no-deps -r requirements.txt \
    && python -m pip install --no-cache-dir --no-deps --no-build-isolation . \
    && chown -R app:app /srv

USER app

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; port=os.environ.get('PORT', '8000'); urllib.request.urlopen('http://127.0.0.1:%s/health' % port, timeout=2)"]

# Railway injects PORT. The shell expands it; exec lets the process receive signals.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
