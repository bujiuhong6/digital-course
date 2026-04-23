# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# 依赖来自 pyproject.toml；镜像内不依赖本机已装的 uv
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir --no-compile .

ENV DATABASE_URL=sqlite+aiosqlite:////data/teach.db

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
