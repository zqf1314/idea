#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run an Idea Radar scout with a switchable DeepSeek/Cloudflare provider.

This wrapper intentionally leaves scouts/scout_lib.py untouched. It selects the
provider from repository variables, injects the selected OpenAI-compatible
configuration, patches the single LLM transport function, and then runs the
requested scout script.
"""
from __future__ import annotations

import json
import os
import runpy
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCOUTS_DIR = REPO_ROOT / "scouts"


def _first(*names: str, default: str = "") -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return default


def _select_provider() -> tuple[str, str, str, str]:
    provider = _first("LLM_PROVIDER", default="deepseek").lower()
    if provider not in {"deepseek", "cloudflare"}:
        raise SystemExit(
            "LLM_PROVIDER must be 'deepseek' or 'cloudflare', got: " + repr(provider)
        )

    if provider == "deepseek":
        base_url = _first(
            "DEEPSEEK_BASE_URL",
            "LEGACY_LLM_BASE_URL",
            default="https://api.deepseek.com",
        )
        api_key = _first("DEEPSEEK_API_KEY", "LEGACY_LLM_API_KEY")
        model = _first(
            "DEEPSEEK_MODEL",
            "LEGACY_LLM_MODEL",
            default="deepseek-v4-flash",
        )
    else:
        base_url = _first("CLOUDFLARE_BASE_URL", "LEGACY_LLM_BASE_URL")
        api_key = _first("CLOUDFLARE_API_KEY", "LEGACY_LLM_API_KEY")
        model = _first(
            "CLOUDFLARE_MODEL",
            "LEGACY_LLM_MODEL",
            default="@cf/zai-org/glm-4.7-flash",
        )

    if not base_url:
        raise SystemExit(f"{provider}: API base URL is empty")
    if not api_key:
        raise SystemExit(f"{provider}: API key is empty")
    if not model:
        raise SystemExit(f"{provider}: model is empty")

    return provider, base_url.rstrip("/"), api_key, model


PROVIDER, BASE_URL, API_KEY, MODEL = _select_provider()

# Preserve the original environment contract expected by scout_lib.py.
os.environ["LLM_BASE_URL"] = BASE_URL
os.environ["LLM_API_KEY"] = API_KEY
os.environ["LLM_MODEL"] = MODEL
# Prevent scout_lib.py from retrying a provider with the unrelated openai/gpt-4o model.
os.environ["LLM_MODEL_FALLBACK"] = MODEL

sys.path.insert(0, str(SCOUTS_DIR))
sys.path.insert(0, str(REPO_ROOT))
import scout_lib as S  # noqa: E402


def provider_llm_chat(
    prompt: str,
    model: str | None = None,
    max_tokens: int = 800,
    temperature: float = 0.0,
    timeout: int = 45,
):
    """OpenAI-compatible chat request with provider-specific compatibility fixes."""
    if S.LLM_DEAD:
        return None

    key = S._llm_key()
    if not key:
        S.LLM_DEAD = "no API key for selected provider"
        return None

    selected_model = model or S._llm_model()
    payload: dict = {
        "model": selected_model,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    if PROVIDER == "deepseek":
        # V4 defaults to thinking mode. The board needs the final JSON directly.
        payload["max_tokens"] = max_tokens
        payload["thinking"] = {"type": "disabled"}
        payload["response_format"] = {"type": "json_object"}
    else:
        # GLM is a reasoning model. Give the final answer room after reasoning and
        # request low reasoning effort for this structured extraction task.
        payload["max_completion_tokens"] = max(max_tokens, 2200)
        payload["response_format"] = {"type": "json_object"}
        if "glm" in selected_model.lower():
            payload["reasoning_effort"] = "low"

    request = urllib.request.Request(
        BASE_URL + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "idea-radar-provider-switch/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=max(timeout, 90)) as response:
            result = json.loads(response.read())
        message = result["choices"][0]["message"]
        content = message.get("content")
        if not content:
            finish_reason = result.get("choices", [{}])[0].get("finish_reason")
            raise RuntimeError(
                f"provider returned empty content (finish_reason={finish_reason!r})"
            )
        return content
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:500]
        except Exception:
            pass
        if exc.code in (401, 403, 404, 410):
            S.LLM_DEAD = (
                f"HTTP {exc.code} from {BASE_URL}; provider/key/model unavailable"
            )
        raise RuntimeError(
            f"HTTP {exc.code} from {PROVIDER}: {detail or exc.reason}"
        ) from exc


S._llm_chat = provider_llm_chat


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: python tools/run_scout_with_provider.py scouts/<name>_scout.py"
        )

    target = (REPO_ROOT / sys.argv[1]).resolve()
    try:
        target.relative_to(SCOUTS_DIR.resolve())
    except ValueError as exc:
        raise SystemExit("target must be inside the scouts directory") from exc
    if not target.is_file():
        raise SystemExit(f"scout file not found: {target}")

    print(f"[llm] provider={PROVIDER} model={MODEL} base={BASE_URL}")
    sys.argv = [str(target)]
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
