"""Hermes Workflow DAG Instantiator.

Compiles a versioned YAML workflow template into a Hermes Kanban DAG by:
1. Loading and validating the workflow YAML.
2. Rendering variables with the runtime context.
3. Discovering and resolving Hermes profiles.
4. Creating Kanban tasks in topological order with correct parent links.
5. Writing the workflow_run mapping to the state index.
6. Completing the root task with the node_to_task_id mapping.

Transaction model:
  creating     -> in progress, DAG being built
  created      -> DAG fully built, root task complete
  failed_partial -> some kanban_create calls failed; safe to resume
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

from .hermes_client import HermesClient, MissingRequiredProfileError
from .renderer import VariableRenderer
from .state_index import StateIndex
from .validator import WorkflowValidator


WORKFLOWS_DIR = Path(__file__).parent.parent / "workflows"


class KanbanCreateError(Exception):
    """Raised when a kanban task cannot be created."""
    pass


class KanbanClient:
    """Thin wrapper around the Hermes Kanban CLI for task creation."""

    def __init__(self, kanban_db: str | None = None) -> None:
        pass  # board selection via HERMES_KANBAN_BOARD env var; --db flag does not exist

    def create_task(
        self,
        title: str,
        assignee: str,
        body: str,
        skills: list[str] | None = None,
        parents: list[str] | None = None,
        idempotency_key: str | None = None,
        metadata_json: str | None = None,
        initial_status: str | None = None,
    ) -> str:
        """Create a Kanban task and return its task_id.

        Args:
            title: Task title.
            assignee: Profile name.
            body: Task body / description.
            skills: List of skill names to attach.
            parents: List of parent task IDs.
            idempotency_key: Idempotency key for deduplication.
            metadata_json: JSON string of initial metadata.
            initial_status: Override initial status (e.g. 'blocked').

        Returns:
            Task ID string (e.g. 't_abc12345').

        Raises:
            KanbanCreateError: If task creation fails.
        """
        cmd = ["hermes", "kanban", "create", title, "--assignee", assignee, "--json"]

        if skills:
            for s in skills:
                cmd.extend(["--skill", s])
        if parents:
            for p in parents:
                cmd.extend(["--parent", p])
        if idempotency_key:
            cmd.extend(["--idempotency-key", idempotency_key])
        if initial_status:
            cmd.extend(["--initial-status", initial_status])

        try:
            result = subprocess.run(
                cmd,
                input=body,
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "HERMES_KANBAN_TASK_BODY_STDIN": "1"},
            )
        except subprocess.TimeoutExpired as e:
            raise KanbanCreateError(f"kanban create timed out: {e}") from e
        except FileNotFoundError as e:
            raise KanbanCreateError(
                f"hermes CLI not found. Is Hermes installed? {e}"
            ) from e

        if result.returncode != 0:
            raise KanbanCreateError(
                f"hermes kanban create failed (rc={result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

        try:
            data = json.loads(result.stdout)
            task_id = data.get("id")
            if not task_id:
                raise KanbanCreateError(
                    f"No task_id in hermes kanban create output: {result.stdout[:200]}"
                )
            return task_id
        except json.JSONDecodeError as e:
            raise KanbanCreateError(
                f"Could not parse hermes kanban create output as JSON: "
                f"{result.stdout[:200]}"
            ) from e

    def complete_task(
        self,
        task_id: str,
        summary: str,
        metadata: dict[str, Any],
    ) -> None:
        """Complete a Kanban task with summary and metadata."""
        cmd = [
            "hermes", "kanban", "complete", task_id,
            "--summary", summary,
            "--metadata", json.dumps(metadata),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                # Non-fatal: log but don't raise
                print(
                    f"[WARN] kanban complete {task_id} failed: "
                    f"{result.stderr.strip()}"
                )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(f"[WARN] kanban complete {task_id} timed out or CLI not found")


def _topological_order(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return nodes in topological order (parents before children)."""
    node_map = {n["id"]: n for n in nodes}
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    children: dict[str, list[str]] = {n["id"]: [] for n in nodes}

    for node in nodes:
        for parent in node.get("parents", []) or []:
            if parent in children:
                children[parent].append(node["id"])
                in_degree[node["id"]] += 1

    queue = [nid for nid in in_degree if in_degree[nid] == 0]
    ordered: list[dict[str, Any]] = []
    while queue:
        nid = queue.pop(0)
        ordered.append(node_map[nid])
        for child in children[nid]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
    return ordered


class WorkflowInstantiator:
    """Compiles workflow YAML into a Hermes Kanban DAG."""

    def __init__(
        self,
        workflows_dir: str | Path | None = None,
        kanban_db: str | None = None,
        state_index_path: str | None = None,
    ) -> None:
        self._workflows_dir = Path(workflows_dir or WORKFLOWS_DIR)
        self._kanban = KanbanClient(kanban_db=kanban_db)
        self._renderer = VariableRenderer()
        self._validator = WorkflowValidator()
        self._hermes = HermesClient()
        self._state = StateIndex(state_index_path)

    def instantiate(
        self,
        workflow_id: str,
        inputs: dict[str, Any],
        workflow_run_id: str | None = None,
        source: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Instantiate a workflow as a Hermes Kanban DAG.

        Args:
            workflow_id: ID matching a file in workflows/<id>.yaml.
            inputs: Runtime input values (repo, issue, base_branch, etc.).
            workflow_run_id: Optional; generated if not provided.
            source: Optional provenance metadata (type, repo, issue, etc.).

        Returns:
            {
              "workflow_run_id": str,
              "root_task_id": str,
              "node_to_task_id": {node_id: task_id, ...},
              "instantiation_status": "created",
            }

        Raises:
            FileNotFoundError: Workflow YAML not found.
            ValueError: Validation errors in the workflow YAML.
            MissingRequiredProfileError: Required profiles absent.
            KanbanCreateError: Task creation failed.
        """
        # 1. Load workflow YAML
        workflow_path = self._workflows_dir / f"{workflow_id}.yaml"
        if not workflow_path.exists():
            raise FileNotFoundError(
                f"Workflow '{workflow_id}' not found at {workflow_path}"
            )
        with open(workflow_path) as f:
            raw_workflow = yaml.safe_load(f)

        # 2. Validate raw workflow (before variable rendering)
        errors = self._validator.validate(raw_workflow)
        if errors:
            raise ValueError(
                f"Workflow '{workflow_id}' failed validation:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        # 3. Apply input defaults and build rendering context
        context = self._build_context(raw_workflow, inputs, workflow_run_id)
        actual_run_id: str = context["workflow_run_id"]

        # 4. Idempotency check
        existing = self._state.get_run(actual_run_id)
        if existing:
            status = existing.get("instantiation_status")
            if status == "created":
                return existing
            # If creating/failed_partial: continue below (resume)

        # 5. Render variables
        rendered = self._renderer.render_workflow(raw_workflow, context)

        # 6. Discover profiles and resolve assignees
        available = self._hermes.list_profiles()
        resolution = self._hermes.resolve_assignees(rendered, available)

        # 7. Build root idempotency key
        src = source or {}
        root_idempotency_key = self._root_idempotency_key(
            src, workflow_id, raw_workflow.get("version", "")
        )

        # 8. Create root task
        root_title = f"[WF] {workflow_id}: run {actual_run_id[:8]}"
        if src.get("issue"):
            root_title = f"[WF] {workflow_id}: issue #{src['issue']}"

        entry = rendered.get("entry", {})
        root_body = (
            f"workflow_id: {workflow_id}\n"
            f"workflow_version: {raw_workflow.get('version', '')}\n"
            f"workflow_run_id: {actual_run_id}\n"
            + "inputs:\n"
            + "".join(f"  {k}: {v}\n" for k, v in inputs.items())
        )
        root_task_id = self._kanban.create_task(
            title=root_title,
            assignee=entry.get("assignee", "orchestrator"),
            body=root_body,
            skills=entry.get("skills"),
            idempotency_key=root_idempotency_key,
            initial_status="running",
        )

        # 9. Save creating state
        if not existing:
            self._state.create_run(
                workflow_run_id=actual_run_id,
                root_task_id=root_task_id,
                status="creating",
                workflow_id=workflow_id,
                inputs=inputs,
            )
        else:
            self._state.update_run(actual_run_id, instantiation_status="creating")

        # 10. Create DAG nodes in topological order
        nodes = rendered.get("nodes", [])
        ordered_nodes = _topological_order(nodes)
        node_to_task_id: dict[str, str] = {}
        existing_map = (existing or {}).get("node_to_task_id", {})
        node_to_task_id.update(existing_map)

        for node in ordered_nodes:
            node_id = node["id"]
            if node_id in node_to_task_id:
                # Already created (resume scenario)
                continue

            node_idempotency_key = (
                f"{root_idempotency_key}:node:{node_id}"
            )
            node_res = resolution.get(node_id, {})
            resolved_assignee = node_res.get("resolved_assignee", node.get("assignee", ""))

            # Parent task IDs: parentless nodes depend on root_task
            node_parents_ids: list[str] = []
            declared_parents = node.get("parents") or []
            if declared_parents:
                for p in declared_parents:
                    if p in node_to_task_id:
                        node_parents_ids.append(node_to_task_id[p])
            else:
                node_parents_ids = [root_task_id]

            # Determine initial status for manual_gate nodes
            node_initial_status = None
            if node.get("mode") == "manual_gate":
                node_initial_status = "blocked"

            # Build task body including workspace and output_contract
            body = self._build_node_body(node, context, node_res)

            task_id = self._kanban.create_task(
                title=node.get("title", f"{workflow_id}: {node_id}"),
                assignee=resolved_assignee,
                body=body,
                skills=node.get("skills"),
                parents=node_parents_ids,
                idempotency_key=node_idempotency_key,
                initial_status=node_initial_status,
            )
            node_to_task_id[node_id] = task_id
            self._state.update_run(
                actual_run_id,
                node_to_task_id={node_id: task_id},
            )

        # 11. Mark created
        self._state.update_run(actual_run_id, instantiation_status="created")

        # 12. Complete root task with node mapping
        self._kanban.complete_task(
            root_task_id,
            summary=(
                f"Workflow '{workflow_id}' run {actual_run_id[:8]} instantiated. "
                f"{len(node_to_task_id)} DAG nodes created."
            ),
            metadata={
                "workflow_run_id": actual_run_id,
                "workflow_id": workflow_id,
                "instantiation_status": "created",
                "node_to_task_id": node_to_task_id,
            },
        )

        return {
            "workflow_run_id": actual_run_id,
            "root_task_id": root_task_id,
            "node_to_task_id": node_to_task_id,
            "instantiation_status": "created",
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_context(
        self,
        workflow: dict[str, Any],
        inputs: dict[str, Any],
        workflow_run_id: str | None,
    ) -> dict[str, Any]:
        """Build the Jinja2 rendering context from workflow inputs + defaults + runtime vars."""
        context: dict[str, Any] = {}

        # Apply defaults from workflow input spec
        for name, spec in (workflow.get("inputs") or {}).items():
            if isinstance(spec, dict) and "default" in spec:
                context[name] = spec["default"]

        # Override with caller-supplied inputs
        context.update(inputs)

        # Runtime variables injected by instantiator
        run_id = workflow_run_id or f"wf_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        context["workflow_run_id"] = run_id
        context["workflow_id"] = workflow.get("id", "")
        context["workflow_version"] = workflow.get("version", "")

        return context

    def _root_idempotency_key(
        self,
        source: dict[str, Any],
        workflow_id: str,
        version: str,
    ) -> str:
        src_type = source.get("type", "manual")
        src_repo = source.get("repo", "")
        src_issue = source.get("issue", "")
        return (
            f"{src_type}:{src_repo}:{src_issue}:"
            f"workflow:{workflow_id}:version:{version}"
        )

    def _build_node_body(
        self,
        node: dict[str, Any],
        context: dict[str, Any],
        resolution: dict[str, str],
    ) -> str:
        """Build the full task body for a workflow node."""
        parts: list[str] = []
        parts.append(node.get("body", ""))

        # Append workspace info
        ws = node.get("workspace")
        if ws:
            parts.append("\n---\nworkspace: " + json.dumps(ws, indent=2))

        # Append output_contract
        oc = node.get("output_contract")
        if oc:
            parts.append("\noutput_contract: " + json.dumps(oc, indent=2))

        # Append resolution metadata
        if resolution.get("assignee_resolution") == "fallback":
            parts.append(
                f"\n---\nworkflow_assignee: {resolution.get('workflow_assignee')}\n"
                f"resolved_assignee: {resolution.get('resolved_assignee')}\n"
                f"assignee_resolution: fallback"
            )

        # Append workflow context keys needed by workers
        wf_ctx = {
            "workflow_run_id": context.get("workflow_run_id", ""),
            "workflow_id": context.get("workflow_id", ""),
            "workflow_assignee": resolution.get("workflow_assignee", node.get("assignee", "")),
            "resolved_assignee": resolution.get("resolved_assignee", node.get("assignee", "")),
        }
        if node.get("task_size_limit"):
            wf_ctx["task_size_limit"] = node["task_size_limit"]

        parts.append("\n---\n" + "\n".join(f"{k}: {v}" for k, v in wf_ctx.items()))

        return "\n".join(parts)
