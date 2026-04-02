# ---- Stage 1: Build frontend static files ----
FROM node:18-alpine AS frontend-build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
# Production: API is same-origin via Nginx, so baseURL = ""
ENV VITE_API_BASE_URL=""
RUN npm run build

# ---- Stage 2: Production backend + static files ----
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app

# Python deps
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen

# Backend source
COPY backend/ .

# Frontend static files (built in stage 1)
COPY --from=frontend-build /app/dist /app/static

EXPOSE 5001

CMD ["uv", "run", "gunicorn", \
     "--bind", "0.0.0.0:5001", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "300", \
     "app:create_app()"]
