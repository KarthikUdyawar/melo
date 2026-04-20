FROM python:3.12-slim

# system deps: ffmpeg for audio processing, curl for healthchecks, node 20 for yt-dlp JS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# copy dependency manifest
COPY pyproject.toml ./

# install all prod deps (no lockfile required)
RUN uv sync --no-dev

# copy source
COPY app/ ./app/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"