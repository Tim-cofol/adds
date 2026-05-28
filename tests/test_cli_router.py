"""Tests for the CLI trigger router."""

from __future__ import annotations

import pytest

from router.routes.cli import parse_args, validate_inputs, CLIValidationError
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).parent.parent / "workflows"


def test_parse_args_basic():
    wf_id, inputs = parse_args(["dev-feature-v1", "repo=/path", "issue=42"])
    assert wf_id == "dev-feature-v1"
    assert inputs["repo"] == "/path"
    assert inputs["issue"] == "42"


def test_parse_args_no_args_raises():
    with pytest.raises(CLIValidationError):
        parse_args([])


def test_parse_args_malformed_kwarg_raises():
    with pytest.raises(CLIValidationError):
        parse_args(["dev-feature-v1", "reponospace"])


def test_validate_inputs_happy_path():
    errors = validate_inputs(
        "dev-feature-v1",
        {"repo": "/path", "issue": "42"},
        WORKFLOWS_DIR,
    )
    assert errors == []


def test_validate_inputs_missing_required():
    errors = validate_inputs(
        "dev-feature-v1",
        {"repo": "/path"},  # issue missing
        WORKFLOWS_DIR,
    )
    assert any("issue" in e for e in errors)


def test_validate_inputs_unknown_workflow():
    errors = validate_inputs(
        "nonexistent-workflow",
        {},
        WORKFLOWS_DIR,
    )
    assert any("not found" in e for e in errors)


def test_validate_inputs_optional_not_required():
    # base_branch has a default and is not required
    errors = validate_inputs(
        "dev-feature-v1",
        {"repo": "/path", "issue": "1"},
        WORKFLOWS_DIR,
    )
    assert errors == []
