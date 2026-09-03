"""Small, dependency-free adapters for common text-generation APIs."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.translation_config import TranslationConfig

logger = logging.getLogger(__name__)
AI_TRANSLATION_TIMEOUT_SECONDS = 20

TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional subtitle translator for short-form vertical videos. "
    "Your job is to translate each cue so the result fits comfortably on a "
    "single line in the target language without overflowing the screen.\n\n"
    "RULES (strictly follow every rule):\n"
    "1) Keep each translated cue SHORT. Aim for 18-32 characters per line in the "
    "target language, and never exceed ~40 characters in a single cue unless the "
    "source itself is unavoidably longer. If a translation is too long, split it "
    "into two shorter phrases separated by ' / ' on the same cue, or drop filler "
    "words (very, really, just, you know, kind of, sort of, like, actually, "
    "basically, I think, I mean, um, uh, hmm, ...).\n"
    "2) Preserve every marker like <<<12>>> exactly once and in the same order. "
    "Do not add, remove, rename, renumber, or reorder markers. Every marker in "
    "the input must appear exactly once in the output.\n"
    "3) Translate the MEANING, not the words. Use natural, spoken language that a "
    "native speaker would actually say. Do NOT translate word-by-word.\n"
    "4) For Chinese, you may use 1-2 short idioms ONLY if they fit the character "
    "budget; never add idioms that exceed it.\n"
    "5) Do NOT add explanations, options, notes, quotation marks, or extra lines. "
    "Return only the translated cues, one per line, each starting with its marker.\n"
    "6) Do NOT translate stage directions, on-screen text labels, watermarks, "
    "channel names, or proper nouns (brand names, platform names, usernames).\n"
    "7) Do NOT soften or censor policy/compliance/promotion content; translate it "
    "as the speaker intends, but keep it within the character budget.\n"
    "8) If a marker has no translatable text, still output the marker followed by "
    "an empty line so timing is preserved."
)


def _build_messages(block: str, source: str, target: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Source language: {source}\n"
                f"Target language: {target}\n\n"
                "Translate this marked subtitle passage:\n"
                f"{block}"
            ),
        },
    ]


def _request_json(
    provider: str,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: int = AI_TRANSLATION_TIMEOUT_SECONDS,
) -> dict[str, Any] | None:
    """POST JSON while keeping headers, API keys, and response bodies out of logs."""
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except HTTPError as exc:
        logger.warning("AI provider %s returned HTTP %s", provider, exc.code)
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        logger.warning("AI provider %s request failed", provider)
    except Exception:
        # Provider SDKs and proxies can return unexpected payload types. The
        # pipeline must still use Google Translate rather than fail the job.
        logger.warning("AI provider %s returned an unexpected response", provider)
    return None


def _request_json_get(
    provider: str,
    url: str,
    headers: dict[str, str],
) -> dict[str, Any] | None:
    """GET JSON for model discovery without logging credentials or response data."""
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=AI_TRANSLATION_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except HTTPError as exc:
        logger.warning("AI provider %s model discovery returned HTTP %s", provider, exc.code)
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        logger.warning("AI provider %s model discovery failed", provider)
    except Exception:
        logger.warning("AI provider %s model discovery returned an unexpected response", provider)
    return None


def _normalize_discovered_models(items: Any) -> list[dict[str, str]]:
    """Convert provider model records to a small, safe UI-facing shape."""
    if not isinstance(items, list):
        return []

    excluded_terms = ("embedding", "moderation", "whisper", "tts", "image", "audio")
    models: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, str):
            model_id = item.strip()
            display_name = model_id
        elif isinstance(item, dict):
            model_id = str(item.get("id") or item.get("name") or "").strip()
            display_name = str(
                item.get("displayName") or item.get("name")
                or item.get("display_name") or model_id
            ).strip()
        else:
            continue
        if model_id.startswith("models/"):
            model_id = model_id.removeprefix("models/")
        if not model_id or model_id in seen:
            continue
        if any(term in model_id.lower() for term in excluded_terms):
            continue
        seen.add(model_id)
        models.append({"id": model_id, "name": display_name or model_id, "source": "discovered"})
        if len(models) >= 100:
            break
    return models


def discover_translation_models(config: TranslationConfig) -> tuple[list[dict[str, str]], str]:
    """Authenticate and return model choices without exposing provider secrets."""
    if not config.api_key or config.provider == "google":
        return [], ""

    try:
        if config.spec.family == "openai_compatible":
            if not (config.endpoint or config.spec.default_endpoint):
                return [], ""
            endpoint = (config.endpoint or config.spec.default_endpoint).rstrip("/")
            data = _request_json_get(
                config.provider,
                f"{endpoint}/models",
                {"Authorization": f"Bearer {config.api_key}"},
            )
            models = _normalize_discovered_models(data.get("data") if data else None)
            return models, "discovered" if models else ""

        if config.spec.family == "gemini":
            if not (config.endpoint or config.spec.default_endpoint):
                return [], ""
            endpoint = (config.endpoint or config.spec.default_endpoint).rstrip("/")
            data = _request_json_get(
                config.provider,
                f"{endpoint}/models",
                {"x-goog-api-key": config.api_key or ""},
            )
            candidates = data.get("models") if data else None
            supported = [
                item for item in candidates or []
                if isinstance(item, dict)
                and "generateContent" in (item.get("supportedGenerationMethods") or [])
            ]
            models = _normalize_discovered_models(supported)
            return models, "discovered" if models else ""

        if config.spec.family == "anthropic":
            if not config.model.strip():
                return [], ""
            probe = _translate_anthropic(
                config,
                "<<<0>>> This is a translation connection test.",
                "en",
                "vi",
            )
            if probe and probe.count("<<<0>>>") == 1:
                models = [
                    {"id": model_id, "name": name, "source": "curated"}
                    for model_id, name in config.spec.models
                ]
                return models, "curated"
    except Exception:
        logger.warning("AI provider %s model discovery adapter failed", config.provider)

    return [], ""


def _extract_openai_content(data: dict[str, Any]) -> str | None:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        text = "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
        return text.strip() or None
    return None


def _translate_openai_compatible(
    config: TranslationConfig,
    block: str,
    source: str,
    target: str,
    timeout_seconds: int = AI_TRANSLATION_TIMEOUT_SECONDS,
) -> str | None:
    endpoint = (config.endpoint or config.spec.default_endpoint).rstrip("/")
    if not endpoint:
        return None
    data = _request_json(
        config.provider,
        f"{endpoint}/chat/completions",
        {
            "model": config.model,
            "messages": _build_messages(block, source, target),
            "temperature": 0.1,
        },
        {"Authorization": f"Bearer {config.api_key}"},
        timeout_seconds,
    )
    return _extract_openai_content(data) if data else None


def _extract_gemini_content(data: dict[str, Any]) -> str | None:
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return None
    text = "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    )
    return text.strip() or None


def _translate_gemini(
    config: TranslationConfig,
    block: str,
    source: str,
    target: str,
    timeout_seconds: int = AI_TRANSLATION_TIMEOUT_SECONDS,
) -> str | None:
    endpoint = (config.endpoint or config.spec.default_endpoint).rstrip("/")
    if not endpoint or not config.api_key:
        return None
    url = f"{endpoint}/models/{quote(config.model, safe='')}:generateContent"
    data = _request_json(
        config.provider,
        url,
        {
            "systemInstruction": {"parts": [{"text": TRANSLATION_SYSTEM_PROMPT}]},
            "contents": [{
                "role": "user",
                "parts": [{
                    "text": (
                        f"Source language: {source}\n"
                        f"Target language: {target}\n\n"
                        f"Translate this marked subtitle passage:\n{block}"
                    ),
                }],
            }],
            "generationConfig": {"temperature": 0.1},
        },
        {"x-goog-api-key": config.api_key},
        timeout_seconds,
    )
    return _extract_gemini_content(data) if data else None


def _extract_anthropic_content(data: dict[str, Any]) -> str | None:
    content = data.get("content")
    if not isinstance(content, list):
        return None
    text = "".join(
        part.get("text", "")
        for part in content
        if isinstance(part, dict) and part.get("type") == "text"
        and isinstance(part.get("text"), str)
    )
    return text.strip() or None


def _translate_anthropic(
    config: TranslationConfig,
    block: str,
    source: str,
    target: str,
    timeout_seconds: int = AI_TRANSLATION_TIMEOUT_SECONDS,
) -> str | None:
    endpoint = (config.endpoint or config.spec.default_endpoint).rstrip("/")
    if not endpoint or not config.api_key:
        return None
    # The output must hold every translated cue of the passage, so the token
    # budget scales with its size instead of clipping long files mid-response.
    max_tokens = min(8192, max(2048, len(block) // 2))
    data = _request_json(
        config.provider,
        f"{endpoint}/v1/messages",
        {
            "model": config.model,
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "system": TRANSLATION_SYSTEM_PROMPT,
            "messages": [{
                "role": "user",
                "content": (
                    f"Source language: {source}\n"
                    f"Target language: {target}\n\n"
                    f"Translate this marked subtitle passage:\n{block}"
                ),
            }],
        },
        {
            "x-api-key": config.api_key,
            "anthropic-version": "2023-06-01",
        },
        timeout_seconds,
    )
    return _extract_anthropic_content(data) if data else None


def translate_marked_block(
    config: TranslationConfig,
    block: str,
    source: str,
    target: str,
    timeout_seconds: int = AI_TRANSLATION_TIMEOUT_SECONDS,
) -> str | None:
    """Translate one marked block, returning None for any provider failure."""
    if not config.is_usable:
        return None
    try:
        if config.spec.family == "openai_compatible":
            return _translate_openai_compatible(config, block, source, target, timeout_seconds)
        if config.spec.family == "gemini":
            return _translate_gemini(config, block, source, target, timeout_seconds)
        if config.spec.family == "anthropic":
            return _translate_anthropic(config, block, source, target, timeout_seconds)
    except Exception:
        logger.warning("AI provider %s adapter failed", config.provider)
    return None
