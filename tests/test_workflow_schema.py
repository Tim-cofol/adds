"""Tests for the workflow YAML schema validation."""

from __future__ import annotations

import pytest
import yaml

from instantiator.validator import WorkflowValidator


MINIMAL_VALID = {
    "id": "test-v1",
    "version": "1.0.0",
    "inputs": {
        "repo": {"type": "path", "required": True}
    },
    "entry": {"assignee": "orchestrator"},
    "nodes": [
        {"id": "clarify", "assignee": "orchestrator", "body": "Do clarify."}
    ],
}


@pytest.fixture
def validator():
    return WorkflowValidator()


def test_valid_minimal_workflow(validator):
    errors = validator.validate(MINIMAL_VALID)
    assert errors == []


def test_missing_required_top_level_fields(validator):
    bad = {"nodes": []}
    errors = validator.validate(bad)
    assert errors  # Schema requires id, version, inputs, entry, nodes


def test_duplicate_node_ids(validator):
    wf = {**MINIMAL_VALID, "nodes": [
        {"id": "a", "assignee": "x", "body": "b"},
        {"id": "a", "assignee": "y", "body": "c"},
    ]}
    errors = validator.validate(wf)
    assert any("Duplicate" in e for e in errors)


def test_parent_references_unknown_node(validator):
    wf = {**MINIMAL_VALID, "nodes": [
        {"id": "a", "assignee": "x", "body": "b", "parents": ["nonexistent"]},
    ]}
    errors = validator.validate(wf)
    assert any("unknown parent" in e for e in errors)


def test_cycle_detection(validator):
    wf = {**MINIMAL_VALID, "nodes": [
        {"id": "a", "assignee": "x", "body": "b", "parents": ["b"]},
        {"id": "b", "assignee": "y", "body": "c", "parents": ["a"]},
    ]}
    errors = validator.validate(wf)
    assert any("cycle" in e.lower() for e in errors)


def test_worktree_workspace_missing_fields(validator):
    wf = {**MINIMAL_VALID, "nodes": [
        {
            "id": "a", "assignee": "x", "body": "b",
            "workspace": {"type": "worktree", "repo": "/path"},  # missing branch + path
        }
    ]}
    errors = validator.validate(wf)
    assert any("branch" in e or "path" in e for e in errors)


def test_valid_dev_feature_yaml(validator):
    """The dev-feature-v1.yaml template itself must pass validation."""
    import os
    yaml_path = os.path.join(os.path.dirname(__file__), "..", "workflows", "dev-feature-v1.yaml")
    with open(yaml_path) as f:
        wf = yaml.safe_load(f)
    errors = validator.validate(wf)
    assert errors == [], f"dev-feature-v1.yaml validation errors: {errors}"
