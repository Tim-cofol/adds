"""Tests for the CLI trigger router."""
import pytest
from router.routes.cli import parse_wf_args, validate_required_params, build_trigger_payload, CliParseError


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
    # Values containing = are fine (e.g. base64, URLs)
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
