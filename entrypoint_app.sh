#!/bin/sh
set -e

# Default command if none provided
DEFAULT_CMD="uv run -- python test_browser.py"

# If ENTRYPOINT_CMD environment variable is set, use it
# Otherwise use the default
CMD_TO_RUN="${ENTRYPOINT_CMD:-$DEFAULT_CMD}"

echo "Starting application: $CMD_TO_RUN"
cd /app

# Execute the command
exec $CMD_TO_RUN