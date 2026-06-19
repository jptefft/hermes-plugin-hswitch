"""Directory-plugin shim for Hermes Git installs.

When installed with `hermes plugins install owner/repo`, Hermes imports this file
from `~/.hermes/plugins/hswitch` as a package (`hermes_plugins.hswitch`). The
real implementation lives in `hermes_hswitch` so the same code also works as a
pip entry-point plugin and during local tests.
"""

if __package__:
    from .hermes_hswitch.plugin import register
else:  # pytest/local top-level import of root __init__.py
    from hermes_hswitch.plugin import register

__all__ = ["register"]
