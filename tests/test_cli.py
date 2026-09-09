import json
import os
import stat
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from qwen_commit import cli

CANNED = "feat: add widget parser\n\nHandles nested widgets."
LAST_BODIES: list[dict] = []


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        LAST_BODIES.append(body)
        if self.path.endswith("/api/chat"):
            raw = json.dumps({"message": {"content": CANNED}}).encode()
        else:
            raw = json.dumps({"choices": [{"message": {"content": CANNED}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


@pytest.fixture()
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    httpd.shutdown()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _stage(repo: Path, name: str = "widget.py", content: str = "def parse(x):\n    return x\n"):
    (repo / name).write_text(content)
    subprocess.run(["git", "add", name], cwd=repo, check=True)


def test_suggestion_printed_and_native_ollama_shape(base_url, repo, capsys):
    _stage(repo)
    code = cli.main(["--provider", "ollama", "--base-url", base_url])
    assert code == 0
    assert capsys.readouterr().out.strip() == CANNED
    body = LAST_BODIES[-1]
    assert "Staged diff:" in body["messages"][0]["content"]
    assert body["options"] == {"num_ctx": 8192}
    assert body["stream"] is False


def test_nothing_staged_returns_usage_error(repo, capsys):
    assert cli.main(["--provider", "ollama", "--base-url", "http://127.0.0.1:1/v1"]) == 2
    assert "nothing staged" in capsys.readouterr().err


def test_code_fences_stripped(base_url, repo, capsys, monkeypatch):
    _stage(repo)
    monkeypatch.setattr(cli, "chat", lambda **kw: "```git\nfeat: x\n```")
    assert cli.main(["--provider", "ollama", "--base-url", base_url]) == 0
    assert capsys.readouterr().out.strip() == "feat: x"


def test_commit_flag_creates_commit(base_url, repo, capsys, monkeypatch):
    _stage(repo)
    monkeypatch.setattr(cli, "chat", lambda **kw: CANNED)
    assert cli.main(["--commit", "--provider", "ollama", "--base-url", base_url]) == 0
    log = subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=repo, capture_output=True, text=True).stdout
    assert log.strip() == CANNED


def test_install_hook_then_real_git_commit_uses_suggestion(base_url, repo, capsys, monkeypatch, tmp_path):
    assert cli.main(["--install-hook"]) == 0
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    fake = bin_dir / "qwen-commit"
    fake.write_text("#!/bin/sh\nprintf 'feat: hooked message\\n'\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GIT_EDITOR", "true")
    _stage(repo)
    proc = subprocess.run(["git", "commit", "-q"], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    log = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=repo, capture_output=True, text=True).stdout
    assert log.strip() == "feat: hooked message"


def test_unreachable_server_returns_error(base_url, repo, capsys):
    _stage(repo)
    code = cli.main(["--provider", "ollama", "--base-url", "http://127.0.0.1:1/v1", "--timeout", "2"])
    assert code == 1
    assert "could not reach" in capsys.readouterr().err
