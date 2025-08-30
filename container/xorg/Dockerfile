FROM kasmweb/core-ubuntu-noble:develop
USER root

# https://www.kasmweb.com/docs/latest/how_to/building_images.html
ENV HOME=/home/kasm-default-profile
ENV STARTUPDIR=/dockerstartup
ENV INST_SCRIPTS=$STARTUPDIR/install
WORKDIR $HOME

######### Customize Container Here ###########

# Set non-interactive frontend to avoid prompts during installation
# ENV DEBIAN_FRONTEND=noninteractive

# Update package index and install essential dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    curl \
    wget \
    ca-certificates \
    build-essential \
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
    && rm -rf /var/lib/apt/lists/*

# Set python3 as the default python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.13 1
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1

# Install uv for Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV UV_CACHE_DIR=/root/.cache/uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Create app directory and copy project files
RUN mkdir -p /app
WORKDIR /app

# Set up application directories with correct ownership
RUN mkdir -p /app/logs /app/cache /app/browser_data

# Install browser dependencies first (cache-friendly layer)
COPY requirements-browser.txt ./
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv pip install -r requirements-browser.txt

# Install Chrome browsers using patchright (after patchright is installed)
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv run patchright install-deps chrome

RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv run patchright install chrome

# Copy Python project files
COPY pyproject.toml uv.lock ./

# Install remaining dependencies
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv sync --frozen --no-dev --no-install-project

COPY ./src ./src
COPY ./misc/test_browser.py ./test_browser.py

# install project
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv sync --frozen --no-dev

# Copy application configuration
COPY ./config.yaml /app/config.yaml

# Copy custom startup script
COPY ./container/xorg/custom_startup.sh $STARTUPDIR/custom_startup.sh
RUN chmod +x $STARTUPDIR/custom_startup.sh

# Set environment variables for the application
ENV DATABASE_URL=sqlite+aiosqlite:////app/cache/cache.db
ENV PATH="/app/.venv/bin:$PATH"

# Test patchright installation
RUN /app/.venv/bin/python -c "from patchright.async_api import async_playwright; print('Patchright installed successfully')"

######### End Customizations ###########

RUN chown 1000:0 $HOME
RUN $STARTUPDIR/set_user_permission.sh $HOME

ENV HOME=/home/kasm-user
WORKDIR $HOME
RUN mkdir -p $HOME && chown -R 1000:0 $HOME

# Set ownership of app directory
RUN chown -R 1000:0 /app

USER 1000

# Expose ports (FastAPI on 8000, KasmVNC on 6901)
EXPOSE 6901 8000

# Set working directory back to app
WORKDIR /app