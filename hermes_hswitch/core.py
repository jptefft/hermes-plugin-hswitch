"""Core auth-store operations for hswitch.

Hermes stores OpenAI Codex OAuth credentials in `~/.hermes/auth.json`:

- providers.openai-codex.tokens: singleton credentials used by the direct runtime
- credential_pool.openai-codex[]: one or more pooled credentials

This module never prints raw tokens and never shells out. It only reads/writes
JSON with atomic replace semantics.
"""

from __future__ import annotations

import base64
import copy
import dataclasses
import datetime as _dt
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

__version__ = "0.1.3"
PROVIDER = "openai-codex"
RISKY_TOKEN_KEYS = {"access_token", "refresh_token", "id_token", "api_key"}
ERROR_MARKERS = (
    "last_status",
    "last_error_code",
    "last_error_reason",
    "last_error_message",
    "last_error_reset_at",
)


class HSwitchError(RuntimeError):
    """User-facing hswitch error."""


@dataclasses.dataclass(frozen=True)
class CredentialSummary:
    number: int
    source: str
    entry_id: str
    label: str | None
    access_fp: str | None
    refresh_fp: str | None
    expires_at: str | None
    last_status: str | None
    active: bool
    pool_index: int | None
    raw: dict[str, Any]

    @property
    def display_name(self) -> str:
        return self.label or self.entry_id or f"#{self.number}"


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser()


def auth_path(path: str | os.PathLike[str] | None = None) -> Path:
    return Path(path).expanduser() if path else hermes_home() / "auth.json"


def load_auth(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    target = auth_path(path)
    if not target.exists():
        raise HSwitchError(
            f"No Hermes auth store found at {target}. Run `hermes login --provider openai-codex` first."
        )
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HSwitchError(f"Auth store is not valid JSON: {target}: {exc}") from exc
    if not isinstance(data, dict):
        raise HSwitchError(f"Auth store must contain a JSON object: {target}")
    return data


def _provider_tokens(data: dict[str, Any]) -> dict[str, Any]:
    provider = (data.get("providers") or {}).get(PROVIDER) or {}
    tokens = provider.get("tokens") or {}
    return tokens if isinstance(tokens, dict) else {}


def _pool_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    pool_root = data.get("credential_pool") or {}
    entries = pool_root.get(PROVIDER) or []
    return entries if isinstance(entries, list) else []


def _token_fp(token: Any) -> str | None:
    if not isinstance(token, str) or not token:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def _jwt_payload(token: Any) -> dict[str, Any]:
    if not isinstance(token, str) or token.count(".") < 2:
        return {}
    try:
        payload = token.split(".", 2)[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        obj = json.loads(decoded.decode("utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _expiry_iso(token: Any) -> str | None:
    payload = _jwt_payload(token)
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return None
    try:
        return _dt.datetime.fromtimestamp(exp, tz=_dt.timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None


def _entry_tokens(entry: dict[str, Any]) -> dict[str, Any]:
    nested = entry.get("tokens")
    if isinstance(nested, dict):
        tokens = dict(nested)
    else:
        tokens = {k: entry.get(k) for k in RISKY_TOKEN_KEYS if entry.get(k)}
    return {k: v for k, v in tokens.items() if v}


def _same_tokens(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return bool(a.get("access_token")) and a.get("access_token") == b.get("access_token") and (
        not a.get("refresh_token") or not b.get("refresh_token") or a.get("refresh_token") == b.get("refresh_token")
    )


def _entry_label(entry: dict[str, Any]) -> str | None:
    for key in ("label", "name", "account", "email"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _entry_id(entry: dict[str, Any], index: int, access_fp: str | None) -> str:
    value = entry.get("id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return access_fp or f"pool-{index + 1}"


def list_credentials(data: dict[str, Any]) -> list[CredentialSummary]:
    """Return redacted summaries of OpenAI Codex credentials in the auth store."""
    active_tokens = _provider_tokens(data)
    out: list[CredentialSummary] = []
    seen_access: set[str] = set()

    for idx, entry in enumerate(_pool_entries(data)):
        if not isinstance(entry, dict):
            continue
        tokens = _entry_tokens(entry)
        access_fp = _token_fp(tokens.get("access_token"))
        refresh_fp = _token_fp(tokens.get("refresh_token"))
        if not access_fp:
            continue
        seen_access.add(access_fp)
        out.append(CredentialSummary(
            number=len(out) + 1,
            source=str(entry.get("source") or "credential_pool"),
            entry_id=_entry_id(entry, idx, access_fp),
            label=_entry_label(entry),
            access_fp=access_fp,
            refresh_fp=refresh_fp,
            expires_at=_expiry_iso(tokens.get("access_token")),
            last_status=str(entry.get("last_status")) if entry.get("last_status") is not None else None,
            active=_same_tokens(active_tokens, tokens),
            pool_index=idx,
            raw=copy.deepcopy(entry),
        ))

    singleton_fp = _token_fp(active_tokens.get("access_token"))
    if singleton_fp and singleton_fp not in seen_access:
        provider = (data.get("providers") or {}).get(PROVIDER) or {}
        out.append(CredentialSummary(
            number=len(out) + 1,
            source="providers.openai-codex",
            entry_id=singleton_fp,
            label="singleton-only",
            access_fp=singleton_fp,
            refresh_fp=_token_fp(active_tokens.get("refresh_token")),
            expires_at=_expiry_iso(active_tokens.get("access_token")),
            last_status=None,
            active=True,
            pool_index=None,
            raw={"tokens": copy.deepcopy(active_tokens), "last_refresh": provider.get("last_refresh")},
        ))
    return out


def find_credential(data: dict[str, Any], selector: str) -> CredentialSummary:
    selector_norm = str(selector or "").strip().lower()
    if not selector_norm:
        raise HSwitchError("Missing credential selector. Use `hswitch list` first.")
    candidates = list_credentials(data)
    if selector_norm.isdigit():
        n = int(selector_norm)
        for item in candidates:
            if item.number == n:
                return item
    matches = []
    for item in candidates:
        values = [item.entry_id, item.label, item.access_fp, item.refresh_fp]
        if any(v and str(v).lower() == selector_norm for v in values):
            matches.append(item)
            continue
        if item.access_fp and item.access_fp.startswith(selector_norm):
            matches.append(item)
    if not matches:
        raise HSwitchError(f"No OpenAI Codex credential matches {selector!r}.")
    if len(matches) > 1:
        labels = ", ".join(f"{m.number}:{m.display_name}" for m in matches)
        raise HSwitchError(f"Ambiguous selector {selector!r}; matches: {labels}")
    return matches[0]


def _backup_auth_file(target: Path) -> Path | None:
    if not target.exists():
        return None
    root = target.parent / "backups" / "hswitch"
    root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    stamp = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup = root / f"auth-{stamp}.json"
    suffix = 1
    while backup.exists():
        backup = root / f"auth-{stamp}.{suffix}.json"
        suffix += 1
    fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(target.read_bytes())
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try:
            backup.unlink(missing_ok=True)
        finally:
            raise
    return backup


def atomic_write_auth(data: dict[str, Any], path: str | os.PathLike[str] | None = None, *, backup: bool = True) -> Path | None:
    target = auth_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    backup_path = _backup_auth_file(target) if backup else None
    serialized = json.dumps(data, indent=2, sort_keys=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return backup_path


def switch_active(data: dict[str, Any], selector: str) -> tuple[dict[str, Any], CredentialSummary]:
    selected = find_credential(data, selector)
    tokens = _entry_tokens(selected.raw)
    if not tokens.get("access_token"):
        raise HSwitchError(f"Credential {selector!r} has no access_token.")

    new_data = copy.deepcopy(data)
    providers = new_data.setdefault("providers", {})
    provider_entry = providers.setdefault(PROVIDER, {})
    provider_entry["tokens"] = {k: v for k, v in tokens.items() if v}
    raw_auth_mode = selected.raw.get("auth_mode")
    provider_entry["auth_mode"] = raw_auth_mode if isinstance(raw_auth_mode, str) and raw_auth_mode.strip() else "chatgpt"
    if "last_refresh" in selected.raw:
        provider_entry["last_refresh"] = selected.raw.get("last_refresh")
    else:
        provider_entry.pop("last_refresh", None)

    if selected.pool_index is not None:
        pool = new_data.setdefault("credential_pool", {}).setdefault(PROVIDER, [])
        if selected.pool_index < len(pool) and isinstance(pool[selected.pool_index], dict):
            entry = pool[selected.pool_index]
            for key in ERROR_MARKERS:
                if key in entry:
                    entry[key] = None
            # Preserve the original hswitch behavior too: move the selected
            # credential to pool priority 0 for Hermes paths that consult the
            # credential pool rather than only providers.<provider>.tokens.
            if selected.pool_index != 0:
                pool.pop(selected.pool_index)
                pool.insert(0, entry)
            for priority, pool_entry in enumerate(pool):
                if isinstance(pool_entry, dict):
                    pool_entry["priority"] = priority
    return new_data, selected


def label_credential(data: dict[str, Any], selector: str, label: str) -> tuple[dict[str, Any], CredentialSummary]:
    clean = str(label or "").strip()
    if not clean:
        raise HSwitchError("Label must not be empty.")
    selected = find_credential(data, selector)
    if selected.pool_index is None:
        raise HSwitchError("Cannot label singleton-only credentials; add it to credential_pool first.")
    new_data = copy.deepcopy(data)
    new_data["credential_pool"][PROVIDER][selected.pool_index]["label"] = clean
    return new_data, selected


def render_list(items: list[CredentialSummary]) -> str:
    if not items:
        return "No OpenAI Codex credentials found. Run `hermes login --provider openai-codex` first."
    lines = ["OpenAI Codex credentials:"]
    for item in items:
        marker = "*" if item.active else " "
        label = f" label={item.label!r}" if item.label else ""
        expires = f" exp={item.expires_at}" if item.expires_at else ""
        status = f" status={item.last_status}" if item.last_status else ""
        lines.append(
            f"{marker} {item.number}. id={item.entry_id} source={item.source}{label} "
            f"access={item.access_fp or '-'} refresh={item.refresh_fp or '-'}{expires}{status}"
        )
    lines.append("\n* = active provider singleton. Tokens are redacted fingerprints, not secrets.")
    return "\n".join(lines)


def redact_auth(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of auth data with token values replaced by fingerprints."""
    def scrub(obj: Any) -> Any:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if k in RISKY_TOKEN_KEYS:
                    out[k] = f"sha256:{_token_fp(v)}" if v else None
                else:
                    out[k] = scrub(v)
            return out
        if isinstance(obj, list):
            return [scrub(v) for v in obj]
        return obj
    return scrub(data)
