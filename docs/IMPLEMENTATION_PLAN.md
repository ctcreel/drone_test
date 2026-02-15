# Drone Fleet Search Control System - Implementation Plan

**Project:** AI-Driven Drone Fleet Search Control System
**Version:** 0.1 (Draft)
**Date:** 2026-02-15
**Status:** Awaiting Approval
**Prerequisites:** [REQUIREMENTS.md](./REQUIREMENTS.md) (Approved), [DESIGN.md](./DESIGN.md) (Approved)

---

## Table of Contents

1. [Implementation Phases](#1-implementation-phases)
2. [Phase 0: Project Scaffolding](#2-phase-0-project-scaffolding)
3. [Phase 1: Core Infrastructure](#3-phase-1-core-infrastructure)
4. [Phase 2: Cloud Tier - Mission Planning](#4-phase-2-cloud-tier---mission-planning)
5. [Phase 3: Cloud Tier - Fleet Coordination](#5-phase-3-cloud-tier---fleet-coordination)
6. [Phase 4: Cloud Tier - Image Analysis](#6-phase-4-cloud-tier---image-analysis)
7. [Phase 5: Edge Tier - Core](#7-phase-5-edge-tier---core)
8. [Phase 6: Edge Tier - Advanced](#8-phase-6-edge-tier---advanced)
9. [Phase 7: Simulation Environment](#9-phase-7-simulation-environment)
10. [Phase 8: Integration Testing](#10-phase-8-integration-testing)
11. [Phase 9: CI/CD Pipeline](#11-phase-9-cicd-pipeline)
12. [Unit Testing Plan](#12-unit-testing-plan)
13. [Integration Testing Plan](#13-integration-testing-plan)
14. [Definition of Done](#14-definition-of-done)

---

## 1. Implementation Phases

### 1.1 Phase Overview

```
Phase 0: Project Scaffolding          ──────▶ Tooling, structure, quality gates
Phase 1: Core Infrastructure (CDK)    ──────▶ AWS resources deployed and verified
Phase 2: Cloud - Mission Planning     ──────▶ Operator can submit objectives, AI generates plans
Phase 3: Cloud - Fleet Coordination   ──────▶ Commands dispatched to drones via IoT Core
Phase 4: Cloud - Image Analysis       ──────▶ Images analyzed, detections flagged
Phase 5: Edge - Core                  ──────▶ MAVLink bridge, mission execution, cloud connectivity
Phase 6: Edge - Advanced              ──────▶ Obstacle avoidance, image pipeline, fail-safe
Phase 7: Simulation Environment       ──────▶ Multi-drone SITL + Gazebo running end-to-end
Phase 8: Integration Testing          ──────▶ API-driven test suite passing in CI
Phase 9: CI/CD Pipeline               ──────▶ Automated deploy + test on merge
```

### 1.2 Dependency Graph

```
Phase 0 ──▶ Phase 1 ──▶ Phase 2 ──┐
                    │              │
                    ├──▶ Phase 3 ──┤
                    │              │
                    └──▶ Phase 4 ──┤
                                   │
Phase 0 ──▶ Phase 5 ──▶ Phase 6 ──┤
                                   │
                                   ├──▶ Phase 7 ──▶ Phase 8
                                   │
Phase 0 ──────────────────────────────────────────▶ Phase 9
```

- Phases 2, 3, 4 can be developed in parallel after Phase 1
- Phases 5, 6 (edge) can be developed in parallel with Phases 2, 3, 4 (cloud)
- Phase 7 (simulation) requires both cloud and edge tiers
- Phase 8 (integration tests) requires simulation
- Phase 9 (CI/CD) starts with Phase 0 scaffolding and evolves throughout

---

## 2. Phase 0: Project Scaffolding

**Goal:** Establish project structure, tooling, quality gates, and development workflow matching the reference repo standards.

### Tasks

| # | Task | Deliverable |
|---|---|---|
| 0.1 | Create `pyproject.toml` with all dependencies (cloud + edge + dev) | Configured build system, ruff, pyright, pytest, commitizen |
| 0.2 | Create `Makefile` with all quality gate targets | `make install`, `lint`, `test`, `check`, `format`, `security`, `cdk-synth`, `cdk-deploy` |
| 0.3 | Create `CLAUDE.md` with project-specific coding rules | Coding standards adapted for drone project (cloud + edge) |
| 0.4 | Create `.pre-commit-config.yaml` | All hooks: ruff, pyright, vulture, bandit, gitleaks, naming, commitizen |
| 0.5 | Create `.editorconfig`, `.gitleaks.toml`, `.gitignore` | Editor consistency, secret detection, clean repo |
| 0.6 | Create directory structure with `__init__.py` files | All packages under `src/`, `edge/`, `infra/`, `tests/`, `edge_tests/`, `infra_tests/` |
| 0.7 | Create `src/config.py` with Pydantic Settings | Environment-driven config for cloud tier |
| 0.8 | Create `src/constants.py` and `src/types.py` | Shared constants and type definitions |
| 0.9 | Create `src/exceptions/` with base exception hierarchy | Template Method + Registry pattern from reference repo |
| 0.10 | Create `src/logging/` with structured logging | JSON + human formatters, correlation IDs |
| 0.11 | Create `edge/config.py` with Pydantic Settings | Environment-driven config for edge tier |
| 0.12 | Create `infra/app.py` with environment config skeleton | CDK app with development/testing/production environments |
| 0.13 | Create initial GitHub Actions workflow for CI checks | Lint + test + security on PRs |
| 0.14 | Run `make check` and verify all quality gates pass with skeleton code | Green CI pipeline |
| 0.15 | Create `sonar-project.properties` | SonarCloud configuration |

### Exit Criteria
- `make install` succeeds
- `make check` passes (lint, test, security, naming)
- Pre-commit hooks run successfully
- GitHub Actions CI runs on PR
- 95%+ test coverage on skeleton code

---

## 3. Phase 1: Core Infrastructure

**Goal:** Deploy all AWS resources via CDK and verify they are operational.

### Tasks

| # | Task | Deliverable |
|---|---|---|
| 1.1 | Implement `infra/stacks/storage_stack.py` | DynamoDB table (single-table design), S3 bucket with lifecycle rules |
| 1.2 | Implement `infra/stacks/iot_stack.py` | IoT Core thing type, policy templates, IoT rules for telemetry/image/status |
| 1.3 | Implement `infra/stacks/api_stack.py` | API Gateway, Cognito user pool, Lambda function stubs |
| 1.4 | Implement `infra/stacks/processing_stack.py` | SQS queue for image analysis, image analyzer Lambda stub, EventBridge rules |
| 1.5 | Implement `infra/stacks/monitoring_stack.py` | CloudWatch dashboard, alarms, SNS notification topic |
| 1.6 | Write CDK infrastructure tests (`infra_tests/`) | Assert all stacks synthesize correctly, resource counts, IAM policies |
| 1.7 | Deploy to `chris-dev` account (`us-east-1`) | Stacks deployed, outputs captured |
| 1.8 | Manual verification of deployed resources | DynamoDB table accessible, S3 bucket exists with lifecycle, IoT Core endpoint reachable, API Gateway responds |

### Exit Criteria
- `make cdk-synth` succeeds for all stacks
- `infra_tests/` pass with 95%+ coverage
- All stacks deployed to chris-dev account
- API Gateway returns 200 on health check
- IoT Core endpoint reachable
- S3 lifecycle rules verified

---

## 4. Phase 2: Cloud Tier - Mission Planning

**Goal:** Operator can submit a search objective and receive an AI-generated mission plan.

### Tasks

| # | Task | Deliverable |
|---|---|---|
| 2.1 | Implement `src/mission/models.py` | Pydantic models: MissionObjective, SearchArea, MissionPlan, DroneAssignment, WaypointSequence |
| 2.2 | Implement `src/environment/models.py` | Pydantic models: EnvironmentModel, BuildingFootprint, ObstacleZone, NoFlyZone |
| 2.3 | Implement `src/environment/loader.py` | Load environment models from S3, parse GeoJSON |
| 2.4 | Implement `src/environment/validator.py` | Validate flight paths against environment model (clearance checks) |
| 2.5 | Implement `src/mission/planner.py` | Bedrock Claude integration: build prompt from objective + area + environment + fleet state, parse structured response |
| 2.6 | Implement `src/mission/search_patterns.py` | Define search pattern types: parallel tracks, expanding square, sector search, building perimeter, vertical scan |
| 2.7 | Implement `src/mission/controller.py` | Mission lifecycle: create, plan, approve, reject, abort, complete |
| 2.8 | Implement API endpoints | POST `/missions`, GET `/missions/{id}`, POST `/missions/{id}/approve`, POST `/missions/{id}/abort` |
| 2.9 | Implement `src/utils/geo.py` | Geographic utilities: area calculation, polygon operations, coordinate transforms |
| 2.10 | Write unit tests for all mission planning components | Tests for planner (mocked Bedrock), controller state machine, validator, models |

### Exit Criteria
- POST `/missions` with objective + area + environment returns a mission plan
- Plan includes drone assignments with waypoints respecting environment obstacles
- Operator can approve/reject plans via API
- All unit tests pass, 95%+ coverage
- Path validation rejects plans that violate clearance distances

---

## 5. Phase 3: Cloud Tier - Fleet Coordination

**Goal:** Cloud can dispatch commands to drones and track fleet state via IoT Core.

### Tasks

| # | Task | Deliverable |
|---|---|---|
| 3.1 | Implement `src/fleet/models.py` | Pydantic models: Drone, DroneStatus, DroneHealth, FleetState |
| 3.2 | Implement `src/fleet/command_dispatcher.py` | Publish mission commands to IoT Core MQTT topics per drone |
| 3.3 | Implement `src/telemetry/models.py` | Pydantic models: TelemetryReport, PositionReport, BatteryReport |
| 3.4 | Implement `src/telemetry/processor.py` | Lambda handler: receive telemetry from IoT Rule, update DynamoDB + Device Shadow |
| 3.5 | Implement `src/fleet/coordinator.py` | Fleet health monitoring: detect anomalies, trigger reassignment, emergency recall |
| 3.6 | Implement drone registration API | POST/GET/DELETE `/drones`, IoT Thing provisioning with X.509 certificate |
| 3.7 | Implement fleet status API | GET `/drones`, GET `/drones/{id}`, GET `/missions/{id}/status` |
| 3.8 | Implement `POST /drones/{id}/recall` | Single-drone emergency recall via IoT Core |
| 3.9 | Write unit tests for all fleet coordination components | Tests for dispatcher (mocked IoT), processor, coordinator logic |

### Exit Criteria
- Drone registration creates IoT Thing with certificate
- Approved mission dispatches waypoint commands to correct MQTT topics
- Telemetry updates are processed and reflected in DynamoDB and Device Shadow
- Fleet status API returns current state of all drones
- Emergency recall publishes to correct topic
- All unit tests pass, 95%+ coverage

---

## 6. Phase 4: Cloud Tier - Image Analysis

**Goal:** Images uploaded from drones are analyzed by Bedrock vision and detections are flagged.

### Tasks

| # | Task | Deliverable |
|---|---|---|
| 4.1 | Implement `src/analysis/models.py` | Pydantic models: CapturedImage, Detection, AnalysisResult, DetectionReview |
| 4.2 | Implement `src/analysis/analyzer.py` | Bedrock Claude vision integration: send image + search context, parse detection response |
| 4.3 | Implement image analyzer Lambda | SQS consumer: pull image from S3, call analyzer, store detections in DynamoDB |
| 4.4 | Implement `src/analysis/detection.py` | Detection management: create, query, review (confirm/dismiss), tag for S3 lifecycle |
| 4.5 | Implement detection API endpoints | GET `/missions/{id}/detections`, POST `/missions/{id}/detections/{id}/review` |
| 4.6 | Implement S3 event notification | Image upload triggers SQS message for analysis |
| 4.7 | Implement detection notification | EventBridge event on new detection, operator notification |
| 4.8 | Write unit tests for all image analysis components | Tests for analyzer (mocked Bedrock), detection lifecycle, S3 tagging |

### Exit Criteria
- Image uploaded to S3 triggers analysis via SQS
- Bedrock vision analyzes image against search objective
- Detections stored in DynamoDB with confidence scores and geo-tags
- Operator can review and confirm/dismiss detections via API
- Confirmed/dismissed detections tagged in S3 for lifecycle rules
- All unit tests pass, 95%+ coverage

---

## 7. Phase 5: Edge Tier - Core

**Goal:** Edge software connects to autopilot via MAVLink and to cloud via MQTT, executes waypoint sequences.

### Tasks

| # | Task | Deliverable |
|---|---|---|
| 5.1 | Implement `edge/mavlink_bridge/bridge.py` | pymavlink connection, heartbeat, command translation, telemetry collection |
| 5.2 | Implement `edge/mavlink_bridge/models.py` | Pydantic models: MavlinkCommand, TelemetryData, AutopilotState |
| 5.3 | Implement `edge/cloud_connector/connector.py` | AWS IoT Core MQTT client with TLS mutual auth, subscribe to command topics, publish telemetry |
| 5.4 | Implement `edge/cloud_connector/models.py` | Pydantic models: CloudMessage, CommandMessage, TelemetryMessage |
| 5.5 | Implement `edge/mission_executor/executor.py` | Receive waypoint sequences from cloud, sequence them to MAVLink bridge, track progress |
| 5.6 | Implement `edge/mission_executor/models.py` | Pydantic models: MissionSegment, WaypointProgress, ExecutorState |
| 5.7 | Implement `edge/main.py` | Edge application entry point: wire up all components, run event loop |
| 5.8 | Implement `edge/config.py` | Pydantic Settings for edge: drone ID, MQTT endpoint, MAVLink connection, timeouts |
| 5.9 | Write unit tests for all edge core components | Tests for MAVLink bridge (mocked pymavlink), cloud connector (mocked MQTT), executor state machine |

### Exit Criteria
- Edge connects to SITL autopilot via pymavlink, sends heartbeat, receives telemetry
- Edge connects to MQTT broker, subscribes to command topics, publishes telemetry
- Edge receives waypoint sequence from cloud and executes it via MAVLink
- Edge reports mission progress to cloud
- All unit tests pass, 95%+ coverage

---

## 8. Phase 6: Edge Tier - Advanced

**Goal:** Edge performs obstacle avoidance, image capture, and graceful degradation on connectivity loss.

### Tasks

| # | Task | Deliverable |
|---|---|---|
| 6.1 | Implement `edge/obstacle_avoidance/avoidance.py` | Consume depth frames, detect obstacles, compute avoidance maneuvers, override planned path |
| 6.2 | Implement `edge/obstacle_avoidance/models.py` | Pydantic models: DepthFrame, ObstacleDetection, AvoidanceManeuver |
| 6.3 | Implement `edge/image_pipeline/pipeline.py` | Camera capture, geo-tagging, compression, duplicate filtering, upload queue |
| 6.4 | Implement `edge/image_pipeline/models.py` | Pydantic models: CapturedFrame, ImageMetadata, UploadRequest |
| 6.5 | Implement `edge/mission_executor/fail_safe.py` | Fail-safe state machine: CONNECTED → DEGRADED → HOLDING → RETURNING |
| 6.6 | Implement message buffering in cloud connector | Buffer outbound messages during connectivity loss, drain on reconnect |
| 6.7 | Implement local mission segment cache | Cache current segment for continued navigation during connectivity gaps |
| 6.8 | Write unit tests for all edge advanced components | Tests for obstacle avoidance (simulated depth frames), image pipeline, fail-safe transitions |

### Exit Criteria
- Obstacle avoidance modifies flight path when obstacle detected in depth frame
- Image pipeline captures, geo-tags, compresses, and queues images for upload
- Fail-safe state machine transitions correctly on connectivity loss and restoration
- Messages buffered during connectivity loss are drained on reconnect
- Edge continues waypoint navigation from cached segment during brief connectivity gaps
- All unit tests pass, 95%+ coverage

---

## 9. Phase 7: Simulation Environment

**Goal:** Multi-drone simulation running end-to-end with cloud and edge tiers.

### Tasks

| # | Task | Deliverable |
|---|---|---|
| 7.1 | Create `simulation/docker-compose.yml` | SITL instances (2-5), Gazebo server, Mosquitto MQTT broker |
| 7.2 | Create Gazebo world files | `urban_block_01.world` (buildings + streets), `building_complex_01.world` (single building complex) |
| 7.3 | Configure SITL multi-drone instances | Port offsets, unique SYSID_THISMAV per drone, Gazebo frame config |
| 7.4 | Configure simulated sensors in Gazebo | Depth camera plugin, RGB camera plugin per drone |
| 7.5 | Create `simulation/launch/multi_drone.sh` | Launch script to start N drones with SITL + edge processes |
| 7.6 | Verify edge software runs against SITL | MAVLink connection, waypoint execution, telemetry flow |
| 7.7 | Verify edge-to-cloud communication | MQTT through Mosquitto (local) or IoT Core (deployed) |
| 7.8 | Run end-to-end test manually | Submit mission → plan → approve → drones fly → images captured → detections flagged |
| 7.9 | Create `simulation/README.md` setup guide | Step-by-step instructions for running simulation locally |

### Exit Criteria
- `docker compose up` starts 3 SITL drones + Gazebo + MQTT broker
- Edge processes connect to SITL and MQTT
- Full mission lifecycle works end-to-end in simulation
- Gazebo renders urban environment with buildings
- Simulated depth and RGB cameras produce frames consumed by edge

---

## 10. Phase 8: Integration Testing

**Goal:** API-driven integration test suite runs against simulation environment and passes in CI.

### Tasks

| # | Task | Deliverable |
|---|---|---|
| 8.1 | Implement test orchestration API endpoints | POST `/test/scenarios`, GET `/test/scenarios/{id}/results` |
| 8.2 | Implement test runner (`integration_tests/runner.py`) | Submits scenarios via API, polls for results, asserts outcomes |
| 8.3 | Create test scenario: `basic_area_search.json` | 3 drones, rectangular area, no obstacles, verify coverage |
| 8.4 | Create test scenario: `obstacle_avoidance.json` | 2 drones, area with buildings, verify no collisions and clearance maintained |
| 8.5 | Create test scenario: `connectivity_loss.json` | 3 drones, inject connectivity loss on drone-002, verify fail-safe behavior |
| 8.6 | Create test scenario: `fleet_coordination.json` | 5 drones, large area, verify separation and no overlap |
| 8.7 | Create test scenario: `image_pipeline.json` | 2 drones, area with planted target, verify detection |
| 8.8 | Create test scenario: `dynamic_replanning.json` | 3 drones, detection triggers reallocation, verify drones redirect |
| 8.9 | Integrate test runner into Makefile | `make integration-test` target |
| 8.10 | Integrate into GitHub Actions | Run integration tests post-deploy against simulation |

### Exit Criteria
- All 6 test scenarios pass via API-driven runner
- Test results are machine-readable JSON with pass/fail, metrics, and failure details
- `make integration-test` runs the full suite locally
- GitHub Actions runs integration tests on post-merge deploy

---

## 11. Phase 9: CI/CD Pipeline

**Goal:** Automated quality gates, deployment, and testing on every PR and merge.

### Tasks

| # | Task | Deliverable |
|---|---|---|
| 9.1 | Implement `pull-request.yml` orchestrator | Triggers CI checks, naming validation, CDK validation on PR |
| 9.2 | Implement `_ci-checks.yml` reusable workflow | Lint (ruff + pyright), test (pytest 95%), security (bandit + pip-audit) |
| 9.3 | Implement `_naming-validation.yml` reusable workflow | Branch name, Python naming, AWS resource naming |
| 9.4 | Implement `_deploy.yml` reusable workflow | CDK synth, diff, deploy to target environment |
| 9.5 | Implement `_edge-build.yml` reusable workflow | Edge unit tests, artifact packaging |
| 9.6 | Implement `post-merge.yml` | Deploy infrastructure, build edge, run integration tests, tag release |
| 9.7 | Implement `.github/actions/setup-python-uv/` custom action | Python 3.12 + UV install + cache |
| 9.8 | Configure branch protection on GitHub | Require CI checks to pass before merge |
| 9.9 | Test full pipeline end-to-end | PR → checks pass → merge → deploy → integration tests pass |

### Exit Criteria
- PRs cannot merge without passing lint, test, security, naming checks
- Merge to main triggers CDK deploy + integration tests
- Failed deployments do not leave broken infrastructure
- Pipeline runs in under 15 minutes for PR checks, under 30 minutes for post-merge

---

## 12. Unit Testing Plan

### 12.1 Testing Philosophy

Following the reference repo standards:
- **Test behavior, not implementation** - assert outcomes, not internal method calls
- **Mock external dependencies only** - AWS services, Bedrock, pymavlink, MQTT
- **95% coverage minimum** - enforced by pytest-cov and CI
- **No skip comments** - no `# noqa`, `# pragma: no cover`, `# type: ignore`
- **Fast execution** - all unit tests complete in under 60 seconds

### 12.2 Cloud Tier Unit Tests

#### `tests/unit/mission/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_models.py` | Mission Pydantic models | Valid/invalid objective creation, search area validation (valid polygon, empty polygon, self-intersecting), waypoint sequence validation |
| `test_planner.py` | Mission planner (Bedrock) | Prompt construction from objective + area + environment + fleet; response parsing for valid plan; handling malformed Bedrock response; path clearance validation on generated plan; retry on Bedrock throttling |
| `test_search_patterns.py` | Search pattern definitions | Each pattern type generates valid waypoints within bounds; patterns respect altitude constraints; building perimeter pattern follows building footprint |
| `test_controller.py` | Mission lifecycle | State transitions: created → planned → approved → executing → completed; reject returns to planned; abort from any active state; cannot approve without plan; cannot execute unapproved plan |
| `test_controller_edge_cases.py` | Mission controller edge cases | Duplicate approval rejected; abort during planning; concurrent modifications; mission not found |

#### `tests/unit/environment/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_models.py` | Environment Pydantic models | Valid/invalid building footprint, obstacle zone, no-fly zone creation; GeoJSON parsing |
| `test_loader.py` | Environment loader | Load from S3 (mocked); parse GeoJSON polygon; parse 3D building model; handle missing/corrupt data |
| `test_validator.py` | Path validator | Path with sufficient clearance passes; path too close to building fails; path through no-fly zone fails; path with altitude below obstacle fails; multi-segment path validation; clearance margin calculation |

#### `tests/unit/fleet/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_models.py` | Fleet Pydantic models | Drone creation with valid/invalid status; fleet state aggregation |
| `test_command_dispatcher.py` | Command dispatcher | Publish mission command to correct MQTT topic (mocked IoT Core); publish recall command; publish fleet-wide broadcast; message envelope format validation |
| `test_coordinator.py` | Fleet coordinator | Detect low battery anomaly; detect connection loss; trigger drone reassignment when drone unavailable; emergency recall all drones; fleet health aggregation |

#### `tests/unit/telemetry/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_models.py` | Telemetry Pydantic models | Valid position report; battery report; out-of-range values rejected |
| `test_processor.py` | Telemetry processor | Process position update → DynamoDB write (mocked); process battery update → DynamoDB write; detect stale telemetry (timestamp too old); update Device Shadow (mocked IoT) |

#### `tests/unit/analysis/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_models.py` | Analysis Pydantic models | Detection creation with confidence, bounding box, geo-tag; review state transitions |
| `test_analyzer.py` | Image analyzer (Bedrock) | Send image + context to Bedrock vision (mocked); parse detection response; handle no-detection response; handle Bedrock error/throttle; image too large handling |
| `test_detection.py` | Detection management | Create detection; query by mission; review (confirm/dismiss); S3 tag update on review (mocked S3); filter by confidence threshold |

#### `tests/unit/utils/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_geo.py` | Geographic utilities | Area calculation for polygon; point-in-polygon; distance between coordinates; polygon bounding box; coordinate validation |
| `test_retry.py` | Retry decorator | Succeeds on first attempt; retries on configured exception; gives up after max attempts; exponential backoff timing; jitter applied |

#### `tests/unit/test_config.py`

| Key Test Cases |
|---|
| Config loads from environment variables; missing required vars raises error; environment enum validation; is_production/is_development properties; cached singleton behavior |

### 12.3 Edge Tier Unit Tests

#### `edge_tests/unit/mavlink_bridge/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_bridge.py` | MAVLink bridge | Connect to autopilot (mocked pymavlink); send heartbeat at 1 Hz; translate waypoint command to MAVLink SET_POSITION_TARGET; translate RTL command; translate land command; collect position telemetry from GLOBAL_POSITION_INT; collect battery from BATTERY_STATUS; handle connection timeout |
| `test_models.py` | Bridge models | Valid command creation; telemetry data parsing; autopilot state transitions |

#### `edge_tests/unit/cloud_connector/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_connector.py` | Cloud connector | Connect to MQTT broker (mocked); subscribe to command topics for this drone; publish telemetry to correct topic; message envelope format; buffer messages when disconnected; drain buffer on reconnect; connectivity state detection |
| `test_models.py` | Connector models | Message serialization/deserialization; version validation; timestamp validation |

#### `edge_tests/unit/mission_executor/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_executor.py` | Mission executor | Receive waypoint sequence → issue first waypoint to bridge; advance to next waypoint on arrival; complete segment and report to cloud; cache segment locally; continue from cache on reconnect |
| `test_fail_safe.py` | Fail-safe state machine | CONNECTED → DEGRADED on connectivity loss; DEGRADED → CONNECTED on reconnect; DEGRADED → HOLDING when segment complete and still disconnected; HOLDING → RETURNING after timeout; RETURNING → CONNECTED on reconnect; cannot skip states |
| `test_models.py` | Executor models | Segment validation; progress tracking; state enum values |

#### `edge_tests/unit/obstacle_avoidance/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_avoidance.py` | Obstacle avoidance | No obstacle → no path modification; obstacle ahead → avoidance maneuver generated; obstacle clears → resume original path; multiple obstacles → compound avoidance; obstacle avoidance overrides planned path; 10 Hz processing loop timing |
| `test_models.py` | Avoidance models | Depth frame parsing; obstacle detection thresholds; maneuver parameters |

#### `edge_tests/unit/image_pipeline/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_pipeline.py` | Image pipeline | Capture frame from camera (mocked); geo-tag with current position and heading; compress image within size threshold; filter duplicate/blurry frames; queue for upload; upload to S3 via cloud connector |
| `test_models.py` | Pipeline models | Frame metadata validation; upload request format; compression settings |

### 12.4 Infrastructure Tests

#### `infra_tests/`

| Test File | Component | Key Test Cases |
|---|---|---|
| `test_storage_stack.py` | Storage stack | DynamoDB table created with correct keys and GSIs; S3 bucket created with lifecycle rules (7-day, 30-day, 90-day, 1-year tiers); encryption enabled; PAY_PER_REQUEST billing |
| `test_iot_stack.py` | IoT stack | IoT thing type created; policy template restricts to own topics; IoT rules route to correct Lambda/S3/DynamoDB targets; Device Shadow configured |
| `test_api_stack.py` | API stack | API Gateway created with correct routes; Lambda functions have correct IAM permissions; Cognito user pool configured; CORS settings |
| `test_processing_stack.py` | Processing stack | SQS queue created with DLQ; Lambda has S3 read + DynamoDB write + Bedrock invoke permissions; EventBridge rules configured |
| `test_monitoring_stack.py` | Monitoring stack | CloudWatch alarms created for each metric; SNS topic for notifications; dashboard configuration |

### 12.5 Test Mocking Strategy

| External Dependency | Mock Approach |
|---|---|
| AWS Bedrock (Claude) | `unittest.mock.patch` on boto3 Bedrock runtime client; fixture returns predefined JSON responses |
| AWS IoT Core | `unittest.mock.patch` on boto3 IoT Data client; verify publish/shadow calls |
| AWS DynamoDB | `unittest.mock.patch` on boto3 DynamoDB resource; or use moto library for higher fidelity |
| AWS S3 | `unittest.mock.patch` on boto3 S3 client; or use moto library |
| AWS SQS | `unittest.mock.patch` on boto3 SQS client; or use moto library |
| pymavlink | `unittest.mock.patch` on `mavutil.mavlink_connection`; fixture returns predefined messages |
| MQTT (paho/awsiot) | `unittest.mock.patch` on MQTT client; capture published messages, simulate received messages |
| Depth camera | Fixture provides pre-recorded depth frames as numpy arrays |
| RGB camera | Fixture provides test images (small JPEG files in test fixtures directory) |

### 12.6 Test Fixtures Directory

```
tests/
├── fixtures/
│   ├── missions/
│   │   ├── valid_objective.json
│   │   ├── valid_search_area.geojson
│   │   └── valid_mission_plan.json
│   ├── environments/
│   │   ├── urban_block.geojson
│   │   └── building_complex.geojson
│   ├── telemetry/
│   │   ├── position_report.json
│   │   └── battery_report.json
│   ├── images/
│   │   ├── test_capture.jpg
│   │   └── test_detection.jpg
│   └── bedrock_responses/
│       ├── mission_plan_response.json
│       └── image_analysis_response.json
│
edge_tests/
├── fixtures/
│   ├── mavlink/
│   │   ├── heartbeat_message.bin
│   │   └── position_message.bin
│   ├── depth_frames/
│   │   ├── no_obstacle.npy
│   │   ├── obstacle_ahead.npy
│   │   └── multiple_obstacles.npy
│   └── cloud_messages/
│       ├── mission_command.json
│       └── recall_command.json
```

---

## 13. Integration Testing Plan

### 13.1 Test Environment

Integration tests run against:
- **Cloud tier:** Deployed AWS stack (chris-dev account, us-east-1)
- **Edge tier:** Edge processes running locally or in CI
- **Simulation:** ArduPilot SITL + Gazebo (Docker Compose)
- **MQTT:** Local Mosquitto (substitutes for IoT Core) or real IoT Core

### 13.2 Test Orchestration

All integration tests are driven through the REST API. The test runner:

1. Starts simulation environment (if not running)
2. Submits test scenario via `POST /api/v1/test/scenarios`
3. Polls `GET /api/v1/test/scenarios/{id}/results` until complete or timeout
4. Asserts results match expected outcomes
5. Collects metrics and generates report

```bash
# Run locally
make simulation-up          # Start SITL + Gazebo + MQTT
make integration-test       # Run all scenarios

# Run in CI
# Docker Compose starts in GitHub Actions, tests hit deployed AWS stack
```

### 13.3 Test Scenarios

#### Scenario 1: Basic Area Search

**Purpose:** Verify the full mission lifecycle with no complications.

| Attribute | Value |
|---|---|
| Drones | 3 |
| Environment | Open area, no obstacles |
| Objective | "Search for a red vehicle" |
| Planted target | Red vehicle at known coordinates |

**Assertions:**
| Assertion | Threshold |
|---|---|
| Mission plan generated | Within 30 seconds |
| All drones take off | Within 60 seconds of approval |
| Area coverage | >= 85% |
| All drones return safely | RTL and land |
| Target detected | At least 1 detection with confidence >= 0.7 |
| Total mission duration | < 15 minutes |

---

#### Scenario 2: Obstacle Avoidance

**Purpose:** Verify drones navigate safely around buildings.

| Attribute | Value |
|---|---|
| Drones | 2 |
| Environment | Urban block with 4 buildings |
| Objective | "Search between the buildings for a person" |

**Assertions:**
| Assertion | Threshold |
|---|---|
| No collisions with buildings | 0 collision events |
| Minimum clearance maintained | >= 10 meters from all structures |
| Flight paths avoid buildings | All waypoint-to-waypoint segments clear |
| Drones search between buildings | Coverage of gaps between structures >= 80% |
| All drones return safely | RTL and land |

---

#### Scenario 3: Connectivity Loss Resilience

**Purpose:** Verify edge fail-safe behavior during cloud connectivity loss.

| Attribute | Value |
|---|---|
| Drones | 3 |
| Environment | Open area |
| Fault injection | Drone-002 loses cloud connectivity at T+120s for 30 seconds |

**Assertions:**
| Assertion | Threshold |
|---|---|
| Drone-002 continues current segment during outage | Waypoint progress continues |
| Drone-002 telemetry buffered | Telemetry appears in cloud after reconnect |
| Drone-002 images buffered | Images uploaded after reconnect |
| Drone-001 and Drone-003 unaffected | Continue mission normally |
| Drone-002 resumes cloud commands after reconnect | Mission continues from correct waypoint |
| No data loss | All buffered telemetry and images received |

---

#### Scenario 4: Extended Connectivity Loss (Hold + RTL)

**Purpose:** Verify hold-position and return-to-launch on extended connectivity loss.

| Attribute | Value |
|---|---|
| Drones | 2 |
| Environment | Open area |
| Fault injection | Drone-001 loses connectivity at T+60s for 5 minutes (exceeds hold timeout) |
| Hold timeout | 60 seconds |
| RTL timeout | 120 seconds |

**Assertions:**
| Assertion | Threshold |
|---|---|
| Drone-001 enters DEGRADED state | Within 5 seconds of connectivity loss |
| Drone-001 enters HOLDING state | After segment complete, still disconnected |
| Drone-001 enters RETURNING state | After 60-second hold timeout |
| Drone-001 returns to launch point | Within 2 minutes of RTL trigger |
| Drone-002 unaffected | Continues mission normally |
| Cloud detects Drone-001 connectivity loss | Alert within 30 seconds |

---

#### Scenario 5: Fleet Coordination

**Purpose:** Verify multi-drone separation and coverage optimization.

| Attribute | Value |
|---|---|
| Drones | 5 |
| Environment | Large rectangular area (1 km x 0.5 km) |
| Objective | "Systematically search the entire area" |

**Assertions:**
| Assertion | Threshold |
|---|---|
| Drone separation maintained | >= 20 meters between any two drones at all times |
| No overlapping search tracks | Overlap < 10% of total track length |
| Coverage optimization | >= 90% area coverage |
| All drones assigned work | No idle drones after plan execution begins |
| All drones return safely | RTL and land |
| Mission completes | Within estimated duration + 20% margin |

---

#### Scenario 6: Image Pipeline End-to-End

**Purpose:** Verify image capture, preprocessing, upload, analysis, and detection workflow.

| Attribute | Value |
|---|---|
| Drones | 2 |
| Environment | Area with 3 planted targets (red car, blue tent, person) |
| Objective | "Search for a red car" |
| Image interval | Every 2 seconds |

**Assertions:**
| Assertion | Threshold |
|---|---|
| Images captured by edge | >= 1 image per drone every 2 seconds |
| Images geo-tagged | All images have position + heading metadata |
| Images compressed | All images < 500 KB |
| Images uploaded to S3 | All non-filtered images present in S3 |
| Correct target detected | "Red car" detected with confidence >= 0.7 |
| Non-targets not flagged as primary | Blue tent and person not flagged as "red car" |
| Detection has correct geo-tag | Detection position within 10 meters of planted target |

---

#### Scenario 7: Dynamic Replanning

**Purpose:** Verify fleet reallocation when a detection is made.

| Attribute | Value |
|---|---|
| Drones | 3 |
| Environment | Large area with target in northeast corner |
| Objective | "Search for a missing person, concentrate on areas of interest" |

**Assertions:**
| Assertion | Threshold |
|---|---|
| Initial plan covers full area | >= 80% coverage planned |
| Detection triggers replanning | Within 30 seconds of first detection |
| At least 1 drone redirected | Drone reassigned toward detection area |
| Concentration area searched thoroughly | >= 95% coverage of 100m radius around detection |
| Operator notified of detection | Notification within 10 seconds of analysis |

---

### 13.4 Integration Test Results Schema

```json
{
  "scenario_id": "string",
  "scenario_name": "string",
  "status": "passed | failed | error | timeout",
  "started_at": "ISO 8601",
  "completed_at": "ISO 8601",
  "duration_seconds": 0,
  "environment": {
    "world_file": "string",
    "drone_count": 0,
    "cloud_stack": "string",
    "simulation_mode": "string"
  },
  "metrics": {
    "coverage_percent": 0.0,
    "obstacle_clearance_minimum_meters": 0.0,
    "drone_separation_minimum_meters": 0.0,
    "images_captured": 0,
    "images_uploaded": 0,
    "images_analyzed": 0,
    "detections_found": 0,
    "mission_plan_generation_seconds": 0.0,
    "mission_duration_seconds": 0.0,
    "telemetry_messages_received": 0,
    "connectivity_loss_events": 0,
    "obstacle_avoidance_events": 0
  },
  "assertions": [
    {
      "name": "string",
      "description": "string",
      "expected": "any",
      "actual": "any",
      "passed": true,
      "failure_reason": "string | null"
    }
  ],
  "drone_summaries": [
    {
      "drone_id": "string",
      "waypoints_completed": 0,
      "distance_flown_meters": 0.0,
      "images_captured": 0,
      "battery_used_percent": 0.0,
      "returned_safely": true,
      "fail_safe_events": []
    }
  ],
  "errors": []
}
```

### 13.5 CI Integration

```yaml
# In post-merge.yml
integration-tests:
  needs: [deploy]
  runs-on: ubuntu-latest
  services:
    sitl:
      image: ardupilot/sitl:latest
    gazebo:
      image: gazebo:latest
    mosquitto:
      image: eclipse-mosquitto:latest
  steps:
    - name: Start simulation (3 drones)
      run: ./simulation/launch/multi_drone.sh --count 3 --headless
    - name: Wait for simulation ready
      run: ./simulation/launch/wait_ready.sh --timeout 120
    - name: Run integration tests
      run: make integration-test
      env:
        API_ENDPOINT: ${{ needs.deploy.outputs.api_endpoint }}
        MQTT_BROKER: localhost:1883
    - name: Upload test results
      uses: actions/upload-artifact@v4
      with:
        name: integration-test-results
        path: integration_tests/results/
```

### 13.6 Test Execution Order

Integration tests run in a specific order due to dependencies:

```
1. basic_area_search          (validates core lifecycle)
2. image_pipeline             (validates image flow)
3. obstacle_avoidance         (validates navigation safety)
4. fleet_coordination         (validates multi-drone coordination)
5. connectivity_loss          (validates edge resilience)
6. extended_connectivity_loss (validates hold + RTL)
7. dynamic_replanning         (validates adaptive behavior)
```

If scenario 1 fails, subsequent scenarios are skipped (core lifecycle is broken).

---

## 14. Definition of Done

A phase is complete when:

1. All tasks in the phase are implemented
2. All unit tests pass with 95%+ coverage for new code
3. `make check` passes (lint, test, security, naming)
4. Pre-commit hooks pass
5. Code reviewed and merged via PR with passing CI
6. CDK changes deployed to chris-dev account (if applicable)
7. Integration tests for that phase's functionality pass (if applicable)
8. Documentation updated (if applicable)

The project is complete when:

1. All 10 phases pass their exit criteria
2. All 7 integration test scenarios pass
3. Full CI/CD pipeline runs end-to-end (PR → merge → deploy → integration test)
4. `make check` passes across the entire codebase
5. All infrastructure deployed and operational in chris-dev account
