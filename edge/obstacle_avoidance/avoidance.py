"""Obstacle avoidance using depth camera frames.

Provides deterministic obstacle detection and avoidance maneuver computation
based on depth camera data. All processing runs on-edge without any ML
or AI inference -- purely geometric and threshold-based algorithms.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from edge.obstacle_avoidance.models import (
    AvoidanceManeuver,
    ObstacleDetection,
    ObstacleSeverity,
)

if TYPE_CHECKING:
    from edge.config import EdgeSettings
    from edge.obstacle_avoidance.models import DepthFrame

logger = logging.getLogger(__name__)

# Severity threshold ratios (fraction of detection range)
_CRITICAL_RATIO: float = 0.2
_HIGH_RATIO: float = 0.4
_MEDIUM_RATIO: float = 0.6
_LOW_RATIO: float = 0.8

# Avoidance maneuver parameters
_CLIMB_MAGNITUDE_METERS: float = 5.0
_LATERAL_MAGNITUDE_METERS: float = 3.0
_HOLD_DURATION_SECONDS: float = 2.0
_CLIMB_DURATION_SECONDS: float = 3.0
_LATERAL_DURATION_SECONDS: float = 2.5

# Maneuver type names
_MANEUVER_HOLD = "hold"
_MANEUVER_CLIMB = "climb"
_MANEUVER_LATERAL_LEFT = "lateral_left"
_MANEUVER_LATERAL_RIGHT = "lateral_right"

# Priority levels
_PRIORITY_CRITICAL: int = 10
_PRIORITY_HIGH: int = 8
_PRIORITY_MEDIUM: int = 5
_PRIORITY_LOW: int = 2

# Bearing threshold for lateral direction selection
_BEARING_CENTER_THRESHOLD_DEGREES: float = 15.0


class ObstacleAvoidance:
    """Deterministic obstacle detection and avoidance computation.

    Analyzes depth camera frames to detect obstacles and computes
    appropriate avoidance maneuvers based on distance, bearing, and
    severity classification. No ML or AI inference is performed --
    all decisions are geometric and threshold-based.
    """

    def __init__(self, settings: EdgeSettings) -> None:
        """Initialize obstacle avoidance with detection parameters.

        Args:
            settings: Edge tier configuration with detection ranges.
        """
        self._detection_range_meters = settings.obstacle_detection_range_meters
        self._minimum_clearance_meters = settings.minimum_clearance_meters

    def process_depth_frame(self, frame: DepthFrame) -> list[ObstacleDetection]:
        """Analyze a depth frame and return detected obstacles.

        Examines the depth frame for objects within the detection range
        and classifies each by severity based on distance.

        Args:
            frame: Depth camera frame data with min/max distance readings.

        Returns:
            List of detected obstacles, sorted by distance (nearest first).
        """
        detections: list[ObstacleDetection] = []

        if frame.min_distance_meters <= 0.0:
            logger.debug(
                "Depth frame has no valid readings (min_distance=%.2f)",
                frame.min_distance_meters,
            )
            return detections

        if frame.min_distance_meters > self._detection_range_meters:
            logger.debug(
                "No obstacles within detection range (min_distance=%.2f, range=%.2f)",
                frame.min_distance_meters,
                self._detection_range_meters,
            )
            return detections

        # The depth frame provides aggregate distance data.
        # Generate a detection for the nearest obstacle in the frame.
        severity = self._classify_severity(
            distance=frame.min_distance_meters,
            detection_range=self._detection_range_meters,
        )

        if severity != ObstacleSeverity.NONE:
            # Estimate obstacle width proportional to how much of the frame it occupies.
            # Use max_distance to infer relative obstacle size in frame.
            estimated_width = self._estimate_obstacle_width(frame=frame)
            estimated_bearing = self._estimate_bearing(frame=frame)

            detection = ObstacleDetection(
                distance_meters=frame.min_distance_meters,
                bearing_degrees=estimated_bearing,
                severity=severity,
                width_meters=estimated_width,
                height_meters=estimated_width * 0.75,  # assume 4:3 aspect
            )
            detections.append(detection)

            logger.info(
                "Obstacle detected: distance=%.2fm, bearing=%.1f deg, severity=%s",
                detection.distance_meters,
                detection.bearing_degrees,
                detection.severity,
            )

        return detections

    def compute_avoidance(
        self,
        detections: list[ObstacleDetection],
    ) -> AvoidanceManeuver | None:
        """Compute an avoidance maneuver for detected obstacles.

        Selects the most critical detection and computes an appropriate
        avoidance maneuver. Returns None if no avoidance is needed.

        Args:
            detections: List of obstacle detections to evaluate.

        Returns:
            An avoidance maneuver if obstacles require action, or None.
        """
        if not detections:
            return None

        # Sort by distance to prioritize nearest obstacles
        sorted_detections = sorted(detections, key=lambda detection: detection.distance_meters)
        most_critical = sorted_detections[0]

        if most_critical.severity == ObstacleSeverity.NONE:
            return None

        if most_critical.distance_meters >= self._minimum_clearance_meters:
            logger.debug(
                "Obstacle at %.2fm is beyond minimum clearance (%.2fm), no avoidance needed",
                most_critical.distance_meters,
                self._minimum_clearance_meters,
            )
            return None

        maneuver = self._select_maneuver(detection=most_critical)
        logger.warning(
            "Avoidance maneuver selected: type=%s, magnitude=%.1fm, priority=%d",
            maneuver.maneuver_type,
            maneuver.magnitude_meters,
            maneuver.priority,
        )
        return maneuver

    def _classify_severity(
        self,
        distance: float,
        detection_range: float,
    ) -> ObstacleSeverity:
        """Classify obstacle severity by distance relative to detection range.

        Args:
            distance: Distance to the obstacle in meters.
            detection_range: Maximum detection range in meters.

        Returns:
            Severity classification based on distance thresholds.
        """
        if detection_range <= 0.0:
            return ObstacleSeverity.NONE

        ratio = distance / detection_range

        if ratio <= _CRITICAL_RATIO:
            return ObstacleSeverity.CRITICAL
        if ratio <= _HIGH_RATIO:
            return ObstacleSeverity.HIGH
        if ratio <= _MEDIUM_RATIO:
            return ObstacleSeverity.MEDIUM
        if ratio <= _LOW_RATIO:
            return ObstacleSeverity.LOW
        return ObstacleSeverity.NONE

    def _select_maneuver(
        self,
        detection: ObstacleDetection,
    ) -> AvoidanceManeuver:
        """Select the best avoidance maneuver for a detected obstacle.

        Strategy:
        - CRITICAL: Hold position immediately.
        - HIGH: Climb to gain altitude clearance.
        - MEDIUM/LOW: Lateral avoidance based on obstacle bearing.

        Args:
            detection: The obstacle detection to avoid.

        Returns:
            The computed avoidance maneuver.
        """
        if detection.severity == ObstacleSeverity.CRITICAL:
            return AvoidanceManeuver(
                maneuver_type=_MANEUVER_HOLD,
                magnitude_meters=0.0,
                duration_seconds=_HOLD_DURATION_SECONDS,
                priority=_PRIORITY_CRITICAL,
            )

        if detection.severity == ObstacleSeverity.HIGH:
            return AvoidanceManeuver(
                maneuver_type=_MANEUVER_CLIMB,
                magnitude_meters=_CLIMB_MAGNITUDE_METERS,
                duration_seconds=_CLIMB_DURATION_SECONDS,
                priority=_PRIORITY_HIGH,
            )

        # For MEDIUM and LOW severity, choose lateral direction
        lateral_direction = self._choose_lateral_direction(
            bearing_degrees=detection.bearing_degrees,
        )
        priority = (
            _PRIORITY_MEDIUM
            if detection.severity == ObstacleSeverity.MEDIUM
            else _PRIORITY_LOW
        )

        return AvoidanceManeuver(
            maneuver_type=lateral_direction,
            magnitude_meters=_LATERAL_MAGNITUDE_METERS,
            duration_seconds=_LATERAL_DURATION_SECONDS,
            priority=priority,
        )

    def _choose_lateral_direction(self, bearing_degrees: float) -> str:
        """Choose lateral avoidance direction based on obstacle bearing.

        Moves away from the obstacle: if obstacle is to the right (positive
        bearing), move left, and vice versa.

        Args:
            bearing_degrees: Bearing to the obstacle in degrees (-180 to 180).

        Returns:
            Lateral maneuver direction string.
        """
        if bearing_degrees > _BEARING_CENTER_THRESHOLD_DEGREES:
            return _MANEUVER_LATERAL_LEFT
        if bearing_degrees < -_BEARING_CENTER_THRESHOLD_DEGREES:
            return _MANEUVER_LATERAL_RIGHT
        # Obstacle is dead center -- default to climbing instead of lateral
        return _MANEUVER_CLIMB

    def _estimate_obstacle_width(self, frame: DepthFrame) -> float:
        """Estimate obstacle width from depth frame data.

        Uses the ratio between min and max distances in the frame
        as a proxy for how much of the field of view the obstacle occupies.

        Args:
            frame: Depth camera frame data.

        Returns:
            Estimated width of the obstacle in meters.
        """
        if frame.max_distance_meters <= 0.0:
            return 1.0

        # Larger ratio difference implies a smaller, closer object
        depth_range = frame.max_distance_meters - frame.min_distance_meters
        coverage_ratio = 1.0 - (depth_range / frame.max_distance_meters)
        return max(0.5, coverage_ratio * frame.min_distance_meters * 0.5)

    def _estimate_bearing(self, frame: DepthFrame) -> float:
        """Estimate bearing to obstacle from depth frame data.

        With aggregate depth frame data (no per-pixel detail), we assume
        the obstacle is centered in the frame (bearing = 0).

        Args:
            frame: Depth camera frame data.

        Returns:
            Estimated bearing in degrees. 0.0 for aggregate frames.
        """
        # Aggregate depth frame -- assume centered obstacle
        return 0.0
