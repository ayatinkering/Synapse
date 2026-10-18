"""Test the installed CLI boundary, including invalid input behavior."""

import subprocess
import sys
from importlib.metadata import version

import pytest


@pytest.mark.parametrize("entrypoint", [["synapse"], [sys.executable, "-m", "synapse"]])
def test_installed_entrypoints_report_distribution_version(entrypoint: list[str]) -> None:
    result = subprocess.run(
        [*entrypoint, "--version"], capture_output=True, text=True, timeout=10, check=False
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"synapse {version('synapse-research')}"
    assert result.stderr == ""


def test_help_discloses_offline_fixture_status() -> None:
    result = subprocess.run(["synapse"], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0
    assert "Offline fixture research pipeline." in result.stdout


def test_unknown_command_fails_clearly() -> None:
    result = subprocess.run(
        ["synapse", "research"], capture_output=True, text=True, timeout=10, check=False
    )
    assert result.returncode == 2
    assert "unrecognized arguments: research" in result.stderr
