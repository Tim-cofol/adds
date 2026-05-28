"""Lightweight JSON-backed state index for workflow runs.

Tracks instantiation transaction state (creating / created / failed_partial)
and maps workflow_run_id -> root_task_id -> node_to_task_id.

This is NOT a workflow runtime status store. Runtime status must be derived
from Hermes Kanban task statuses.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


DEFAULT_INDEX_PATH = os.path.expanduser("~/.hermes/workflow_state_index.json")


class StateIndex:
    """Persistent JSON-backed index of workflow run state."""

    def __init__(self, index_path: str | None = None) -> None:
        self._path = Path(index_path or DEFAULT_INDEX_PATH)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_run(
        self,
        workflow_run_id: str,
        root_task_id: str,
        node_to_task_id: dict[str, str] | None = None,
        status: str = "creating",
        **extra: Any,
    ) -> dict[str, Any]:
        """Create a new workflow run record.

        Args:
            workflow_run_id: Unique run identifier.
            root_task_id: Kanban task ID of the root task.
            node_to_task_id: Mapping of node_id -> kanban task_id (may be partial).
            status: 'creating' | 'created' | 'failed_partial'.
            **extra: Additional fields to store (e.g. workflow_id, inputs).

        Returns:
            The new run record.
        """
        index = self._load()
        if workflow_run_id in index:
            raise ValueError(f"Run '{workflow_run_id}' already exists. Use update_run.")
        record: dict[str, Any] = {
            "workflow_run_id": workflow_run_id,
            "root_task_id": root_task_id,
            "node_to_task_id": node_to_task_id or {},
            "instantiation_status": status,
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            **extra,
        }
        index[workflow_run_id] = record
        self._save(index)
        return record

    def update_run(self, workflow_run_id: str, **kwargs: Any) -> dict[str, Any]:
        """Update fields on an existing run record.

        Args:
            workflow_run_id: Run to update.
            **kwargs: Fields to update (e.g. status='created', node_to_task_id={...}).

        Returns:
            Updated run record.

        Raises:
            KeyError: If the run does not exist.
        """
        index = self._load()
        if workflow_run_id not in index:
            raise KeyError(f"Run '{workflow_run_id}' not found in state index.")
        record = index[workflow_run_id]
        for k, v in kwargs.items():
            if k == "instantiation_status":
                record["instantiation_status"] = v
            elif k == "node_to_task_id" and isinstance(v, dict):
                record["node_to_task_id"].update(v)
            else:
                record[k] = v
        record["updated_at"] = int(time.time())
        self._save(index)
        return record

    def get_run(self, workflow_run_id: str) -> dict[str, Any] | None:
        """Fetch a run record by ID. Returns None if not found."""
        index = self._load()
        return index.get(workflow_run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        """Return all run records sorted by created_at descending."""
        index = self._load()
        return sorted(index.values(), key=lambda r: r.get("created_at", 0), reverse=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            with open(self._path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, index: dict[str, Any]) -> None:
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(index, f, indent=2)
        tmp.replace(self._path)
