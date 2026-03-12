from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()
import os
from typing import Any, Optional

import httpx

DEFAULT_MODEL_NAME = os.getenv("OPENROUTER_MODEL", "stepfun/step-3.5-flash")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")


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

    # Optional but recommended by OpenRouter for attribution
    app_url = os.getenv("OPENROUTER_APP_URL")
    app_name = os.getenv("OPENROUTER_APP_NAME")
    if app_url:
        headers["HTTP-Referer"] = app_url
    if app_name:
        headers["X-Title"] = app_name

    return headers


def _extract_text(resp_json: dict[str, Any]) -> str:
    # OpenAI-compatible: choices[0].message.content
    try:
        return resp_json["choices"][0]["message"]["content"]
    except Exception as e:
        raise OpenRouterError(f"Unexpected response shape: {resp_json!r}") from e


def generate_documentation(prompt_text: str, source_file: str, *, model: Optional[str] = None) -> str:
    model = model or DEFAULT_MODEL_NAME

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a precise technical documentation writer. Output Markdown only."},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.2,
    }

    headers = _build_headers()

    with httpx.Client(timeout=120.0) as client:
        r = client.post(OPENROUTER_API_URL, headers=headers, json=payload)

    if r.status_code >= 400:
        raise OpenRouterError(f"OpenRouter HTTP {r.status_code}: {r.text}")

    text = _extract_text(r.json())
    # Hard guarantee you're getting *something*
    return text.strip()


def generate_repo_documentation(prompt_text: str, *, model: Optional[str] = None) -> str:
    model = model or DEFAULT_MODEL_NAME

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You write high-level repository documentation. Output Markdown only."},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.2,
    }

    headers = _build_headers()

    with httpx.Client(timeout=180.0) as client:
        r = client.post(OPENROUTER_API_URL, headers=headers, json=payload)

    if r.status_code >= 400:
        raise OpenRouterError(f"OpenRouter HTTP {r.status_code}: {r.text}")

    return _extract_text(r.json()).strip()