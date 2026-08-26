"""Provider metadata and persisted configuration for AI-assisted translation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import AppSettings


@dataclass(frozen=True)
class TranslationProviderSpec:
    id: str
    name: str
    family: str
    default_model: str
    default_endpoint: str = ""
    endpoint_required: bool = False
    models: tuple[tuple[str, str], ...] = ()


TRANSLATION_PROVIDERS: dict[str, TranslationProviderSpec] = {
    "google": TranslationProviderSpec(
        id="google",
        name="Google Translate",
        family="google",
        default_model="google-free",
        models=(("google-free", "Google Translate miễn phí"),),
    ),
    "openai": TranslationProviderSpec(
        id="openai",
        name="OpenAI",
        family="openai_compatible",
        default_model="gpt-4o-mini",
        default_endpoint="https://api.openai.com/v1",
        models=(
            ("gpt-4o-mini", "GPT-4o mini"),
            ("gpt-4.1-mini", "GPT-4.1 mini"),
        ),
    ),
    "openrouter": TranslationProviderSpec(
        id="openrouter",
        name="OpenRouter",
        family="openai_compatible",
        default_model="openai/gpt-4o-mini",
        default_endpoint="https://openrouter.ai/api/v1",
        models=(
            ("openai/gpt-4o-mini", "OpenAI GPT-4o mini"),
            ("google/gemini-2.0-flash-001", "Google Gemini 2.0 Flash"),
            ("anthropic/claude-3.5-haiku", "Anthropic Claude 3.5 Haiku"),
        ),
    ),
    "nvidia": TranslationProviderSpec(
        id="nvidia",
        name="NVIDIA NIM",
        family="openai_compatible",
        default_model="meta/llama-3.1-8b-instruct",
        default_endpoint="https://integrate.api.nvidia.com/v1",
        models=(
            ("meta/llama-3.1-8b-instruct", "Llama 3.1 8B Instruct"),
            ("nvidia/llama-3.1-nemotron-ultra-253b-v1", "NVIDIA Nemotron Ultra"),
        ),
    ),
    "openai_compatible": TranslationProviderSpec(
        id="openai_compatible",
        name="Endpoint tương thích OpenAI",
        family="openai_compatible",
        default_model="",
        endpoint_required=True,
        models=(("custom", "Model tùy chỉnh"),),
    ),
    "gemini": TranslationProviderSpec(
        id="gemini",
        name="Google Gemini",
        family="gemini",
        default_model="gemini-2.0-flash",
        default_endpoint="https://generativelanguage.googleapis.com/v1beta",
        models=(
            ("gemini-2.0-flash", "Gemini 2.0 Flash"),
            ("gemini-1.5-flash", "Gemini 1.5 Flash"),
        ),
    ),
    "anthropic": TranslationProviderSpec(
        id="anthropic",
        name="Anthropic",
        family="anthropic",
        default_model="claude-3-5-haiku-latest",
        default_endpoint="https://api.anthropic.com",
        models=(
            ("claude-3-5-haiku-latest", "Claude 3.5 Haiku"),
            ("claude-3-7-sonnet-latest", "Claude 3.7 Sonnet"),
        ),
    ),
}

DEFAULT_TRANSLATION_PROVIDER = "google"


@dataclass(frozen=True)
class TranslationConfig:
    provider: str = DEFAULT_TRANSLATION_PROVIDER
    model: str = "google-free"
    endpoint: str = ""
    api_key: str | None = None
    # Direct adapter calls are trusted by tests/connection checks; persisted
    # pipeline configs must be explicitly verified by the user first.
    verified: bool = True

    @property
    def spec(self) -> TranslationProviderSpec:
        return TRANSLATION_PROVIDERS.get(
            self.provider,
            TRANSLATION_PROVIDERS[DEFAULT_TRANSLATION_PROVIDER],
        )

    @property
    def is_usable(self) -> bool:
        """Whether this config can attempt an AI request without unsafe guessing."""
        if self.provider == DEFAULT_TRANSLATION_PROVIDER:
            return False
        if not self.verified or not self.api_key or not self.api_key.strip() or not self.model.strip():
            return False
        return validate_translation_config(
            self.provider,
            self.model,
            self.endpoint,
        ) is None


def normalize_provider(value: Any) -> str:
    provider = str(value or DEFAULT_TRANSLATION_PROVIDER).strip().lower()
    return provider if provider in TRANSLATION_PROVIDERS else DEFAULT_TRANSLATION_PROVIDER


def default_model_for(provider: str) -> str:
    return TRANSLATION_PROVIDERS.get(
        normalize_provider(provider),
        TRANSLATION_PROVIDERS[DEFAULT_TRANSLATION_PROVIDER],
    ).default_model


def default_endpoint_for(provider: str) -> str:
    return TRANSLATION_PROVIDERS.get(
        normalize_provider(provider),
        TRANSLATION_PROVIDERS[DEFAULT_TRANSLATION_PROVIDER],
    ).default_endpoint


def validate_endpoint(endpoint: str) -> bool:
    try:
        parsed = urlparse(endpoint.strip())
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_translation_config(
    provider: str,
    model: str | None,
    endpoint: str | None,
    require_model: bool = True,
    require_endpoint: bool = True,
) -> str | None:
    normalized_provider = str(provider or "").strip().lower()
    spec = TRANSLATION_PROVIDERS.get(normalized_provider)
    if not spec:
        return "Nhà cung cấp dịch AI không được hỗ trợ."

    normalized_model = str(model or "").strip()
    normalized_endpoint = str(endpoint or "").strip()
    if require_model and normalized_provider != DEFAULT_TRANSLATION_PROVIDER and not normalized_model:
        return "Vui lòng chọn hoặc nhập mô hình AI."
    if require_endpoint and normalized_provider == "openai_compatible" and not normalized_endpoint:
        return "Endpoint tùy chỉnh là bắt buộc với nhà cung cấp này."
    if normalized_provider != DEFAULT_TRANSLATION_PROVIDER and normalized_endpoint and not validate_endpoint(normalized_endpoint):
        return "Endpoint phải bắt đầu bằng http:// hoặc https:// và có tên máy chủ hợp lệ."
    return None


async def load_translation_config(session: AsyncSession) -> TranslationConfig:
    """Load AI settings without exposing the secret to API responses or logs."""
    keys = {
        "translation_provider",
        "translation_model",
        "translation_endpoint",
        "translation_key_verified",
        "translation_api_key",
    }
    result = await session.execute(
        select(AppSettings).where(AppSettings.key.in_(keys))
    )
    values = {row.key: row.value for row in result.scalars().all()}

    provider = normalize_provider(values.get("translation_provider"))
    model = str(values.get("translation_model") or default_model_for(provider)).strip()
    endpoint = str(values.get("translation_endpoint") or "").strip()
    api_key = str(values.get("translation_api_key") or "").strip() or None
    verified = str(values.get("translation_key_verified", "false")).lower() == "true"

    # A missing model on a legacy row should never make the pipeline fail.
    if provider != DEFAULT_TRANSLATION_PROVIDER and not model:
        model = default_model_for(provider)

    return TranslationConfig(
        provider=provider,
        model=model,
        endpoint=endpoint,
        api_key=api_key,
        verified=verified,
    )


def mask_api_key_hint(value: str | None) -> str:
    if not value:
        return ""
    return f"••••{value[-4:]}"
