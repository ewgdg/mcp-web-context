FROM ghcr.io/stephanlensky/swayvnc-chrome:latest

COPY chrome-version.txt /tmp/chrome-version.txt
RUN CHROME_VERSION=$(cat /tmp/chrome-version.txt) && \
    apt-get update && \
    apt-get install -y gnupg wget curl ca-certificates && \
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable=${CHROME_VERSION} 

ARG ENABLE_XWAYLAND

# install xwayland
RUN if [ "$ENABLE_XWAYLAND" = "true" ]; then \
    apt-get update && \
    apt-get -y install xwayland && \
    Xwayland -version && \
    echo "Xwayland installed."; \
    else \
    echo "Xwayland installation skipped."; \
    fi

# set DISPLAY for xwayland
RUN if [ "$ENABLE_XWAYLAND" = "true" ]; then \
    sed -i '/^export XDG_RUNTIME_DIR/i \
    export DISPLAY=${DISPLAY:-:0}' \
    /entrypoint_user.sh; \
    fi

# add `xwayland enable` to sway config
RUN if [ "$ENABLE_XWAYLAND" = "true" ]; then \
    sed -i 's/xwayland disable/xwayland enable/' \
    /home/$DOCKER_USER/.config/sway/config; \
    fi

ARG WAYVNC_UNSUPPORTED_GPU

# add `--unsupported-gpu` flag to sway command
RUN if [ "$WAYVNC_UNSUPPORTED_GPU" = "true" ]; then \
    sed -i 's/sway &/sway --unsupported-gpu \&/' /entrypoint_user.sh; \
    fi

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite+aiosqlite:////app/cache/cache.db

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Make directory for the app
RUN mkdir /app
RUN mkdir /app/cache
RUN mkdir /app/logs
RUN chown -R $DOCKER_USER:$DOCKER_USER /app

# chown for /app directory in entrypoint.sh
# this is to ensure the latterly mounted folders are owned by the user
RUN sed -i '/\/entrypoint_user\.sh/i \
    chown -R "$DOCKER_USER:$DOCKER_USER" /app\
    ' /entrypoint.sh

RUN --mount=type=cache,target=/home/$DOCKER_USER/.cache/uv \
    chown -R $DOCKER_USER:$DOCKER_USER /home/$DOCKER_USER/.cache 

# Switch to the non-root user
USER $DOCKER_USER

# Set the working directory
WORKDIR /app

ENV UV_CACHE_DIR=/home/$DOCKER_USER/.cache/uv

# Install python
RUN uv python install 3.13

# Install the Python project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev --no-install-project

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY --chown=$DOCKER_USER:$DOCKER_USER ./src /app/src
COPY --chown=$DOCKER_USER:$DOCKER_USER ./test/test_browser.py /app/test_browser.py
# ADD ./src /app/src

# Add binaries from the project's virtual environment to the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Sync the project's dependencies and install the project
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev

USER root

# Pass custom command to entrypoint script provided by the base image
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uv", "run", "test_browser.py"]
