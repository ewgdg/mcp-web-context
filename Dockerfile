# Builder stage for Python dependencies
FROM python:3.13-slim AS builder

# Install uv for Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_CACHE_DIR=/root/.cache/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Install Python project and fetch Camoufox browser
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv sync --locked --no-dev --no-install-project

# Copy source code for installation
COPY ./src ./src
COPY ./test/test_browser.py ./test_browser.py

# Install the application itself
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv sync --frozen --no-dev

# Runtime stage
FROM python:3.13-bookworm

# Update package index and install runtime system dependencies
RUN apt-get update && apt-get install -y \
    sway \
    wayvnc \
    curl \
    wget \
    ca-certificates
# && rm -rf /var/lib/apt/lists/*

# Install uv for Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN --mount=type=cache,target=/root/.cache/uv \
    uvx playwright install-deps firefox

RUN rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite+aiosqlite:////app/cache/cache.db

ARG APP_USER=app
ARG UID=1000
# Create user and set up directories for runtime
RUN useradd -m -s /bin/bash -u ${UID} ${APP_USER} && \
    mkdir -p /home/${APP_USER}/.config/sway /home/${APP_USER}/.cache/camoufox /run/user/${UID} && \
    chown -R ${APP_USER}:${APP_USER} /home/${APP_USER} /run/user/${UID}

# Install Camoufox browser as app user for proper installation location
USER ${APP_USER}
RUN --mount=type=cache,target=/home/${APP_USER}/.cache/uv,uid=${UID},gid=${UID} \
    uvx camoufox fetch

# Copy built Python environment from builder
COPY --from=builder --chown=${APP_USER}:${APP_USER} /app /app

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

RUN python -m camoufox version

# Switch to non-root user for runtime
USER ${APP_USER}
WORKDIR /app

RUN mkdir -p /app/.logs /app/cache
# RUN mkdir -p /home/${APP_USER}/.cache/camoufox

# Copy application files
COPY --chown=${APP_USER}:${APP_USER} ./entrypoint.sh ./entrypoint.sh
COPY --chown=${APP_USER}:${APP_USER} ./sway_config /home/${APP_USER}/.config/sway/config

USER root
RUN chmod +x ./entrypoint.sh

USER ${APP_USER}
ENV HOME=/home/${APP_USER}
ENV XDG_CACHE_HOME=/home/${APP_USER}/.cache

# Expose ports
EXPOSE 5910 8000

# Add required Wayland environment variables for swayvnc
ENV XDG_RUNTIME_DIR=/run/user/${UID}
# ENV WLR_BACKENDS=headless
# ENV WLR_LIBINPUT_NO_DEVICES=1
ENV SWAYSOCK=/tmp/sway-ipc.sock
ENV MOZ_ENABLE_WAYLAND=1
# allow software rendering when GPU acceleration isn't available
# ENV WLR_RENDERER_ALLOW_SOFTWARE=1

# Set custom entrypoint and default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "test_browser.py"]
