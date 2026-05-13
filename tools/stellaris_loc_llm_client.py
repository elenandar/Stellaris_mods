#!/usr/bin/env python3
"""OpenAI-compatible LLM client for Stellaris batch translation."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Callable


FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def add_llm_cli_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--base-url", help="OpenAI-compatible API base URL.")
    parser.add_argument("--api-key", help="API key for the OpenAI-compatible endpoint.")
    parser.add_argument("--model", help="Model name.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature.")
    parser.add_argument("--timeout", type=int, default=120, help="HTTP request timeout in seconds.")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retry count.")
    return parser


def resolve_llm_config(
    base_url: str | None,
    api_key: str | None,
    model: str | None,
) -> tuple[str, str, str]:
    resolved_base_url = base_url or os.environ.get("LLM_BASE_URL", "")
    resolved_api_key = api_key or os.environ.get("LLM_API_KEY", "")
    resolved_model = model or os.environ.get("LLM_MODEL", "")

    missing: list[str] = []
    if not resolved_base_url:
        missing.append("base_url/LLM_BASE_URL")
    if not resolved_api_key:
        missing.append("api_key/LLM_API_KEY")
    if not resolved_model:
        missing.append("model/LLM_MODEL")

    if missing:
        raise ValueError("Missing LLM configuration: " + ", ".join(missing))

    return resolved_base_url, resolved_api_key, resolved_model


def extract_json_array_from_response(text: str) -> list[dict[str, Any]]:
    """Extract a JSON array from plain JSON or fenced markdown response content."""
    candidates: list[str] = []
    stripped = text.strip()
    if stripped:
        candidates.append(stripped)

    for match in FENCED_JSON_RE.finditer(text):
        candidate = match.group(1).strip()
        if candidate:
            candidates.append(candidate)

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end >= start:
        candidate = text[start : end + 1].strip()
        if candidate:
            candidates.append(candidate)

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)

        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, list):
            return payload

    raise ValueError("Could not extract a valid JSON array from LLM response.")


def _extract_message_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM response is missing choices.")

    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("LLM response is missing message content.")

    content = message.get("content")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts)

    raise ValueError("Unsupported LLM response content format.")


def _default_request_chat_completion(
    *,
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def translate_batch_with_llm(
    batch_items: list[dict],
    model: str,
    base_url: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    timeout: int = 120,
    max_retries: int = 3,
    request_func: Callable[..., dict[str, Any]] | None = None,
) -> list[dict]:
    """Translate a batch using an OpenAI-compatible /chat/completions API."""
    del batch_items

    requester = request_func or _default_request_chat_completion
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response_payload = requester(
                base_url=base_url,
                api_key=api_key,
                payload=payload,
                timeout=timeout,
            )
            message_text = _extract_message_text(response_payload)
            return extract_json_array_from_response(message_text)
        except (
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
            urllib.error.URLError,
            urllib.error.HTTPError,
        ) as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(min(2 ** (attempt - 1), 8))

    raise RuntimeError(f"LLM translation failed after {max_retries} attempts: {last_error}")
