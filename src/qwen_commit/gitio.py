"""Git interactions: staged diff collection, diff budgeting, hook install."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

MIN_SECTION_CHARS = 800

HOOK_SCRIPT = """#!/bin/sh
# Installed by qwen-commit. Prefills the commit message editor with a locally
# generated suggestion. Delete this file to uninstall.
COMMIT_MSG_FILE="$1"
COMMIT_SOURCE="$2"

case "$COMMIT_SOURCE" in
  message|commit|merge|squash) exit 0 ;;
esac

# Leave the file alone once it holds a real (non-comment) message.
if [ -n "$(grep -v '^#' "$COMMIT_MSG_FILE" 2>/dev/null | tr -d '[:space:]')" ]; then
  exit 0
fi

SUGGESTION="$(qwen-commit 2>/dev/null)" || exit 0
[ -n "$SUGGESTION" ] || exit 0

{
  printf '%s\\n\\n' "$SUGGESTION"
  cat "$COMMIT_MSG_FILE"
} > "$COMMIT_MSG_FILE.tmp" && mv "$COMMIT_MSG_FILE.tmp" "$COMMIT_MSG_FILE"
"""


class GitError(RuntimeError):
    pass


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def staged_diff() -> str:
    return _git("diff", "--cached", "--no-color")


def recent_log(lines: int) -> str:
    try:
        return _git("log", "--oneline", "-n", str(lines)).strip()
    except GitError:
        return ""


def commit_with(message: str) -> str:
    return _git("commit", "-m", message)


def _cut_at_newline(text: str, limit: int, from_end: bool = False) -> str:
    if len(text) <= limit:
        return text
    chunk = text[:limit] if not from_end else text[-limit:]
    cut = chunk.rfind("\n") if not from_end else chunk.find("\n")
    if cut == -1:
        return chunk
    return chunk[:cut] if not from_end else chunk[cut + 1 :]


def truncate_diff(diff: str, max_chars: int) -> str:
    if len(diff) <= max_chars:
        return diff
    sections = re.split(r"(?m)^(?=diff --git )", diff)
    file_sections = [s for s in sections if s.startswith("diff --git")]
    per = max(MIN_SECTION_CHARS, max_chars // max(1, len(file_sections)))
    out = []
    for section in sections:
        if not section.startswith("diff --git") or len(section) <= per:
            out.append(section)
            continue
        head = _cut_at_newline(section, per * 2 // 3)
        tail = _cut_at_newline(section, per - len(head), from_end=True)
        dropped = len(section) - len(head) - len(tail)
        out.append(f"{head}\n... [truncated {dropped} chars] ...\n{tail}")
    return "".join(out)


def hooks_dir() -> Path:
    try:
        custom = _git("config", "core.hooksPath").strip()
    except GitError:
        custom = ""
    if custom:
        return Path(custom).expanduser()
    git_dir = Path(_git("rev-parse", "--git-dir").strip()).resolve()
    return git_dir / "hooks"


def install_hook() -> Path:
    directory = hooks_dir()
    directory.mkdir(parents=True, exist_ok=True)
    hook = directory / "prepare-commit-msg"
    backup = hook.with_name("prepare-commit-msg.pre-qwen-commit")
    if hook.exists():
        if backup.exists():
            raise GitError(
                f"{hook} already exists and {backup} is in the way; merge them by hand"
            )
        shutil.copy2(hook, backup)
    hook.write_text(HOOK_SCRIPT)
    hook.chmod(0o755)
    return hook
