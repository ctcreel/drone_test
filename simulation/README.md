# Simulation Environment

Local simulation environment for the drone fleet search control system. Runs ArduPilot SITL instances, a Gazebo world, and a Mosquitto MQTT broker (standing in for AWS IoT Core) inside Docker containers.

## Prerequisites

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| [Docker](https://docs.docker.com/get-docker/) | 24.0+ | Container runtime for all simulation services |
| [Docker Compose](https://docs.docker.com/compose/install/) | 2.20+ | Multi-container orchestration |
| [Python](https://www.python.org/) | 3.12+ | Edge application runtime |
| [UV](https://docs.astral.sh/uv/) | 0.4+ | Python package manager |

Optional (for GUI visualization):

| Tool | Version | Purpose |
|------|---------|---------|
| [Gazebo](https://gazebosim.org/) | 11+ | 3D visualization of drone and world |
| X11 / XQuartz (macOS) | -- | Display server for Gazebo GUI |

## Quick Start

1. **Install Python dependencies** from the project root:

   ```bash
   uv sync --all-extras
   ```

2. **Start the simulation stack** (Gazebo, 3 SITL drones, Mosquitto):

   ```bash
   cd simulation
   docker compose up -d
   ```

3. **Verify services are running:**

   ```bash
   docker compose ps
   ```

   You should see five containers (`drone-fleet-mosquitto`, `drone-fleet-gazebo`, `drone-fleet-sitl-1`, `drone-fleet-sitl-2`, `drone-fleet-sitl-3`) all in the "running" state.

4. **Launch the edge software** for all drones:

   ```bash
   ./launch/multi_drone.sh
   ```

5. **Stop everything:**

   ```bash
   # Stop edge processes with Ctrl+C, then:
   docker compose down
   ```

## Selecting a World File

Two Gazebo world files are provided:

| World File | Description | Use Case |
|------------|-------------|----------|
| `worlds/urban_block_01.world` | Four buildings of varying heights (10-30m) with street corridors | Multi-drone area search, urban navigation |
| `worlds/building_complex_01.world` | Single L-shaped building with parking area and trees | Single-building inspection, close-quarters flight |

To select a world, set the `GAZEBO_WORLD` environment variable before starting:

```bash
# Urban block (default)
GAZEBO_WORLD=/worlds/urban_block_01.world docker compose up -d

# Building complex
GAZEBO_WORLD=/worlds/building_complex_01.world docker compose up -d
```

## Running with N Drones

### Docker Compose (SITL instances)

The default `docker-compose.yml` defines 3 SITL drone services. To add more, duplicate a `sitl-drone-N` service block with:

- A unique `SYSID_THISMAV` value
- A unique `INSTANCE` number (0-indexed)
- A unique `--custom-location` (stagger latitude by ~0.001 per drone)
- A unique port mapping (increment by 10: 5760, 5770, 5780, 5790, ...)

### Edge Software

The launch script accepts the number of drones as an argument:

```bash
# Launch 5 edge processes (requires 5 SITL instances running)
./launch/multi_drone.sh 5

# Or via environment variable
NUM_DRONES=5 ./launch/multi_drone.sh
```

Each edge process connects to its SITL instance via MAVLink TCP on sequential ports (5760, 5770, 5780, ...).

## SITL Parameter Files

Pre-configured parameter files for each drone are in `config/`:

| File | Drone | Starting Position |
|------|-------|-------------------|
| `config/sitl_drone_1.parm` | SYSID 1 | 35.3632, -97.4867 |
| `config/sitl_drone_2.parm` | SYSID 2 | 35.3642, -97.4867 |
| `config/sitl_drone_3.parm` | SYSID 3 | 35.3652, -97.4867 |

To use a parameter file with SITL, add the `--defaults` flag:

```bash
sim_vehicle.py -v ArduCopter --defaults config/sitl_drone_1.parm
```

## Connecting Edge Software

The edge application connects to each drone via MAVLink over TCP. Connection strings follow the format:

```
tcp:<host>:<port>
```

Default port assignments:

| Drone | MAVLink Port | Connection String |
|-------|-------------|-------------------|
| Drone 1 | 5760 | `tcp:localhost:5760` |
| Drone 2 | 5770 | `tcp:localhost:5770` |
| Drone 3 | 5780 | `tcp:localhost:5780` |

The MQTT broker (Mosquitto) is available at `localhost:1883` with anonymous access enabled. The edge software publishes telemetry and receives commands through MQTT topics that mirror the AWS IoT Core topic structure.

## Camera Configuration

Camera sensor parameters are defined in `config/gazebo_camera.yaml`:

- **RGB camera**: 640x480 at 30 FPS, 90-degree field of view. Captures images for the cloud AI pipeline (Claude via Bedrock).
- **Depth camera**: 320x240 at 15 FPS, 90-degree field of view. Provides range data for local obstacle avoidance on the Jetson edge computer.

## Troubleshooting

### Containers fail to start

```bash
# Check logs for a specific service
docker compose logs gazebo
docker compose logs sitl-drone-1

# Restart a single service
docker compose restart sitl-drone-1
```

### SITL drones cannot connect to Gazebo

Ensure the Gazebo container is fully started before SITL instances attempt to connect. The `docker-compose.yml` uses `depends_on` to enforce ordering, but Gazebo may need additional time to initialize:

```bash
# Watch Gazebo logs until it reports ready
docker compose logs -f gazebo
```

### MAVLink connection refused

Verify the SITL instance is listening on the expected port:

```bash
# Check from host
nc -zv localhost 5760

# Check from inside the Docker network
docker exec drone-fleet-sitl-1 ss -tlnp
```

### Gazebo GUI not displaying (Linux)

Allow X11 connections from Docker:

```bash
xhost +local:docker
```

### Gazebo GUI not displaying (macOS)

Install and start XQuartz, then allow network connections:

```bash
brew install --cask xquartz
# Open XQuartz > Preferences > Security > "Allow connections from network clients"
xhost + 127.0.0.1
```

### Mosquitto health check failing

The health check runs `mosquitto_sub` against the `$SYS/broker/uptime` topic. If it fails:

```bash
# Test MQTT connectivity manually
mosquitto_pub -h localhost -t "test/topic" -m "hello"
mosquitto_sub -h localhost -t "test/topic" -C 1
```

### Edge software cannot import modules

Ensure dependencies are installed from the project root:

```bash
uv sync --all-extras
```

### Port conflicts

If ports 1883, 5760, 5770, 5780, or 11345 are already in use, either stop the conflicting service or modify the port mappings in `docker-compose.yml`.

```bash
# Find what is using a port
lsof -i :5760
```
