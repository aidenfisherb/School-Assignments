"""Tests for src/envfile.py."""

import os

from src.envfile import load_env_file


def test_loads_values_and_skips_comments(tmp_path, monkeypatch):
    for name in ("ENVTEST_A", "ENVTEST_B", "ENVTEST_C"):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"
    env.write_text('# comment\nENVTEST_A=plain\nENVTEST_B="quoted value"\n\nexport ENVTEST_C=x=y\n')
    load_env_file(env)
    assert os.environ["ENVTEST_A"] == "plain"
    assert os.environ["ENVTEST_B"] == "quoted value"
    assert os.environ["ENVTEST_C"] == "x=y"


def test_existing_environment_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVTEST_A", "from-terminal")
    env = tmp_path / ".env"
    env.write_text("ENVTEST_A=from-file\n")
    load_env_file(env)
    assert os.environ["ENVTEST_A"] == "from-terminal"


def test_missing_file_is_fine(tmp_path):
    load_env_file(tmp_path / "nope.env")
