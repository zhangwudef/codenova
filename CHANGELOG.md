# Changelog

All notable changes to CodeNova will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ESLint flat config (`eslint.config.js`) for frontend, with React Hooks and Refresh plugins.
- `CHANGELOG.md` to track notable changes across releases.
- `.github/FUNDING.yml` for sponsorship configuration.
- `.github/dependabot.yml` for automated dependency update monitoring.
- `.github/CODEOWNERS` for automatic reviewer assignment.
- `.github/workflows/release.yml` for tag-triggered GitHub Releases and Docker image publishing to GHCR.
- `.github/workflows/codeql.yml` for automated security code scanning.
- `AUTHORS.md` for contributor recognition.
- Codecov coverage badge in README.
- `docs/api.md` API reference.
- `docs/troubleshooting.md` FAQ and troubleshooting guide.
- `docs/decisions/` ADR (Architecture Decision Records) directory.

### Changed
- Replaced placeholder email `zhangwudef@example.com` with the real contact `r24847975@gmail.com` in `SECURITY.md`, `CODE_OF_CONDUCT.md`, and `CONTRIBUTING.md`.
- `backend/Dockerfile` now uses an optional `PIP_INDEX_URL` build-arg instead of a hardcoded mirror, defaulting to the official PyPI.
- Re-enabled the ESLint hook in `.pre-commit-config.yaml` (previously commented out due to missing config).

### Fixed
- Removed duplicate `httpx==0.27.2` entry in `backend/requirements.txt` (was declared under both "GitHub 集成" and "开发与测试").

## [0.1.0] - 2026-08-01

### Added
- AST-based semantic code chunking via Tree-sitter (Python / JS / TS / Java / Go / Rust).
- Dual-index retrieval: semantic vector index + call-graph index (1-hop expansion).
- Incremental indexing based on Git diff.
- ReactFlow dependency graph and Mermaid sequence diagram visualization.
- RAG-powered Q&A with source code location references.
- Q&A-as-document persistence to Markdown.
- Demo edition (`docker-compose.demo.yml`, 3 services) and full edition (`docker-compose.yml`, 7 services).
- Bilingual README (Simplified Chinese + English).
- `docs/benchmark.md` with S1 real benchmark data (AST vs fixed vs semantic chunking).
- `docs/DEPLOYMENT.md` covering Render / Fly.io / local Docker.
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`.
- Issue templates (bug report, feature request) and PR template.
- GitHub Actions CI: backend pytest + coverage, frontend build + test.
- pre-commit hooks: ruff, ruff-format, generic checks.
- API Key authentication middleware.
- Demo mode file-count limit (`DEMO_MAX_FILES`) to prevent OOM.

### Known Limitations
- Online demo not yet deployed (self-hosting guide available).
- Frontend unit test coverage is minimal (threshold at 30%).
- Backend coverage baseline at 50%.
- Benchmark S2-S6 scripts ready but not yet executed with real data.
