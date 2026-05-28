"""Workflow schema validator for Hermes Workflow templates.

Validates parsed workflow YAML against the JSON Schema and checks structural
constraints such as unique node IDs, valid parent references, and DAG acyclicity.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "workflow.schema.json"


class WorkflowValidator:
    """Validates workflow YAML dicts against schema and structural rules."""

    def __init__(self, schema_path: str | None = None) -> None:
        path = Path(schema_path) if schema_path else SCHEMA_PATH
        with open(path) as f:
            self._schema = json.load(f)

    def validate(self, workflow: dict[str, Any]) -> list[str]:
        """Validate a parsed workflow dict.

        Args:
            workflow: Parsed workflow YAML dict (pre-rendering, may contain {vars}).

        Returns:
            List of error strings. Empty list means valid.
        """
        errors: list[str] = []
        errors.extend(self._validate_schema(workflow))
        if errors:
            # Stop early — structural checks need basic fields present
            return errors
        errors.extend(self._validate_node_ids_unique(workflow))
        errors.extend(self._validate_parents_exist(workflow))
        errors.extend(self._validate_no_cycles(workflow))
        errors.extend(self._validate_workspace_objects(workflow))
        errors.extend(self._validate_required_inputs(workflow))
        return errors

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_schema(self, workflow: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        try:
            jsonschema.validate(instance=workflow, schema=self._schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema error at {list(e.absolute_path)}: {e.message}")
        except jsonschema.SchemaError as e:
            errors.append(f"Internal schema error: {e.message}")
        return errors

    def _validate_node_ids_unique(self, workflow: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        seen: set[str] = set()
        for node in workflow.get("nodes", []):
            node_id = node.get("id", "")
            if node_id in seen:
                errors.append(f"Duplicate node id: '{node_id}'")
            seen.add(node_id)
        return errors

    def _validate_parents_exist(self, workflow: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        node_ids = {n.get("id") for n in workflow.get("nodes", [])}
        for node in workflow.get("nodes", []):
            for parent in node.get("parents", []) or []:
                if parent not in node_ids:
                    errors.append(
                        f"Node '{node.get('id')}' references unknown parent '{parent}'"
                    )
        return errors

    def _validate_no_cycles(self, workflow: dict[str, Any]) -> list[str]:
        """Kahn's algorithm topological sort to detect cycles."""
        errors: list[str] = []
        nodes = workflow.get("nodes", [])
        node_ids = [n["id"] for n in nodes if "id" in n]
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
        graph: dict[str, list[str]] = {nid: [] for nid in node_ids}
        for node in nodes:
            nid = node.get("id", "")
            for parent in node.get("parents", []) or []:
                if parent in graph:
                    graph[parent].append(nid)
                    in_degree[nid] = in_degree.get(nid, 0) + 1
        queue = [nid for nid in node_ids if in_degree.get(nid, 0) == 0]
        visited = 0
        while queue:
            current = queue.pop(0)
            visited += 1
            for child in graph.get(current, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)
        if visited < len(node_ids):
            errors.append("Workflow DAG contains a cycle — topological sort failed.")
        return errors

    def _validate_workspace_objects(self, workflow: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for node in workflow.get("nodes", []):
            ws = node.get("workspace")
            if ws is None:
                continue
            ws_type = ws.get("type")
            if ws_type == "worktree":
                for req in ("repo", "branch", "path"):
                    if not ws.get(req):
                        errors.append(
                            f"Node '{node.get('id')}' workspace type=worktree missing field '{req}'"
                        )
        return errors

    def _validate_required_inputs(self, workflow: dict[str, Any]) -> list[str]:
        """Verify that all inputs have a 'type' field and required inputs are marked."""
        errors: list[str] = []
        for name, spec in (workflow.get("inputs") or {}).items():
            if not isinstance(spec, dict):
                errors.append(f"Input '{name}' must be an object with a 'type' field")
                continue
            if "type" not in spec:
                errors.append(f"Input '{name}' is missing required field 'type'")
        return errors
