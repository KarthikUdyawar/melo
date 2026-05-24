FROM python:3.12-slim AS base

# system deps: ffmpeg for audio processing, curl for healthchecks
# yt-dlp JS formats handled via pinned format selector (no Node needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# install uv — pinned version for reproducible builds
COPY --from=ghcr.io/astral-sh/uv:0.5.21 /uv /uvx /usr/local/bin/

WORKDIR /app

# Create non-root user
RUN groupadd --system app && \
    useradd --system --gid app --create-home --shell /bin/false app && \
    chown -R app:app /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# install deps from lockfile — layer cached until pyproject.toml/uv.lock change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# copy source last — layer invalidated only on app code change
COPY app/ ./app/

# Drop privileges
USER app
