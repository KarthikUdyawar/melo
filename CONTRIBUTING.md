# Contributing to Melo

Thanks for taking the time to contribute. Melo is a personal self-hosted audio library — contributions that improve reliability, developer experience, or extensibility are welcome.

---

## Table of Contents

- [Contributing to Melo](#contributing-to-melo)
  - [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [Local Setup](#local-setup)
  - [Branch Naming](#branch-naming)
  - [Commit Convention](#commit-convention)
  - [Running Tests](#running-tests)
  - [Pre-commit Hooks](#pre-commit-hooks)
  - [Pull Request Checklist](#pull-request-checklist)
  - [Code Style](#code-style)
  - [Out of Scope](#out-of-scope)

---

## Prerequisites

| Tool             | Version | Install                                                |
| ---------------- | ------- | ------------------------------------------------------ |
| Python           | ≥ 3.12  | [python.org](https://www.python.org/)                  |
| uv               | latest  | `curl -LsSf https://astral.sh/uv/install.sh \| sh`     |
| Docker + Compose | v2      | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Make             | any     | OS package manager                                     |

---

## Local Setup

```bash
# 1. Clone
git clone https://github.com/KarthikUdyawar/melo && cd melo

# 2. Install dependencies (creates .venv automatically)
uv sync --all-groups

# 3. Install pre-commit hooks (run once)
make pre-commit-install

# 4. Configure environment
cp example.env .env.development   # edit DATABASE_URL etc. for local dev

# 5. Start the stack
make up

# 6. Verify
make health
```

---

## Branch Naming

```
feature/<ticket-id>-short-description    # new functionality
fix/<ticket-id>-short-description        # bug fix
chore/<short-description>                # tooling, deps, docs
refactor/<short-description>             # no behaviour change
```

Examples:
- `feature/ffmpeg-speed`
- `fix/route-ordering-preview`
- `chore/update-yt-dlp`

Base branch: **`develop`**. Never commit directly to `master`.

---

## Commit Convention

Melo uses [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `perf`

**Scope:** `api`, `worker`, `storage`, `processor`, `downloader`, `db`, `schemas`, `tests`, `ci`, `docker`

Examples:
```
feat(api): add cursor pagination to GET /songs
fix(downloader): set noplaylist=True to prevent playlist resolution
chore(deps): bump yt-dlp to 2026.03.17
test(integration): add playlist ordering edge cases
```

---

## Running Tests

```bash
# Unit tests — no Docker required, fast
make test-unit

# Integration tests — requires Docker (spins up Postgres)
make test-integration

# Full suite + coverage report
make test

# HTML coverage report → htmlcov/index.html
make test-cov

# End-to-end smoke test — requires full stack running
make smoke
```

Coverage threshold: **80%** (currently 94.77%).

---

## Pre-commit Hooks

Hooks run automatically on `git commit`. To run manually:

```bash
# Run on all files
make pre-commit

# Install hooks (first time only)
make pre-commit-install
```

**Hook suite:**
- `ruff` — lint + auto-fix
- `black` — formatting
- `mypy --strict` — type checking
- `bandit` — security scan
- `gitleaks` — secret detection
- `pytest` — runs on push

If a hook fails, fix the reported issue and re-stage:

```bash
git add -p
git commit
```

---

## Pull Request Checklist

Before opening a PR, verify:

- [ ] Branch based on `develop`, not `master`
- [ ] Commit messages follow Conventional Commits
- [ ] `make pre-commit` passes cleanly
- [ ] `make test` green (≥ 80% coverage)
- [ ] New behaviour has tests
- [ ] No `print()` / debug artifacts left in code
- [ ] `README.md` updated if API surface changed
- [ ] Sprint doc updated if ticket closed

---

## Code Style

Melo follows **Clean Code** principles (Uncle Bob):

- Functions do **one thing**
- Names are **intention-revealing** (`probe_metadata` not `get_info`)
- No comments that explain *what* — code should be self-explanatory
- No `None` returns from functions that callers must always null-check — raise exceptions instead
- Error types live in the service layer (`DownloadError`, `ProcessingError`, `StorageError`)
- Routers contain no business logic — delegate to services

Formatter: `ruff` + `black` (88-char line length, Python 3.12 target).

Typing: `mypy --strict`. All public functions must be annotated.

---

## Out of Scope

The following are **not** accepted for v1:

- Multi-user authentication
- Frontend UI (planned Sprint 4)
- Lyrics / waveform visualisation
- AI recommendations
- Mobile app

If in doubt, open an issue before writing code.
