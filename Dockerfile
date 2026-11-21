FROM node:24-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 COE_DATA_DIR=/data COE_PROVIDER=demo
WORKDIR /app
COPY pyproject.toml ./
COPY backend/ ./backend/
COPY --from=frontend /build/backend/app/static/ ./backend/app/static/
RUN pip install --no-cache-dir '.[bedrock]' && useradd --create-home coe && mkdir /data && chown coe:coe /data
USER coe
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
