# Changelog

All notable changes to `hermes-plugin-hswitch` are tracked here.

## 0.1.3 - 2026-06-19

- Scrubbed documentation examples to remove real account labels and real token fingerprints.
- Replaced personal maintainer names in package/docs metadata with contributor-neutral text.
- Rebuilt release artifacts from the scrubbed tree.

## 0.1.2 - 2026-06-19

- Reworked README with clearer install paths, examples, safety notes, and development instructions.
- Added `CONTRIBUTING.md` for test, security, and design expectations.
- Added package metadata for topics/classifiers and included docs in the source distribution.
- Updated plugin install notes and GitHub repository about fields/topics.

## 0.1.1 - 2026-06-19

- Fixed credential switching so reordered pool entries also get renumbered `priority` values.
- Added a regression test that catches mismatches between `hswitch current` and `hermes auth list openai-codex`.
- Verified switching round-trips between two OAuth accounts through both standalone `hswitch` and `hermes hswitch`.

## 0.1.0 - 2026-06-07

- Initial public beta.
- Added standalone `hswitch` CLI.
- Added Hermes plugin command registration for `hermes hswitch`.
- Added safe auth-store writes with private backups and redacted token fingerprints.
