# Contributing to CodeNova

First off, thank you for taking the time to contribute! 🎉

CodeNova is an open-source project, and every contribution — bug reports, feature requests, code, docs, or just spreading the word — makes a real difference.

This document explains how to get involved. By participating, you are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## 📋 Table of Contents

- [Environment Setup](#environment-setup)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Commit Convention](#commit-convention)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)
- [Code of Conduct](#code-of-conduct)

---

## Environment Setup

### Prerequisites

- **Git** (latest stable)
- **Docker** and **Docker Compose** (used by both the demo and full editions)
- **Python 3.11+** (for backend development)
- **Node.js 18+** and **npm** (for frontend development)
- An **OpenAI API key** (or a compatible LLM endpoint) for the Q&A features

### Fork and Clone

1. Fork the repository on GitHub: <https://github.com/zhangwudef/codenova>
2. Clone your fork locally:

   ```bash
   git clone https://github.com/<your-username>/codenova.git
   cd codenova
   ```

3. Add the upstream remote so you can stay in sync:

   ```bash
   git remote add upstream https://github.com/zhangwudef/codenova.git
   ```

### Configure the Environment

```bash
cp .env.example .env
# Edit .env and fill in at least OPENAI_API_KEY
```

### Install pre-commit Hooks

The project enforces code style via [pre-commit](https://pre-commit.com/). Install it once per clone:

```bash
pip install pre-commit
pre-commit install
```

This runs `ruff`, `ruff-format`, and a few generic checks automatically on every commit.

### Start the Stack

For day-to-day development the demo edition is the fastest path:

```bash
docker compose -f docker-compose.demo.yml up -d
```

Then visit <http://localhost:5173>. See the [README](README.md) for the full edition and detailed access URLs.

#### Backend (Python)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### Frontend (React + TypeScript)

```bash
cd frontend
npm install
npm run dev
```

---

## Development Workflow

1. **Sync with upstream** before starting new work:

   ```bash
   git checkout main
   git pull upstream main
   ```

2. **Create a feature branch** off `main`. Use a short, descriptive name:

   ```bash
   git checkout -b feat/ast-go-support
   ```

3. **Make your changes**, keeping commits focused and small.
4. **Run checks locally** before pushing:

   ```bash
   pre-commit run --all-files
   cd backend && python -m pytest tests/ -v
   cd ../frontend && npm run build
   ```

5. **Push** to your fork and open a Pull Request against `main`:

   ```bash
   git push origin feat/ast-go-support
   ```

6. **Address review feedback** by pushing additional commits (avoid force-pushing during review unless asked).

---

## Code Style

### Backend (Python)

- Enforced by `ruff` and `ruff-format`, configured in [`backend/pyproject.toml`](backend/pyproject.toml).
- Line width: **100** characters.
- Target Python version: **3.11**.
- Type-checking with `mypy` is encouraged for new service code.
- Keep functions small and focused; prefer explicit data models (Pydantic schemas under `backend/app/services/*/schemas.py`).

### Frontend (TypeScript / React)

- TypeScript strict mode is on; do not use `any` unless absolutely necessary.
- Components live in `frontend/src/components/`; state in `frontend/src/stores/` (Zustand).
- Follow the existing Tailwind class conventions; prefer functional components and hooks.

### General

- Match the style of surrounding code — when in doubt, imitate what is already there.
- Do not reformat code you are not touching in the same PR.
- Keep diffs minimal and reviewable.

---

## Commit Convention

We follow [**Conventional Commits**](https://www.conventionalcommits.org/). Each commit message should be structured as:

```
<type>(<optional scope>): <short imperative summary>

<optional body explaining the why>

<optional footer>
```

### Common Types

| Type     | Use for                                             |
| -------- | --------------------------------------------------- |
| `feat`   | A new feature                                        |
| `fix`    | A bug fix                                           |
| `docs`   | Documentation-only changes                          |
| `style`  | Formatting, whitespace, semicolons — no logic change|
| `refactor` | Code restructuring with no behavior change       |
| `perf`   | Performance improvements                            |
| `test`   | Adding or correcting tests                          |
| `chore`  | Build, tooling, dependencies, CI                   |
| `ci`     | CI configuration changes                           |

### Examples

```
feat(parser): add Go call-graph extraction
fix(rag): handle empty embedding responses
docs(readme): add English translation
test(ast-splitter): cover nested class fallback
chore(deps): bump langchain to 0.2.x
```

> 💡 `pre-commit` and CI will not rewrite your messages, but reviewers may ask you to reword non-conforming commits before merge.

---

## Pull Request Process

1. **Open the PR** against the `main` branch of `zhangwudef/codenova`.
2. **Fill in the PR template** (see [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)) — description, motivation, related issues, and the checklist.
3. **Keep the PR focused** on a single concern. Split unrelated changes into separate PRs.
4. **Make sure CI is green.** The CI pipeline runs `pytest`, the frontend build, and `ruff` (non-blocking).
5. **Respond to review** constructively and promptly. Push follow-up commits rather than rewriting history once review has started.
6. **Squash or rebase** if a maintainer asks for a cleaner history before merge.
7. A maintainer will merge once approved. You do not need to merge your own PR.

### What reviewers look for

- Does the change match the described goal?
- Are there tests for new behavior?
- Does `pre-commit run --all-files` pass cleanly?
- Is the public API / CLI surface affected? If so, is it documented?
- No secrets, credentials, or large binaries are committed.

---

## Reporting Issues

Before opening a new issue, please **search existing issues** to avoid duplicates.

### Bug Reports

Use the **Bug report** template (`.github/ISSUE_TEMPLATE/bug_report.md`). Include:

- A clear title and a minimal reproduction step list.
- Expected vs. actual behavior.
- Environment details (OS, Docker version, Python/Node versions, browser).
- Relevant logs, screenshots, or stack traces.

### Feature Requests

Use the **Feature request** template (`.github/ISSUE_TEMPLATE/feature_request.md`). Include:

- The problem you are trying to solve.
- Your proposed solution and any alternatives you considered.
- Any additional context, screenshots, or references.

### Security Issues

Do **not** open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md) for the private disclosure process.

---

## Code of Conduct

Participation in this project is governed by the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). Please be kind, respectful, and inclusive. Report unacceptable behavior to **r24847975@gmail.com**.

---

Thank you for helping make CodeNova better! 🚀
