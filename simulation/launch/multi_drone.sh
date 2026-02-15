#!/usr/bin/env bash
#
# Multi-Drone Simulation Launcher
#
# Starts N drone instances, each with its own SITL + edge process.
# Configures unique SYSID_THISMAV and MAVLink port offsets per drone.
#
# Usage:
#   ./multi_drone.sh          # Start 3 drones (default)
#   ./multi_drone.sh 5        # Start 5 drones
#   MQTT_HOST=10.0.0.1 ./multi_drone.sh 2  # Custom MQTT host
#
# Environment variables:
#   NUM_DRONES       Number of drones to launch (default: 3)
#   MQTT_HOST        Mosquitto broker host (default: localhost)
#   MQTT_PORT        Mosquitto broker port (default: 1883)
#   BASE_MAVLINK_PORT  Starting MAVLink TCP port (default: 5760)
#   MAVLINK_PORT_STEP  Port increment per drone (default: 10)
#   LOG_LEVEL        Edge application log level (default: INFO)

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

NUM_DRONES="${1:-${NUM_DRONES:-3}}"
MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
BASE_MAVLINK_PORT="${BASE_MAVLINK_PORT:-5760}"
MAVLINK_PORT_STEP="${MAVLINK_PORT_STEP:-10}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Track child PIDs for cleanup
declare -a CHILD_PIDS=()

# ═══════════════════════════════════════════════════════════════════════════
# Cleanup handler
# ═══════════════════════════════════════════════════════════════════════════

cleanup() {
    echo ""
    echo "=========================================="
    echo "Shutting down ${#CHILD_PIDS[@]} drone processes..."
    echo "=========================================="

    for pid in "${CHILD_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "Sending SIGTERM to PID $pid"
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done

    # Wait briefly for graceful shutdown
    sleep 2

    # Force-kill any remaining processes
    for pid in "${CHILD_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "Force-killing PID $pid"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done

    echo "All drone processes stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════

if [[ "$NUM_DRONES" -lt 1 ]] || [[ "$NUM_DRONES" -gt 10 ]]; then
    echo "Error: NUM_DRONES must be between 1 and 10 (got $NUM_DRONES)"
    exit 1
fi

# Verify edge module is importable
if ! python -c "import edge" 2>/dev/null; then
    echo "Error: Cannot import 'edge' module."
    echo "Run 'uv sync --all-extras' from the project root first."
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════
# Launch drones
# ═══════════════════════════════════════════════════════════════════════════

echo "=========================================="
echo "Launching $NUM_DRONES drone simulation(s)"
echo "  MQTT broker: $MQTT_HOST:$MQTT_PORT"
echo "  Base MAVLink port: $BASE_MAVLINK_PORT"
echo "  Port step: $MAVLINK_PORT_STEP"
echo "  Log level: $LOG_LEVEL"
echo "=========================================="
echo ""

for i in $(seq 1 "$NUM_DRONES"); do
    SYSID="$i"
    MAVLINK_PORT=$((BASE_MAVLINK_PORT + (i - 1) * MAVLINK_PORT_STEP))
    DRONE_ID="drone-$(printf '%03d' "$i")"

    echo "Starting $DRONE_ID (SYSID=$SYSID, MAVLink port=$MAVLINK_PORT)"

    # Export environment variables for the edge application
    DRONE_DRONE_ID="$DRONE_ID" \
    DRONE_MQTT_ENDPOINT="$MQTT_HOST" \
    DRONE_MQTT_PORT="$MQTT_PORT" \
    DRONE_CONNECTIVITY_MODE="mosquitto" \
    DRONE_MAVLINK_CONNECTION="tcp:127.0.0.1:$MAVLINK_PORT" \
    DRONE_LOG_LEVEL="$LOG_LEVEL" \
    python -m edge.main &

    CHILD_PIDS+=($!)
    echo "  -> PID ${CHILD_PIDS[-1]}"
    echo ""

    # Brief pause between launches to avoid port contention
    sleep 1
done

echo "=========================================="
echo "All $NUM_DRONES drones launched."
echo "Press Ctrl+C to stop all drones."
echo "=========================================="

# Wait for all child processes
wait
