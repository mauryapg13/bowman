"""llm.py — the one HTTP seam for both ports. Provider chosen by environment.

  OPENROUTER_API_KEY  -> OpenAI-compatible chat completions at openrouter.ai (stdlib urllib)
  ANTHROPIC_API_KEY   -> Anthropic Messages API via the official SDK
Returns (text, input_tokens, output_tokens, provider, model). Every call is
timeout-bounded and retried on 429/5xx. Ports never read the environment
themselves beyond the model-name override.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "z-ai/glm-5.3-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
TIMEOUT_S = 90
RETRIES = 3


class LLMError(Exception):
    pass


def provider() -> str | None:
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def default_model(prov: str) -> str:
    return DEFAULT_OPENROUTER_MODEL if prov == "openrouter" else DEFAULT_ANTHROPIC_MODEL


def complete(system: str, text: str, image_png: bytes | None = None, model: str | None = None,
             max_tokens: int = 1024) -> tuple[str, int, int, str, str]:
    prov = provider()
    if prov is None:
        raise LLMError("no OPENROUTER_API_KEY / ANTHROPIC_API_KEY in the environment")
    model = model or default_model(prov)
    if prov == "openrouter":
        return _openrouter(system, text, image_png, model, max_tokens)
    return _anthropic(system, text, image_png, model, max_tokens)


def _openrouter(system: str, text: str, image_png: bytes | None, model: str, max_tokens: int):
    content: list[dict] = []
    if image_png is not None:
        content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.standard_b64encode(image_png).decode()}})
    content.append({"type": "text", "text": text})
    body = json.dumps({"model": model, "max_tokens": max_tokens, "temperature": 0,
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}).encode()
    req = urllib.request.Request(OPENROUTER_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/mauryapg13/bowman", "X-Title": "bowman buy-or-wait"})
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode())
            choice = data["choices"][0]["message"]
            txt = choice.get("content") or ""
            if isinstance(txt, list):                     # some providers return content parts
                txt = "".join(p.get("text", "") for p in txt if isinstance(p, dict))
            u = data.get("usage", {}) or {}
            return txt, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)), "openrouter", model
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504) and attempt < RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            raise LLMError(f"openrouter HTTP {e.code}: {e.read()[:300]!r}") from e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as e:
            last = e
            if attempt < RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
    raise LLMError(f"openrouter failed after {RETRIES} attempts: {last!r}")


def _anthropic(system: str, text: str, image_png: bytes | None, model: str, max_tokens: int):
    try:
        import anthropic
    except ImportError as e:
        raise LLMError("anthropic SDK not installed (pip install anthropic)") from e
    client = anthropic.Anthropic()
    content: list[dict] = []
    if image_png is not None:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                     "data": base64.standard_b64encode(image_png).decode()}})
    content.append({"type": "text", "text": text})
    resp = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                  messages=[{"role": "user", "content": content}])
    txt = "".join(b.text for b in resp.content if b.type == "text")
    return txt, resp.usage.input_tokens, resp.usage.output_tokens, "anthropic", model
