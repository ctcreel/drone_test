# Drone Fleet Search Control System - Requirements Document

**Project:** AI-Driven Drone Fleet Search Control System
**Version:** 0.1 (Draft)
**Date:** 2026-02-15
**Status:** Awaiting Approval

---

## 1. Project Overview

Build a two-tier (edge + cloud) control system for coordinating visual search missions across a fleet of ArduPilot/PX4 drones operating in complex environments including urban cityscapes and in and around buildings.

The **cloud tier** (AWS) handles mission planning via AI, fleet coordination, deep image analysis, and the operator interface. The **edge tier** (Nvidia Jetson companion computer on each drone) handles real-time obstacle avoidance, local path following, image capture and preprocessing, MAVLink interface, and connectivity bridging.

An operator provides a search objective (e.g., "search this building complex for a missing person") and the cloud system generates 3D-aware flight plans, dispatches high-level intent to the drone fleet, and analyzes visual data. Each drone's edge computer translates high-level waypoint commands into safe, obstacle-aware flight in real time, independent of cloud latency.

## 2. Scope

### 2.1 In Scope

- **Cloud tier:** Mission planning, fleet coordination, deep image analysis, operator interface on AWS
- **Edge tier:** Nvidia Jetson companion computer on each drone for real-time autonomy
- AI-powered search planning using Claude via AWS Bedrock
- Visual search capability using camera feeds and computer vision (edge preprocessing + cloud analysis)
- MAVLink-based command and telemetry interface for ArduPilot/PX4 drones
- Fleet coordination for 2-5 drones
- Simulation environment using ArduPilot SITL (Software In The Loop)
- Infrastructure as Code using AWS CDK (Python)
- CI/CD pipeline using GitHub Actions
- Operator interface for submitting search objectives and monitoring missions
- Drone-to-cloud communication over internet/cellular
- 3D environment awareness and obstacle-aware path planning for complex environments (buildings, urban cityscapes)
- Real-time obstacle avoidance on the edge, independent of cloud connectivity

### 2.2 Out of Scope (Phase 1)

- Physical drone hardware integration (simulation-first approach; edge software designed for Jetson but tested in simulation)
- Thermal, LIDAR, or other non-visual sensor integration
- Fleets larger than 5 drones
- Fully offline/disconnected mission execution (edge supports graceful degradation, not full autonomy)
- Regulatory compliance filing (FAA Part 107 waivers, etc.)
- Ground station relay communication
- Custom-trained ML models (edge uses pre-trained lightweight models)
- Real-time video streaming (will use periodic image capture with edge preprocessing)

## 3. Functional Requirements

### 3.1 Mission Planning (FR-100)

| ID | Requirement | Priority |
|---|---|---|
| FR-101 | The system shall accept a search objective as natural language input from an operator (e.g., "Search the area bounded by these coordinates for a red vehicle") | Must |
| FR-102 | The system shall accept a geographic search area defined by coordinates (polygon or bounding box) | Must |
| FR-103 | The AI planner (Claude via Bedrock) shall decompose a search objective into individual drone assignments with 3D waypoints, altitudes, and camera parameters that account for obstacles in the environment | Must |
| FR-104 | The AI planner shall optimize search patterns to minimize overlap and maximize area coverage given the available fleet size and environment constraints | Must |
| FR-105 | The system shall support common search patterns adapted for complex environments: parallel tracks, expanding square, sector search, creeping line, building perimeter, and vertical scan | Should |
| FR-106 | The AI planner shall dynamically reassign drones if a drone becomes unavailable during a mission | Should |
| FR-107 | The system shall allow an operator to approve, modify, or reject a generated mission plan before execution | Must |

### 3.2 Fleet Command and Control (FR-200)

The cloud tier sends high-level intent (waypoint sequences, search assignments) to each drone's edge computer. The edge computer translates intent into real-time MAVLink commands to the autopilot, handling moment-to-moment flight safety locally.

| ID | Requirement | Priority |
|---|---|---|
| FR-201 | The cloud shall send high-level mission commands (waypoint sequences, search patterns, recall) to each drone's edge computer via internet/cellular | Must |
| FR-202 | The cloud shall receive telemetry data (position, altitude, speed, battery, status, edge health) from each drone's edge computer | Must |
| FR-203 | The cloud shall monitor drone and edge health and flag anomalies (low battery, connection loss, deviation from plan, edge faults) | Must |
| FR-204 | The cloud shall support the following high-level commands: arm, takeoff, execute waypoint sequence, loiter, return to launch, land, abort | Must |
| FR-205 | The cloud shall maintain a real-time state model for each drone in the fleet | Must |
| FR-206 | The cloud shall support emergency recall of individual drones or the entire fleet | Must |
| FR-207 | The system shall handle temporary cloud connection loss gracefully; the edge shall continue current segment autonomously and attempt reconnection | Must |

### 3.3 Visual Search and Analysis (FR-300)

Image processing follows a two-stage pipeline: the edge performs capture, geo-tagging, and optional first-pass filtering; the cloud performs deep analysis using Bedrock vision models.

| ID | Requirement | Priority |
|---|---|---|
| FR-301 | The edge shall capture images from the drone camera at configurable intervals | Must |
| FR-302 | The edge shall geo-tag each captured image with the drone's position and orientation at time of capture | Must |
| FR-303 | The edge shall preprocess images (compress, filter duplicates/blurry frames) before uploading to reduce bandwidth | Must |
| FR-304 | The edge shall perform optional first-pass detection using a lightweight on-device model and flag potential matches locally | Should |
| FR-305 | The cloud shall analyze uploaded images using a vision model (Bedrock Claude vision) to detect objects matching the search objective | Must |
| FR-306 | The cloud shall flag potential matches with confidence scores and notify the operator | Must |
| FR-307 | The cloud shall maintain a searchable catalog of all images captured during a mission | Should |
| FR-308 | The cloud AI shall refine the search strategy based on analysis results (e.g., concentrate drones around an area of interest) | Should |

### 3.4 Operator Interface (FR-400)

| ID | Requirement | Priority |
|---|---|---|
| FR-401 | The system shall provide an API for submitting search objectives | Must |
| FR-402 | The system shall provide mission status via API (drone positions, mission progress, detections) | Must |
| FR-403 | The system shall provide a web-based dashboard for mission monitoring | Should |
| FR-404 | The system shall support mission abort and drone recall via the operator interface | Must |
| FR-405 | The system shall display flagged detections with images and locations for operator review | Should |

### 3.5 Navigation and Environment Awareness (FR-600)

| ID | Requirement | Priority |
|---|---|---|
| FR-601 | The system shall accept a 3D environment model (building footprints, elevation data, obstacle maps) for the search area | Must |
| FR-602 | The AI planner shall generate flight paths that maintain safe clearance distances from buildings, structures, and other obstacles | Must |
| FR-603 | The system shall support multi-altitude search plans (e.g., searching different floors/levels of a building exterior) | Must |
| FR-604 | The system shall enforce no-fly zones and geofence boundaries within complex environments | Must |
| FR-605 | The system shall coordinate drone separation to prevent inter-drone collisions in confined spaces | Must |
| FR-606 | The system shall support waypoint-to-waypoint path validation against the environment model before dispatching commands | Must |
| FR-607 | The system shall dynamically replan paths if an obstacle is detected that was not in the original environment model | Should |
| FR-608 | The system shall support importing environment data from common formats (GIS shapefiles, OpenStreetMap data, 3D building models) | Should |

### 3.6 Edge Compute - Drone Companion Computer (FR-700)

Each drone carries an Nvidia Jetson companion computer that provides local autonomy, real-time obstacle avoidance, and acts as the bridge between the cloud tier and the ArduPilot autopilot.

| ID | Requirement | Priority |
|---|---|---|
| FR-701 | The edge shall interface with the ArduPilot autopilot via MAVLink over serial/UDP | Must |
| FR-702 | The edge shall receive high-level waypoint sequences from the cloud and translate them into MAVLink commands for the autopilot | Must |
| FR-703 | The edge shall perform real-time obstacle avoidance using depth camera or stereo vision input, independent of cloud connectivity | Must |
| FR-704 | The edge shall modify flight paths locally to avoid obstacles while maintaining progress toward the assigned waypoint | Must |
| FR-705 | The edge shall report telemetry (position, battery, obstacle events, edge health, connectivity status) to the cloud at a configurable rate | Must |
| FR-706 | The edge shall execute fail-safe behavior autonomously when cloud connectivity is lost: hold position for configurable timeout, then return to launch | Must |
| FR-707 | The edge shall buffer telemetry and images during connectivity loss and upload when connection is restored | Must |
| FR-708 | The edge shall maintain a local copy of the current mission segment so it can continue waypoint navigation during brief connectivity gaps | Must |
| FR-709 | The edge shall support over-the-air software updates from the cloud | Should |
| FR-710 | The edge shall expose a local diagnostic API for field debugging | Should |

### 3.7 Simulation (FR-500)

| ID | Requirement | Priority |
|---|---|---|
| FR-501 | The system shall integrate with ArduPilot SITL for autopilot simulation | Must |
| FR-502 | The simulation shall support multiple concurrent simulated drones (2-5), each with a simulated edge compute layer | Must |
| FR-503 | The simulation shall generate synthetic camera and depth sensor imagery for visual search and obstacle avoidance testing | Should |
| FR-504 | The simulation environment shall be runnable locally for development and in CI for testing | Must |
| FR-505 | The simulation shall include 3D environments with buildings and obstacles for testing complex navigation | Must |
| FR-506 | The simulation shall integrate with Gazebo or similar 3D simulator for realistic urban environment testing and sensor simulation | Should |
| FR-507 | The edge compute software shall run identically in simulation and on physical Jetson hardware (same codebase, simulated sensor inputs) | Must |

### 3.8 Integration Testing (FR-800)

All integration tests are API-driven so they can be executed programmatically by CI/CD pipelines and AI agents. Tests run against the simulation environment (SITL + simulated edge) with the full cloud stack deployed.

| ID | Requirement | Priority |
|---|---|---|
| FR-801 | The system shall expose a test orchestration API that can create, execute, and evaluate integration test scenarios against the simulation environment | Must |
| FR-802 | The test API shall support submitting a search mission (objective + area + environment model) and receiving structured results (mission plan, drone tracks, detections, timing) | Must |
| FR-803 | The test API shall support asserting mission outcomes: area coverage percentage, obstacle clearance maintained, all drones returned safely, detections match expected targets | Must |
| FR-804 | The test suite shall include end-to-end mission tests: submit objective, approve plan, execute in simulation, verify search coverage and detections | Must |
| FR-805 | The test suite shall include edge resilience tests: simulate cloud connectivity loss during mission and verify edge graceful degradation (continue segment, hold, RTL) | Must |
| FR-806 | The test suite shall include obstacle avoidance tests: execute missions in environments with known obstacles and verify no collisions occur | Must |
| FR-807 | The test suite shall include fleet coordination tests: verify drone separation maintained, no overlapping search areas, correct reassignment on drone loss | Must |
| FR-808 | The test suite shall include image pipeline tests: verify images are captured, preprocessed on edge, uploaded, analyzed in cloud, and detections are flagged | Must |
| FR-809 | The test API shall return machine-readable results (JSON) with pass/fail status, metrics, and detailed failure information | Must |
| FR-810 | Integration tests shall be executable from GitHub Actions as part of the CI/CD pipeline | Must |
| FR-811 | The test suite shall support parameterized test scenarios (different environments, fleet sizes, search objectives) loaded from configuration files | Should |

## 4. Non-Functional Requirements

### 4.1 Performance (NFR-100)

| ID | Requirement |
|---|---|
| NFR-101 | Command latency from cloud to edge shall be < 2 seconds under normal network conditions |
| NFR-102 | Telemetry updates from edge to cloud shall be processed at a minimum rate of 1 Hz per drone |
| NFR-103 | Cloud image analysis shall complete within 10 seconds of image receipt |
| NFR-104 | Mission plan generation shall complete within 30 seconds of objective submission |
| NFR-105 | Edge obstacle avoidance loop shall execute at a minimum of 10 Hz (100ms cycle time) |
| NFR-106 | Edge-to-autopilot MAVLink command latency shall be < 50ms |
| NFR-107 | Edge image preprocessing (capture, geo-tag, compress) shall complete within 500ms per frame |

### 4.2 Reliability (NFR-200)

| ID | Requirement |
|---|---|
| NFR-201 | The cloud shall maintain fleet operation if a single drone loses connectivity |
| NFR-202 | The edge shall execute graceful degradation on cloud connectivity loss: continue current waypoint segment, hold position after timeout, RTL after extended timeout |
| NFR-203 | The cloud shall persist mission state to survive service restarts |
| NFR-204 | The edge shall operate obstacle avoidance continuously regardless of cloud connectivity status |
| NFR-205 | The edge shall recover autonomously from edge software crashes via watchdog process restart |

### 4.3 Security (NFR-300)

| ID | Requirement |
|---|---|
| NFR-301 | All drone-to-cloud communication shall be encrypted (TLS) |
| NFR-302 | The operator API shall require authentication |
| NFR-303 | Drone command authority shall be limited to authenticated and authorized sessions |
| NFR-304 | No drone commands shall be executed without operator approval of the mission plan |

### 4.4 Scalability (NFR-400)

| ID | Requirement |
|---|---|
| NFR-401 | Architecture shall support future scaling to 20+ drones without fundamental redesign |
| NFR-402 | The system shall support concurrent missions (future, design for it now) |

## 5. Technical Constraints

| Constraint | Detail |
|---|---|
| Cloud Platform | AWS (account: chris-dev profile) |
| IaC | AWS CDK (Python) |
| CI/CD | GitHub Actions deploying to AWS (cloud tier) and building edge artifacts |
| Drone Platform | ArduPilot / PX4 compatible autopilots |
| Edge Hardware | Nvidia Jetson (Orin Nano or equivalent) per drone |
| Edge-to-Autopilot | MAVLink over serial/UDP (local) |
| Edge-to-Cloud | MQTT or WebSocket over TLS via cellular/WiFi |
| AI Planning Model | Claude via AWS Bedrock (cloud tier) |
| Cloud Vision Analysis | AWS Bedrock (Claude vision) or Amazon Rekognition |
| Edge Vision | Lightweight pre-trained models (obstacle detection, optional first-pass search) |
| Simulation | ArduPilot SITL + Gazebo (3D environments + simulated sensors) |
| Environment Data | GIS data, OpenStreetMap, 3D building models |
| Repository | github.com/ctcreel/drone_test |

## 6. Assumptions

1. Each drone is equipped with an Nvidia Jetson companion computer connected to the autopilot via serial/UDP
2. Each drone has a depth camera or stereo vision system for real-time obstacle detection
3. Drones have cellular (4G/5G) or WiFi internet connectivity (may be intermittent in complex environments)
4. Cameras on drones can capture still images; the Jetson handles capture and preprocessing locally
5. The operator is responsible for ensuring legal compliance for drone operations
6. ArduPilot SITL + Gazebo provides sufficient fidelity for initial development and testing of both cloud and edge tiers
7. AWS Bedrock provides access to Claude models in the target region
8. 3D environment data (building footprints, elevation) is available or can be sourced for the target search area
9. The Jetson has sufficient compute for concurrent obstacle avoidance and image preprocessing (validated by Orin Nano benchmarks)
10. Power budget allows for Jetson operation throughout mission duration (~10-15W draw)

## 7. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Network latency/reliability over cellular | Delayed or lost cloud commands | Edge continues mission segment autonomously; graceful degradation with hold-position and RTL timeouts |
| AI planning errors | Incorrect flight plans could cause collisions or missed coverage | Operator approval gate; collision avoidance checks; conservative altitude separation |
| AWS Bedrock rate limits | Could throttle image analysis during active missions | Implement queuing; batch processing; consider Rekognition as fallback |
| SITL limitations | Simulated environment may not reveal real-world integration issues | Plan for phased hardware integration testing |
| Cost management | Bedrock API calls and compute could generate unexpected costs | Implement cost monitoring and budget alerts; use spot instances where possible |
| Obstacle collision | Inaccurate or outdated environment models could lead to collision with structures | Conservative clearance margins; operator review of flight paths over 3D model; dynamic replanning on anomaly detection |
| GPS degradation in urban canyons | Tall buildings can degrade GPS accuracy | Account for GPS uncertainty in clearance margins; flag high-risk corridors in flight plans |
| Environment model accuracy | Available 3D data may not reflect current state of environment (construction, temporary structures) | Require operator confirmation of environment data currency; support environment model updates |
| Jetson power/thermal | Sustained GPU workload in hot environments could cause throttling or exceed power budget | Thermal testing; power monitoring on edge; configurable workload priorities (obstacle avoidance > image processing) |
| Edge software reliability | Crash or hang on edge computer during flight | Watchdog process with auto-restart; autopilot fail-safe independent of edge; edge health reporting to cloud |
| Edge-cloud protocol mismatch | Version skew between cloud and edge software during updates | Versioned API contract; backward-compatible message formats; staged rollout support |

## 8. Success Criteria

1. Operator can submit a natural language search objective with a geographic area
2. The system generates and presents a coordinated flight plan for 2-5 simulated drones
3. Upon operator approval, simulated drones (with simulated edge computers) execute the search pattern in a 3D environment with buildings/obstacles
4. Simulated edge computers perform real-time obstacle avoidance around structures
5. Images from the simulation are preprocessed on the simulated edge and analyzed in the cloud; potential matches are flagged
6. The operator can monitor mission progress and recall drones
7. Edge gracefully handles simulated cloud connectivity loss (continues segment, holds position, RTL)
8. All cloud infrastructure is deployed via CDK through GitHub Actions
9. All integration tests pass via API-driven test suite against the simulation environment

## 9. Glossary

| Term | Definition |
|---|---|
| MAVLink | Micro Air Vehicle Link - lightweight protocol for drone communication |
| SITL | Software In The Loop - ArduPilot's simulation mode that runs the autopilot code without hardware |
| Waypoint | A geographic coordinate (lat/lon/alt) that a drone navigates to |
| RTL | Return To Launch - fail-safe command that returns a drone to its takeoff point |
| GCS | Ground Control Station - software/hardware for monitoring and controlling drones |
| Bedrock | AWS managed service for accessing foundation AI models |
| Geofence | A virtual boundary defining the permitted flight area |
| Urban Canyon | A street or corridor between tall buildings where GPS signals can be degraded by multipath reflection |
| Gazebo | An open-source 3D robotics simulator commonly used with ArduPilot/PX4 for realistic environment simulation |
| Jetson | Nvidia embedded GPU computing platform for edge AI inference |
| Edge | The companion computer (Jetson) running on each drone, responsible for local autonomy |
| Cloud | The AWS-hosted services responsible for mission planning, fleet coordination, and deep analysis |
| Depth Camera | A camera that captures distance-to-object data in addition to color, used for obstacle detection |
| SLAM | Simultaneous Localization and Mapping - technique for building a map of the environment while tracking position within it |
| VIO | Visual-Inertial Odometry - position tracking using camera and IMU data, useful when GPS is degraded |
