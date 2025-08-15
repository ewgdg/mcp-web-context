# Base stage: Ubuntu + Python (shared by builder and runtime)
FROM ubuntu:24.04 AS base

# Set non-interactive frontend to avoid prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Update package index and install essential dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Add the deadsnakes PPA for recent Python versions
RUN add-apt-repository ppa:deadsnakes/ppa

# Install Python 3.13 and essentials
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.13 \
    python3.13-venv \
    python3.13-dev \
    python3-pip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set python3 as the default python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.13 1
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1

# Install uv for Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV UV_CACHE_DIR=/root/.cache/uv

# Builder stage for Python dependencies
FROM base AS builder

# Install uv for Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_CACHE_DIR=/root/.cache/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Install Python project and dependencies
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv sync --locked --no-dev --no-install-project

# Copy source code for installation
COPY ./src ./src
COPY ./test/test_browser.py ./test_browser.py

# Install the application itself
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv sync --frozen --no-dev

# Runtime stage
FROM base AS runtime

# Install runtime-specific dependencies (sway, wayvnc for browser visualization)
RUN apt-get update && apt-get install -y --no-install-recommends \
    sway \
    wayvnc \
    alacritty \
    openssl \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=${UV_CACHE_DIR} \
    uvx patchright install-deps chrome

RUN --mount=type=cache,target=${UV_CACHE_DIR} \
    uvx patchright install chrome

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite+aiosqlite:////app/cache/cache.db

ARG APP_USER=app
ARG UID=1001

# Create user and set up directories for runtime
RUN useradd -m -s /bin/bash -u ${UID} ${APP_USER} && \
    mkdir -p /home/${APP_USER}/.config/sway /run/user/${UID} && \
    chown -R ${APP_USER}:${APP_USER} /home/${APP_USER} /run/user/${UID}

# Generate certificates with separate keys for WayVNC
RUN mkdir -p /certs && \
    openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
    -keyout /certs/key.pem -out /certs/cert.pem -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" && \
    openssl genrsa -traditional -out /certs/rsa_key.pem 4096 && \
    chown -R ${APP_USER}:${APP_USER} /certs

# Install Patchright browser as app user for proper installation location
USER ${APP_USER}

# Copy built Python environment from builder
COPY --from=builder --chown=${APP_USER}:${APP_USER} /app /app

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user for runtime
USER ${APP_USER}
WORKDIR /app

# Test patchright installation after setting up the user environment
RUN /app/.venv/bin/python -c "from patchright.async_api import async_playwright; print('Patchright installed successfully')"

RUN mkdir -p /app/logs /app/cache

# Copy application files
COPY --chown=${APP_USER}:${APP_USER} ./entrypoint.sh ./entrypoint.sh
COPY --chown=${APP_USER}:${APP_USER} ./sway_config /home/${APP_USER}/.config/sway/config

# Update sway config with SWAY_RESOLUTION environment variable
RUN sed -i "s/output HEADLESS-1 mode .*/output HEADLESS-1 mode ${SWAY_RESOLUTION:-1920x1080} position 0,0/" /home/${APP_USER}/.config/sway/config

# Create wayvnc config directory (config will be generated at runtime)
RUN mkdir -p /home/${APP_USER}/.config/wayvnc && \
    chown -R ${APP_USER}:${APP_USER} /home/${APP_USER}/.config/wayvnc

USER root
RUN chmod +x ./entrypoint.sh

USER ${APP_USER}
ENV XDG_CACHE_HOME=/home/${APP_USER}/.cache
ENV XDG_SESSION_TYPE=wayland

# Expose ports
EXPOSE 5910 8000

# Add required Wayland environment variables for swayvnc
ENV XDG_RUNTIME_DIR=/run/user/${UID}
ENV WLR_BACKENDS=headless
ENV WLR_LIBINPUT_NO_DEVICES=1
# fall back to software rendering if no GPU is available
ENV WLR_RENDERER_ALLOW_SOFTWARE=1

# Manually set Sway socket path
ENV SWAYSOCK=${XDG_RUNTIME_DIR}/sway-ipc.sock

# Set custom entrypoint and default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "test_browser.py"]
