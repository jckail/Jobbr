# --- web build ---
FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- runtime ---
FROM python:3.12-slim@sha256:eeb8088e67610b37583880c7627e3931f087cba55a35810819e34a398f624a47
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 JOBBR_STATIC_DIR=/app/static JOBBR_BASE_PATH=/jobbr
WORKDIR /app
COPY backend/pyproject.toml backend/requirements.lock ./
RUN pip install --require-hashes -r requirements.lock
COPY backend/jobbr ./jobbr
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
RUN pip install --no-deps .
COPY --from=web /web/dist ./static
RUN useradd -r -u 10001 jobbr && mkdir /data && chown jobbr /data
USER 10001
ENV JOBBR_DATABASE_URL=sqlite:////data/jobbr.db
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "jobbr.main:app", "--host", "0.0.0.0", "--port", "8000"]
