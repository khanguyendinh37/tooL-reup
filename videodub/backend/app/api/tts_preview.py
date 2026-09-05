"""TTS preview endpoint - synthesize a short sample for a chosen voice.

This is a lightweight endpoint used by the Settings and Dubbing pages to
let the user hear a voice before committing to it. We don't run the full
dubbing pipeline (no TTS rate, no atempo, no segment merging) - we just
ask Edge TTS to say a short demo sentence and stream the bytes back.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import uuid
from typing import Optional

import edge_tts
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.tts_engine import get_edge_voice

logger = logging.getLogger(__name__)

router = APIRouter()

# Per-locale demo sentences. We pick something short and natural so the
# preview returns in well under a second. Each entry is the native
# spelling - not a translation - so the listener can judge the accent.
_DEMO_SENTENCES: dict[str, str] = {
    "vi": "Xin chào, đây là giọng đọc mẫu.",
    "en": "Hello, this is a sample of my voice.",
    "ja": "こんにちは、これは声のサンプルです。",
    "ko": "안녕하세요, 이것은 음성 샘플입니다.",
    "zh": "你好,这是我的声音样本。",
    "th": "สวัสดีค่ะ นี่คือตัวอย่างเสียงของฉัน",
    "fr": "Bonjour, ceci est un échantillon de ma voix.",
    "de": "Hallo, das ist eine Hörprobe meiner Stimme.",
    "es": "Hola, esta es una muestra de mi voz.",
    "pt": "Olá, esta é uma amostra da minha voz.",
    "ru": "Здравствуйте, это образец моего голоса.",
    "ar": "مرحبا، هذه عينة من صوتي.",
    "hi": "नमस्ते, यह मेरी आवाज़ का नमूना है।",
    "id": "Halo, ini contoh suara saya.",
    "ms": "Helo, ini contoh suara saya.",
    "it": "Ciao, questo è un campione della mia voce.",
    "nl": "Hallo, dit is een voorproefje van mijn stem.",
    "pl": "Cześć, to jest próbka mojego głosu.",
    "tr": "Merhaba, bu sesimin bir örneğidir.",
    "uk": "Привіт, це зразок мого голосу.",
}

# Maximum length we are willing to synthesize. Capping keeps a misuse
# (someone POSTing a long paragraph to test the endpoint) from blocking
# the Edge TTS pool for everyone else.
_MAX_TEXT_LEN = 200

# Block control characters and bidi direction overrides. Edge TTS would
# happily read them, but they only show up in adversarial inputs. The
# bidi range (U+202A..U+202E, U+2066..U+2069) is harmless visually but
# is sometimes smuggled in to flip text direction in terminals that
# render log lines. We allow ordinary whitespace (tab, newline, CR)
# and the printable range.
_CONTROL_CHARS = re.compile(
    "[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f\\u202a-\\u202e\\u2066-\\u2069]"
)


class TtsPreviewRequest(BaseModel):
    voice: str = Field(..., description="Edge TTS voice id (e.g. vi-VN-HoaiMyNeural)")
    text: Optional[str] = Field(
        None,
        description="Optional custom text. If omitted, a default sentence is used.",
    )
    lang: Optional[str] = Field(
        None,
        description="Language code used to pick a default sentence. Defaults to the voice prefix.",
    )
    rate: Optional[str] = Field(
        None,
        description="Optional Edge TTS rate (e.g. '+10%', '-5%'). Defaults to '+0%'.",
    )


def _demo_text_for(voice_id: str, requested_text: Optional[str], lang: Optional[str]) -> str:
    """Pick a short sentence appropriate for the requested voice."""
    if requested_text is not None:
        cleaned = _CONTROL_CHARS.sub("", requested_text).strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="Text is empty after sanitization")
        return cleaned[:_MAX_TEXT_LEN]

    # The lang hint (from the dropdown) takes priority over the voice
    # prefix. This is so a user who picks "vi" then selects a voice
    # whose native lang is different (e.g. en-US) still hears a
    # Vietnamese sample - matches what the UI is filtering for.
    if lang and lang in _DEMO_SENTENCES:
        return _DEMO_SENTENCES[lang]
    prefix = voice_id.split("-")[0].lower() if voice_id else ""
    if prefix in _DEMO_SENTENCES:
        return _DEMO_SENTENCES[prefix]
    # Fallback when the voice is in a language we don't have a sample
    # for - English is the safest default since the listener is most
    # likely the app operator.
    return _DEMO_SENTENCES["en"]


@router.post("/preview")
async def tts_preview(req: TtsPreviewRequest) -> Response:
    """Synthesize a short audio sample and return it as MP3 bytes."""
    edge_voice = get_edge_voice(req.voice)
    text = _demo_text_for(edge_voice, req.text, req.lang)
    rate = req.rate or "+0%"

    # Edge TTS can return its bytes into a BytesIO directly; we use the
    # ``Communicate.save`` path with a temp file only because the
    # library doesn't expose a streaming API and writing to a
    # NamedTemporaryFile is the simplest way to get reliable bytes back
    # on Windows.
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        communicate = edge_tts.Communicate(text, edge_voice, rate=rate)
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
    except Exception as exc:
        logger.warning("TTS preview failed for voice %s: %s", edge_voice, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Edge TTS did not return audio for voice '{edge_voice}'",
        ) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    if not audio_bytes:
        raise HTTPException(
            status_code=502,
            detail=f"Edge TTS returned empty audio for voice '{edge_voice}'",
        )

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            # A short cache is fine - the same voice + text always
            # produces the same bytes. Five minutes matches the most
            # likely "I'm still choosing a voice" session length.
            "Cache-Control": "private, max-age=300",
            "X-Tts-Voice": edge_voice,
            "X-Tts-Preview-Id": uuid.uuid4().hex[:12],
        },
    )
