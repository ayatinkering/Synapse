# Working on Synapse

Synapse is an evidence-grounded research assistant. Use `docs/PRD.md` for product
requirements, `docs/BUILD_PLAN.md` for milestone scope, and `docs/STATUS.md` for
verified progress. Consult `docs/ARCHITECTURE.md` when changing boundaries or storage.
These documents describe planned capabilities unless STATUS provides evidence.

## Development agreement

- Implement one milestone at a time, beginning with the offline S-A fixture pipeline.
- Make routine reversible decisions autonomously; use relevant installed skills selectively.
- Preserve existing work and the installed `.agents/skills` files and `skills-lock.json`.
- Test observable behavior and important failure paths. Never weaken acceptance
  checks just to make implementation pass; explain any legitimate correction.
- Preserve trust-boundary validation, data-loss handling, error handling, and accessibility.
- Keep source text and provider output untrusted. Enforce tool budgets in application code.
- Record actual commands, results, and remaining limitations in STATUS. No invented metrics.
- Commit and push coherent verified increments on `codex/` branches. Inspect remote
  history before the first push. Do not stage unrelated changes.
- Do not force-push, merge, deploy, or call paid providers without relevant authorization.
- Do not commit secrets, local databases, fetched pages, or generated runs. Version only
  deliberately curated fixtures. Setup may download locked dependencies; tests stay offline.
- No live provider integration in the foundation milestone. Configure credentials through
  the appropriate secure flow when a later authorized milestone needs them.

## Commands

Python 3.12 is the local development baseline; CI also exercises 3.13.

```bash
uv sync --locked
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync pytest -m 'not live'
uv build
uv run --no-sync synapse --version
```

Run checks relevant to the change and the milestone's acceptance checks before committing.
For substantial code changes, inspect the diff against the PRD and investigate review
findings. Recheck affected behavior after fixes. Do not add speculative features or
repeat unchanged checks without a reason. Default tests must not depend on provider
keys, real search results, network access, or model-generated outputs.
