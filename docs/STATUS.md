# Synapse status

Updated: 2026-10-18. Branch: `codex/synapse-foundation`.

## Done

- M0 documentation, installable Python package, locked tooling, and offline CI definition.
- All 34 supplied skill files/lockfile were preserved byte-for-byte.
- Foundation committed as `09167c2` and pushed to `origin/codex/synapse-foundation`.
- Hosted CI passed on both Python 3.12 and 3.13, including frozen setup, lint,
  formatting, typing, offline tests, distribution builds, and isolated wheel checks.

## Next

Plan and implement S-A, starting with its public contracts and deterministic fixture
run. Confirm testing boundaries if invoking TDD. No subsequent milestone is active.

## Planned

S-A offline fixture pipeline is next. S-B discovery, S-C synthesis, S-D1 live critique,
S-D2 revision, and S-E evaluation have not started. No application UI, research runs,
SQLite persistence, exports, search, model calls, or measured research results exist.

## Inspection evidence

- Initial checkout had no commits; only installed skills and `skills-lock.json` were present.
- Origin: `https://github.com/ayatinkering/Synapse.git`.
- `git ls-remote --symref origin HEAD 'refs/heads/*'` succeeded with no refs: empty remote.
- Python 3.12.3 and uv 0.12.12 are installed locally.
- Existing skill file hashes recorded for byte-for-byte preservation verification.

## Verification

Executed on Python 3.12.14 with uv 0.12.12:

| Command/check | Actual result |
|---|---|
| `uv sync --locked` | Success; frozen dependency setup |
| `uv run --no-sync ruff check .` | All checks passed |
| `uv run --no-sync ruff format --check .` | 12 Python files already formatted |
| `uv run --no-sync mypy` | No issues in 6 source/test files |
| `uv run --no-sync pytest -m 'not live'` | 5 passed |
| `uv build` | sdist and wheel built successfully |
| `UV_PROJECT_ENVIRONMENT=/tmp/synapse-foundation-frozen uv sync --locked --offline` followed by the offline test command in that environment | Fresh environment installed from cache; 5 passed |
| `uv pip install --python /tmp/synapse-foundation-wheel/bin/python dist/synapse_research-0.1.0-py3-none-any.whl` in a separate `uv venv` | Built wheel installed without runtime dependencies |
| `/tmp/synapse-foundation-wheel/bin/synapse --version` and `python -m synapse --version` from `/tmp` using that environment | Both printed `synapse 0.1.0`; import resolves to its site-packages |
| Distribution archive inspection | Wheel has 8 package/metadata entries; sdist has 11 entries; no skills, secrets, or caches included |
| Supplied PRD comparison | Entire Synapse section preserved; other project requirements excluded |
| SHA-256 preservation comparison | All 34 original skill files/lockfile unchanged |
| `git check-ignore` with representative local secret/runtime paths | Environment files, Streamlit secrets, databases, runtime directories, caches, and machine settings ignored |

The initial sdist included nested skill READMEs because a basename glob matched
them. Root-anchored include patterns fixed the issue; the rebuilt archive passed
the same exclusion check. uv warns that the local cache sits inside the source
directory; explicit archive inspection confirms it is excluded. Cross-filesystem
wheel installation fell back from hardlinks to copying, without affecting results.

## GitHub evidence

- Foundation commit: `09167c2f2dbab046336017d2b47ff58a2a2ea2b6`.
- Verified run: [CI 39118270917](https://github.com/ayatinkering/Synapse/actions/runs/39118270917).
- Both matrix jobs completed successfully; every install/check/build/wheel step passed.
- The repository was empty. GitHub automatically selected its first pushed branch,
  `codex/synapse-foundation`, as the default branch. No `main` branch was created,
  no merge was performed, and repository settings were not changed.
- This status update records the verified foundation run; its own commit does not
  change the package, dependency lock, tests, or CI workflow.

## Limits

- M0 verifies development infrastructure only; it does not satisfy product S01-S15.
- Package checks do not establish research quality or live provider compatibility.
- No paid calls, credential configuration, deployment, merge, or force push authorized
  by this increment. Dependency setup downloads are separate from provider use.
