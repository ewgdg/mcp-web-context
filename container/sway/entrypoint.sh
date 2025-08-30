#!/bin/sh
set -e

# --- FIX for systemd-related errors on Ubuntu/Debian base images ---
# These OSes have startup scripts that try to talk to systemd.
# This shim intercepts the `systemctl` command and prevents errors.
SHIM_DIR="/tmp/fake-bin"
mkdir -p "$SHIM_DIR"
cat <<EOF > "$SHIM_DIR/systemctl"
#!/bin/sh
# This shim intercepts calls to systemctl to prevent errors.
exit 0
EOF
chmod +x "$SHIM_DIR/systemctl"
export PATH="$SHIM_DIR:$PATH"
# --- End of fix ---

# Ensure the XDG_RUNTIME_DIR is set up correctly.
# This is critical for Wayland, D-Bus, and other services.
if [ -z "$XDG_RUNTIME_DIR" ]; then
  export XDG_RUNTIME_DIR=/tmp/$(id -u)-runtime-dir
  if ! [ -d "$XDG_RUNTIME_DIR" ]; then
    mkdir -p "$XDG_RUNTIME_DIR"
    chmod 0700 "$XDG_RUNTIME_DIR"
  fi
fi

# Define a cleanup function to gracefully shut down Sway.
# This will be called when the script exits.
cleanup() {
    echo "Entrypoint script exiting, shutting down processes..."
    
    # Send SIGTERM to all related processes
    pkill -x -TERM sway || true
    
    # Wait briefly for graceful shutdown
    timeout=30  # 3 seconds in 0.1s increments
    while [ $timeout -gt 0 ] && pgrep -x sway >/dev/null 2>&1; do
        sleep 0.1
        timeout=$((timeout - 1))
    done
    
    # Force kill any remaining processes
    pkill -x -KILL sway || true
    
    echo "Process cleanup completed"
}

# Generate WayVNC config with runtime environment variables
echo "Generating WayVNC config..."
printf "address=0.0.0.0
port=${WAYVNC_PORT:-5910}
enable_auth=${WAYVNC_ENABLE_AUTH:-false}
username=${WAYVNC_USERNAME:-wayvnc}
password=${WAYVNC_PASSWORD:-wayvnc}
private_key_file=/certs/key.pem
certificate_file=/certs/cert.pem
rsa_private_key_file=/certs/rsa_key.pem
" > /home/app/.config/wayvnc/config

# Start sway in the background with unsupported GPU flag
echo "Starting Sway in the background..."
dbus-run-session sway --unsupported-gpu &
DBUS_SESSION_PID=$!
echo "D-Bus session PID: $DBUS_SESSION_PID"

# Now that Sway is running, set up cleanup traps
echo "Setting up cleanup traps..."
trap cleanup EXIT TERM INT

# Wait for Sway's Inter-Process Communication (IPC) to be ready.
# This is the most reliable way to know Sway has started successfully
# before launching an application inside it.
echo "Waiting for Sway IPC to be ready..."
until swaymsg -t get_version >/dev/null 2>&1; do
    sleep 0.5
done
echo "Sway is ready."

# Wait for sway to create Wayland socket and set WAYLAND_DISPLAY
echo "Waiting for Wayland socket..."
RETRIES=5
for i in $(seq 1 $RETRIES); do
    # Look for wayland socket in XDG_RUNTIME_DIR
    WAYLAND_SOCKET=$(find "$XDG_RUNTIME_DIR" -name "wayland-*" -type s 2>/dev/null | head -1)
    if [ -n "$WAYLAND_SOCKET" ]; then
        # Extract socket name (e.g., wayland-1 from /run/user/1001/wayland-1)
        WAYLAND_DISPLAY=$(basename "$WAYLAND_SOCKET")
        export WAYLAND_DISPLAY
        echo "Found Wayland socket: $WAYLAND_DISPLAY"
        break
    fi
    echo "Attempt $i/$RETRIES: No Wayland socket found, waiting..."
    sleep 1
done

if [ -z "$WAYLAND_DISPLAY" ]; then
    echo "WARNING: No Wayland socket found after $RETRIES attempts"
    echo "Available files in $XDG_RUNTIME_DIR:"
    ls -la "$XDG_RUNTIME_DIR" 2>/dev/null || echo "Cannot access $XDG_RUNTIME_DIR"
fi

# Forward signals to command process
forward_signal() {
    echo "Received signal, forwarding to command process (PID: $COMMAND_PID)..."
    if [ -n "$COMMAND_PID" ] && kill -0 "$COMMAND_PID" 2>/dev/null; then
        kill -TERM "$COMMAND_PID" 2>/dev/null
        # Wait for graceful shutdown
        wait "$COMMAND_PID" 2>/dev/null || true
    fi
}

# Set up signal forwarding
trap forward_signal TERM INT

# Execute the CMD arguments (use & to run in background so trap stays active)
if [ $# -eq 0 ]; then
    echo "No command provided, running sleep infinity..."
    sleep infinity &
    COMMAND_PID=$!
else
    echo "Executing command: $@"
    "$@" &
    COMMAND_PID=$!
fi

# Wait for the command process to complete
wait $COMMAND_PID