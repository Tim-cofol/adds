"""CLI trigger router for Hermes Workflow Orchestration System.

Usage:
    python3 -m router.routes.cli dev-feature-v1 repo=/path/to/repo issue=123
    python3 -m router.routes.cli dev-feature-v1 repo=/path/to/repo issue=123 base_branch=develop

The command parses workflow_id (first positional arg) and key=value input pairs,
validates required inputs against the workflow definition, then calls the
WorkflowInstantiator to create the Kanban DAG.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

# Allow running as both module and script
_HERE = Path(__file__).parent.parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from instantiator.instantiate import WorkflowInstantiator

WORKFLOWS_DIR = _HERE / "workflows"


class CLIValidationError(Exception):
    pass


def parse_args(args: list[str]) -> tuple[str, dict[str, Any]]:
    """Parse CLI args into (workflow_id, inputs_dict).

    Args:
        args: e.g. ['dev-feature-v1', 'repo=/path', 'issue=123']

    Returns:
        (workflow_id, inputs)

    Raises:
        CLIValidationError: Missing workflow_id or malformed key=value pair.
    """
    if not args:
        raise CLIValidationError(
            "Usage: cli.py <workflow_id> [key=value ...]"
        )
    workflow_id = args[0]
    inputs: dict[str, Any] = {}
    for arg in args[1:]:
        if "=" not in arg:
            raise CLIValidationError(
                f"Invalid argument '{arg}': expected key=value format."
            )
        key, _, value = arg.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            raise CLIValidationError(f"Empty key in argument '{arg}'.")
        inputs[key] = value
    return workflow_id, inputs


def validate_inputs(
    workflow_id: str,
    inputs: dict[str, Any],
    workflows_dir: Path = WORKFLOWS_DIR,
) -> list[str]:
    """Validate that all required workflow inputs are present.

    Args:
        workflow_id: The workflow to load.
        inputs: Caller-supplied inputs.
        workflows_dir: Directory to search for workflow YAML files.

    Returns:
        List of error strings. Empty = valid.
    """
    errors: list[str] = []
    workflow_path = workflows_dir / f"{workflow_id}.yaml"
    if not workflow_path.exists():
        errors.append(f"Workflow '{workflow_id}' not found at {workflow_path}")
        return errors

    with open(workflow_path) as f:
        workflow = yaml.safe_load(f)

    for name, spec in (workflow.get("inputs") or {}).items():
        if not isinstance(spec, dict):
            continue
        required = spec.get("required", True)
        has_default = "default" in spec
        if required and not has_default and name not in inputs:
            errors.append(f"Required input '{name}' is missing.")

    return errors


def handle_wf_command(
    args: list[str],
    kanban_db: str | None = None,
    state_index_path: str | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Handle a /wf CLI command.

    Args:
        args: CLI args e.g. ['dev-feature-v1', 'repo=/path', 'issue=123'].
        kanban_db: Optional path to Hermes Kanban SQLite DB.
        state_index_path: Optional path to workflow state index JSON.
        source: Optional provenance dict (type, repo, issue).

    Returns:
        {
          'workflow_run_id': str,
          'root_task_id': str,
          'node_to_task_id': dict,
          'status': 'created',
        }

    Raises:
        CLIValidationError: Invalid arguments or missing required inputs.
        FileNotFoundError: Workflow YAML not found.
        Exception: Propagated from WorkflowInstantiator.
    """
    workflow_id, inputs = parse_args(args)

    errors = validate_inputs(workflow_id, inputs)
    if errors:
        raise CLIValidationError(
            f"Input validation failed for workflow '{workflow_id}':\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    instantiator = WorkflowInstantiator(
        kanban_db=kanban_db,
        state_index_path=state_index_path,
    )
    result = instantiator.instantiate(
        workflow_id=workflow_id,
        inputs=inputs,
        source=source or {"type": "cli"},
    )
    return {**result, "status": result.get("instantiation_status", "created")}


def main() -> None:
    """Entry point for CLI usage."""
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python3 -m router.routes.cli <workflow_id> [key=value ...]")
        print("")
        print("Examples:")
        print("  python3 -m router.routes.cli dev-feature-v1 repo=/path/to/repo issue=123")
        print("  python3 -m router.routes.cli dev-feature-v1 repo=/path issue=42 base_branch=develop")
        sys.exit(0)

    try:
        result = handle_wf_command(args)
        print(json.dumps(result, indent=2))
    except CLIValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Fatal: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
