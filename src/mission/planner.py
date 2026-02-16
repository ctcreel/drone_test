"""Mission planner using AWS Bedrock (Claude) for AI-driven planning."""

import json
import os
from typing import Any

import boto3

from src.environment.models import EnvironmentModel
from src.exceptions.server_errors import ExternalServiceError, ProcessingError
from src.mission.models import MissionObjective, MissionPlan


def _build_planning_prompt(
    objective: MissionObjective,
    environment: EnvironmentModel,
    available_drones: list[dict[str, Any]],
) -> str:
    """Build a structured prompt for the Bedrock mission planner.

    Args:
        objective: Operator's mission objective.
        environment: Environment model with obstacles and no-fly zones.
        available_drones: List of available drones with positions and battery.

    Returns:
        Formatted prompt string.
    """
    drone_descriptions = [
        f"  - {drone['drone_id']}: "
        f"battery={drone.get('battery_percent', 100)}%, "
        f"position=({drone.get('latitude', 0)}, "
        f"{drone.get('longitude', 0)})"
        for drone in available_drones
    ]
    drones_text = "\n".join(drone_descriptions) if drone_descriptions else "  No drones available"

    coords = [coord.model_dump() for ring in objective.search_area.coordinates for coord in ring]
    search_area_json = json.dumps(coords, indent=2)

    return f"""You are a drone fleet mission planner. \
Generate a mission plan as JSON.

## Objective
{objective.description}

## Search Area
{search_area_json}

## Environment
- Buildings: {len(environment.building_footprints)}
- Obstacle zones: {len(environment.obstacle_zones)}
- No-fly zones: {len(environment.no_fly_zones)}
- Bounds: {json.dumps(environment.bounds)}

## Available Drones
{drones_text}

## Constraints
- Maintain 10m clearance from all buildings and obstacles
- Stay above 20m altitude in urban areas
- Minimum 5m separation between drones
- Camera capture every 2-5 seconds
- Maximum mission duration: 120 minutes

## Response Format
Return ONLY valid JSON matching this structure:
{{
  "search_pattern": "parallel_tracks",
  "reasoning": "Brief explanation of pattern choice",
  "drone_assignments": [
    {{
      "drone_id": "drone-001",
      "role": "primary_search",
      "segments": [
        {{
          "waypoints": [
            {{
              "latitude": 0.0,
              "longitude": 0.0,
              "altitude": 40.0,
              "speed": 5.0,
              "camera_interval_seconds": 3
            }}
          ],
          "altitude": 40.0,
          "camera_interval_seconds": 3
        }}
      ]
    }}
  ],
  "estimated_duration_seconds": 600,
  "estimated_coverage_percent": 95.0,
  "safety_notes": ["Note about potential hazards"]
}}"""


def plan_mission(
    objective: MissionObjective,
    environment: EnvironmentModel,
    available_drones: list[dict[str, Any]],
) -> MissionPlan:
    """Generate a mission plan using AWS Bedrock.

    Args:
        objective: Operator's mission objective.
        environment: Environment model for planning.
        available_drones: List of available drones.

    Returns:
        Generated mission plan.

    Raises:
        ExternalServiceError: If Bedrock call fails.
        ProcessingError: If response parsing fails.
    """
    model_id = os.environ.get(
        "BEDROCK_MODEL_ID",
        "anthropic.claude-sonnet-4-5-20250929-v1:0",
    )

    prompt = _build_planning_prompt(objective, environment, available_drones)

    try:
        bedrock = boto3.client("bedrock-runtime")  # type: ignore[call-overload]
        response = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                }
            ),
        )
    except Exception as error:
        raise ExternalServiceError(
            service_name="bedrock",
            message=f"Bedrock invocation failed: {error}",
        ) from error

    try:
        response_body = json.loads(response["body"].read())
        content_text = response_body["content"][0]["text"]

        # Extract JSON from response (may be wrapped in markdown code blocks)
        json_text = content_text
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0]
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0]

        plan_data = json.loads(json_text.strip())
        return MissionPlan(**plan_data)
    except (json.JSONDecodeError, KeyError, IndexError) as error:
        raise ProcessingError(
            message=f"Failed to parse Bedrock response: {error}",
        ) from error
