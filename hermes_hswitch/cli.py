"""Command-line interface for hswitch."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .core import (
    HSwitchError,
    PROVIDER,
    __version__,
    auth_path,
    atomic_write_auth,
    label_credential,
    list_credentials,
    load_auth,
    redact_auth,
    render_list,
    switch_active,
)

_COMMANDS = {"list", "current", "doctor", "path", "use", "label", "next", "toggle"}


def build_parser(parser: argparse.ArgumentParser | None = None) -> argparse.ArgumentParser:
    parser = parser or argparse.ArgumentParser(prog="hswitch")
    parser.description = "Safely switch the active Hermes OpenAI Codex OAuth credential."
    parser.add_argument("--version", action="version", version=f"hswitch {__version__}")
    parser.add_argument("--auth-file", help="Path to Hermes auth.json (default: $HERMES_HOME/auth.json or ~/.hermes/auth.json)")
    parser.add_argument("--provider", default=PROVIDER, help="OAuth provider to switch (currently only openai-codex is supported)")
    parser.add_argument("--json", action="store_true", help="Emit JSON where supported")
    parser.add_argument("--no-backup", action="store_true", help="Do not write a backup under ~/.hermes/backups/hswitch before mutation")
    parser.add_argument("--dry-run", action="store_true", help="Show intended mutation without writing")
    parser.add_argument("--list", dest="compat_list", action="store_true", help="Compatibility alias for `hswitch list`")
    parser.add_argument(
        "command",
        nargs="?",
        default="list",
        help="Command: list, current, use, next, toggle, label, doctor, path. A bare selector is treated as `use <selector>`.",
    )
    parser.add_argument("args", nargs="*", help="Command arguments")
    return parser


def _json_print(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def _ensure_supported_provider(provider: str) -> None:
    clean = str(provider or "").strip()
    if clean != PROVIDER:
        raise HSwitchError(f"Unsupported provider {clean!r}; hswitch currently supports only {PROVIDER!r}.")


def _redacted_items(items):
    return [i.__dict__ | {"raw": redact_auth(i.raw)} for i in items]


def _next_selector(data: dict) -> str:
    items = list_credentials(data)
    if not items:
        raise HSwitchError("No OpenAI Codex credentials found. Run `hswitch list` first.")
    if len(items) == 1:
        raise HSwitchError("Only one OpenAI Codex credential is available; nothing to switch to.")
    active_index = next((idx for idx, item in enumerate(items) if item.active), -1)
    next_item = items[(active_index + 1) % len(items)] if active_index >= 0 else items[0]
    return str(next_item.number)


def _command_and_args(args: argparse.Namespace) -> tuple[str, list[str]]:
    if getattr(args, "compat_list", False):
        return "list", []
    raw_cmd = str(getattr(args, "command", None) or "list")
    rest = list(getattr(args, "args", []) or [])
    cmd = raw_cmd.lower()
    if cmd == "toggle":
        cmd = "next"
    if cmd in _COMMANDS:
        return cmd, rest
    # Compatibility with the original hswitch: `hswitch 2`, `hswitch work`, etc.
    return "use", [raw_cmd, *rest]


def _one_arg(cmd: str, rest: list[str], label: str = "selector") -> str:
    if len(rest) != 1:
        raise HSwitchError(f"`hswitch {cmd}` expects exactly one {label}.")
    return rest[0]


def run(args: argparse.Namespace) -> int:
    _ensure_supported_provider(getattr(args, "provider", PROVIDER))
    cmd, rest = _command_and_args(args)

    if cmd == "path":
        if rest:
            raise HSwitchError("`hswitch path` does not take arguments.")
        print(auth_path(getattr(args, "auth_file", None)))
        return 0

    data = load_auth(getattr(args, "auth_file", None))

    if cmd == "list":
        if rest:
            raise HSwitchError("`hswitch list` does not take arguments.")
        items = list_credentials(data)
        if getattr(args, "json", False):
            _json_print(_redacted_items(items))
        else:
            print(render_list(items))
        return 0

    if cmd == "current":
        if rest:
            raise HSwitchError("`hswitch current` does not take arguments.")
        active = [i for i in list_credentials(data) if i.active]
        if getattr(args, "json", False):
            _json_print(_redacted_items(active))
        else:
            print(render_list(active) if active else "No active OpenAI Codex credential singleton found.")
        return 0

    if cmd == "doctor":
        if rest:
            raise HSwitchError("`hswitch doctor` does not take arguments.")
        items = list_credentials(data)
        active = [i for i in items if i.active]
        print(f"auth_file: {auth_path(getattr(args, 'auth_file', None))}")
        print(f"credentials: {len(items)}")
        print(f"active: {active[0].display_name if active else 'none'}")
        if not items:
            print("next: run `hermes login --provider openai-codex` or `hermes auth add openai-codex`")
            return 1
        if len(items) == 1:
            print("note: only one credential is available, so switching is not useful yet")
        return 0

    if cmd in {"use", "next"}:
        selector = _one_arg(cmd, rest) if cmd == "use" else _next_selector(data)
        if cmd == "next" and rest:
            raise HSwitchError("`hswitch next` does not take arguments.")
        new_data, selected = switch_active(data, selector)
        if getattr(args, "dry_run", False):
            print(f"Would switch active OpenAI Codex credential to {selected.number}:{selected.display_name} ({selected.access_fp})")
            return 0
        backup = atomic_write_auth(new_data, getattr(args, "auth_file", None), backup=not getattr(args, "no_backup", False))
        print(f"Active OpenAI Codex credential: {selected.number}:{selected.display_name} ({selected.access_fp})")
        if backup:
            print(f"Backup: {backup}")
        print("Restart Hermes sessions using OpenAI Codex so they pick up the new token.")
        return 0

    if cmd == "label":
        if len(rest) != 2:
            raise HSwitchError("`hswitch label` expects: <selector> <label>.")
        new_data, selected = label_credential(data, rest[0], rest[1])
        if getattr(args, "dry_run", False):
            print(f"Would label credential {selected.number}:{selected.display_name} as {rest[1]!r}")
            return 0
        backup = atomic_write_auth(new_data, getattr(args, "auth_file", None), backup=not getattr(args, "no_backup", False))
        print(f"Credential {selected.number}:{selected.display_name} label set to {rest[1]!r}")
        if backup:
            print(f"Backup: {backup}")
        return 0

    raise HSwitchError(f"Unknown command: {cmd}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    raw = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(raw)
    try:
        return run(args)
    except HSwitchError as exc:
        print(f"hswitch: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
