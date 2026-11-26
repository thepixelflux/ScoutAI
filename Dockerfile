FROM node:20-alpine AS frontend
WORKDIR /src
COPY frontend/package*.json ./
RUN --mount=type=secret,id=build_ca if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements-deploy.txt ./
RUN --mount=type=secret,id=build_ca if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; pip install --no-cache-dir -r requirements-deploy.txt
COPY backend/ ./
COPY --from=frontend /src/dist /app/static
RUN chmod -R a+rX /app && useradd --create-home --uid 10001 scout
USER scout
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 EMBEDDINGS_ENABLED=false
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.seed && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]
