# Drone Fleet Search Control System - Design Plan

**Project:** AI-Driven Drone Fleet Search Control System
**Version:** 0.1 (Draft)
**Date:** 2026-02-15
**Status:** Awaiting Approval
**Prerequisites:** [REQUIREMENTS.md](./REQUIREMENTS.md) (Approved)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Cloud Tier Design](#2-cloud-tier-design)
3. [Edge Tier Design](#3-edge-tier-design)
4. [Communication Design](#4-communication-design)
5. [Data Model](#5-data-model)
6. [AI Integration](#6-ai-integration)
7. [Simulation Architecture](#7-simulation-architecture)
8. [Integration Testing Architecture](#8-integration-testing-architecture)
9. [CDK Infrastructure Design](#9-cdk-infrastructure-design)
10. [CI/CD Pipeline Design](#10-cicd-pipeline-design)
11. [Project Structure](#11-project-structure)
12. [Security Design](#12-security-design)
13. [Observability](#13-observability)

---

## 1. Architecture Overview

### 1.1 Two-Tier Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         OPERATOR                                     │
│                    (Web Dashboard / API)                              │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────┴──────────────────────────────────────────┐
│                      CLOUD TIER (AWS)                                │
│                                                                      │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────────┐  │
│  │   API    │  │   Mission    │  │  Image   │  │    Fleet       │  │
│  │ Gateway  │──│   Planner    │  │ Analyzer │  │   Coordinator  │  │
│  └──────────┘  │  (Bedrock)   │  │(Bedrock) │  │                │  │
│                └──────────────┘  └──────────┘  └────────────────┘  │
│                                                                      │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ DynamoDB │  │     S3       │  │   SQS    │  │  IoT Core      │  │
│  │ (State)  │  │  (Images/    │  │ (Queues) │  │  (MQTT Broker) │  │
│  │          │  │   Models)    │  │          │  │                │  │
│  └──────────┘  └──────────────┘  └──────────┘  └───────┬────────┘  │
└─────────────────────────────────────────────────────────┼───────────┘
                                                          │ MQTT/TLS
                    ┌─────────────────────────────────────┤
                    │                                     │
        ┌───────────┴──────────┐          ┌───────────────┴──────────┐
        │   EDGE TIER (Drone 1)│          │   EDGE TIER (Drone N)    │
        │   ┌────────────────┐ │          │   ┌────────────────────┐ │
        │   │  Nvidia Jetson │ │          │   │  Nvidia Jetson     │ │
        │   │  ┌───────────┐ │ │          │   │  ┌──────────────┐  │ │
        │   │  │ Mission   │ │ │          │   │  │ Mission      │  │ │
        │   │  │ Executor  │ │ │          │   │  │ Executor     │  │ │
        │   │  ├───────────┤ │ │          │   │  ├──────────────┤  │ │
        │   │  │ Obstacle  │ │ │          │   │  │ Obstacle     │  │ │
        │   │  │ Avoidance │ │ │          │   │  │ Avoidance    │  │ │
        │   │  ├───────────┤ │ │          │   │  ├──────────────┤  │ │
        │   │  │ Image     │ │ │          │   │  │ Image        │  │ │
        │   │  │ Pipeline  │ │ │          │   │  │ Pipeline     │  │ │
        │   │  ├───────────┤ │ │          │   │  ├──────────────┤  │ │
        │   │  │ MAVLink   │ │ │          │   │  │ MAVLink      │  │ │
        │   │  │ Bridge    │ │ │          │   │  │ Bridge       │  │ │
        │   │  └─────┬─────┘ │ │          │   │  └──────┬───────┘  │ │
        │   └────────┼───────┘ │          │   └─────────┼──────────┘ │
        │            │ MAVLink  │          │             │ MAVLink    │
        │   ┌────────┴───────┐ │          │   ┌─────────┴──────────┐ │
        │   │  ArduPilot     │ │          │   │  ArduPilot         │ │
        │   │  Autopilot     │ │          │   │  Autopilot         │ │
        │   └────────────────┘ │          │   └────────────────────┘ │
        └──────────────────────┘          └──────────────────────────┘
```

### 1.2 Responsibility Split

| Concern | Cloud Tier | Edge Tier |
|---|---|---|
| Mission planning | Generates full mission plan via AI | Receives and caches mission segments |
| Navigation | Provides waypoint sequences | Executes waypoints, avoids obstacles in real time |
| Image analysis | Deep analysis via Bedrock vision | Capture, geo-tag, compress, optional first-pass |
| Fleet coordination | Coordinates all drones, prevents overlap | Reports own state, follows assigned plan |
| Safety | Monitors fleet health, issues recalls | Obstacle avoidance, fail-safe on connectivity loss |
| State | Authoritative fleet state in DynamoDB | Local mission segment cache, telemetry buffer |
| Latency budget | Seconds (planning, deep analysis) | Milliseconds (obstacle avoidance, MAVLink commands) |

---

## 2. Cloud Tier Design

### 2.1 AWS Services

| Service | Purpose |
|---|---|
| **API Gateway** | REST API for operator interface (mission submission, status, recall) |
| **Lambda** | Request handlers for API, IoT rule actions, image analysis orchestration |
| **DynamoDB** | Mission state, drone registry, telemetry history, detection catalog |
| **S3** | Drone images, environment models (3D data, GIS), mission plan artifacts |
| **SQS** | Image analysis queue (decouples upload from Bedrock analysis) |
| **AWS IoT Core** | MQTT broker for edge-to-cloud communication, Device Shadows for drone state |
| **Bedrock** | Claude for mission planning, Claude vision for image analysis |
| **Cognito** | Operator authentication for API and dashboard |
| **CloudWatch** | Logs, metrics, alarms for cloud and edge health |
| **EventBridge** | Mission lifecycle events, scheduled health checks |

### 2.2 Cloud Services Architecture

```
Operator API Flow:
  API Gateway → Lambda (handler) → DynamoDB (state)
                                 → Bedrock (planning)
                                 → IoT Core (dispatch to drones)

Image Analysis Flow:
  IoT Core (image upload notification) → S3 (store image)
                                       → SQS (analysis queue)
                                       → Lambda (analyzer)
                                       → Bedrock Vision (analyze)
                                       → DynamoDB (store detection)
                                       → EventBridge (notify operator)

Telemetry Flow:
  IoT Core (MQTT telemetry) → IoT Rule → Lambda (processor)
                                        → DynamoDB (update state)
                                        → CloudWatch (metrics)
```

### 2.3 Lambda Functions

| Function | Trigger | Purpose |
|---|---|---|
| `mission_planner` | API Gateway POST | Accepts search objective, calls Bedrock to generate plan |
| `mission_controller` | API Gateway (various) | Mission CRUD, approve/reject/abort |
| `fleet_coordinator` | EventBridge (scheduled) | Monitors fleet state, detects anomalies, triggers reassignment |
| `telemetry_processor` | IoT Rule | Processes incoming drone telemetry, updates DynamoDB and Device Shadow |
| `image_analyzer` | SQS | Pulls images from S3, sends to Bedrock vision, stores detections |
| `command_dispatcher` | DynamoDB Stream / direct | Translates approved mission plans into commands and publishes to IoT Core |
| `drone_registrar` | API Gateway / IoT lifecycle | Manages drone registration, provisioning, and deregistration |

### 2.4 API Design

**Base path:** `/api/v1`

| Method | Path | Purpose |
|---|---|---|
| POST | `/missions` | Submit a new search mission (objective + area + environment model) |
| GET | `/missions/{mission_id}` | Get mission details and status |
| POST | `/missions/{mission_id}/approve` | Approve a generated mission plan for execution |
| POST | `/missions/{mission_id}/abort` | Abort an active mission, recall all drones |
| GET | `/missions/{mission_id}/status` | Real-time mission status (drone positions, progress, detections) |
| GET | `/missions/{mission_id}/detections` | List detections with images and confidence scores |
| POST | `/missions/{mission_id}/detections/{detection_id}/review` | Operator confirms or dismisses a detection |
| GET | `/drones` | List registered drones and their current status |
| GET | `/drones/{drone_id}` | Get drone details, health, and telemetry |
| POST | `/drones/{drone_id}/recall` | Emergency recall a single drone |
| POST | `/environments` | Upload a 3D environment model |
| GET | `/environments/{environment_id}` | Get environment model details |
| POST | `/test/scenarios` | Submit integration test scenario (test API) |
| GET | `/test/scenarios/{scenario_id}/results` | Get test scenario results |

All endpoints return JSON. Error responses follow RFC 7807 Problem Details format (matching reference repo pattern).

---

## 3. Edge Tier Design

### 3.1 Edge Software Architecture

The edge software runs on each drone's Nvidia Jetson. It is a single Python application with modular components communicating via internal message passing.

```
┌─────────────────────────────────────────────────┐
│              Edge Application (Jetson)            │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │           Cloud Connector                    │ │
│  │  (MQTT client, Device Shadow sync,           │ │
│  │   connectivity monitoring, message buffer)   │ │
│  └──────────────────┬──────────────────────────┘ │
│                     │                             │
│  ┌──────────────────┴──────────────────────────┐ │
│  │           Mission Executor                   │ │
│  │  (Waypoint sequencing, mission segment       │ │
│  │   cache, progress tracking, fail-safe logic) │ │
│  └──────────────────┬──────────────────────────┘ │
│                     │                             │
│  ┌─────────────┐    │    ┌─────────────────────┐ │
│  │  Obstacle   │◄───┼───►│  Image Pipeline     │ │
│  │  Avoidance  │    │    │  (capture, geo-tag,  │ │
│  │  (depth     │    │    │   compress, optional │ │
│  │   camera,   │    │    │   first-pass detect) │ │
│  │   local     │    │    │                      │ │
│  │   replan)   │    │    │                      │ │
│  └──────┬──────┘    │    └──────────────────────┘ │
│         │           │                             │
│  ┌──────┴───────────┴──────────────────────────┐ │
│  │           MAVLink Bridge                     │ │
│  │  (pymavlink, heartbeat, command translation, │ │
│  │   telemetry collection, autopilot interface) │ │
│  └──────────────────┬──────────────────────────┘ │
│                     │ MAVLink serial/UDP          │
└─────────────────────┼───────────────────────────┘
                      │
              ┌───────┴───────┐
              │   ArduPilot   │
              │   Autopilot   │
              └───────────────┘
```

### 3.2 Edge Components

**Cloud Connector**
- AWS IoT Core MQTT client (TLS mutual auth with X.509 certificates)
- Receives mission commands from cloud, publishes telemetry and image notifications
- Syncs Device Shadow (reported state: position, battery, mission progress, edge health)
- Buffers outbound messages during connectivity loss, drains on reconnect
- Monitors connectivity status and exposes it to other components

**Mission Executor**
- Receives waypoint sequences from cloud via Cloud Connector
- Caches current mission segment locally for connectivity resilience
- Sequences waypoints to MAVLink Bridge, tracks progress
- Implements fail-safe state machine:
  - `CONNECTED` → normal operation, executing cloud commands
  - `DEGRADED` → connectivity lost, continue current waypoint segment
  - `HOLDING` → segment complete without reconnection, hold position
  - `RETURNING` → hold timeout exceeded, return to launch
- Reports mission progress to Cloud Connector for upload

**Obstacle Avoidance**
- Consumes depth camera frames at 10+ Hz
- Maintains local obstacle map (short-range, immediate surroundings)
- When obstacle detected on planned path: compute avoidance maneuver, issue modified waypoint to MAVLink Bridge
- Runs independently of cloud connectivity
- Priority: always overrides planned path when safety requires it

**Image Pipeline**
- Captures camera frames at configurable intervals (e.g., every 2 seconds)
- Geo-tags each frame with position and orientation from MAVLink telemetry
- Compresses and filters (skip blurry/duplicate frames)
- Queues for upload to S3 via Cloud Connector
- Optional: run lightweight YOLO or similar model on Jetson GPU for first-pass detection

**MAVLink Bridge**
- pymavlink connection to autopilot (serial or UDP)
- Sends heartbeat at 1 Hz minimum
- Translates high-level commands (go to waypoint, loiter, RTL, land) into MAVLink messages
- Collects telemetry (GLOBAL_POSITION_INT, SYS_STATUS, BATTERY_STATUS, HEARTBEAT)
- Exposes telemetry to all other edge components

### 3.3 Edge Fail-Safe State Machine

```
                    ┌──────────────┐
    cloud connected │  CONNECTED   │ normal operation
         ┌─────────│              │◄─────────┐
         │         └──────┬───────┘          │
         │                │ connectivity     │ connectivity
         │                │ lost             │ restored
         │                ▼                  │ (any state)
         │         ┌──────────────┐          │
         │         │   DEGRADED   │──────────┘
         │         │ (continue    │
         │         │  segment)    │
         │         └──────┬───────┘
         │                │ segment complete,
         │                │ still disconnected
         │                ▼
         │         ┌──────────────┐
         │         │   HOLDING    │──────────┘
         │         │ (hold        │
         │         │  position)   │
         │         └──────┬───────┘
         │                │ hold timeout
         │                │ exceeded
         │                ▼
         │         ┌──────────────┐
         └─────────│  RETURNING   │──────────┘
                   │ (RTL)        │
                   └──────────────┘
```

---

## 4. Communication Design

### 4.1 MQTT Topic Structure

All communication between cloud and edge flows through AWS IoT Core MQTT.

```
drone-fleet/
├── {drone_id}/
│   ├── command/            # Cloud → Edge: mission commands
│   │   ├── mission         # New mission segment assignment
│   │   ├── recall          # Emergency recall
│   │   └── configure       # Runtime configuration updates
│   ├── telemetry/          # Edge → Cloud: drone state
│   │   ├── position        # Position updates (1 Hz)
│   │   ├── health          # Battery, system status (0.2 Hz)
│   │   └── obstacle        # Obstacle detection events
│   ├── image/              # Edge → Cloud: image notifications
│   │   └── captured        # New image available in S3
│   └── status/             # Edge → Cloud: edge application state
│       ├── connectivity    # Connectivity state changes
│       └── mission         # Mission progress updates
└── fleet/
    ├── broadcast/          # Cloud → All edges: fleet-wide commands
    │   ├── recall          # Fleet-wide emergency recall
    │   └── configure       # Fleet-wide configuration
    └── coordination/       # Cloud → All edges: coordination data
        └── separation      # Drone separation warnings
```

### 4.2 Device Shadow Structure

Each drone has an IoT Device Shadow representing its last known state.

```json
{
  "state": {
    "reported": {
      "position": {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "altitude": 50.0,
        "heading": 180.0
      },
      "battery": {
        "voltage": 11.8,
        "remaining_percent": 72,
        "estimated_flight_time_seconds": 840
      },
      "mission": {
        "mission_id": "mission-abc-123",
        "segment_index": 3,
        "waypoint_index": 7,
        "status": "executing"
      },
      "edge": {
        "connectivity": "connected",
        "fail_safe_state": "CONNECTED",
        "obstacle_avoidance_active": true,
        "cpu_temperature_celsius": 52,
        "gpu_utilization_percent": 35
      }
    },
    "desired": {
      "mission": {
        "mission_id": "mission-abc-123",
        "action": "execute"
      },
      "configuration": {
        "telemetry_rate_hz": 1,
        "image_capture_interval_seconds": 2,
        "hold_timeout_seconds": 60,
        "return_timeout_seconds": 120
      }
    }
  }
}
```

### 4.3 Message Formats

All messages use JSON with a versioned envelope:

```json
{
  "version": "1.0",
  "timestamp": "2026-02-15T18:30:00Z",
  "source": "cloud|edge",
  "drone_id": "drone-001",
  "message_type": "mission_command",
  "payload": { }
}
```

**Mission Command Payload (Cloud → Edge):**

```json
{
  "mission_id": "mission-abc-123",
  "segment": {
    "segment_index": 0,
    "waypoints": [
      {
        "index": 0,
        "latitude": 37.7749,
        "longitude": -122.4194,
        "altitude": 50.0,
        "speed": 5.0,
        "action": "navigate",
        "camera": { "capture": true, "interval_seconds": 2 }
      }
    ],
    "on_complete": "loiter",
    "clearance_minimum_meters": 10.0
  }
}
```

---

## 5. Data Model

### 5.1 DynamoDB Table Design

Single-table design following the reference repo pattern (partition key `pk`, sort key `sk`).

| Entity | pk | sk | Attributes |
|---|---|---|---|
| Mission | `MISSION#{mission_id}` | `METADATA` | objective, area, environment_id, status, created_at, operator_id |
| Mission Plan | `MISSION#{mission_id}` | `PLAN` | plan_json, search_pattern, drone_assignments, approved_at |
| Mission Drone | `MISSION#{mission_id}` | `DRONE#{drone_id}` | assignment, waypoints, progress, status |
| Drone | `DRONE#{drone_id}` | `METADATA` | name, registration, iot_thing_name, status, last_seen |
| Drone Telemetry | `DRONE#{drone_id}` | `TELEMETRY#{timestamp}` | position, battery, heading, speed |
| Detection | `MISSION#{mission_id}` | `DETECTION#{detection_id}` | image_key, position, confidence, label, reviewed, reviewer_decision |
| Environment | `ENV#{environment_id}` | `METADATA` | name, bounds, s3_key, format, created_at |
| Test Scenario | `TEST#{scenario_id}` | `METADATA` | name, parameters, status, created_at |
| Test Result | `TEST#{scenario_id}` | `RESULT#{timestamp}` | pass_fail, metrics, failures, duration |

**GSI-1** (for querying by status):
- pk: `status`, sk: `created_at`
- Use: List active missions, pending detections for review

**GSI-2** (for querying drone history):
- pk: `drone_id`, sk: `timestamp`
- Use: Drone telemetry history, mission participation history

### 5.2 S3 Bucket Structure

```
drone-fleet-{account_id}-{environment}/
├── images/
│   └── {mission_id}/{drone_id}/{timestamp}.jpg
├── environments/
│   └── {environment_id}/
│       ├── model.json          # Processed environment model
│       └── source/             # Original uploaded files
├── mission-plans/
│   └── {mission_id}/plan.json
└── test-scenarios/
    └── {scenario_id}/
        ├── config.json
        └── results/
```

---

## 6. AI Integration

### 6.1 Mission Planning (Claude via Bedrock)

The mission planner Lambda calls Claude with a structured prompt containing:

1. **Search objective** (operator's natural language input)
2. **Search area** (GeoJSON polygon with coordinates)
3. **Environment model** (building footprints, obstacles, no-fly zones as GeoJSON)
4. **Fleet status** (available drones, battery levels, current positions)
5. **Constraints** (clearance distances, altitude limits, drone separation minimums)

Claude returns a structured JSON mission plan:

```json
{
  "search_pattern": "parallel_tracks",
  "reasoning": "The rectangular area with two buildings is best covered by...",
  "drone_assignments": [
    {
      "drone_id": "drone-001",
      "role": "primary_search",
      "segments": [
        {
          "waypoints": [...],
          "altitude": 40.0,
          "camera_interval_seconds": 2
        }
      ]
    }
  ],
  "estimated_duration_seconds": 600,
  "estimated_coverage_percent": 95,
  "safety_notes": ["Building at 37.775/-122.419 requires 15m clearance"]
}
```

The planner validates the response against the environment model (path clearance checks) before presenting to the operator.

### 6.2 Image Analysis (Claude Vision via Bedrock)

The image analyzer Lambda sends captured images to Claude vision with:

1. **Search objective context** (what we are looking for)
2. **Image metadata** (position, altitude, heading, drone ID)
3. **Analysis prompt** requesting structured detection output

Claude vision returns:

```json
{
  "detections": [
    {
      "label": "red vehicle",
      "confidence": 0.87,
      "bounding_box": { "x": 120, "y": 340, "width": 80, "height": 45 },
      "reasoning": "Partial view of a red sedan visible near building entrance"
    }
  ],
  "scene_description": "Urban parking area adjacent to commercial building",
  "search_relevant": true
}
```

### 6.3 Dynamic Replanning

When high-confidence detections occur, the fleet coordinator Lambda:
1. Queries recent detections for the mission
2. Calls Claude with current fleet state + detection cluster locations
3. Claude generates updated assignments concentrating drones around areas of interest
4. Updated segments are dispatched to affected drones via IoT Core

---

## 7. Simulation Architecture

### 7.1 Simulation Stack

```
┌──────────────────────────────────────────────────────────┐
│                   Developer Machine / CI                   │
│                                                            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              Docker Compose Environment               │  │
│  │                                                       │  │
│  │  ┌──────────┐  ┌──────────┐       ┌──────────┐      │  │
│  │  │ SITL     │  │ SITL     │  ...  │ SITL     │      │  │
│  │  │ Drone 1  │  │ Drone 2  │       │ Drone N  │      │  │
│  │  │ :5760    │  │ :5770    │       │ :5780    │      │  │
│  │  └────┬─────┘  └────┬─────┘       └────┬─────┘      │  │
│  │       │              │                  │             │  │
│  │  ┌────┴─────┐  ┌────┴─────┐       ┌────┴─────┐      │  │
│  │  │ Edge Sim │  │ Edge Sim │  ...  │ Edge Sim │      │  │
│  │  │ Process 1│  │ Process 2│       │ Process N│      │  │
│  │  └────┬─────┘  └────┴─────┘       └────┬─────┘      │  │
│  │       │              │                  │             │  │
│  │  ┌────┴──────────────┴──────────────────┴─────┐      │  │
│  │  │              Gazebo Server                  │      │  │
│  │  │         (3D world with buildings)           │      │  │
│  │  └────────────────────────────────────────────┘      │  │
│  │                                                       │  │
│  │  ┌────────────────────────────────────────────┐      │  │
│  │  │         Local MQTT Broker (Mosquitto)       │      │  │
│  │  │    (substitutes for IoT Core in sim)        │      │  │
│  │  └────────────────────────────────────────────┘      │  │
│  └─────────────────────────────────────────────────────┘  │
│                           │ MQTT                           │
│  ┌────────────────────────┴────────────────────────────┐  │
│  │           Cloud Services (Local or AWS)              │  │
│  │  (Lambda functions run locally via SAM/LocalStack    │  │
│  │   or against deployed AWS stack)                     │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 7.2 Simulation Components

| Component | Implementation | Notes |
|---|---|---|
| Autopilot | ArduPilot SITL | One instance per drone, ports offset by 10 per instance |
| 3D World | Gazebo | Urban environment with buildings, configurable worlds |
| Depth Sensor | Gazebo depth camera plugin | Simulates Jetson depth camera input |
| RGB Camera | Gazebo camera plugin | Generates synthetic images for vision pipeline |
| Edge Software | Same Python codebase | Runs as process, connects to SITL via pymavlink UDP |
| MQTT Broker | Mosquitto (local) | Drop-in replacement for IoT Core in simulation |
| Cloud Services | AWS (deployed) or local | Integration tests hit real AWS; unit tests use local mocks |

### 7.3 Simulation Modes

| Mode | Purpose | Cloud | Edge | SITL | Gazebo |
|---|---|---|---|---|---|
| Unit test | Fast, isolated component tests | Mocked | Mocked | No | No |
| Edge integration | Test edge software against SITL | Mocked MQTT | Real | Yes | Optional |
| Full simulation | End-to-end with all tiers | Real AWS | Real | Yes | Yes |
| CI pipeline | Automated validation | Real AWS | Real | Yes | Headless Gazebo |

---

## 8. Integration Testing Architecture

### 8.1 Test Orchestration

Integration tests are driven through the operator API (`/api/v1/test/scenarios`). A test scenario is a JSON document that defines:

```json
{
  "scenario_name": "basic_area_search",
  "description": "Search a rectangular area with two buildings using 3 drones",
  "environment": {
    "world_file": "urban_block_01.world",
    "environment_model_id": "env-urban-01"
  },
  "fleet": {
    "drone_count": 3,
    "start_positions": [
      { "latitude": 37.7749, "longitude": -122.4194, "altitude": 0 }
    ]
  },
  "mission": {
    "objective": "Search for a red vehicle in the designated area",
    "search_area": { "type": "Polygon", "coordinates": [...] }
  },
  "assertions": {
    "minimum_coverage_percent": 85,
    "obstacle_clearance_maintained": true,
    "all_drones_returned_safely": true,
    "maximum_mission_duration_seconds": 900,
    "expected_detections": [
      { "label": "red vehicle", "minimum_confidence": 0.7 }
    ]
  },
  "fault_injection": {
    "connectivity_loss": {
      "drone_id": "drone-002",
      "start_seconds": 120,
      "duration_seconds": 30
    }
  }
}
```

### 8.2 Test Categories

| Category | What It Tests | Assertions |
|---|---|---|
| End-to-end mission | Full lifecycle: submit → plan → approve → execute → complete | Coverage %, drones returned, detections found |
| Edge resilience | Connectivity loss during mission | Edge continues segment, holds, RTL based on timeouts |
| Obstacle avoidance | Missions through environments with known obstacles | No collisions, clearance maintained |
| Fleet coordination | Multi-drone separation and coverage optimization | No overlapping tracks, separation maintained |
| Image pipeline | Capture → preprocess → upload → analyze → detect | Images arrive in S3, detections stored with correct geo-tags |
| Dynamic replanning | Detection triggers fleet reallocation | Drones redirect to area of interest |
| Fail-safe | Drone failure during mission | Remaining drones reassigned, failed drone RTLs |

### 8.3 Test Results Format

```json
{
  "scenario_id": "test-abc-123",
  "scenario_name": "basic_area_search",
  "status": "passed",
  "duration_seconds": 245,
  "metrics": {
    "coverage_percent": 92.3,
    "obstacle_clearance_minimum_meters": 12.4,
    "drone_separation_minimum_meters": 18.7,
    "images_captured": 47,
    "images_analyzed": 47,
    "detections_found": 2,
    "mission_duration_seconds": 198
  },
  "assertions": [
    { "name": "minimum_coverage_percent", "expected": 85, "actual": 92.3, "passed": true },
    { "name": "obstacle_clearance_maintained", "expected": true, "actual": true, "passed": true },
    { "name": "all_drones_returned_safely", "expected": true, "actual": true, "passed": true }
  ],
  "failures": [],
  "drone_tracks": {
    "drone-001": [{ "timestamp": "...", "latitude": 37.7749, "longitude": -122.4194, "altitude": 50.0 }]
  }
}
```

---

## 9. CDK Infrastructure Design

### 9.1 Stack Structure

Following the reference repo pattern, the CDK app uses environment-specific configuration with separate logical stacks.

```
infra/
├── app.py                      # CDK app entry point, environment config
└── stacks/
    ├── network_stack.py        # VPC (if needed for future), security groups
    ├── storage_stack.py        # DynamoDB table, S3 buckets
    ├── iot_stack.py            # IoT Core things, policies, rules, shadows
    ├── api_stack.py            # API Gateway, Lambda functions, Cognito
    ├── processing_stack.py     # SQS queues, image analysis Lambda, EventBridge
    └── monitoring_stack.py     # CloudWatch dashboards, alarms, SNS topics
```

### 9.2 Environment Configuration

```python
environment_config = {
    "development": {
        "removal_policy": RemovalPolicy.DESTROY,
        "log_retention": 7,
        "monitoring": False,
        "backups": False,
        "bedrock_rate_limit": 10,
        "max_drones": 3,
    },
    "testing": {
        "removal_policy": RemovalPolicy.DESTROY,
        "log_retention": 14,
        "monitoring": True,
        "backups": False,
        "bedrock_rate_limit": 20,
        "max_drones": 5,
    },
    "production": {
        "removal_policy": RemovalPolicy.RETAIN,
        "log_retention": 90,
        "monitoring": True,
        "backups": True,
        "bedrock_rate_limit": 50,
        "max_drones": 20,
    },
}
```

### 9.3 IoT Core Stack Design

```
IoT Things:
  - One IoT Thing per drone (drone-001, drone-002, ...)
  - X.509 certificate per thing for mutual TLS auth
  - IoT Policy restricting each drone to its own MQTT topics

IoT Rules:
  - telemetry_to_lambda: Routes drone-fleet/+/telemetry/# → Lambda (telemetry_processor)
  - image_to_s3: Routes drone-fleet/+/image/captured → S3 + SQS
  - status_to_dynamodb: Routes drone-fleet/+/status/# → DynamoDB (direct action)

Device Shadows:
  - Named shadow per drone for state synchronization
  - Classic shadow for backward compatibility
```

---

## 10. CI/CD Pipeline Design

### 10.1 Pipeline Structure

Following the reference repo's workflow pattern:

```
.github/workflows/
├── pull-request.yml            # Orchestrator for PR checks
├── post-merge.yml              # Post-merge deployment and cleanup
├── _ci-checks.yml              # Reusable: lint, test, security
├── _naming-validation.yml      # Reusable: naming conventions
├── _deploy.yml                 # Reusable: CDK synth/diff/deploy
└── _edge-build.yml             # Reusable: edge software build and artifact
```

### 10.2 PR Pipeline

```
PR opened/updated
  ├── CI Checks (parallel)
  │   ├── Lint (ruff + pyright)
  │   ├── Test (pytest, 95% coverage)
  │   └── Security (bandit + pip-audit)
  ├── Naming Validation
  │   ├── Branch name format
  │   ├── Python naming conventions
  │   └── AWS resource naming
  ├── CDK Validation
  │   ├── CDK synth (all stacks)
  │   └── CDK diff (against target environment)
  └── Edge Build
      ├── Edge unit tests
      └── Edge artifact build (verify it packages)
```

### 10.3 Post-Merge Pipeline

```
Merge to main
  ├── Deploy cloud infrastructure (CDK deploy)
  ├── Build and publish edge artifact
  ├── Run integration tests against deployed stack
  │   ├── Start simulation environment
  │   ├── Execute test scenarios via API
  │   └── Report results
  ├── Tag release (if [release] in commit message)
  └── Cleanup
```

### 10.4 Branch Strategy

| Branch | Environment | Auto-deploy |
|---|---|---|
| `development` | development | Yes |
| `testing` | testing | Yes |
| `main` | production | Manual approval |

---

## 11. Project Structure

Following the reference repo layout:

```
drone_test/
├── src/                            # Cloud tier application code
│   ├── main.py                     # FastAPI entry point (API handlers)
│   ├── config.py                   # Pydantic Settings (environment config)
│   ├── constants.py                # Global constants
│   ├── types.py                    # Type definitions
│   ├── exceptions/                 # Exception hierarchy (reference pattern)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── handlers.py
│   ├── logging/                    # Structured logging (reference pattern)
│   │   ├── __init__.py
│   │   ├── logger.py
│   │   ├── config.py
│   │   ├── formatters.py
│   │   └── context.py
│   ├── mission/                    # Mission planning domain
│   │   ├── __init__.py
│   │   ├── planner.py              # Bedrock AI planning integration
│   │   ├── controller.py           # Mission lifecycle management
│   │   ├── models.py               # Mission Pydantic models
│   │   └── search_patterns.py      # Search pattern definitions
│   ├── fleet/                      # Fleet coordination domain
│   │   ├── __init__.py
│   │   ├── coordinator.py          # Fleet state management
│   │   ├── command_dispatcher.py   # Publishes commands to IoT Core
│   │   └── models.py               # Fleet/drone Pydantic models
│   ├── analysis/                   # Image analysis domain
│   │   ├── __init__.py
│   │   ├── analyzer.py             # Bedrock vision analysis
│   │   ├── detection.py            # Detection management
│   │   └── models.py               # Analysis Pydantic models
│   ├── environment/                # 3D environment domain
│   │   ├── __init__.py
│   │   ├── loader.py               # Environment model loading/parsing
│   │   ├── validator.py            # Path clearance validation
│   │   └── models.py               # Environment Pydantic models
│   ├── telemetry/                  # Telemetry processing
│   │   ├── __init__.py
│   │   ├── processor.py            # Telemetry ingestion and state update
│   │   └── models.py               # Telemetry Pydantic models
│   └── utils/                      # Shared utilities
│       ├── __init__.py
│       ├── retry.py                # Retry decorator (reference pattern)
│       └── geo.py                  # Geographic utility functions
│
├── edge/                           # Edge tier application code
│   ├── main.py                     # Edge application entry point
│   ├── config.py                   # Edge Pydantic Settings
│   ├── constants.py                # Edge constants
│   ├── cloud_connector/            # MQTT client, message buffering
│   │   ├── __init__.py
│   │   ├── connector.py
│   │   └── models.py
│   ├── mission_executor/           # Waypoint sequencing, fail-safe
│   │   ├── __init__.py
│   │   ├── executor.py
│   │   ├── fail_safe.py
│   │   └── models.py
│   ├── obstacle_avoidance/         # Depth processing, local replan
│   │   ├── __init__.py
│   │   ├── avoidance.py
│   │   └── models.py
│   ├── image_pipeline/             # Capture, geo-tag, compress
│   │   ├── __init__.py
│   │   ├── pipeline.py
│   │   └── models.py
│   └── mavlink_bridge/             # pymavlink interface
│       ├── __init__.py
│       ├── bridge.py
│       └── models.py
│
├── infra/                          # AWS CDK infrastructure
│   ├── app.py
│   └── stacks/
│       ├── __init__.py
│       ├── storage_stack.py
│       ├── iot_stack.py
│       ├── api_stack.py
│       ├── processing_stack.py
│       └── monitoring_stack.py
│
├── tests/                          # Cloud tier tests
│   └── unit/
│       ├── mission/
│       ├── fleet/
│       ├── analysis/
│       ├── environment/
│       ├── telemetry/
│       └── test_config.py
│
├── edge_tests/                     # Edge tier tests
│   └── unit/
│       ├── cloud_connector/
│       ├── mission_executor/
│       ├── obstacle_avoidance/
│       ├── image_pipeline/
│       └── mavlink_bridge/
│
├── infra_tests/                    # CDK infrastructure tests
│   ├── test_storage_stack.py
│   ├── test_iot_stack.py
│   ├── test_api_stack.py
│   ├── test_processing_stack.py
│   └── test_monitoring_stack.py
│
├── integration_tests/              # Integration test scenarios
│   ├── scenarios/                  # Test scenario JSON configs
│   │   ├── basic_area_search.json
│   │   ├── obstacle_avoidance.json
│   │   ├── connectivity_loss.json
│   │   └── fleet_coordination.json
│   ├── runner.py                   # Test runner (calls API)
│   └── conftest.py
│
├── simulation/                     # Simulation environment
│   ├── docker-compose.yml          # SITL + Gazebo + Mosquitto
│   ├── worlds/                     # Gazebo world files
│   │   ├── urban_block_01.world
│   │   └── building_complex_01.world
│   └── launch/                     # Simulation launch scripts
│       └── multi_drone.sh
│
├── scripts/                        # Validation and utility scripts
│   ├── validate_naming.py
│   ├── validate_imports.py
│   └── check_abbreviations.py
│
├── docs/                           # Documentation
│   ├── REQUIREMENTS.md
│   ├── DESIGN.md
│   └── guides/
│       ├── BRANCHING.md
│       ├── ENVIRONMENT_VARIABLES.md
│       └── SIMULATION_SETUP.md
│
├── .github/
│   ├── workflows/
│   │   ├── pull-request.yml
│   │   ├── post-merge.yml
│   │   ├── _ci-checks.yml
│   │   ├── _naming-validation.yml
│   │   ├── _deploy.yml
│   │   └── _edge-build.yml
│   └── actions/
│       └── setup-python-uv/
│
├── CLAUDE.md                       # AI assistant coding rules
├── Makefile                        # Task runner
├── pyproject.toml                  # Project configuration
├── .pre-commit-config.yaml         # Git hooks
├── .editorconfig                   # Editor configuration
├── .gitleaks.toml                  # Secret detection
├── .gitignore
└── sonar-project.properties        # SonarCloud config
```

---

## 12. Security Design

### 12.1 Authentication and Authorization

| Component | Mechanism |
|---|---|
| Operator → API | Cognito User Pool (JWT tokens) |
| Edge → IoT Core | X.509 mutual TLS (per-drone certificate) |
| IoT Core → Lambda | IAM role-based (IoT Rule actions) |
| Lambda → Bedrock | IAM role-based (execution role) |
| Lambda → DynamoDB/S3 | IAM role-based (least privilege grants) |

### 12.2 Edge Security

- Each drone has a unique X.509 certificate provisioned during registration
- IoT Policy restricts each drone to publish/subscribe only on its own MQTT topics
- Certificates can be revoked per-drone if a drone is compromised or decommissioned
- Edge software validates cloud command signatures before execution

### 12.3 Data Security

- All data in transit: TLS 1.2+
- S3: Server-side encryption (SSE-S3)
- DynamoDB: Encryption at rest (AWS managed key)
- No secrets in code or environment variables (use AWS Secrets Manager for any API keys)
- gitleaks pre-commit hook prevents accidental secret commits

---

## 13. Observability

### 13.1 Metrics

| Metric | Source | Alarm Threshold |
|---|---|---|
| Mission plan generation latency | Lambda | > 30 seconds |
| Image analysis latency | Lambda | > 10 seconds |
| Telemetry processing latency | Lambda | > 2 seconds |
| Edge connectivity loss events | IoT Core | > 0 (alert) |
| Bedrock throttling events | CloudWatch | > 0 (warn) |
| Lambda errors (per function) | CloudWatch | > 5 in 5 minutes |
| API Gateway 5xx rate | CloudWatch | > 1% |
| SQS queue depth (image analysis) | CloudWatch | > 50 messages |
| Drone battery critical | Telemetry | < 20% |

### 13.2 Logging

Following the reference repo's structured logging pattern:
- JSON-formatted logs in production (CloudWatch)
- Human-readable colored logs in development
- Correlation IDs across the request chain (API → Lambda → IoT → Edge)
- Mission ID included in all logs for a given mission
- Drone ID included in all edge and telemetry logs

### 13.3 Dashboard

CloudWatch dashboard displaying:
- Active missions and their status
- Fleet map (drone positions from last telemetry)
- Image analysis queue depth and throughput
- Bedrock API usage and latency
- Edge connectivity status per drone
- Alert panel for active alarms
