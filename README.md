# hswitch

Safe account switching for Hermes Agent's OpenAI Codex OAuth provider.

`hswitch` is a small Hermes plugin and terminal command for people who keep more than one ChatGPT/Codex OAuth login in Hermes. It lets you see the available accounts, switch the active one, and keep Hermes' auth store consistent without hand-editing `~/.hermes/auth.json`.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Hermes plugin](https://img.shields.io/badge/Hermes-plugin-6f42c1.svg)](https://github.com/NousResearch/hermes-agent)

## Why this exists

Hermes can store multiple OAuth credentials for the same provider. That is useful when one account hits a limit, is under cooldown, or you simply want to choose which account a session should use.

Doing that by editing JSON is annoying and risky. `hswitch` gives you a boring, explicit command instead:

```bash
hswitch list
hswitch use work
hswitch use backup
```

It updates the active OpenAI Codex credential and keeps the credential pool order in sync, including the numeric priority values Hermes uses internally.

## What it changes

`hswitch use <selector>` updates only the OpenAI Codex section of Hermes' auth store:

- `providers.openai-codex.tokens`, the active singleton credential
- `providers.openai-codex.auth_mode` and `last_refresh` metadata
- `credential_pool.openai-codex[]`, moving the selected credential to priority `0`
- stale error/cooldown markers on the selected pool entry

It does not print token values. It shows SHA-256 fingerprints so you can tell accounts apart without leaking credentials.

Before every write, it creates a private backup under:

```text
~/.hermes/backups/hswitch/
```

## Install

### Hermes plugin from GitHub

```bash
hermes plugins install OWNER/hermes-plugin-hswitch --enable --force
```

Restart Hermes CLI or the gateway so plugin commands are discovered, then run:

```bash
hermes hswitch list
hermes hswitch use 2
hermes hswitch current
```

### Standalone CLI

If the package is published to PyPI:

```bash
pip install hermes-plugin-hswitch
```

Or install straight from GitHub:

```bash
pip install git+https://github.com/OWNER/hermes-plugin-hswitch
```

Then use:

```bash
hswitch list
hswitch use 2
```

On Debian/Raspberry Pi systems with externally managed Python, use a venv instead of forcing `--break-system-packages`.

## Commands

```bash
hswitch list              # show available OpenAI Codex OAuth credentials
hswitch --list            # compatibility alias for list
hswitch current           # show the active credential
hswitch use <selector>    # make one credential active
hswitch <selector>        # compatibility alias for use <selector>
hswitch next              # switch to the next credential
hswitch toggle            # alias for next
hswitch label <selector> <name>
hswitch doctor            # explain whether the auth store looks usable
hswitch path              # print the auth.json path being used
```

`<selector>` can be:

- list number: `1`, `2`, `3`
- pool entry id
- label
- access-token fingerprint prefix shown by `list`

## Example

```text
$ hswitch list
OpenAI Codex credentials:
* 1. id=acct-a source=manual:device_code label='work'   access=111111111111 refresh=aaaaaaaaaaaa
  2. id=acct-b source=manual:device_code label='backup' access=222222222222 refresh=bbbbbbbbbbbb

* = active provider singleton. Tokens are redacted fingerprints, not secrets.

$ hswitch use backup
Active OpenAI Codex credential: 2:backup (222222222222)
Backup: ~/.hermes/backups/hswitch/auth-20260619T183053.798122Z.json
Restart Hermes sessions using OpenAI Codex so they pick up the new token.
```

Hermes sees the same active account:

```bash
hermes auth list openai-codex
```

```text
openai-codex (2 credentials):
  #1  backup  oauth   device_code ←
  #2  work    oauth   device_code
```

## Safety model

`hswitch` is intentionally narrow:

- supports only Hermes' `openai-codex` OAuth provider
- switches existing credentials only
- never performs OAuth login or token refresh
- never calls OpenAI
- never prints raw `access_token`, `refresh_token`, `id_token`, or API keys
- writes `auth.json` atomically
- stores backups only in a backup folder
- defaults bare `hswitch` to read-only listing

If you need to add credentials first, use Hermes:

```bash
hermes login --provider openai-codex
# or
hermes auth add openai-codex
```

## Known limitations

- Active Hermes sessions may need a restart after switching credentials.
- The auth shape is tied to Hermes' current `providers.openai-codex` plus `credential_pool.openai-codex` layout.
- GitHub Actions CI is not included yet because the original publishing token did not have GitHub `workflow` scope.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip pytest build
python -m pytest -q
python -m build
python -m pip install -e .
hswitch --help
```

For plugin-path testing, install from GitHub or load the directory as a Hermes plugin:

```bash
hermes plugins install OWNER/hermes-plugin-hswitch --enable --force
hermes hswitch doctor
```

## Project layout

```text
plugin.yaml                 # Hermes plugin manifest
__init__.py                 # directory-plugin shim for GitHub installs
hermes_hswitch/core.py      # auth-store logic
hermes_hswitch/cli.py       # standalone CLI
hermes_hswitch/plugin.py    # Hermes CLI command registration
tests/                      # pytest coverage for core + plugin loading
```

## License

MIT. See [LICENSE](LICENSE).
