"""Tests for the CLI trigger router."""

from __future__ import annotations

import pytest

from router.routes.cli import (
    parse_args,
    validate_inputs,
    CLIValidationError,
    parse_wf_args,
    validate_required_params,
    build_trigger_payload,
    CliParseError,
)
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).parent.parent / "workflows"


# --- parse_args / validate_inputs (complex_impl API with WorkflowInstantiator) ---

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


def test_parse_args_empty_key_raises():
    with pytest.raises(CLIValidationError):
        parse_args(["dev-feature-v1", "=value"])


def test_parse_args_value_with_equals_sign_ok():
    _, inputs = parse_args(["dev-feature-v1", "token=abc=def"])
    assert inputs["token"] == "abc=def"


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
    errors = validate_inputs(
        "dev-feature-v1",
        {"repo": "/path", "issue": "1"},
        WORKFLOWS_DIR,
    )
    assert errors == []


# --- parse_wf_args / validate_required_params / build_trigger_payload (simple_impl API) ---

def test_parse_basic_wf_args():
    wf_id, params = parse_wf_args(["dev-feature", "repo=/tmp/r", "issue=42"])
    assert wf_id == "dev-feature"
    assert params == {"repo": "/tmp/r", "issue": "42"}


def test_parse_no_argv_raises():
    with pytest.raises(CliParseError):
        parse_wf_args([])


def test_parse_malformed_param_raises():
    with pytest.raises(CliParseError):
        parse_wf_args(["dev-feature", "badparam"])


def test_parse_empty_key_raises():
    with pytest.raises(CliParseError):
        parse_wf_args(["dev-feature", "=value"])


def test_parse_value_with_equals_sign_ok():
    _, params = parse_wf_args(["dev-feature", "token=abc=def"])
    assert params["token"] == "abc=def"


def test_validate_required_params_all_present():
    missing = validate_required_params("wf", {"repo": "/r", "issue": "1"}, ["repo", "issue"])
    assert missing == []


def test_validate_required_params_missing():
    missing = validate_required_params("wf", {"repo": "/r"}, ["repo", "issue"])
    assert "issue" in missing


def test_build_trigger_payload_shape():
    payload = build_trigger_payload("dev-feature-v1", {"repo": "/r", "issue": "5"})
    assert payload["workflow_id"] == "dev-feature-v1"
    assert payload["source"] == "cli"
    assert payload["params"]["issue"] == "5"


def test_build_trigger_payload_custom_source():
    payload = build_trigger_payload("wf", {}, source="github-label")
    assert payload["source"] == "github-label"
