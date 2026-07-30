#!/bin/bash
# ============================================
# SlimPDF - Server Control Script
#   Usage: bash scripts/server.sh {start|stop|restart|status}
#   Port:  SLIMPDF_PORT=5050 bash scripts/server.sh start
# ============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

PORT="${SLIMPDF_PORT:-5000}"
HOST="${SLIMPDF_HOST:-127.0.0.1}"
PID_FILE="$PROJECT_DIR/.slimpdf.pid"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/server.log"
HEALTH_URL="http://$HOST:$PORT/api/health"

# --- helpers --------------------------------------------------------------

# Print the live PID (from pidfile, falling back to the port listener), or nothing
get_pid() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return
        fi
        rm -f "$PID_FILE"  # stale pidfile
    fi
    # Fallback: whoever is listening on the port AND is our app (on macOS,
    # AirPlay/ControlCenter also listens on 5000 - never kill that!)
    local candidate
    for candidate in $(lsof -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null); do
        if ps -p "$candidate" -o args= 2>/dev/null | grep -q "app\.py"; then
            echo "$candidate"
            return
        fi
    done
}

wait_health() {
    local retries=${1:-15}
    for _ in $(seq 1 "$retries"); do
        if curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" 2>/dev/null | grep -q 200; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# --- commands -------------------------------------------------------------

start() {
    local pid
    pid=$(get_pid)
    if [ -n "$pid" ]; then
        echo "Already running (PID $pid) at http://$HOST:$PORT"
        exit 0
    fi

    mkdir -p "$LOG_DIR"
    echo "Starting SlimPDF on http://$HOST:$PORT ..."
    nohup python3 app.py >> "$LOG_FILE" 2>&1 &
    pid=$!
    echo "$pid" > "$PID_FILE"

    if wait_health 15; then
        echo "Started (PID $pid). Health check OK: $HEALTH_URL"
        echo "Logs: $LOG_FILE"
    else
        echo "ERROR: process started (PID $pid) but health check failed after 15s."
        echo "Recent log:"
        tail -20 "$LOG_FILE"
        exit 1
    fi
}

stop() {
    local pid
    pid=$(get_pid)
    if [ -z "$pid" ]; then
        echo "Not running."
        rm -f "$PID_FILE"
        return
    fi

    # SIGTERM triggers the app's graceful-shutdown handler (app.py raises
    # SystemExit so atexit temp-file cleanup runs). Note: SIGINT is unreliable
    # here - processes launched via nohup from a non-interactive shell ignore it
    echo "Stopping PID $pid (SIGTERM, graceful) ..."
    kill -TERM "$pid" 2>/dev/null

    for _ in $(seq 1 10); do
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$PID_FILE"
            echo "Stopped gracefully."
            return
        fi
        sleep 1
    done

    echo "Still alive after 10s, escalating to SIGKILL ..."
    kill -KILL "$pid" 2>/dev/null
    rm -f "$PID_FILE"
    echo "Stopped (forced)."
}

status() {
    local pid
    pid=$(get_pid)
    if [ -z "$pid" ]; then
        echo "Status: NOT running (port $PORT)"
        exit 1
    fi
    echo "Status: running (PID $pid) at http://$HOST:$PORT"
    if curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" 2>/dev/null | grep -q 200; then
        echo "Health: OK ($HEALTH_URL)"
    else
        echo "Health: FAILED - process alive but $HEALTH_URL not responding"
        exit 1
    fi
}

case "${1:-}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; start ;;
    status)  status ;;
    *)
        echo "Usage: bash scripts/server.sh {start|stop|restart|status}"
        echo "  SLIMPDF_PORT=5050 bash scripts/server.sh start   # custom port"
        exit 1
        ;;
esac
