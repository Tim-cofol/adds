"""CLI Trigger Router for Hermes Workflow Orchestration.

Parses /wf commands and dispatches to the Instantiator.

Usage:
    python -m router.routes.cli dev-feature repo=/path/to/repo issue=42
    hermes wf dev-feature repo=/path/to/repo issue=42
"""
from __future__ import annotations

import argparse
import sys
from typing import Any


class CliParseError(Exception):
    """Raised when /wf CLI input cannot be parsed or required params are missing."""
    pass


def parse_wf_args(argv: list[str]) -> tuple[str, dict[str, str]]:
    """Parse /wf CLI arguments.

    Args:
        argv: Argument list starting with workflow_id, followed by key=value pairs.
              E.g. ['dev-feature', 'repo=/path/to/repo', 'issue=42']

    Returns:
        Tuple of (workflow_id, params_dict).

    Raises:
        CliParseError: If workflow_id is missing or a key=value pair is malformed.
    """
    if not argv:
        raise CliParseError("Usage: /wf <workflow_id> [key=value ...]")

    workflow_id = argv[0]
    if not workflow_id or workflow_id.startswith("="):
        raise CliParseError(f"Invalid workflow_id: {workflow_id!r}")

    params: dict[str, str] = {}
    for token in argv[1:]:
        if "=" not in token:
            raise CliParseError(
                f"Invalid parameter {token!r} — expected key=value format"
            )
        key, _, value = token.partition("=")
        if not key:
            raise CliParseError(f"Empty key in parameter {token!r}")
        params[key] = value

    return workflow_id, params


def validate_required_params(
    workflow_id: str,
    params: dict[str, str],
    required_params: list[str],
) -> list[str]:
    """Validate that all required parameters are present.

    Args:
        workflow_id: The workflow identifier.
        params: Dict of provided params.
        required_params: List of required parameter names.

    Returns:
        List of missing parameter names (empty if all present).
    """
    return [p for p in required_params if p not in params or not params[p]]


def build_trigger_payload(
    workflow_id: str,
    params: dict[str, str],
    source: str = "cli",
) -> dict[str, Any]:
    """Build a normalized trigger payload for the Instantiator.

    Args:
        workflow_id: Workflow identifier (e.g. 'dev-feature-v1').
        params: Dict of key=value inputs.
        source: Trigger source identifier.

    Returns:
        Trigger payload dict suitable for passing to the Instantiator.
    """
    return {
        "workflow_id": workflow_id,
        "source": source,
        "params": params,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Prints trigger payload as JSON and returns 0 on success."""
    import json

    argv = argv if argv is not None else sys.argv[1:]

    try:
        workflow_id, params = parse_wf_args(argv)
    except CliParseError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    payload = build_trigger_payload(workflow_id, params)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
