from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json

from app.core.translation_config import (
    DEFAULT_TRANSLATION_PROVIDER,
    TranslationConfig,
    default_model_for,
    load_translation_config,
    mask_api_key_hint,
    normalize_provider,
    validate_translation_config,
)
from app.core.translation_providers import discover_translation_models, translate_marked_block
from app.core.translator import _extract_marked_translations
from app.models.database import get_session, AppSettings

router = APIRouter()

DEFAULT_BLUR_HEIGHT_RATIO = 0.24
DEFAULT_BLUR_STRENGTH = 34
DEFAULT_BLUR_STEPS = 2
DEFAULT_SUBTITLE_POSITION_Y = 0.94
DEFAULT_BLUR_REGION = {
    "x": 0.0,
    "y": 0.76,
    "width": 1.0,
    "height": 0.24,
}
SUBTITLE_POSITION_Y_BY_PRESET = {
    "top": 0.1,
    "center": 0.5,
    "bottom": DEFAULT_SUBTITLE_POSITION_Y,
}


def _clamp_unit(value: Any, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    if numeric != numeric:  # NaN
        numeric = default
    return min(max(numeric, 0.0), 1.0)


def _normalize_blur_region(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return dict(DEFAULT_BLUR_REGION)

    width = min(max(_clamp_unit(value.get("width"), 1.0), 0.02), 1.0)
    height = min(max(_clamp_unit(value.get("height"), 0.24), 0.02), 1.0)
    x = min(_clamp_unit(value.get("x"), 0.0), 1.0 - width)
    y = min(_clamp_unit(value.get("y"), 0.76), 1.0 - height)
    return {"x": x, "y": y, "width": width, "height": height}


def _position_y_from_config(config: Dict[str, Any], position: str) -> float:
    raw_position_y = config.get("position_y")
    if raw_position_y is None and (position == "custom" or config.get("use_custom_position")):
        raw_position_y = config.get("custom_y")
    return _clamp_unit(
        raw_position_y,
        SUBTITLE_POSITION_Y_BY_PRESET.get(position, DEFAULT_SUBTITLE_POSITION_Y),
    )


DEFAULT_SETTINGS = {
    "whisper_model": "small",
    "default_target_lang": "vi",
    "default_voice": "vi-VN-HoaiMyNeural",
    "tts_speed": "1.0",
    "default_source_lang": "en",
    "notifications_enabled": "true",
    "default_dubbing_volume": "2.0",
    "default_background_volume": "1.0",
    "default_original_volume": "0.1",
    "subtitle_enabled": "false",
    "subtitle_position": "bottom",
    "subtitle_position_y": str(DEFAULT_SUBTITLE_POSITION_Y),
    "subtitle_size": "13",
    "subtitle_color": "white",
    "blur_existing_subtitles": "false",
    "translation_provider": DEFAULT_TRANSLATION_PROVIDER,
    "translation_model": "google-free",
    "translation_endpoint": "",
    "translation_key_verified": "false",
    "translation_models": "[]",
    # This value is write-only and is removed from GET /api/settings responses.
    "translation_api_key": "",
}

# Subtitle font size is stored as a pixel value. Old presets saved the
# string keys "small"/"medium"/"large"; those map to these defaults.
SUBTITLE_SIZE_PRESETS = {"small": 13, "medium": 18, "large": 24}
SUBTITLE_SIZE_MIN = 10
SUBTITLE_SIZE_MAX = 40

# Preset keys in database
PRESET_KEY_PREFIX = "user_preset_"


def _parse_subtitle_config(config_str: str) -> Dict[str, Any]:
    """Parse saved subtitle settings without losing custom coordinates."""
    defaults = {
        "position": "bottom",
        "position_y": DEFAULT_SUBTITLE_POSITION_Y,
        "size": "13",
        "color": "white",
        "blur_existing_subtitles": False,
        "blur_region": dict(DEFAULT_BLUR_REGION),
        "blur_height_ratio": DEFAULT_BLUR_HEIGHT_RATIO,
        "blur_strength": DEFAULT_BLUR_STRENGTH,
        "blur_steps": DEFAULT_BLUR_STEPS,
    }
    if not config_str:
        return defaults
    try:
        config = json.loads(config_str)
        if not isinstance(config, dict):
            return defaults

        # Subtitle font size is stored as a pixel value. Old presets saved the
        # string keys "small"/"medium"/"large"; map those to pixel defaults.
        raw_size = config.get("size", config.get("font_size"))
        if isinstance(raw_size, str):
            size = str(SUBTITLE_SIZE_PRESETS.get(raw_size.lower(), 13))
        elif isinstance(raw_size, (int, float)):
            size = str(int(max(SUBTITLE_SIZE_MIN, min(SUBTITLE_SIZE_MAX, int(raw_size)))))
        else:
            size = "13"

        position = str(config.get("position") or "bottom")

        # Map font_color to color name. Accept the older color-name field too.
        font_color = str(config.get("font_color", "#FFFFFF")).upper().lstrip("#")
        color_map_reverse = {
            "FFFFFF": "white",
            "FFD700": "yellow",
            "00FFFF": "cyan",
            "FF4444": "red",
        }
        color = color_map_reverse.get(font_color, str(config.get("color") or "white"))
        if color not in color_map_reverse.values():
            color = "white"

        blur_existing = config.get("blur_existing_subtitles", False)
        if isinstance(blur_existing, str):
            blur_existing = blur_existing.lower() in {"1", "true", "yes", "on"}

        return {
            "position": position,
            "position_y": _position_y_from_config(config, position),
            "size": size,
            "color": color,
            "blur_existing_subtitles": bool(blur_existing),
            "blur_region": _normalize_blur_region(config.get("blur_region")),
            "blur_height_ratio": DEFAULT_BLUR_HEIGHT_RATIO,
            "blur_strength": DEFAULT_BLUR_STRENGTH,
            "blur_steps": DEFAULT_BLUR_STEPS,
        }
    except (TypeError, ValueError, json.JSONDecodeError):
        return defaults


def _build_subtitle_config(
    position: str,
    size: str,
    color: str,
    blur_existing_subtitles: bool = False,
    position_y: Optional[float] = None,
    blur_region: Optional[Dict[str, Any]] = None,
) -> str:
    """Build subtitle settings while preserving the editor's custom geometry."""
    # Font size is stored as a numeric pixel value. Old presets map to defaults.
    if isinstance(size, str) and size.lower() in SUBTITLE_SIZE_PRESETS:
        font_size = SUBTITLE_SIZE_PRESETS[size.lower()]
    else:
        try:
            font_size = int(size)
            font_size = max(SUBTITLE_SIZE_MIN, min(SUBTITLE_SIZE_MAX, font_size))
        except (TypeError, ValueError):
            font_size = 13
    color_map = {
        "white": "#FFFFFF",
        "yellow": "#FFD700",
        "cyan": "#00FFFF",
        "red": "#FF4444",
    }
    normalized_position = str(position or "bottom")
    fallback_y = 0.9 if normalized_position == "custom" else SUBTITLE_POSITION_Y_BY_PRESET.get(
        normalized_position,
        DEFAULT_SUBTITLE_POSITION_Y,
    )
    normalized_y = _clamp_unit(position_y, fallback_y)
    normalized_region = _normalize_blur_region(blur_region)
    config = {
        "enabled": True,
        "font_family": "Arial",
        "font_size": font_size,
        "font_color": color_map.get(color, "#FFFFFF"),
        "outline_color": "#000000",
        "outline_width": 2,
        "shadow_enabled": False,
        "shadow_color": "#000000",
        "shadow_offset_x": 2,
        "shadow_offset_y": 2,
        "back_color": "#E6E6E6",
        "back_opacity": 0.1,
        "position": normalized_position,
        "position_y": normalized_y,
        "margin_v": 20,
        "margin_l": 20,
        "margin_r": 20,
        "alignment": 2,
        "custom_x": 0.5,
        "custom_y": normalized_y,
        "use_custom_position": normalized_position == "custom",
        "blur_existing_subtitles": blur_existing_subtitles,
        "blur_region": normalized_region,
        "blur_height_ratio": DEFAULT_BLUR_HEIGHT_RATIO,
        "blur_strength": DEFAULT_BLUR_STRENGTH,
        "blur_steps": DEFAULT_BLUR_STEPS,
        "animation_speed": 1.0,
        "text_overlays": [],
        "image_overlays": [],
    }
    return json.dumps(config)


class SettingsUpdate(BaseModel):
    whisper_model: Optional[str] = None
    default_source_lang: Optional[str] = None
    default_target_lang: Optional[str] = None
    default_voice: Optional[str] = None
    tts_speed: Optional[float] = None
    notifications_enabled: Optional[bool] = None
    default_dubbing_volume: Optional[float] = None
    default_background_volume: Optional[float] = None
    default_original_volume: Optional[float] = None
    subtitle_enabled: Optional[bool] = None
    subtitle_position: Optional[str] = None
    subtitle_position_y: Optional[float] = None
    subtitle_size: Optional[str] = None
    subtitle_color: Optional[str] = None
    blur_existing_subtitles: Optional[bool] = None
    blur_region: Optional[Dict[str, Any]] = None
    translation_provider: Optional[str] = None
    translation_model: Optional[str] = None
    translation_endpoint: Optional[str] = None
    translation_key_verified: Optional[bool] = None
    translation_models: Optional[List[Dict[str, str]]] = None
    # Secret is accepted on write but is never returned by the API.
    translation_api_key: Optional[str] = None
    translation_clear_api_key: Optional[bool] = None


class TranslationTestRequest(BaseModel):
    translation_provider: Optional[str] = None
    translation_model: Optional[str] = None
    translation_endpoint: Optional[str] = None
    translation_api_key: Optional[str] = None


async def _upsert_setting(session: AsyncSession, key: str, value: str) -> None:
    result = await session.execute(select(AppSettings).where(AppSettings.key == key))
    existing = result.scalar_one_or_none()
    if existing:
        existing.value = value
    else:
        session.add(AppSettings(key=key, value=value))


async def _persist_verified_translation(
    session: AsyncSession,
    provider: str,
    model: str,
    endpoint: str,
    api_key: str,
    models: List[Dict[str, str]],
) -> None:
    """Persist a route immediately after a successful connection test.

    The API key stays write-only, while the verified route and safe model
    metadata become available to the next background job even if the user
    leaves Settings without pressing the separate general Save button.
    """
    await _upsert_setting(session, "translation_provider", provider)
    await _upsert_setting(session, "translation_model", model)
    await _upsert_setting(session, "translation_endpoint", endpoint)
    await _upsert_setting(session, "translation_api_key", api_key)
    await _upsert_setting(session, "translation_key_verified", "true")
    await _upsert_setting(session, "translation_models", json.dumps(models))


class PresetCreate(BaseModel):
    name: str
    config: Dict[str, Any]


class PresetResponse(BaseModel):
    id: str
    name: str
    config: Dict[str, Any]


@router.get("")
async def get_settings(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(AppSettings))
    rows = result.scalars().all()

    settings = {row.key: row.value for row in rows}

    for key, default_val in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = default_val

    stored_api_key = settings.pop("translation_api_key", "")
    settings["translation_provider"] = normalize_provider(settings.get("translation_provider"))
    settings["translation_model"] = settings.get("translation_model") or default_model_for(
        settings["translation_provider"]
    )
    settings["translation_api_key_set"] = bool(str(stored_api_key).strip())
    settings["translation_api_key_hint"] = mask_api_key_hint(stored_api_key)
    settings["translation_key_verified"] = (
        bool(str(stored_api_key).strip())
        and str(settings.get("translation_key_verified", "false")).lower() == "true"
    )
    try:
        saved_models = json.loads(settings.get("translation_models", "[]"))
        settings["translation_models"] = saved_models if isinstance(saved_models, list) else []
    except (TypeError, json.JSONDecodeError):
        settings["translation_models"] = []

    # Parse default_subtitle_config if exists to provide individual keys
    if "default_subtitle_config" in settings:
        subtitle_config = _parse_subtitle_config(settings["default_subtitle_config"])
        settings["subtitle_position"] = subtitle_config["position"]
        settings["subtitle_position_y"] = subtitle_config["position_y"]
        settings["subtitle_size"] = subtitle_config["size"]
        settings["subtitle_color"] = subtitle_config["color"]
        settings["blur_existing_subtitles"] = subtitle_config["blur_existing_subtitles"]
        settings["blur_region"] = subtitle_config["blur_region"]

    return settings


@router.put("")
async def update_settings(update: SettingsUpdate, session: AsyncSession = Depends(get_session)):
    updates = update.model_dump(exclude_none=True)

    current_translation = await load_translation_config(session)
    next_provider = normalize_provider(updates.get("translation_provider", current_translation.provider))
    next_model = str(updates.get("translation_model", current_translation.model) or "").strip()
    next_endpoint = str(updates.get("translation_endpoint", current_translation.endpoint) or "").strip()
    clear_api_key_requested = bool(updates.get("translation_clear_api_key", False))
    requested_api_key = updates.get("translation_api_key")
    requested_key_verified = bool(updates.get("translation_key_verified", False))
    requested_models = updates.get("translation_models")
    next_api_key = (
        str(requested_api_key).strip()
        if requested_api_key is not None and str(requested_api_key).strip()
        else None
    )
    if not clear_api_key_requested and not next_api_key:
        next_api_key = current_translation.api_key

    translation_error = validate_translation_config(
        next_provider,
        next_model,
        next_endpoint,
        require_model=requested_key_verified,
        require_endpoint=requested_key_verified,
    )
    # An incomplete provider is an intentional Google fallback until a key is
    # supplied. Only reject malformed settings once they could become active.
    if next_api_key and translation_error:
        raise HTTPException(status_code=422, detail=translation_error)

    # If subtitle individual keys are provided, also update default_subtitle_config
    subtitle_keys = {
        "subtitle_position", "subtitle_position_y", "subtitle_size", "subtitle_color",
        "subtitle_enabled", "blur_existing_subtitles", "blur_region",
    }
    has_subtitle_update = any(k in updates for k in subtitle_keys)

    if has_subtitle_update:
        # Get current subtitle config from DB
        result = await session.execute(
            select(AppSettings).where(AppSettings.key == "default_subtitle_config")
        )
        existing_config = result.scalar_one_or_none()
        current_config_str = existing_config.value if existing_config else "{}"
        current_config = _parse_subtitle_config(current_config_str)

        # Update with new values. A preset change moves the subtitle unless an
        # explicit editor coordinate is included in the same request.
        if "subtitle_position" in updates:
            current_config["position"] = updates["subtitle_position"]
            if "subtitle_position_y" not in updates and current_config["position"] != "custom":
                current_config["position_y"] = SUBTITLE_POSITION_Y_BY_PRESET.get(
                    current_config["position"],
                    DEFAULT_SUBTITLE_POSITION_Y,
                )
        if "subtitle_position_y" in updates:
            current_config["position_y"] = updates["subtitle_position_y"]
        if "subtitle_size" in updates:
            current_config["size"] = updates["subtitle_size"]
        if "subtitle_color" in updates:
            current_config["color"] = updates["subtitle_color"]
        if "blur_existing_subtitles" in updates:
            current_config["blur_existing_subtitles"] = updates["blur_existing_subtitles"]
        if "blur_region" in updates:
            current_config["blur_region"] = updates["blur_region"]

        # Build and save default_subtitle_config
        new_config_str = _build_subtitle_config(
            current_config["position"],
            current_config["size"],
            current_config["color"],
            current_config["blur_existing_subtitles"],
            position_y=current_config.get("position_y"),
            blur_region=current_config.get("blur_region"),
        )

        if existing_config:
            existing_config.value = new_config_str
        else:
            session.add(AppSettings(key="default_subtitle_config", value=new_config_str))

    # API keys are deliberately handled outside the generic settings loop so an
    # empty/omitted value cannot accidentally erase a working configuration.
    api_key = updates.pop("translation_api_key", None)
    clear_api_key = bool(updates.pop("translation_clear_api_key", False))
    updates.pop("translation_key_verified", None)
    updates.pop("translation_models", None)
    key_or_route_changed = clear_api_key or api_key is not None or any(
        key in updates for key in ("translation_provider", "translation_model", "translation_endpoint")
    )
    if clear_api_key:
        result = await session.execute(
            select(AppSettings).where(AppSettings.key == "translation_api_key")
        )
        existing_key = result.scalar_one_or_none()
        if existing_key:
            await session.delete(existing_key)
    elif api_key is not None and str(api_key).strip():
        result = await session.execute(
            select(AppSettings).where(AppSettings.key == "translation_api_key")
        )
        existing_key = result.scalar_one_or_none()
        if existing_key:
            existing_key.value = str(api_key).strip()
        else:
            session.add(AppSettings(key="translation_api_key", value=str(api_key).strip()))

    if key_or_route_changed:
        verified_value = requested_key_verified and bool(next_api_key) and next_provider != DEFAULT_TRANSLATION_PROVIDER
        model_value = requested_models if verified_value and isinstance(requested_models, list) else []
        for key, value in (
            ("translation_key_verified", str(verified_value).lower()),
            ("translation_models", json.dumps(model_value)),
        ):
            result = await session.execute(select(AppSettings).where(AppSettings.key == key))
            existing = result.scalar_one_or_none()
            if existing:
                existing.value = value
            else:
                session.add(AppSettings(key=key, value=value))

    for key, value in updates.items():
        # These two values live inside default_subtitle_config. Do not write a
        # Python dict string to separate rows that the GET endpoint could later
        # mistake for the canonical editor state.
        if key in {"subtitle_position_y", "blur_region"}:
            continue
        result = await session.execute(
            select(AppSettings).where(AppSettings.key == key)
        )
        existing = result.scalar_one_or_none()

        value = str(value).lower() if isinstance(value, bool) else str(value)

        if existing:
            existing.value = value
        else:
            session.add(AppSettings(key=key, value=value))

    await session.commit()
    return {"status": "updated"}


@router.post("/translation/test")
async def test_translation(update: TranslationTestRequest, session: AsyncSession = Depends(get_session)):
    """Authenticate a provider and return only compatible, non-secret model metadata."""
    stored = await load_translation_config(session)
    provider = normalize_provider(update.translation_provider or stored.provider)
    model = str(update.translation_model if update.translation_model is not None else stored.model).strip()
    endpoint = str(update.translation_endpoint if update.translation_endpoint is not None else stored.endpoint).strip()
    api_key = (
        str(update.translation_api_key).strip()
        if update.translation_api_key is not None and str(update.translation_api_key).strip()
        else stored.api_key
    )

    if provider == DEFAULT_TRANSLATION_PROVIDER or not api_key:
        return {
            "ok": True,
            "provider": DEFAULT_TRANSLATION_PROVIDER,
            "model": "google-free",
            "models": [],
            "model_source": "",
            "message": "Google Translate đang sẵn sàng; chưa có API key AI để kiểm tra.",
            "used_fallback": True,
        }

    validation_error = validate_translation_config(
        provider,
        model,
        endpoint,
        require_model=False,
    )
    if validation_error:
        return {
            "ok": False,
            "provider": provider,
            "model": model,
            "models": [],
            "model_source": "",
            "message": validation_error,
            "used_fallback": True,
        }

    # OpenAI-compatible and Gemini expose a real models endpoint. Anthropic is
    # authenticated with a small marker request inside discover_translation_models.
    discovery_model = model or default_model_for(provider)
    config = TranslationConfig(
        provider=provider,
        model=discovery_model,
        endpoint=endpoint,
        api_key=api_key,
        verified=True,
    )
    models, model_source = discover_translation_models(config)
    if models:
        selected_model = model if any(item["id"] == model for item in models) else models[0]["id"]
        await _persist_verified_translation(
            session,
            provider,
            selected_model,
            endpoint,
            api_key,
            models,
        )
        await session.commit()
        return {
            "ok": True,
            "provider": provider,
            "model": selected_model,
            "models": models,
            "model_source": model_source,
            "message": "Kết nối thành công và đã lưu route cho lần dịch tiếp theo.",
            "used_fallback": False,
        }

    return {
        "ok": False,
        "provider": provider,
        "model": model,
        "models": [],
        "model_source": "",
        "message": "Không thể xác thực API key hoặc tải danh sách model. Google Translate vẫn được dùng làm dự phòng.",
        "used_fallback": True,
    }


# Preset endpoints
@router.get("/presets", response_model=List[PresetResponse])
async def get_presets(session: AsyncSession = Depends(get_session)):
    """Get all user presets"""
    result = await session.execute(
        select(AppSettings).where(AppSettings.key.like(f"{PRESET_KEY_PREFIX}%"))
    )
    rows = result.scalars().all()

    presets = []
    for row in rows:
        try:
            preset_id = row.key.replace(PRESET_KEY_PREFIX, "")
            config = json.loads(row.value)
            presets.append(PresetResponse(id=preset_id, name=config.get("name", preset_id), config=config.get("config", {})))
        except Exception:
            continue

    return presets


@router.post("/presets", response_model=PresetResponse)
async def create_preset(preset: PresetCreate, session: AsyncSession = Depends(get_session)):
    """Save current config as a preset"""
    import uuid
    preset_id = str(uuid.uuid4())[:12]
    key = f"{PRESET_KEY_PREFIX}{preset_id}"

    preset_data = {
        "name": preset.name,
        "config": preset.config
    }

    session.add(AppSettings(key=key, value=json.dumps(preset_data)))
    await session.commit()

    return PresetResponse(id=preset_id, name=preset.name, config=preset.config)


@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str, session: AsyncSession = Depends(get_session)):
    """Delete a preset"""
    key = f"{PRESET_KEY_PREFIX}{preset_id}"
    result = await session.execute(
        select(AppSettings).where(AppSettings.key == key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        await session.delete(existing)
        await session.commit()
        return {"status": "deleted"}

    return {"status": "not_found"}
