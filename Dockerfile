# ---- Base with uv + Python ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS base
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/.venv \
    PATH="/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

RUN git config --global user.name "anntotationtool" && \
    git config --global user.email "annotation@tool.com"

# ---- Prod deps (no dev) ----
FROM base AS deps
COPY pyproject.toml uv.lock README.md ./
RUN ["uv", "sync", "--frozen", "--no-dev", "--compile-bytecode"]

# ---- Runtime (prod) ----
FROM base AS runtime
# copy the venv from deps stage
# COPY --from=deps /app/.venv /app/.venv
# app code last for better caching
COPY . .
# Default prod command (override in compose for dev)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]

# ---- Dev image (with debugger) ----
FROM base AS dev
COPY pyproject.toml uv.lock README.md ./
RUN ["uv", "sync", "--frozen", "--group", "dev", "--group", "docs"]
COPY . .
# wait for VS Code debugger to attach, then run Daphne
WORKDIR /app/core/
ENV DJANGO_SETTINGS_MODULE=core.settings
CMD ["uv", "run", "python", "-X", "frozen_modules=off", "-m", "debugpy","--listen", "0.0.0.0:5678", "-m", "django", "runserver", "0.0.0.0:8000"]
