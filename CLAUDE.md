# CLAUDE.md - Drone Fleet Search Control System Coding Standards

## CRITICAL: Run Before Completing Any Task

```bash
make check   # ALL checks must pass
make test    # ALL tests must pass, 95%+ coverage required
```

**If these fail, the code is NOT complete. Fix issues first.**

---

## Architecture

Two-tier system:
- **Cloud (src/):** AWS Lambda, DynamoDB, S3, IoT Core, Bedrock - mission planning, fleet coordination, image analysis
- **Edge (edge/):** Nvidia Jetson - MAVLink bridge, obstacle avoidance, image capture, fail-safe state machine
- **Infrastructure (infra/):** AWS CDK in Python - storage, IoT, API, processing, monitoring stacks

AI lives in the CLOUD (Bedrock Claude). Edge runs DETERMINISTIC code only.

---

## Design Patterns Used in This Codebase

| Pattern | Location | Purpose |
|---------|----------|---------|
| Template Method | `src/exceptions/base.py` | Base exception defines structure, subclasses customize |
| Registry | `src/exceptions/base.py` | Auto-registration of exceptions by error_code |
| Factory | `src/logging/logger.py` | `get_logger()` creates configured loggers |
| Singleton State | `src/logging/logger.py` | Module-level `_state` for one-time setup |
| Adapter | `src/logging/adapters/` | Lambda/ASGI adapters for different runtimes |
| State Machine | `edge/mission_executor/fail_safe.py` | CONNECTED > DEGRADED > HOLDING > RETURNING |

**Use these patterns when appropriate. Don't invent new patterns unnecessarily.**

---

## Core Rules

### 1. Fail Fast - No Defensive Code

```python
# WRONG - defensive
value = data.get('key', [])
if user is not None:
    user.save()

# CORRECT - fail fast
value = data['key']
user.save()
```

### 2. Validate at Boundaries Only

```python
# External input: validate ONCE with Pydantic
validated = MissionObjective(**request)

# Internal code: trust completely, no isinstance/hasattr
internal_object.process()
```

### 3. No Skip Comments

```python
# FORBIDDEN - never add these
# noqa, # nosec, # type: ignore, # pragma: no cover
```

Write clean code instead of suppressing warnings.

---

## Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Classes | PascalCase | `MissionPlanner`, `DroneFleetError` |
| Functions | snake_case with verb | `create_mission_plan`, `get_drone_status` |
| Methods | snake_case | `calculate_waypoints`, `to_dict` |
| Constants | SCREAMING_SNAKE | `DEFAULT_ALTITUDE`, `MAX_FLEET_SIZE` |
| Variables | snake_case | `mission_plan`, `drone_count` |

**Functions MUST start with a verb:** get, set, create, update, delete, build, process, handle, validate, dispatch, execute, etc.

---

## Forbidden Abbreviations

Use full words: `message` not `msg`, `request` not `req`, `config` not `cfg`, `context` not `ctx`, `command` not `cmd`, `response` not `resp`, `telemetry` not `telem`

---

## Code Structure

### Imports

```python
# Always at file top, never inside functions
import logging
from typing import TYPE_CHECKING

from aws_cdk import Stack
from pydantic import BaseModel

from src.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable
```

### Function Signatures (3+ parameters)

```python
# Vertical formatting required
def create_mission_plan(
    objective: MissionObjective,
    search_area: SearchArea,
    *,
    fleet_state: FleetState,
    environment_model: EnvironmentModel | None = None,
) -> MissionPlan:
```

### Function Calls (3+ arguments)

```python
# Named parameters required
result = create_mission_plan(
    objective=objective,
    search_area=area,
    fleet_state=fleet,
)
```

---

## Type Annotations

- Use Python 3.12+ syntax: `list[str]` not `List[str]`, `str | None` not `Optional[str]`
- `Any` only for CDK `**kwargs` or circular imports (with comment)
- All functions must have return type annotations

---

## Testing

- Coverage must be 95%+
- Test behavior, not implementation
- Use `pytest.raises` for exception testing
- Mock external dependencies only (boto3, pymavlink, MQTT)
- Class-based test organization by functionality

---

## MQTT Topics

```
drone-fleet/{drone_id}/command/{command_type}
drone-fleet/{drone_id}/telemetry
drone-fleet/{drone_id}/image/metadata
drone-fleet/{drone_id}/status
```

---

## Quick Reference

```bash
# Setup
uv sync --all-extras

# Before committing
make format   # Auto-format code
make check    # All quality checks
make test     # Tests with coverage

# Individual checks
make lint     # Ruff + Pyright + Vulture
make security # Bandit + pip-audit
make naming   # Naming conventions

# CDK
make cdk-synth  # Synthesize templates
make cdk-diff   # Show changes
make cdk-deploy # Deploy (runs all checks first)
```
