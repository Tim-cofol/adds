"""Tests for assignee resolution / profile registry."""
import pytest
from instantiator.hermes_client import HermesClient, MissingRequiredProfileError, DEFAULT_PROFILE_REGISTRY


WORKFLOW = {
    "nodes": [
        {"id": "clarify", "assignee": "orchestrator"},
        {"id": "simple_impl", "assignee": "dev-codex"},
        {"id": "review", "assignee": "reviewer"},
        {"id": "pr", "assignee": "shipper"},
    ]
}


def test_direct_resolution_when_all_profiles_available():
    client = HermesClient()
    available = ["orchestrator", "dev-claude", "dev-codex", "reviewer", "shipper"]
    resolution = client.resolve_assignees(WORKFLOW, available)
    assert resolution["simple_impl"]["resolved_assignee"] == "dev-codex"
    assert resolution["simple_impl"]["assignee_resolution"] == "direct"


def test_dev_codex_falls_back_to_dev_claude():
    client = HermesClient()
    # dev-codex absent, dev-claude present
    available = ["orchestrator", "dev-claude", "reviewer", "shipper"]
    resolution = client.resolve_assignees(WORKFLOW, available)
    assert resolution["simple_impl"]["resolved_assignee"] == "dev-claude"
    assert resolution["simple_impl"]["assignee_resolution"] == "fallback"


def test_missing_required_profile_raises():
    client = HermesClient()
    # reviewer is required with no fallback
    available = ["orchestrator", "dev-claude", "dev-codex", "shipper"]
    with pytest.raises(MissingRequiredProfileError) as exc_info:
        client.resolve_assignees(WORKFLOW, available)
    assert "reviewer" in str(exc_info.value)


def test_missing_required_profile_error_lists_all_missing():
    client = HermesClient()
    # shipper and reviewer both absent
    available = ["orchestrator", "dev-claude"]
    with pytest.raises(MissingRequiredProfileError) as exc_info:
        client.resolve_assignees(WORKFLOW, available)
    error_str = str(exc_info.value)
    assert "reviewer" in error_str or "shipper" in error_str


def test_workflow_assignee_recorded_in_resolution():
    client = HermesClient()
    available = ["orchestrator", "dev-claude", "reviewer", "shipper"]
    resolution = client.resolve_assignees(WORKFLOW, available)
    assert resolution["simple_impl"]["workflow_assignee"] == "dev-codex"


def test_custom_registry_applied():
    client = HermesClient()
    custom_registry = {
        "orchestrator": {"hermes_profile": "orchestrator", "required": True, "fallback": None},
        "dev-codex": {"hermes_profile": "dev-codex", "required": False, "fallback": "alt-coder"},
        "reviewer": {"hermes_profile": "reviewer", "required": True, "fallback": None},
        "shipper": {"hermes_profile": "shipper", "required": True, "fallback": None},
    }
    available = ["orchestrator", "alt-coder", "reviewer", "shipper"]
    resolution = client.resolve_assignees(WORKFLOW, available, registry=custom_registry)
    assert resolution["simple_impl"]["resolved_assignee"] == "alt-coder"
    assert resolution["simple_impl"]["assignee_resolution"] == "fallback"
