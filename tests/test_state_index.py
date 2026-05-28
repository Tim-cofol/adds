"""Tests for the workflow state index."""
import os
import tempfile
import pytest
from instantiator.state_index import StateIndex


def _tmp_index():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    return StateIndex(index_path=path)


def test_create_and_retrieve_run():
    idx = _tmp_index()
    record = idx.create_run("run-001", "t_abc123", node_to_task_id={"clarify": "t_11"})
    assert record["workflow_run_id"] == "run-001"
    assert record["root_task_id"] == "t_abc123"
    assert record["node_to_task_id"]["clarify"] == "t_11"
    assert record["instantiation_status"] == "creating"


def test_get_run_returns_record():
    idx = _tmp_index()
    idx.create_run("run-002", "t_xyz")
    record = idx.get_run("run-002")
    assert record is not None
    assert record["root_task_id"] == "t_xyz"


def test_get_run_returns_none_for_unknown():
    idx = _tmp_index()
    assert idx.get_run("nonexistent") is None


def test_duplicate_run_id_raises():
    idx = _tmp_index()
    idx.create_run("run-dup", "t_aaa")
    with pytest.raises(ValueError):
        idx.create_run("run-dup", "t_bbb")


def test_update_status():
    idx = _tmp_index()
    idx.create_run("run-upd", "t_zzz")
    idx.update_run("run-upd", instantiation_status="created")
    record = idx.get_run("run-upd")
    assert record["instantiation_status"] == "created"


def test_update_node_to_task_id_merges():
    idx = _tmp_index()
    idx.create_run("run-m", "t_r", node_to_task_id={"a": "t_1"})
    idx.update_run("run-m", node_to_task_id={"b": "t_2"})
    record = idx.get_run("run-m")
    assert record["node_to_task_id"] == {"a": "t_1", "b": "t_2"}


def test_update_unknown_run_raises():
    idx = _tmp_index()
    with pytest.raises(KeyError):
        idx.update_run("no-such-run", instantiation_status="created")


def test_list_runs_sorted_newest_first():
    import time
    idx = _tmp_index()
    idx.create_run("run-a", "t_1")
    time.sleep(1.1)
    idx.create_run("run-b", "t_2")
    runs = idx.list_runs()
    assert len(runs) == 2
    # Should be sorted by created_at descending (run-b is newer)
    assert runs[0]["workflow_run_id"] == "run-b"


def test_idempotency_key_stored_in_record():
    idx = _tmp_index()
    idx.create_run("run-ik", "t_ik", idempotency_key="wf:dev-feature-v1:repo:issue-42")
    record = idx.get_run("run-ik")
    assert record["idempotency_key"] == "wf:dev-feature-v1:repo:issue-42"
