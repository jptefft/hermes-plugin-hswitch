# Contributing

Thanks for helping make `hswitch` less sketchy and more useful.

## Local setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip pytest build
python -m pip install -e .
```

## Test before you open a PR

```bash
python -m pytest -q
python -m build
hswitch --help
```

If you touch plugin loading, also verify the Hermes command path:

```bash
hermes plugins install OWNER/hermes-plugin-hswitch --enable --force
hermes hswitch doctor
```

## Security rules

Do not commit real Hermes auth files, OAuth tokens, screenshots with token values, `.env` files, backups, or terminal logs that include secrets.

Tests should use fake token strings. Public output should show fingerprints only.

## Design rules

- Keep the tool narrow. It should switch existing OpenAI Codex OAuth credentials, not become a general auth manager.
- Prefer explicit commands over magic behavior.
- Preserve backups before writes.
- Keep `hswitch current`, `hswitch list`, and `hermes auth list openai-codex` consistent.
- If you reorder the pool, update both list order and numeric `priority` values.
