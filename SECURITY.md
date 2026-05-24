# Security Policy

## Supported Versions

Melo is a personal self-hosted tool. **Only the latest commit on the default branch (`master`) is supported.**

| Version | Supported |
| ------- | --------- |
| latest  | ✅         |
| older   | ❌         |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities privately via [GitHub Security Advisories](https://github.com/KarthikUdyawar/melo/security/advisories/new).

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

Expected response time: **within 7 days**.

## Scope

| In scope                             | Out of scope                           |
| ------------------------------------ | -------------------------------------- |
| API endpoint vulnerabilities         | YouTube ToS issues                     |
| Auth bypass (if auth added)          | Bugs in upstream deps (yt-dlp, FFmpeg) |
| Secret/credential exposure           | Issues requiring physical access       |
| Docker escape / privilege escalation | Social engineering                     |

## Security Design Notes

- All secrets loaded from env files — never hardcoded
- `.env.*` files excluded from Docker image via `.dockerignore`
- Swagger UI disabled in production (`docs_url=None`)
- MinIO objects accessed via API proxy — presigned URLs not exposed to clients
- FFmpeg subprocess args are internal constants only — no user input passed to shell (`# nosec B603/B607`)
- `/tmp/melo` temp files cleaned in `finally` blocks after every stream
