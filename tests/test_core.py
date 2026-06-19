from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from hermes_hswitch.cli import main
from hermes_hswitch.core import HSwitchError, atomic_write_auth, list_credentials, load_auth, switch_active


def sample_auth():
    return {
        "version": 1,
        "active_provider": "openai-codex",
        "providers": {
            "openai-codex": {
                "tokens": {"access_token": "access-one", "refresh_token": "refresh-one"},
                "auth_mode": "chatgpt",
            }
        },
        "credential_pool": {
            "openai-codex": [
                {
                    "id": "one",
                    "label": "work",
                    "source": "device_code",
                    "auth_type": "oauth",
                    "access_token": "access-one",
                    "refresh_token": "refresh-one",
                },
                {
                    "id": "two",
                    "label": "personal",
                    "source": "manual:device_code",
                    "auth_type": "oauth",
                    "access_token": "access-two",
                    "refresh_token": "refresh-two",
                    "last_status": "exhausted",
                    "last_error_code": 401,
                    "last_error_reason": "token_invalidated",
                    "last_error_reset_at": 9999999999,
                },
            ]
        },
    }


def write_auth(tmp_path: Path, data=None) -> Path:
    path = tmp_path / "hermes" / "auth.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data or sample_auth(), indent=2), encoding="utf-8")
    return path


def test_list_credentials_marks_active_and_redacts():
    items = list_credentials(sample_auth())
    assert len(items) == 2
    assert items[0].active is True
    assert items[1].active is False
    assert items[0].access_fp and items[0].access_fp != "access-one"
    assert items[1].display_name == "personal"


def test_switch_active_by_number_updates_provider_and_clears_error_markers():
    new_data, selected = switch_active(sample_auth(), "2")
    assert selected.entry_id == "two"
    provider = new_data["providers"]["openai-codex"]
    assert provider["tokens"]["access_token"] == "access-two"
    assert provider["tokens"]["refresh_token"] == "refresh-two"
    # Selected credentials are moved to priority 0 for compatibility with
    # Hermes paths that still consult credential_pool order.
    pool_entry = new_data["credential_pool"]["openai-codex"][0]
    assert pool_entry["id"] == "two"
    assert pool_entry["last_status"] is None
    assert pool_entry["last_error_code"] is None
    assert pool_entry["last_error_reason"] is None
    assert pool_entry["last_error_reset_at"] is None


def test_switch_active_renumbers_pool_priorities_after_reorder():
    data = sample_auth()
    data["credential_pool"]["openai-codex"][0]["priority"] = 0
    data["credential_pool"]["openai-codex"][1]["priority"] = 1

    new_data, selected = switch_active(data, "2")

    assert selected.entry_id == "two"
    pool = new_data["credential_pool"]["openai-codex"]
    assert [(entry["id"], entry["priority"]) for entry in pool] == [("two", 0), ("one", 1)]


def test_switch_active_by_label():
    new_data, selected = switch_active(sample_auth(), "personal")
    assert selected.entry_id == "two"
    assert new_data["providers"]["openai-codex"]["tokens"]["access_token"] == "access-two"


def test_missing_selector_raises():
    with pytest.raises(HSwitchError):
        switch_active(sample_auth(), "nope")


def test_cli_use_writes_backup_and_updates_file(tmp_path):
    auth = write_auth(tmp_path)
    code = main(["--auth-file", str(auth), "use", "2"])
    assert code == 0
    data = load_auth(auth)
    assert data["providers"]["openai-codex"]["tokens"]["access_token"] == "access-two"
    backups = list((auth.parent / "backups" / "hswitch").glob("auth-*.json"))
    assert backups, "expected auth backup under backup folder"


def test_cli_label_then_use_by_label(tmp_path):
    auth = write_auth(tmp_path)
    assert main(["--auth-file", str(auth), "label", "2", "alt"]) == 0
    assert main(["--auth-file", str(auth), "use", "alt"]) == 0
    data = load_auth(auth)
    assert data["credential_pool"]["openai-codex"][0]["label"] == "alt"
    assert data["credential_pool"]["openai-codex"][0]["id"] == "two"
    assert data["providers"]["openai-codex"]["tokens"]["access_token"] == "access-two"


def test_cli_dry_run_does_not_modify(tmp_path):
    auth = write_auth(tmp_path)
    before = auth.read_text()
    assert main(["--auth-file", str(auth), "--dry-run", "use", "2"]) == 0
    assert auth.read_text() == before



def test_cli_legacy_bare_selector_and_list_alias(tmp_path):
    auth = write_auth(tmp_path)
    assert main(["--auth-file", str(auth), "--list"]) == 0
    assert main(["--auth-file", str(auth), "2"]) == 0
    data = load_auth(auth)
    assert data["providers"]["openai-codex"]["tokens"]["access_token"] == "access-two"
    assert data["credential_pool"]["openai-codex"][0]["id"] == "two"


def test_cli_next_switches_from_active_to_next(tmp_path):
    auth = write_auth(tmp_path)
    assert main(["--auth-file", str(auth), "next"]) == 0
    data = load_auth(auth)
    assert data["providers"]["openai-codex"]["tokens"]["access_token"] == "access-two"


def test_cli_accepts_provider_openai_codex_compat_flag(tmp_path):
    auth = write_auth(tmp_path)
    assert main(["--provider", "openai-codex", "--auth-file", str(auth), "current"]) == 0


def test_cli_rejects_unsupported_provider(tmp_path):
    auth = write_auth(tmp_path)
    assert main(["--provider", "other", "--auth-file", str(auth), "list"]) == 2


def test_atomic_backups_are_unique_when_written_quickly(tmp_path):
    auth = write_auth(tmp_path)
    data = load_auth(auth)
    first = atomic_write_auth(data, auth)
    second = atomic_write_auth(data, auth)
    assert first != second
    backups = list((auth.parent / "backups" / "hswitch").glob("auth-*.json"))
    assert len(backups) >= 2



def test_switch_active_resets_provider_metadata_and_copies_token_set():
    data = sample_auth()
    provider = data["providers"]["openai-codex"]
    provider["auth_mode"] = "api_key"
    provider["last_refresh"] = 111
    data["credential_pool"]["openai-codex"][1]["tokens"] = {
        "access_token": "access-two",
        "refresh_token": "refresh-two",
        "id_token": "id-two",
    }
    data["credential_pool"]["openai-codex"][1].pop("access_token")
    data["credential_pool"]["openai-codex"][1].pop("refresh_token")

    new_data, _ = switch_active(data, "2")
    provider = new_data["providers"]["openai-codex"]
    assert provider["auth_mode"] == "chatgpt"
    assert "last_refresh" not in provider
    assert provider["tokens"] == {
        "access_token": "access-two",
        "refresh_token": "refresh-two",
        "id_token": "id-two",
    }


def test_cli_allows_global_options_after_command(tmp_path):
    auth = write_auth(tmp_path)
    before = auth.read_text()
    assert main(["use", "2", "--auth-file", str(auth), "--dry-run"]) == 0
    assert auth.read_text() == before
    assert main(["list", "--auth-file", str(auth), "--json"]) == 0


def test_backups_are_private_even_with_permissive_umask(tmp_path):
    auth = write_auth(tmp_path)
    data = load_auth(auth)
    old_umask = os.umask(0o022)
    try:
        backup = atomic_write_auth(data, auth)
    finally:
        os.umask(old_umask)
    assert backup is not None
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert stat.S_IMODE(backup.parent.stat().st_mode) == 0o700
