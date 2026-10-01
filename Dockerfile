# --- web build ---
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- runtime ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 JOBBR_STATIC_DIR=/app/static JOBBR_BASE_PATH=/jobbr
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/jobbr ./jobbr
RUN pip install .
COPY --from=web /web/dist ./static
RUN useradd -r -u 10001 jobbr && mkdir /data && chown jobbr /data
USER 10001
ENV JOBBR_DATABASE_URL=sqlite:////data/jobbr.db
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "jobbr.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
