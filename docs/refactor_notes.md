# Refactor Notes

This file records safe constraints for future architecture work. It is intentionally conservative.

## Current Scope

The current blueprint optimization is documentation-only:

- No Python behavior changes.
- No CLI command changes.
- No output schema changes.
- No module moves.
- No import rewrites.
- No runtime data cleanup.

## Invariants

Any future refactor must preserve:

- Existing CLI command names and arguments.
- Existing JSON artifact field names unless a migration is explicitly planned.
- Existing Markdown artifact generation paths unless a compatibility layer exists.
- Current safety gates for generation, Meegle publishing, workflow transitions, PSD export, and delivery staging.
- Current K1/K2/K3/K4 semantics.
- Current ability to run local workflows without live Meegle/Lark access.
- Current tests or stronger equivalent coverage.

## Preferred Migration Strategy

If the flat `agent/core/` layout is reorganized later:

1. Create new domain subpackages.
2. Move implementation files mechanically.
3. Leave old files as compatibility wrappers.
4. Update internal imports gradually.
5. Run tests after every small move.
6. Only remove wrappers in a major cleanup after all external references are updated.

Compatibility wrapper example:

```python
# agent/core/style_alignment.py
from agent.core.style.alignment import *
```

## Proposed Future Package Layout

```text
agent/core/
  requirement/
  style/
  creative/
  generation/
  psd/
  delivery/
  collaboration/
  session/
  evolution/
```

## High-Risk Files

| File | Risk | Suggested approach |
|---|---|---|
| `agent/app.py` | Central orchestration hub with many artifact writes and session updates. | Extract small use-case helpers only after artifact map coverage is clear. |
| `agent/cli.py` | User-facing command surface. | Split parser construction only if command compatibility tests are expanded. |
| `agent/models.py` | Persisted schema contract. | Avoid field changes unless migration and backward compatibility are planned. |
| `agent/memory/store.py` | Persistence paths and latest-artifact conventions. | Add tests before changing naming or save/load behavior. |

## Candidate Helper Extractions

These are future options, not current changes:

- `ArtifactWriter`: central JSON/Markdown write helper.
- `RunContext`: resolved project/work item/output directory context.
- `ArtifactIndex`: canonical artifact lookup across latest snapshot and output directory.
- `UseCase` modules: small orchestration classes for requirement, generation, PSD, delivery, and collaboration flows.
- `EvolutionPolicy`: central self-learning promotion and safety policy.

## Documentation Maintenance

When adding new modules or artifacts, update:

- `docs/module_map.md`
- `docs/workflow_map.md`
- `docs/artifact_map.md`
- `docs/evolution_blueprint.md` if learning behavior is involved
- `README.md` if the public command surface changes
