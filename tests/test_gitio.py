import subprocess
from pathlib import Path

import pytest

from qwen_commit import gitio


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _section(name: str, lines: int) -> str:
    body = "\n".join(f"+line {i} of {name}" for i in range(lines))
    return f"diff --git a/{name} b/{name}\nindex 0000000..1111111 100644\n--- a/{name}\n+++ b/{name}\n@@ -0,0 +1,{lines} @@\n{body}\n"


def test_truncate_diff_leaves_small_diffs_alone():
    diff = _section("small.py", 10)
    assert gitio.truncate_diff(diff, 10000) == diff


def test_truncate_diff_stays_within_budget_and_marks_cuts():
    diff = _section("a.py", 400) + _section("b.py", 400)
    out = gitio.truncate_diff(diff, 4000)
    assert len(out) < len(diff)
    assert out.count("[truncated") == 2
    for line in out.splitlines():
        if "[truncated" not in line:
            assert line in diff


def test_truncate_diff_never_cuts_mid_line():
    diff = _section("a.py", 500)
    out = gitio.truncate_diff(diff, 2000)
    original_lines = set(diff.splitlines())
    for line in out.splitlines():
        assert line in original_lines or line.startswith("... [truncated")


def test_staged_diff_and_commit_roundtrip(repo: Path):
    (repo / "f.txt").write_text("hello\n")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    assert "hello" in gitio.staged_diff()
    gitio.commit_with("feat: add f")
    log = subprocess.run(["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True).stdout
    assert "feat: add f" in log


def test_recent_log_empty_on_fresh_repo(repo: Path):
    assert gitio.recent_log(5) == ""


def test_install_hook_creates_executable_hook(repo: Path):
    hook = gitio.install_hook()
    assert hook.name == "prepare-commit-msg"
    assert hook.exists()
    assert hook.stat().st_mode & 0o111
    assert "qwen-commit" in hook.read_text()


def test_install_hook_backs_up_existing_hook(repo: Path):
    hook_dir = gitio.hooks_dir()
    hook_dir.mkdir(parents=True, exist_ok=True)
    hook = hook_dir / "prepare-commit-msg"
    hook.write_text("#!/bin/sh\nexit 0\n")
    gitio.install_hook()
    backup = hook_dir / "prepare-commit-msg.pre-qwen-commit"
    assert backup.read_text().startswith("#!/bin/sh")
    assert "qwen-commit" in hook.read_text()


def test_install_hook_refuses_when_backup_in_way(repo: Path):
    gitio.install_hook()
    hook_dir = gitio.hooks_dir()
    (hook_dir / "prepare-commit-msg.pre-qwen-commit").write_text("old")
    with pytest.raises(gitio.GitError):
        gitio.install_hook()


def test_hooks_dir_respects_core_hooksPath(repo: Path, monkeypatch):
    custom = repo / "custom-hooks"
    subprocess.run(["git", "config", "core.hooksPath", str(custom)], cwd=repo, check=True)
    assert gitio.hooks_dir() == custom
