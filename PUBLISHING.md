# Publishing Checklist

This repo is prepared for two distribution paths:

1. GitHub Hermes plugin install
2. PyPI/pip package install

## Before first public push

- [ ] Review every file in `git status --short`
- [ ] Confirm no real `auth.json`, OAuth tokens, `.env`, databases, backups, or logs are committed
- [ ] Run `python -m pytest -q`
- [ ] Run `python -m build`
- [ ] Decide whether the GitHub repo should be public or private first

## Create the GitHub repo

Recommended: private first, inspect on GitHub, then flip public.

```bash
gh repo create hermes-plugin-hswitch --private --source=. --remote=origin
```

## Push with the local guardrail

This machine blocks GitHub pushes unless explicitly allowed:

```bash
HERMES_ALLOW_GITHUB_PUBLISH=1 git push -u origin main
```

## Install from GitHub as a Hermes plugin

After pushing:

```bash
hermes plugins install OWNER/hermes-plugin-hswitch --enable
```

Restart Hermes CLI/gateway, then:

```bash
hermes hswitch list
hermes hswitch doctor
```

## Publish to PyPI later, optional

Only after testing GitHub install:

```bash
python -m build
python -m twine upload dist/*
```

Then users can also install:

```bash
pip install hermes-plugin-hswitch
hswitch list
```
