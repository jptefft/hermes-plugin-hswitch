# Security Policy

## Supported versions

This project is early-stage. Security fixes target the latest released version.

## Reporting a vulnerability

Please open a private GitHub security advisory or contact the maintainer directly.
Do not post OAuth tokens, `auth.json`, screenshots containing token values, or full
terminal logs with secrets in public issues.

## Secret-handling design

`hswitch` intentionally:

- never prints raw OAuth tokens
- shows SHA-256 token fingerprints only
- writes `auth.json` atomically
- creates backups only under `~/.hermes/backups/hswitch/`
- does not publish code, talk to GitHub, or call OpenAI

If you find a path that leaks token material, treat it as a security bug.
