FROM node:24-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NEROOPS_DATA_DIR=/data
WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend/ ./backend/
COPY alembic.ini ./
COPY migrations/ ./migrations/
RUN pip install --no-cache-dir .
COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY frontend/public/fallback.html ./frontend/public/fallback.html
EXPOSE 8000
CMD ["uvicorn", "neroops.main:app", "--host", "0.0.0.0", "--port", "8000"]
