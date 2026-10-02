# --- web build ---
FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- runtime ---
FROM python:3.12-slim@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016
# The pinned base predates Debian's PCRE2 security update.
RUN apt-get update && apt-get install -y --no-install-recommends --only-upgrade \
    libpcre2-8-0=10.46-1~deb13u3 && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 JOBBR_STATIC_DIR=/app/static JOBBR_BASE_PATH=/jobbr
WORKDIR /app
COPY backend/pyproject.toml backend/requirements.lock ./
RUN pip install --require-hashes -r requirements.lock
COPY backend/jobbr ./jobbr
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY scripts/backup.py ./backup.py
RUN pip install --no-deps .
COPY --from=web /web/dist ./static
RUN useradd -r -u 10001 jobbr && mkdir /data && chown jobbr /data
USER 10001
ENV JOBBR_DATABASE_URL=sqlite:////data/jobbr.db
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "jobbr.main:app", "--host", "0.0.0.0", "--port", "8000"]
