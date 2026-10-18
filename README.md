# Synapse

An evidence-grounded research assistant being built around discovery, analysis,
cited synthesis, and critique. The intended product preserves the source snapshots
behind each cited excerpt so a user can inspect the evidence.

**Current state: engineering foundation only.** The package exposes help and version
commands. Research runs, Streamlit UI, persistence, exports, and provider integrations
are planned; none are implemented yet. See [status](docs/STATUS.md).

## Setup

Install Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/),
then run from the repository root:

```bash
uv sync --locked
uv run --no-sync synapse --version
uv run --no-sync python -m synapse --help
```

The first setup downloads development/build dependencies. Running the foundation
requires no API keys, external services, or paid calls. `uv.lock` freezes the development
dependencies; `uv.toml` keeps the cache inside the ignored `.uv-cache` directory.
The source package is `synapse`; the distribution is `synapse-research`.

## Checks

```bash
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync pytest -m 'not live'
uv build
```

CI runs these checks on Python 3.12 and 3.13 and installs the resulting wheel in
a separate environment outside the checkout. Jobs have read-only repository permissions,
no provider secrets, and pinned action commits. A socket guard rejects accidental
in-process network connections in default tests; it is not an OS-level sandbox and
does not prevent child processes from accessing the network. No application code
currently makes network calls. Live tests will require explicit selection and
authorization when provider integrations exist.

To format owned Python code during development:

```bash
uv run --no-sync ruff format src tests
```

## Build roadmap

1. S-A: offline fixture pipeline, persisted runs, minimal UI, and matching exports.
2. S-B: real search, safe HTML extraction, and provenance.
3. S-C: model-backed structured synthesis and deterministic citation validation.
4. S-D: live critique, followed by one optional preserved revision.
5. S-E: fixed-source baselines, held-out evaluation, failure analysis, and demo.

See [the PRD](docs/PRD.md), [build checkpoints](docs/BUILD_PLAN.md),
[architecture](docs/ARCHITECTURE.md), and [agent working agreement](AGENTS.md).

Installed agent skills and their lockfile are preserved as provided. They guide
development and are not application runtime dependencies. Ruff and mypy check
the owned application/test code rather than linting third-party skill resources.
