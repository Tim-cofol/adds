"""Hermes profile registry resolver for workflow instantiation.

Resolves logical workflow assignees (e.g. 'dev-codex') to actual Hermes
profile names present on the local system. Applies fallback logic and blocks
on missing required profiles.
"""

from __future__ import annotations

import subprocess
from typing import Any


class MissingRequiredProfileError(Exception):
    """Raised when a required profile is absent and has no valid fallback."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(
            f"Required profiles not found and no fallback available: {missing}. "
            "Please create these Hermes profiles or update the workflow registry."
        )


# Default profile registry: maps logical role -> required flag, fallback, capabilities
DEFAULT_PROFILE_REGISTRY: dict[str, dict[str, Any]] = {
    "orchestrator": {
        "hermes_profile": "orchestrator",
        "required": True,
        "fallback": None,
        "capabilities": ["workflow_orchestration", "kanban_routing"],
    },
    "dev-claude": {
        "hermes_profile": "dev-claude",
        "required": True,
        "fallback": None,
        "capabilities": ["complex_implementation", "integration", "tdd"],
    },
    "dev-codex": {
        "hermes_profile": "dev-codex",
        "required": False,
        "fallback": "dev-claude",
        "capabilities": ["simple_implementation", "batch_fix"],
    },
    "reviewer": {
        "hermes_profile": "reviewer",
        "required": True,
        "fallback": None,
        "capabilities": ["code_review", "risk_assessment"],
    },
    "shipper": {
        "hermes_profile": "shipper",
        "required": True,
        "fallback": None,
        "capabilities": ["github_pr", "ci_check", "release_recommendation"],
    },
}


class HermesClient:
    """Client for querying local Hermes installation state."""

    def list_profiles(self) -> list[str]:
        """Return list of available Hermes profile names.

        Calls 'hermes profile list' and parses the output.
        Falls back to an empty list if hermes CLI is unavailable.
        """
        try:
            result = subprocess.run(
                ["hermes", "profile", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return []
            profiles: list[str] = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # Output may be "name  (active)" or just "name"
                    name = line.split()[0].rstrip("*")
                    if name:
                        profiles.append(name)
            return profiles
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return []

    def resolve_assignees(
        self,
        workflow: dict[str, Any],
        available_profiles: list[str],
        registry: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, str]]:
        """Resolve workflow assignees to actual Hermes profiles.

        Args:
            workflow: Parsed workflow dict with nodes.
            available_profiles: Profiles from list_profiles().
            registry: Profile registry dict (defaults to DEFAULT_PROFILE_REGISTRY).

        Returns:
            Dict mapping node_id -> {
                "workflow_assignee": logical name,
                "resolved_assignee": actual profile name,
                "assignee_resolution": "direct" | "fallback",
            }

        Raises:
            MissingRequiredProfileError: If any required profile is absent.
        """
        if registry is None:
            registry = DEFAULT_PROFILE_REGISTRY

        available_set = set(available_profiles)
        resolution: dict[str, dict[str, str]] = {}
        missing_required: list[str] = []

        all_assignees: set[str] = set()
        for node in workflow.get("nodes", []):
            all_assignees.add(node.get("assignee", ""))

        # Pre-check: all assignees must be resolvable
        for assignee in all_assignees:
            if not assignee:
                continue
            spec = registry.get(assignee, {})
            hermes_profile = spec.get("hermes_profile", assignee)
            required = spec.get("required", True)
            fallback = spec.get("fallback")

            if hermes_profile in available_set:
                continue  # Direct match
            if fallback and fallback in available_set:
                continue  # Fallback available
            if required:
                missing_required.append(assignee)

        if missing_required:
            raise MissingRequiredProfileError(missing_required)

        # Build per-node resolution map
        for node in workflow.get("nodes", []):
            node_id = node.get("id", "")
            assignee = node.get("assignee", "")
            spec = registry.get(assignee, {})
            hermes_profile = spec.get("hermes_profile", assignee)
            fallback = spec.get("fallback")

            if hermes_profile in available_set:
                resolution[node_id] = {
                    "workflow_assignee": assignee,
                    "resolved_assignee": hermes_profile,
                    "assignee_resolution": "direct",
                }
            elif fallback and fallback in available_set:
                resolution[node_id] = {
                    "workflow_assignee": assignee,
                    "resolved_assignee": fallback,
                    "assignee_resolution": "fallback",
                }
            else:
                # Should not happen after pre-check, but be safe
                resolution[node_id] = {
                    "workflow_assignee": assignee,
                    "resolved_assignee": assignee,
                    "assignee_resolution": "unresolved",
                }

        return resolution
