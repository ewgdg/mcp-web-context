#!/bin/sh
set -e

# Start D-Bus session bus
dbus-daemon --session --address=unix:path=$XDG_RUNTIME_DIR/bus &

# Start sway in the background with unsupported GPU flag
sway --unsupported-gpu &

# Wait a moment for sway to initialize
sleep 2

# Execute the CMD arguments
echo "Executing command: $@"
exec "$@"