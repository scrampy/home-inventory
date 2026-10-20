FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    DATABASE_URL=sqlite:////app/data/homeinv.db \
    PORT=8000

WORKDIR /app
RUN useradd --system --uid 10001 --create-home --home-dir /home/app app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY wsgi.py docker-entrypoint.sh ./
COPY migrations migrations
COPY homeinv homeinv
# /app/data holds the SQLite database: mount a persistent volume here.
RUN mkdir -p /app/data /app/instance \
    && chown app:app /app/data /app/instance \
    && chmod +x docker-entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '8000'), timeout=4)"

ENTRYPOINT ["./docker-entrypoint.sh"]
