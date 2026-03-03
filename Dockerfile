# syntax=docker/dockerfile:1.7

# ---- Base with uv + Python ----
FROM ghcr.io/astral-sh/uv:python3.13-alpine AS base
RUN apk add --no-cache git ca-certificates && update-ca-certificates
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/.venv \
    PATH="/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

RUN git config --global user.name "anntotationtool" && \
    git config --global user.email "annotation@tool.com"

# ---- Runtime deps only ----
FROM base AS deps-runtime
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---- Dev deps only ----
FROM base AS deps-dev
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --group dev --group docs --no-install-project

# ---- Frontend build ----
FROM node:22-alpine AS vite-build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund
COPY vite.config.mjs ./
COPY static ./static
COPY core ./core
RUN npm run build

# ---- Runtime (prod) ----
FROM base AS runtime
COPY --from=deps-runtime /.venv /.venv
COPY core ./core
COPY static ./static
COPY --from=vite-build /app/dist /app/dist
ENV DJANGO_SETTINGS_MODULE=core.settings.prod
RUN mkdir -p /app/staticfiles/ && \
    /.venv/bin/python core/manage.py collectstatic --noinput
WORKDIR /app/core
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "-v", "2", "core.asgi:application"]

# ---- Dev image (with debugger) ----
FROM base AS dev
COPY --from=deps-dev /.venv /.venv
COPY . .
# wait for VS Code debugger to attach, then run Daphne
WORKDIR /app/core/
ENV DJANGO_SETTINGS_MODULE=core.settings
CMD ["/.venv/bin/python", "-X", "frozen_modules=off", "-m", "debugpy","--listen", "0.0.0.0:5678", "-m", "django", "runserver", "0.0.0.0:8000"]
