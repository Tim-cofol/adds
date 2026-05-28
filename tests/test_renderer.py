"""Tests for the variable renderer."""
import pytest
from instantiator.renderer import VariableRenderer, UndefinedVariableError


def test_renders_simple_string():
    renderer = VariableRenderer()
    result = renderer.render_string("hello {name}", {"name": "world"})
    assert result == "hello world"


def test_raises_on_undefined_variable():
    renderer = VariableRenderer()
    with pytest.raises(UndefinedVariableError):
        renderer.render_string("hello {missing}", {})


def test_renders_node_strings_recursively():
    renderer = VariableRenderer()
    node = {
        "id": "simple_impl",
        "title": "Fix issue #{issue}",
        "body": "Handle issue {issue} in {repo}",
        "workspace": {"type": "worktree", "repo": "{repo}", "branch": "ai/{issue}/fix", "path": "/tmp/{issue}"},
    }
    ctx = {"issue": "42", "repo": "/home/user/myrepo"}
    rendered = renderer.render_node(node, ctx)
    assert rendered["title"] == "Fix issue #42"
    assert rendered["body"] == "Handle issue 42 in /home/user/myrepo"
    assert rendered["workspace"]["repo"] == "/home/user/myrepo"


def test_sanitizes_worktree_branch_name():
    renderer = VariableRenderer()
    node = {
        "id": "x",
        "workspace": {"type": "worktree", "branch": "ai/{prefix}/issue-{issue}/simple", "path": "/tmp/x"},
    }
    ctx = {"prefix": "dev feature", "issue": "1"}
    rendered = renderer.render_node(node, ctx)
    # spaces/special chars should be replaced by hyphens
    assert " " not in rendered["workspace"]["branch"]


def test_renders_full_workflow():
    renderer = VariableRenderer()
    workflow = {
        "id": "test-wf",
        "version": "1.0.0",
        "inputs": {},
        "entry": {"assignee": "orchestrator"},
        "runtime": {"board": "{board}"},
        "nodes": [
            {"id": "n1", "assignee": "dev-codex", "body": "Do {task} in {repo}"},
        ],
    }
    ctx = {"board": "myboard", "task": "cleanup", "repo": "/projects/x"}
    rendered = renderer.render_workflow(workflow, ctx)
    assert rendered["runtime"]["board"] == "myboard"
    assert rendered["nodes"][0]["body"] == "Do cleanup in /projects/x"


def test_render_node_does_not_mutate_original():
    renderer = VariableRenderer()
    node = {"id": "x", "body": "{msg}"}
    renderer.render_node(node, {"msg": "hi"})
    assert node["body"] == "{msg}"
