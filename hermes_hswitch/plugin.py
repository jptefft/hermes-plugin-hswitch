"""Hermes plugin registration for hswitch."""

from __future__ import annotations

from .cli import build_parser, run
from .core import __version__


def _setup_argparse(subparser):
    build_parser(subparser)
    subparser.set_defaults(func=_handler)


def _handler(args):
    code = run(args)
    if code:
        raise SystemExit(code)


def register(ctx):
    """Register `hermes hswitch ...` as a Hermes plugin CLI command."""
    ctx.register_cli_command(
        name="hswitch",
        help="Switch active OpenAI Codex OAuth credential safely",
        setup_fn=_setup_argparse,
        handler_fn=_handler,
    )


__all__ = ["register", "__version__"]
