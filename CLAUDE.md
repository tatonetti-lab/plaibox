# CLAUDE.md

Plaibox: a Python CLI that manages the lifecycle of vibe-coded projects —
sandbox → projects → archive under `~/plaibox/`, with a `.plaibox.yaml`
metadata file per project, AI-session tracking (`plaibox claude|codex`),
cross-device sync and private projects. README.md is the user-facing spec.

## Stack
- Python ≥3.10 (develop on 3.12), Click CLI, PyYAML. No other runtime deps — keep it that way.
- Shells out to `git` and `gh` for repos, promote and sync.

## Commands
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v                      # all tests
pytest tests/test_sync.py -k private   # one area
```

## Layout
- `src/plaibox/cli.py` — every Click command (`new`, `ls`, `promote`, `archive`,
  `delete`, `unprivate`, `open`, `tidy`, `session`, `import`, `scan`, `sync …`).
- `config.py` (`~/.plaibox/config.yaml`), `metadata.py` (`.plaibox.yaml`),
  `project.py` (moves between spaces), `shell.py` (`plaibox init-shell` hooks:
  auto-cd, venv activation), `sync.py` (cross-device metadata + sandbox repos).
- `tests/` mirrors the modules one-to-one.

## Conventions
- Tests must never touch the real `~/plaibox` or `~/.plaibox`: use the
  `tmp_plaibox_root` and `tmp_config_dir` fixtures and pass `--config`.
- Features start as a design spec and plan in `docs/superpowers/specs/` and
  `docs/superpowers/plans/` (dated `YYYY-MM-DD-name.md`), then land as small commits.
- Conventional Commits: `feat:`, `fix:`, `docs:`; feature branches merge as `feature/<name>`.
- Private projects: code never leaves the machine; only metadata syncs. Any
  change to sync or promote must preserve the `private` flag (see tests/test_sync.py).
- Destructive commands (`delete`) only work from `archive/`; keep it that way.
- Update README.md usage when a command or flag changes.

## Don't
- Edit `src/plaibox.egg-info/` — it's build output (ignored, but older copies are tracked).
