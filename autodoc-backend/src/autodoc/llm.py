from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()
import os
import re
import time
from typing import Any, Optional

import httpx

from autodoc.models import GenerationUsage

DEFAULT_MODEL_NAME = os.getenv("OPENROUTER_MODEL", "stepfun/step-3.5-flash")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")

# Cost per 1K tokens: (prompt_cost, completion_cost)
COST_PER_1K_TOKENS: dict[str, tuple[float, float]] = {
    "stepfun/step-3.5-flash": (0.0001, 0.0002),
    "anthropic/claude-sonnet-4-5": (0.003, 0.015),
    "__default__": (0.001, 0.002),
}

MAX_RETRIES = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}


class OpenRouterError(RuntimeError):
    pass


def _build_headers() -> dict[str, str]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterError("Missing OPENROUTER_API_KEY environment variable")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    app_url = os.getenv("OPENROUTER_APP_URL")
    app_name = os.getenv("OPENROUTER_APP_NAME")
    if app_url:
        headers["HTTP-Referer"] = app_url
    if app_name:
        headers["X-Title"] = app_name

    return headers


def _extract_text(resp_json: dict[str, Any]) -> str:
    try:
        return resp_json["choices"][0]["message"]["content"]
    except Exception as e:
        raise OpenRouterError(f"Unexpected response shape: {resp_json!r}") from e


def _extract_usage(resp_json: dict[str, Any], model: str, prompt_text: str) -> GenerationUsage:
    usage = resp_json.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", max(1, len(prompt_text) // 4))
    completion_tokens = usage.get("completion_tokens", 0)

    costs = COST_PER_1K_TOKENS.get(model, COST_PER_1K_TOKENS["__default__"])
    estimated_cost = (prompt_tokens / 1000 * costs[0]) + (completion_tokens / 1000 * costs[1])

    return GenerationUsage(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_usd=estimated_cost,
    )


def _post_with_retry(payload: dict, headers: dict, timeout: float) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            if r.status_code in RETRY_STATUSES:
                wait = 2 ** attempt
                time.sleep(wait)
                last_error = OpenRouterError(f"OpenRouter HTTP {r.status_code}: {r.text}")
                continue
            if r.status_code >= 400:
                raise OpenRouterError(f"OpenRouter HTTP {r.status_code}: {r.text}")
            return r.json()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            wait = 2 ** attempt
            time.sleep(wait)
            last_error = e
            continue
    raise OpenRouterError(f"Failed after {MAX_RETRIES} attempts") from last_error


def generate_documentation(
    prompt_text: str,
    source_file: str,
    *,
    model: Optional[str] = None,
) -> tuple[str, GenerationUsage]:
    model = model or DEFAULT_MODEL_NAME

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": (
                "You are an expert technical documentation engineer. Your job is to write accurate, grounded documentation from source code.\n\n"
                "Rules:\n"
                "- Output Markdown only. No preamble, no apologies, no meta-commentary.\n"
                "- Only describe behaviour that is EXPLICITLY present in the provided code. Never invent APIs, parameters, or behaviours.\n"
                "- Every claim about the code must be traceable to a specific file or diff shown to you.\n"
                "- If the code is ambiguous or incomplete, say so explicitly rather than guessing."
            )},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.2,
    }

    headers = _build_headers()
    resp_json = _post_with_retry(payload, headers, timeout=120.0)
    text = _extract_text(resp_json)
    usage = _extract_usage(resp_json, model, prompt_text)
    return text.strip(), usage


def call_llm_json(prompt: str, model: Optional[str] = None) -> dict | list | None:
    """Call LLM expecting JSON response. Returns parsed object or None on failure."""
    model = model or DEFAULT_MODEL_NAME

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return valid JSON only. No markdown, no explanation."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }

    headers = _build_headers()
    try:
        resp_json = _post_with_retry(payload, headers, timeout=60.0)
        text = _extract_text(resp_json).strip()
        # Try direct parse first
        import json
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Fallback: extract first JSON object/array from text
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            return json.loads(m.group())
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            return json.loads(m.group())
        return None
    except Exception:
        return None


def generate_repo_documentation(prompt_text: str, *, model: Optional[str] = None) -> str:
    model = model or DEFAULT_MODEL_NAME

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": (
                "You are a senior software architect writing onboarding documentation.\n"
                "Output Markdown only. Synthesise the unit docs into a high-level overview — do not repeat them verbatim.\n"
                "Focus on: purpose, architecture, key entry points, and how a new contributor navigates the codebase."
            )},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.2,
    }

    headers = _build_headers()
    resp_json = _post_with_retry(payload, headers, timeout=180.0)
    return _extract_text(resp_json).strip()
