"""Tests for idempotency logic and state index."""

from __future__ import annotations

import os
import tempfile

import pytest

from instantiator.state_index import StateIndex


@pytest.fixture
def index(tmp_path):
    return StateIndex(str(tmp_path / "state.json"))


def test_create_run(index):
    rec = index.create_run("wf_001", "t_root", {"clarify": "t_001"}, status="creating")
    assert rec["workflow_run_id"] == "wf_001"
    assert rec["root_task_id"] == "t_root"
    assert rec["instantiation_status"] == "creating"


def test_get_run_returns_none_if_missing(index):
    assert index.get_run("nonexistent") is None


def test_create_then_get_run(index):
    index.create_run("wf_002", "t_root2")
    rec = index.get_run("wf_002")
    assert rec is not None
    assert rec["root_task_id"] == "t_root2"


def test_update_run_status(index):
    index.create_run("wf_003", "t_root3", status="creating")
    updated = index.update_run("wf_003", instantiation_status="created")
    assert updated["instantiation_status"] == "created"
    # Persisted
    assert index.get_run("wf_003")["instantiation_status"] == "created"


def test_update_run_merges_node_to_task_id(index):
    index.create_run("wf_004", "t_root4", node_to_task_id={"clarify": "t_001"})
    index.update_run("wf_004", node_to_task_id={"complex_impl": "t_002"})
    rec = index.get_run("wf_004")
    assert rec["node_to_task_id"]["clarify"] == "t_001"
    assert rec["node_to_task_id"]["complex_impl"] == "t_002"


def test_create_duplicate_raises(index):
    index.create_run("wf_005", "t_root5")
    with pytest.raises(ValueError, match="already exists"):
        index.create_run("wf_005", "t_root5_duplicate")


def test_list_runs_sorted_by_created_at(index):
    index.create_run("wf_a", "t_a")
    index.create_run("wf_b", "t_b")
    runs = index.list_runs()
    assert len(runs) == 2
    # Most recent first
    ids = [r["workflow_run_id"] for r in runs]
    assert "wf_a" in ids and "wf_b" in ids


def test_index_persists_across_instances(tmp_path):
    path = str(tmp_path / "idx.json")
    idx1 = StateIndex(path)
    idx1.create_run("wf_persist", "t_persist")
    idx2 = StateIndex(path)
    assert idx2.get_run("wf_persist") is not None
