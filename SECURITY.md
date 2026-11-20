# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report vulnerabilities privately through GitHub:
**Security → Report a vulnerability** on this repository
([private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)).

Please include the affected version or commit, steps to reproduce, and the impact you expect.
You can expect an acknowledgement within a few days. Fixes are released as soon as practical and
credited in the release notes unless you prefer otherwise.

## Supported versions

Only the latest release receives security fixes.

## Scope

In scope: the backend API, the web UI, the container images and the default deployment files.
Out of scope: vulnerabilities in third-party services you connect (S3 providers, OpenAI, Gemini) and
issues that require an already-compromised admin account or host.

The security model (authentication, roles, SSRF protection, limits, container hardening) is described
in [docs/architecture.md](docs/architecture.md#security-model).
