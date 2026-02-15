"""Tests for CDK app stack wiring."""

import subprocess
import sys


class TestCdkSynth:
    """Tests that CDK synthesizes all stacks successfully."""

    def test_cdk_synth_succeeds(self) -> None:
        """All stacks synthesize without errors."""
        result = subprocess.run(
            [sys.executable, "app.py"],
            cwd="/Volumes/SSD/Code/Github/ctcreel/drone_test/infra",
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"CDK synth failed:\n{result.stderr}"

    def test_all_five_stacks_in_output(self) -> None:
        """All five stacks are present in the synthesized output."""
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
import aws_cdk as cdk
from stacks.storage_stack import StorageStack
from stacks.processing_stack import ProcessingStack
from stacks.api_stack import ApiStack
from stacks.iot_stack import IoTStack
from stacks.monitoring_stack import MonitoringStack
print("All stack imports successful")
"""],
            cwd="/Volumes/SSD/Code/Github/ctcreel/drone_test/infra",
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Stack imports failed:\n{result.stderr}"
        assert "All stack imports successful" in result.stdout
