"""Tests for profile registry assignee resolution."""

from __future__ import annotations

import pytest

from instantiator.hermes_client import HermesClient, MissingRequiredProfileError


WORKFLOW = {
    "nodes": [
        {"id": "clarify", "assignee": "orchestrator"},
        {"id": "complex_impl", "assignee": "dev-claude"},
        {"id": "simple_impl", "assignee": "dev-codex"},
        {"id": "review", "assignee": "reviewer"},
        {"id": "pr", "assignee": "shipper"},
    ]
}

REGISTRY_ALL_REQUIRED = {
    "orchestrator": {"hermes_profile": "orchestrator", "required": True, "fallback": None},
    "dev-claude": {"hermes_profile": "dev-claude", "required": True, "fallback": None},
    "dev-codex": {"hermes_profile": "dev-codex", "required": False, "fallback": "dev-claude"},
    "reviewer": {"hermes_profile": "reviewer", "required": True, "fallback": None},
    "shipper": {"hermes_profile": "shipper", "required": True, "fallback": None},
}


@pytest.fixture
def client():
    return HermesClient()


def test_direct_resolution_all_profiles(client):
    available = ["orchestrator", "dev-claude", "dev-codex", "reviewer", "shipper"]
    result = client.resolve_assignees(WORKFLOW, available, REGISTRY_ALL_REQUIRED)
    assert result["clarify"]["resolved_assignee"] == "orchestrator"
    assert result["clarify"]["assignee_resolution"] == "direct"
    assert result["simple_impl"]["resolved_assignee"] == "dev-codex"
    assert result["simple_impl"]["assignee_resolution"] == "direct"


def test_fallback_when_dev_codex_absent(client):
    available = ["orchestrator", "dev-claude", "reviewer", "shipper"]
    result = client.resolve_assignees(WORKFLOW, available, REGISTRY_ALL_REQUIRED)
    assert result["simple_impl"]["resolved_assignee"] == "dev-claude"
    assert result["simple_impl"]["assignee_resolution"] == "fallback"


def test_missing_required_profile_raises(client):
    available = ["dev-claude", "dev-codex"]  # orchestrator, reviewer, shipper missing
    with pytest.raises(MissingRequiredProfileError) as exc_info:
        client.resolve_assignees(WORKFLOW, available, REGISTRY_ALL_REQUIRED)
    assert "orchestrator" in exc_info.value.missing or "reviewer" in exc_info.value.missing


def test_missing_optional_no_fallback_raises(client):
    registry = {
        **REGISTRY_ALL_REQUIRED,
        "dev-codex": {"hermes_profile": "dev-codex", "required": False, "fallback": None},
    }
    available = ["orchestrator", "dev-claude", "reviewer", "shipper"]
    # dev-codex absent and no fallback — should raise (required=False but no fallback)
    with pytest.raises(MissingRequiredProfileError):
        client.resolve_assignees(WORKFLOW, available, registry)


def test_resolution_metadata_recorded(client):
    available = ["orchestrator", "dev-claude", "reviewer", "shipper"]
    result = client.resolve_assignees(WORKFLOW, available, REGISTRY_ALL_REQUIRED)
    r = result["simple_impl"]
    assert r["workflow_assignee"] == "dev-codex"
    assert r["resolved_assignee"] == "dev-claude"
    assert r["assignee_resolution"] == "fallback"
