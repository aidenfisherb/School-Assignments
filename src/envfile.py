"""
Loads a local `.env` file into the environment, for running on your own
machine. The GitHub Actions workflow never has a .env (it's git-ignored);
there, the same names come from repo secrets and variables instead.

Variables already set in the environment always win, so a .env can never
override what the workflow (or your terminal) provides.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: Path = Path(".env")) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if name and name not in os.environ:
            os.environ[name] = value
