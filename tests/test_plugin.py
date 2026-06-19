from __future__ import annotations

import argparse
import importlib.util
import sys
import types
from pathlib import Path

from hermes_hswitch.plugin import _setup_argparse, register


class FakeContext:
    def __init__(self):
        self.commands = {}

    def register_cli_command(self, name, help, setup_fn, handler_fn):
        self.commands[name] = {
            "help": help,
            "setup_fn": setup_fn,
            "handler_fn": handler_fn,
        }


def test_registers_hswitch_cli_command():
    ctx = FakeContext()
    register(ctx)
    assert "hswitch" in ctx.commands
    assert "OpenAI Codex" in ctx.commands["hswitch"]["help"]


def test_directory_plugin_root_imports_without_pip_package(monkeypatch):
    """GitHub-installed Hermes plugins load root __init__.py as a package.

    This catches the easy-to-miss bug where root __init__.py uses
    `from hermes_hswitch...` and only works because the package is installed
    editable during development.
    """
    root = Path(__file__).resolve().parents[1]
    for name in [n for n in sys.modules if n == "hermes_hswitch" or n.startswith("hermes_plugins.hswitch")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    if "hermes_plugins" not in sys.modules:
        ns_pkg = types.ModuleType("hermes_plugins")
        ns_pkg.__path__ = []  # type: ignore[attr-defined]
        ns_pkg.__package__ = "hermes_plugins"
        monkeypatch.setitem(sys.modules, "hermes_plugins", ns_pkg)

    spec = importlib.util.spec_from_file_location(
        "hermes_plugins.hswitch",
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "hermes_plugins.hswitch"
    module.__path__ = [str(root)]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "hermes_plugins.hswitch", module)
    spec.loader.exec_module(module)

    assert callable(module.register)



def test_plugin_argparse_accepts_bare_selector_and_trailing_options(tmp_path):
    auth = tmp_path / "auth.json"
    root = argparse.ArgumentParser(prog="hermes")
    subcommands = root.add_subparsers(dest="command_name")
    hswitch_parser = subcommands.add_parser("hswitch")
    _setup_argparse(hswitch_parser)

    ns = root.parse_args(["hswitch", "2", "--auth-file", str(auth), "--dry-run"])
    assert ns.command_name == "hswitch"
    assert ns.command == "2"
    assert ns.auth_file == str(auth)
    assert ns.dry_run is True
    assert callable(ns.func)
