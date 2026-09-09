"""Qwen text-model endpoints: provider presets plus OpenAI-compatible and
Ollama-native wire formats (stdlib only)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Mapping

PROVIDERS = {
    "dashscope": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "model": "qwen3-coder-plus",
    },
    "modelscope": {
        "base_url": "https://api-inference.modelscope.cn/v1",
        "model": "Qwen/Qwen3-8B",
    },
    "ollama": {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen3:4b",
    },
}

API_KEY_ENV_VARS = ("QWEN_API_KEY", "DASHSCOPE_API_KEY", "MODELSCOPE_API_KEY")

DEFAULT_OLLAMA_NUM_CTX = 8192


class UnknownProvider(KeyError):
    pass


class APIError(RuntimeError):
    pass


def resolve_config(
    *,
    provider: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> tuple[str, str, str, str | None]:
    env = os.environ if environ is None else environ
    name = provider or env.get("QWEN_PROVIDER") or "dashscope"
    if name not in PROVIDERS:
        raise UnknownProvider(f"unknown provider: {name}")
    defaults = PROVIDERS[name]
    if provider or env.get("QWEN_PROVIDER"):
        resolved_base = base_url or defaults["base_url"]
        resolved_model = model or defaults["model"]
    else:
        resolved_base = base_url or env.get("QWEN_BASE_URL") or defaults["base_url"]
        resolved_model = model or env.get("QWEN_MODEL") or defaults["model"]
    resolved_key = api_key
    if not resolved_key:
        for var in API_KEY_ENV_VARS:
            if env.get(var):
                resolved_key = env[var]
                break
    return name, resolved_base, resolved_model, resolved_key


def _post(url: str, payload: dict, api_key: str | None, timeout: float) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        raise APIError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise APIError(f"could not reach {url}: {exc.reason}") from exc


def strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def chat(
    *,
    base_url: str,
    api_key: str | None,
    model: str,
    system: str,
    user: str,
    timeout: float = 120.0,
    options: dict | None = None,
    wire: str = "openai",
) -> str:
    content = f"{system}\n\n{user}"
    if wire == "ollama":
        # Ollama's OpenAI-compatible layer ignores options.num_ctx; native honors it.
        payload: dict = {
            "model": model,
            "stream": False,
            "messages": [{"role": "user", "content": content}],
        }
        if options:
            payload["options"] = dict(options)
        url = base_url.rstrip("/")
        if url.endswith("/v1"):
            url = url[: -len("/v1")]
        body = _post(f"{url}/api/chat", payload, api_key, timeout)
        try:
            return strip_fences(body["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise APIError(f"unexpected response shape: {json.dumps(body)[:300]}") from exc
    payload = {
        "model": model,
        "stream": False,
        "messages": [{"role": "user", "content": content}],
    }
    if options:
        payload["options"] = dict(options)
    body = _post(f"{base_url.rstrip('/')}/chat/completions", payload, api_key, timeout)
    try:
        return strip_fences(body["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise APIError(f"unexpected response shape: {json.dumps(body)[:300]}") from exc
