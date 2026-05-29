"""Tests for the workflow schema validator."""
import pytest
from instantiator.validator import WorkflowValidator


VALID_WORKFLOW = {
    "id": "dev-feature-v1",
    "version": "1.0.0",
    "inputs": {
        "repo": {"type": "path", "required": True},
        "issue": {"type": "string", "required": True},
    },
    "entry": {"assignee": "orchestrator"},
    "nodes": [
        {"id": "clarify", "assignee": "orchestrator", "body": "Clarify issue.", "parents": []},
        {"id": "impl", "assignee": "dev-codex", "body": "Implement.", "parents": ["clarify"]},
    ],
}


def test_valid_workflow_has_no_errors():
    v = WorkflowValidator()
    errors = v.validate(VALID_WORKFLOW)
    assert errors == []


def test_missing_required_field_version():
    v = WorkflowValidator()
    wf = {**VALID_WORKFLOW}
    del wf["version"]  # type: ignore[misc]
    errors = v.validate(wf)
    assert any("version" in e for e in errors)


def test_duplicate_node_ids():
    v = WorkflowValidator()
    wf = {
        **VALID_WORKFLOW,
        "nodes": [
            {"id": "dup", "assignee": "a", "body": "x"},
            {"id": "dup", "assignee": "b", "body": "y"},
        ],
    }
    errors = v.validate(wf)
    assert any("dup" in e for e in errors)


def test_unknown_parent_reference():
    v = WorkflowValidator()
    wf = {
        **VALID_WORKFLOW,
        "nodes": [{"id": "n1", "assignee": "a", "body": "x", "parents": ["nonexistent"]}],
    }
    errors = v.validate(wf)
    assert any("nonexistent" in e for e in errors)


def test_cycle_detection():
    v = WorkflowValidator()
    wf = {
        **VALID_WORKFLOW,
        "nodes": [
            {"id": "a", "assignee": "x", "body": "x", "parents": ["b"]},
            {"id": "b", "assignee": "x", "body": "y", "parents": ["a"]},
        ],
    }
    errors = v.validate(wf)
    assert any("cycle" in e.lower() for e in errors)


def test_worktree_workspace_missing_branch():
    v = WorkflowValidator()
    wf = {
        **VALID_WORKFLOW,
        "nodes": [
            {
                "id": "n1",
                "assignee": "dev-codex",
                "body": "x",
                "workspace": {"type": "worktree", "repo": "/tmp/r", "path": "/tmp/p"},
            }
        ],
    }
    errors = v.validate(wf)
    assert any("branch" in e for e in errors)


def test_valid_workflow_with_worktree_workspace():
    v = WorkflowValidator()
    wf = {
        **VALID_WORKFLOW,
        "nodes": [
            {
                "id": "n1",
                "assignee": "dev-codex",
                "body": "x",
                "workspace": {"type": "worktree", "repo": "/tmp/r", "branch": "fix/n1", "path": "/tmp/p"},
            }
        ],
    }
    errors = v.validate(wf)
    assert errors == []


def test_idempotency_key_strategy_accepted():
    v = WorkflowValidator()
    wf = {
        **VALID_WORKFLOW,
        "runtime": {"board": "default", "idempotency": {"strategy": "source_workflow_version"}},
    }
    errors = v.validate(wf)
    assert errors == []
