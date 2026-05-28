"""Jinja2-based variable renderer for Hermes Workflow templates.

Renders workflow YAML content with runtime context variables, using strict
undefined-variable checking to catch missing substitutions early.
"""

import re
import copy
from typing import Any

import jinja2


class UndefinedVariableError(Exception):
    """Raised when a template references a variable not present in context."""
    pass


def _sanitize_branch_name(name: str) -> str:
    """Sanitize a git branch name: replace unsafe characters with hyphens."""
    # Replace characters not allowed in git branch names
    sanitized = re.sub(r"[^\w./-]", "-", name)
    # Collapse multiple hyphens
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    # Remove leading/trailing hyphens or dots
    sanitized = sanitized.strip("-.")
    return sanitized


class VariableRenderer:
    """Renders workflow templates using Jinja2 with strict undefined-variable checking.

    Uses {var} brace syntax (not {{ var }}) to match the workflow YAML convention.
    """

    def __init__(self) -> None:
        self._env = jinja2.Environment(
            variable_start_string="{",
            variable_end_string="}",
            undefined=jinja2.StrictUndefined,
            keep_trailing_newline=True,
        )

    def render_string(self, template: str, context: dict[str, Any]) -> str:
        """Render a single template string with context.

        Args:
            template: String with {variable} placeholders.
            context: Dict of variable name -> value.

        Returns:
            Rendered string.

        Raises:
            UndefinedVariableError: If any variable in template is not in context.
        """
        try:
            tmpl = self._env.from_string(template)
            result = tmpl.render(**context)
            if isinstance(result, str) and result.startswith("ai/") or "/" in result:
                # Check if this looks like a branch name — sanitize it
                pass
            return result
        except jinja2.UndefinedError as e:
            raise UndefinedVariableError(
                f"Undefined variable in template: {e}. "
                f"Template: {template!r}. "
                f"Available context keys: {sorted(context.keys())}"
            ) from e

    def render_node(self, node: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Render all string fields in a workflow node dict.

        Args:
            node: Workflow node dict (will not be modified in-place).
            context: Rendering context.

        Returns:
            New node dict with all string values rendered.
        """
        rendered = copy.deepcopy(node)
        rendered = self._render_recursive(rendered, context)
        # Post-process: sanitize branch names in workspace
        ws = rendered.get("workspace", {})
        if ws.get("type") == "worktree" and "branch" in ws:
            ws["branch"] = _sanitize_branch_name(ws["branch"])
        return rendered

    def render_workflow(self, workflow: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Render all variable references in a full workflow dict.

        Args:
            workflow: Parsed workflow YAML dict.
            context: Runtime context with all required variables.

        Returns:
            New workflow dict with all variables substituted.
        """
        rendered = copy.deepcopy(workflow)
        rendered = self._render_recursive(rendered, context)
        # Sanitize all worktree branch names
        for node in rendered.get("nodes", []):
            ws = node.get("workspace", {})
            if ws.get("type") == "worktree" and "branch" in ws:
                ws["branch"] = _sanitize_branch_name(ws["branch"])
        return rendered

    def _render_recursive(self, obj: Any, context: dict[str, Any]) -> Any:
        """Recursively render all string values in a nested dict/list structure."""
        if isinstance(obj, str):
            return self.render_string(obj, context)
        elif isinstance(obj, dict):
            return {k: self._render_recursive(v, context) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._render_recursive(item, context) for item in obj]
        else:
            return obj
