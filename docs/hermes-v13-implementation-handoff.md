# Hermes v1.3 Implementation Handoff

This handoff exists because the context window may be close to full. Treat this file and `hermes_workflow_kanban_design_instruction.md` as the durable source for the next agent.

## Current Decision Set

- Workflow id: `dev-feature-v3`.
- Required profiles: `orchestrator`, `architect`, `dev-codex`, `reviewer`, `shipper`.
- Development is serial: `kanban.max_in_progress_per_profile` must be `1`.
- Default human intervention happens only during clarify, unless protected paths, repeated automated failures, or external permissions require escalation.
- `architect` creates `architecture_plan.md` and `development_plan.json`; each development task should be about 1000 changed lines or less.
- `dev-codex` implements one plan item at a time and does not commit until `automated_check` passes.

## Artifact Map

- `workflows/dev-feature-v3.yaml`: source workflow template.
- `skill-bundles/*.yaml`: profile skill bundles for Hermes.
- `profiles/*/profile.yaml`: local Hermes profile descriptions.
- `skills/workflow-orchestrator/SKILL.md`: orchestration rules and dynamic serial expansion behavior.
- `scripts/expand_hermes_dev_graph.py`: deterministic expander for `development_plan.json` into serial `dev/check/commit` Kanban tasks.
- `scripts/install_hermes_v13_artifacts.py`: copies artifacts into `~/.hermes` and sets the serial worker cap.
- `scripts/validate_hermes_v13_artifacts.py`: validates repo and installed artifacts.

## Verification Commands

```bash
python3 -m pytest -s tests/test_hermes_v13_artifacts.py -q
python3 -m pytest -s tests/test_expand_hermes_dev_graph.py -q
python3 scripts/validate_hermes_v13_artifacts.py
python3 scripts/validate_hermes_v13_artifacts.py --installed
```
