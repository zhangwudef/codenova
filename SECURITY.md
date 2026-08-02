# Security Policy

Thank you for helping keep CodeNova and its users safe. This document describes
how to report security vulnerabilities and what you can expect from us in return.

## Reporting a Vulnerability

If you believe you have discovered a security vulnerability in CodeNova,
**please do not open a public GitHub issue**.

Instead, report it privately so that we can investigate and coordinate a fix
before any public disclosure. You can reach us in either of these ways:

- **Email** (preferred): send a description to **r24847975@gmail.com**
- **GitHub Private Vulnerability Reporting**: use the
  ["Report a vulnerability"](https://github.com/zhangwudef/codenova/security/advisories/new)
  feature under the **Security** tab of the repository. This is the recommended
  channel if email is unavailable.

### What to Include

To help us reproduce and triage the issue quickly, please include:

1. A clear description of the vulnerability and its impact.
2. The affected version or commit hash.
3. Step-by-step instructions to reproduce the issue (a minimal reproducible
   example is ideal).
4. The environment you used (OS, Docker version, Python/Node versions,
   relevant configuration).
5. Any proof-of-concept code, screenshots, or logs.
6. Your suggested mitigation or fix, if you have one.

Please do not include sensitive personal data beyond what is necessary to
demonstrate the issue, and please do not access or modify data that does not
belong to you.

## Supported Versions

CodeNova is an early-stage project. We provide security updates for the
following versions only:

| Version | Supported          |
| ------- | ------------------ |
| `main`  | ✅ Active development |
| Latest tagged release | ✅ Supported |
| Older releases | ❌ Not supported — please update to the latest release |

We strongly recommend running the latest release or the `main` branch.

## Vulnerability Response Time

We take every report seriously. Our target response times are:

| Stage                              | Target                  |
| ---------------------------------- | ----------------------- |
| Initial acknowledgment of receipt | Within **48 hours**     |
| Preliminary assessment & triage    | Within **5 business days** |
| Status update to the reporter      | At least every **7 days** until resolved |
| Fix or mitigation release          | Within **30 days** for high-severity issues; longer timelines may apply to lower-severity issues and will be communicated to the reporter |

These targets are commitments on a best-effort basis. If a report is complex or
requires coordination with downstream dependencies, we will keep you informed
of the timeline and rationale.

## Disclosure Policy

- We follow **coordinated (responsible) disclosure**. We will not publicly
  disclose a vulnerability until a fix is available, unless you explicitly
  consent or the issue is already being actively exploited.
- Once a fix is released, we will publish a security advisory on GitHub and, if
  applicable, credit the reporter (unless they prefer to remain anonymous).
- We kindly request that reporters hold disclosure for a reasonable window
  (default **90 days**) after the initial report, or until a fix is released —
  whichever comes first — to protect users.

## Scope

This policy covers the CodeNova source code in this repository, including the
backend (`backend/`), frontend (`frontend/`), and the deployment manifests
(`docker-compose*.yml`, `Dockerfile*`).

The following are **out of scope**:

- Vulnerabilities in third-party dependencies that should be reported upstream.
- Issues requiring already-compromised credentials or physical access to the
  reporter's own machine.
- Theoretical issues without a plausible attack path.

## Acknowledgments

We are grateful to everyone who takes the time to report security issues
responsibly. With your help, CodeNova stays safe for the whole community.
