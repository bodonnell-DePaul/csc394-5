FROM node:20-alpine AS frontend-build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY frontend ./frontend
COPY vite.config.js ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY --from=frontend-build /app/src/public ./src/public

EXPOSE 10000

CMD ["sh", "-c", "exec uvicorn src.server.main:app --host 0.0.0.0 --port ${PORT:-8000}"]