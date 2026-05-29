"""Tests for variable renderer."""

from __future__ import annotations

import pytest

from instantiator.renderer import VariableRenderer, UndefinedVariableError


@pytest.fixture
def renderer():
    return VariableRenderer()


def test_render_simple_string(renderer):
    result = renderer.render_string("hello {name}", {"name": "world"})
    assert result == "hello world"


def test_render_multiple_vars(renderer):
    result = renderer.render_string("{a}/{b}", {"a": "foo", "b": "bar"})
    assert result == "foo/bar"


def test_render_undefined_variable_raises(renderer):
    with pytest.raises(UndefinedVariableError):
        renderer.render_string("hello {missing}", {"name": "world"})


def test_render_node_substitutes_all_fields(renderer):
    node = {
        "id": "complex_impl",
        "title": "Implement #{issue}",
        "body": "Repo: {repo}\nIssue: {issue}",
        "workspace": {
            "type": "worktree",
            "repo": "{repo}",
            "branch": "ai/dev-feature/issue-{issue}/complex_impl",
            "path": ".hermes/worktrees/{workflow_run_id}/complex_impl",
        },
    }
    ctx = {"issue": "42", "repo": "/home/user/proj", "workflow_run_id": "wf_abc123"}
    rendered = renderer.render_node(node, ctx)
    assert rendered["title"] == "Implement #42"
    assert "/home/user/proj" in rendered["body"]
    assert rendered["workspace"]["branch"] == "ai/dev-feature/issue-42/complex_impl"
    assert "wf_abc123" in rendered["workspace"]["path"]


def test_render_node_does_not_mutate_original(renderer):
    node = {"id": "x", "body": "{msg}"}
    renderer.render_node(node, {"msg": "hi"})
    assert node["body"] == "{msg}"


def test_render_branch_sanitizes_unsafe_chars(renderer):
    node = {
        "id": "x",
        "body": "b",
        "workspace": {
            "type": "worktree",
            "repo": "/repo",
            "branch": "feat/{issue} [WIP]",
            "path": ".hermes/{workflow_run_id}",
        },
    }
    ctx = {"issue": "42", "workflow_run_id": "wf_abc"}
    rendered = renderer.render_node(node, ctx)
    branch = rendered["workspace"]["branch"]
    assert " " not in branch
    assert "[" not in branch
    assert "]" not in branch


def test_render_workflow_substitutes_runtime_inputs(renderer):
    workflow = {
        "id": "test-v1",
        "version": "1.0.0",
        "runtime": {"board": "{board}"},
        "nodes": [
            {"id": "n1", "body": "issue is {issue}"},
        ],
    }
    ctx = {"board": "myboard", "issue": "7"}
    rendered = renderer.render_workflow(workflow, ctx)
    assert rendered["runtime"]["board"] == "myboard"
    assert rendered["nodes"][0]["body"] == "issue is 7"


def test_render_workflow_raises_on_undefined(renderer):
    workflow = {"id": "x", "nodes": [{"id": "n", "body": "{missing_var}"}]}
    with pytest.raises(UndefinedVariableError):
        renderer.render_workflow(workflow, {})
