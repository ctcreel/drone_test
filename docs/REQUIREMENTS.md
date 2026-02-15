# Drone Fleet Search Control System - Requirements Document

**Project:** AI-Driven Drone Fleet Search Control System
**Version:** 0.1 (Draft)
**Date:** 2026-02-15
**Status:** Awaiting Approval

---

## 1. Project Overview

Build a cloud-based control system hosted on AWS that uses an AI model to plan and coordinate visual search missions across a fleet of ArduPilot/PX4 drones. An operator provides a search objective (e.g., "search this area for a missing person") and the system autonomously generates flight plans, dispatches commands to the drone fleet, monitors progress, and analyzes visual data to fulfill the objective.

## 2. Scope

### 2.1 In Scope

- Cloud-based mission planning and fleet coordination service on AWS
- AI-powered search planning using Claude via AWS Bedrock
- Visual search capability using camera feeds and computer vision
- MAVLink-based command and telemetry interface for ArduPilot/PX4 drones
- Fleet coordination for 2-5 drones
- Simulation environment using ArduPilot SITL (Software In The Loop)
- Infrastructure as Code using AWS CDK (Python)
- CI/CD pipeline using GitHub Actions
- Operator interface for submitting search objectives and monitoring missions
- Drone-to-cloud communication over internet/cellular

### 2.2 Out of Scope (Phase 1)

- Physical drone hardware integration (simulation-first approach)
- Thermal, LIDAR, or other non-visual sensor integration
- Fleets larger than 5 drones
- Offline/disconnected operation
- Regulatory compliance filing (FAA Part 107 waivers, etc.)
- Ground station relay communication
- Custom-trained ML models
- Real-time video streaming (will use periodic image capture)

## 3. Functional Requirements

### 3.1 Mission Planning (FR-100)

| ID | Requirement | Priority |
|---|---|---|
| FR-101 | The system shall accept a search objective as natural language input from an operator (e.g., "Search the area bounded by these coordinates for a red vehicle") | Must |
| FR-102 | The system shall accept a geographic search area defined by coordinates (polygon or bounding box) | Must |
| FR-103 | The AI planner (Claude via Bedrock) shall decompose a search objective into individual drone assignments with waypoints, altitudes, and camera parameters | Must |
| FR-104 | The AI planner shall optimize search patterns to minimize overlap and maximize area coverage given the available fleet size | Must |
| FR-105 | The system shall support common search patterns: parallel tracks, expanding square, sector search, creeping line | Should |
| FR-106 | The AI planner shall dynamically reassign drones if a drone becomes unavailable during a mission | Should |
| FR-107 | The system shall allow an operator to approve, modify, or reject a generated mission plan before execution | Must |

### 3.2 Fleet Command and Control (FR-200)

| ID | Requirement | Priority |
|---|---|---|
| FR-201 | The system shall send MAVLink commands to each drone in the fleet via internet/cellular connection | Must |
| FR-202 | The system shall receive telemetry data (position, altitude, speed, battery, status) from each drone | Must |
| FR-203 | The system shall monitor drone health and flag anomalies (low battery, connection loss, deviation from plan) | Must |
| FR-204 | The system shall support the following commands: arm, takeoff, navigate to waypoint, loiter, return to launch, land | Must |
| FR-205 | The system shall maintain a real-time state model for each drone in the fleet | Must |
| FR-206 | The system shall support emergency recall of individual drones or the entire fleet | Must |
| FR-207 | The system shall handle temporary connection loss gracefully with configurable timeout behavior | Should |

### 3.3 Visual Search and Analysis (FR-300)

| ID | Requirement | Priority |
|---|---|---|
| FR-301 | The system shall receive images captured by drone cameras at configurable intervals | Must |
| FR-302 | The system shall analyze captured images using a vision model to detect objects matching the search objective | Must |
| FR-303 | The system shall geo-tag each analyzed image with the drone's position at time of capture | Must |
| FR-304 | The system shall flag potential matches with confidence scores and notify the operator | Must |
| FR-305 | The system shall maintain a searchable catalog of all images captured during a mission | Should |
| FR-306 | The AI shall refine the search strategy based on analysis results (e.g., concentrate drones around an area of interest) | Should |

### 3.4 Operator Interface (FR-400)

| ID | Requirement | Priority |
|---|---|---|
| FR-401 | The system shall provide an API for submitting search objectives | Must |
| FR-402 | The system shall provide mission status via API (drone positions, mission progress, detections) | Must |
| FR-403 | The system shall provide a web-based dashboard for mission monitoring | Should |
| FR-404 | The system shall support mission abort and drone recall via the operator interface | Must |
| FR-405 | The system shall display flagged detections with images and locations for operator review | Should |

### 3.5 Simulation (FR-500)

| ID | Requirement | Priority |
|---|---|---|
| FR-501 | The system shall integrate with ArduPilot SITL for drone simulation | Must |
| FR-502 | The simulation shall support multiple concurrent simulated drones (2-5) | Must |
| FR-503 | The simulation shall generate synthetic camera imagery for visual search testing | Should |
| FR-504 | The simulation environment shall be runnable locally for development and in CI for testing | Must |

## 4. Non-Functional Requirements

### 4.1 Performance (NFR-100)

| ID | Requirement |
|---|---|
| NFR-101 | Command latency from system to drone shall be < 2 seconds under normal network conditions |
| NFR-102 | Telemetry updates shall be processed at a minimum rate of 1 Hz per drone |
| NFR-103 | Image analysis shall complete within 10 seconds of image receipt |
| NFR-104 | Mission plan generation shall complete within 30 seconds of objective submission |

### 4.2 Reliability (NFR-200)

| ID | Requirement |
|---|---|
| NFR-201 | The system shall maintain operation if a single drone loses connectivity |
| NFR-202 | Drones shall execute fail-safe behavior (return to launch) if cloud connectivity is lost beyond a configurable timeout |
| NFR-203 | The system shall persist mission state to survive service restarts |

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
| CI/CD | GitHub Actions deploying to AWS |
| Drone Platform | ArduPilot / PX4 compatible autopilots |
| Communication Protocol | MAVLink over TCP/UDP via internet |
| AI Planning Model | Claude via AWS Bedrock |
| Vision Analysis | AWS Bedrock (Claude vision) or Amazon Rekognition |
| Simulation | ArduPilot SITL |
| Repository | github.com/ctcreel/drone_test |

## 6. Assumptions

1. Drones are equipped with a companion computer (e.g., Raspberry Pi) running a MAVLink-to-internet bridge
2. Drones have reliable cellular (4G/5G) or WiFi internet connectivity during missions
3. Cameras on drones can capture and transmit still images at regular intervals
4. The operator is responsible for ensuring legal compliance for drone operations
5. ArduPilot SITL provides sufficient fidelity for initial development and testing
6. AWS Bedrock provides access to Claude models in the target region

## 7. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Network latency/reliability over cellular | Delayed or lost commands could cause unsafe drone behavior | Implement drone-side fail-safes; design for eventual consistency |
| AI planning errors | Incorrect flight plans could cause collisions or missed coverage | Operator approval gate; collision avoidance checks; conservative altitude separation |
| AWS Bedrock rate limits | Could throttle image analysis during active missions | Implement queuing; batch processing; consider Rekognition as fallback |
| SITL limitations | Simulated environment may not reveal real-world integration issues | Plan for phased hardware integration testing |
| Cost management | Bedrock API calls and compute could generate unexpected costs | Implement cost monitoring and budget alerts; use spot instances where possible |

## 8. Success Criteria

1. Operator can submit a natural language search objective with a geographic area
2. The system generates and presents a coordinated flight plan for 2-5 simulated drones
3. Upon operator approval, simulated drones execute the search pattern
4. Images from the simulation are analyzed and potential matches are flagged
5. The operator can monitor mission progress and recall drones
6. All infrastructure is deployed via CDK through GitHub Actions

## 9. Glossary

| Term | Definition |
|---|---|
| MAVLink | Micro Air Vehicle Link - lightweight protocol for drone communication |
| SITL | Software In The Loop - ArduPilot's simulation mode that runs the autopilot code without hardware |
| Waypoint | A geographic coordinate (lat/lon/alt) that a drone navigates to |
| RTL | Return To Launch - fail-safe command that returns a drone to its takeoff point |
| GCS | Ground Control Station - software/hardware for monitoring and controlling drones |
| Bedrock | AWS managed service for accessing foundation AI models |
