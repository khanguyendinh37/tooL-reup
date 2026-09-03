import html
import json
import logging
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError
from typing import Iterable, Optional

from app.core.translation_config import TranslationConfig
from app.core.translation_providers import translate_marked_block

logger = logging.getLogger(__name__)

# Google Translate preserves the compact angle-bracket marker more reliably
# than word-based labels; validation still prevents any line/timing shifts.
MARKER_TEMPLATE = "<<<{}>>>"
MARKER_RE = re.compile(r"<<<\d+>>>")
CONTEXT_CHUNK_SIZE = 8
CONTEXT_MAX_GAP_SECONDS = 2.0
CONTEXT_MAX_CHARS = 2600
# A usable AI route first translates the whole SRT in a single request so the
# model carries tone, names, and terminology across the entire video. The
# timeout scales with cue count because one long generation replaces many
# small ones.
FULL_PASS_TIMEOUT_BASE_SECONDS = 90
FULL_PASS_TIMEOUT_PER_CUE_SECONDS = 2
FULL_PASS_TIMEOUT_CAP_SECONDS = 600
GROUP_AI_TIMEOUT_SECONDS = 45
GOOGLE_MAX_RETRIES = 1
GOOGLE_REQUEST_TIMEOUT_SECONDS = 10
GOOGLE_CIRCUIT_COOLDOWN_SECONDS = 30
MYMEMORY_REQUEST_TIMEOUT_SECONDS = 8
MYMEMORY_MAX_WORKERS = 4
_google_circuit_open_until = 0.0

LANGUAGE_ALIASES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "chinese": "zh-CN",
    "zh-tw": "zh-TW",
    "zh-hant": "zh-TW",
}


def _marker(index: int) -> str:
    return MARKER_TEMPLATE.format(index)


# Per-cue target length for the translated text. The aim is one line on a
# vertical short-form video so the subtitle never overflows or covers the
# visual. Translators are told to keep the text within this range; when a
# cue arrives longer than ``MAX_CUE_CHARS`` we still write it (so a
# faithful translation is never dropped), but the renderer is told to use
# the smaller font for those cues.
TARGET_CUE_CHARS = 28
MAX_CUE_CHARS = 40


def _is_chinese_lang(lang: Optional[str]) -> bool:
    if not lang:
        return False
    return lang.lower().startswith("zh")


def _compress_too_long_cue(text: str, target_lang: Optional[str] = None) -> str:
    """Best-effort: shorten an AI translation that still exceeded the per-cue
    character budget. We drop filler words first; if still too long, we cut at
    the nearest clause boundary (comma, period, conjunction) so the rendered
    line stays readable and never ends mid-word.

    For Chinese, each character counts as one visual unit, so the limits
    translate directly. For other languages, the AI prompt keeps text within
    the budget and this function is just a safety net.
    """
    if not text or len(text) <= MAX_CUE_CHARS:
        return text

    drop_patterns = [
        r"\b(thật ra|thực ra|nói chung|nói thật|cơ bản|căn bản)\b\s*",
        r"\b(rất|quá|cực kỳ|cực)\s+",
        r"\b(literally|basically|honestly|actually|seriously|kind of|sort of|just|really|very)\s+",
        r"\b(um+|uh+|er+|ah+|hmm+)\b,?\s*",
        r"\s*[,…]+\s*",
    ]
    compressed = text
    for pattern in drop_patterns:
        new = re.sub(pattern, " ", compressed, flags=re.IGNORECASE).strip()
        if len(new) <= MAX_CUE_CHARS:
            return " ".join(new.split())
        compressed = new

    if len(compressed) > MAX_CUE_CHARS:
        # Cut at the nearest clause boundary, allowing a small overshoot past
        # MAX_CUE_CHARS so a comma sitting just past the limit is still used
        # as the cut point instead of splitting a word. Boundaries are:
        # comma, period, Vietnamese conjunctions (và, nhưng, hay, hoặc, vì,
        # do), or a space.
        search_end = min(len(compressed), MAX_CUE_CHARS + 6)
        boundary = max(
            compressed.rfind(",", 0, search_end),
            compressed.rfind(".", 0, search_end),
            compressed.rfind(" và ", 0, search_end),
            compressed.rfind(" nhưng ", 0, search_end),
            compressed.rfind(" hay ", 0, search_end),
            compressed.rfind(" hoặc ", 0, search_end),
            compressed.rfind(" vì ", 0, search_end),
            compressed.rfind(" do ", 0, search_end),
            compressed.rfind(" ", 0, search_end),
        )
        if boundary > MAX_CUE_CHARS * 0.5:
            compressed = compressed[:boundary].rstrip(" ,.;:-")
        else:
            compressed = compressed[:MAX_CUE_CHARS].rstrip()
    return " ".join(compressed.split())


def _clean_subtitle_text(text: str) -> str:
    """Flatten an SRT cue to one readable line for translation/TTS."""
    return " ".join(str(text or "").replace("\r", " ").replace("\n", " ").split())


def _normalize_language(language: Optional[str]) -> Optional[str]:
    if not language:
        return None
    normalized = language.strip().lower()
    if not normalized or normalized == "auto":
        return None
    return LANGUAGE_ALIASES.get(normalized, normalized)


def parse_srt(srt_path: str) -> list:
    with open(srt_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    blocks = re.split(r"\n\s*\n", content.strip()) if content.strip() else []
    entries = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines()]
        if len(lines) < 3:
            continue

        index = lines[0]
        timestamp = lines[1]
        text = "\n".join(lines[2:]).strip()

        start_match = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})", timestamp)
        end_match = re.search(r"(\d{2}:\d{2}:\d{2},\d{3})\s*$", timestamp)
        if start_match and end_match:
            entries.append({
                "index": index,
                "start": start_match.group(1),
                "end": end_match.group(1),
                "original_text": text,
                "translated_text": "",
            })

    return entries


def srt_to_segments(srt_path: str) -> list:
    entries = parse_srt(srt_path)
    segments = []
    for entry in entries:
        start = timestamp_to_seconds(entry["start"])
        end = timestamp_to_seconds(entry["end"])
        text = entry.get("translated_text") or entry["original_text"]
        segments.append({
            "start": start,
            "end": end,
            "text": text,
        })
    return segments


def _parse_google_translation_response(result: object) -> Optional[str]:
    """Parse both Google free-endpoint response shapes."""
    if isinstance(result, list) and result and all(isinstance(item, str) for item in result):
        return "".join(item for item in result if item).strip() or None
    if isinstance(result, list) and result and isinstance(result[0], list):
        return "".join(
            part[0] for part in result[0]
            if isinstance(part, list) and part and isinstance(part[0], str) and part[0]
        ).strip() or None
    return None


def _google_circuit_is_open() -> bool:
    return time.monotonic() < _google_circuit_open_until


def _google_translate_http(
    text: str,
    src: str,
    dest: str,
    timeout: int = GOOGLE_REQUEST_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Translate through a free endpoint with a Google API-compatible fallback."""
    global _google_circuit_open_until
    if _google_circuit_is_open():
        return None

    params = {
        "sl": src,
        "tl": dest,
        "q": text,
    }
    requests = [
        (
            "https://clients5.google.com/translate_a/t?"
            + urllib.parse.urlencode({"client": "dict-chrome-ex", **params})
        ),
        (
            "https://translate.googleapis.com/translate_a/single?"
            + urllib.parse.urlencode({"client": "gtx", "dt": "t", **params})
        ),
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json,text/plain,*/*",
    }

    for url in requests:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = response.read().decode("utf-8")
            translated = _parse_google_translation_response(json.loads(data))
            if translated:
                _google_circuit_open_until = 0.0
                return translated
        except HTTPError as exc:
            logger.warning(
                "Google Translate endpoint failed (%s): %s",
                urllib.parse.urlparse(url).netloc,
                exc.code,
            )
            # A 429 is account/IP-wide, so probing the second endpoint only
            # adds another throttled request. Open the breaker immediately and
            # let the caller fail fast or use a configured AI route.
            if exc.code == 429:
                _google_circuit_open_until = time.monotonic() + GOOGLE_CIRCUIT_COOLDOWN_SECONDS
                return None
        except Exception as exc:
            logger.warning(
                "Google Translate endpoint failed (%s): %s",
                urllib.parse.urlparse(url).netloc,
                getattr(exc, "code", None) or type(exc).__name__,
            )

    return None


def _translate_with_retry(text: str, src: str, dest: str,
                          max_retries: int = GOOGLE_MAX_RETRIES, delay: float = 0.25) -> Optional[str]:
    """Translate with bounded exponential backoff."""
    for attempt in range(max_retries):
        result = _google_translate_http(text, src, dest)
        if result and result.strip():
            return result.strip()
        wait = delay * (2 ** attempt)
        if attempt < max_retries - 1:
            logger.warning(
                "Translation attempt %s failed; retrying in %.1fs",
                attempt + 1,
                wait,
            )
            time.sleep(wait)
    return None


def _mymemory_translate_text(
    text: str,
    src: str,
    dest: str,
    timeout: int = MYMEMORY_REQUEST_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Translate one cue through MyMemory when the Google route is throttled."""
    source_text = _clean_subtitle_text(text)
    if not source_text:
        return None

    params = urllib.parse.urlencode({
        "q": source_text,
        "langpair": f"{src or 'auto'}|{dest}",
    })
    url = f"https://api.mymemory.translated.net/get?{params}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "VideoDub/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        response_data = payload.get("responseData") if isinstance(payload, dict) else None
        translated = response_data.get("translatedText") if isinstance(response_data, dict) else None
        translated = html.unescape(str(translated or "")).strip()
        if not translated or translated.casefold() == source_text.casefold():
            return None
        return _compress_too_long_cue(translated, dest)
    except HTTPError as exc:
        logger.warning("Public translation fallback returned HTTP %s", exc.code)
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, AttributeError):
        logger.warning("Public translation fallback request failed")
    except Exception:
        logger.warning("Public translation fallback returned an unexpected response")
    return None


def _translate_with_public_fallback(
    entries: list,
    indices: Iterable[int],
    src: str,
    dest: str,
) -> Optional[dict[int, str]]:
    """Translate cues concurrently without markers after Google/AI failure.

    MyMemory may rewrite angle brackets, so each cue is sent independently and
    mapped back by its original index. A group is accepted only when every cue
    returns a non-empty translation, preserving the existing strict coverage
    guarantee.
    """
    requested = list(indices)
    if not requested:
        return {}

    translations: dict[int, str] = {}
    worker_count = min(MYMEMORY_MAX_WORKERS, len(requested))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                _mymemory_translate_text,
                entries[index].get("original_text", ""),
                src,
                dest,
            ): index
            for index in requested
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                translated = future.result()
            except Exception:
                translated = None
            if translated:
                translations[index] = translated

    if len(translations) != len(requested) or not _translations_are_meaningful(entries, translations):
        logger.warning(
            "Public translation fallback covered %s/%s meaningful cues",
            len(translations),
            len(requested),
        )
        return None
    return {index: translations[index] for index in requested}


def _build_contextual_block(entries: list, indices: Iterable[int] | int,
                            count: Optional[int] = None) -> str:
    """Build a marked block while keeping each subtitle cue independently mappable.

    ``count`` keeps compatibility with the previous helper signature.
    """
    if isinstance(indices, int):
        start = indices
        end = min(start + (count or CONTEXT_CHUNK_SIZE), len(entries))
        selected_indices = range(start, end)
    else:
        selected_indices = indices

    parts = []
    for index in selected_indices:
        text = _clean_subtitle_text(entries[index].get("original_text", ""))
        if text:
            parts.append(f"{_marker(index)} {text}")
    return "\n".join(parts)


def _full_pass_timeout_seconds(cue_count: int) -> int:
    estimate = FULL_PASS_TIMEOUT_BASE_SECONDS + cue_count * FULL_PASS_TIMEOUT_PER_CUE_SECONDS
    return min(estimate, FULL_PASS_TIMEOUT_CAP_SECONDS)


def _translate_whole_file_with_ai(
    entries: list,
    translatable_indices: list[int],
    source: str,
    target: str,
    translation_config: TranslationConfig,
) -> Optional[dict[int, str]]:
    """One full-context AI pass over every cue, or None if it is not trustworthy."""
    block = _build_contextual_block(entries, translatable_indices)
    result = translate_marked_block(
        translation_config,
        block,
        source,
        target,
        timeout_seconds=_full_pass_timeout_seconds(len(translatable_indices)),
    )
    translations = _extract_marked_translations(result or "", translatable_indices, target_lang=target)
    if not translations or not _translations_are_meaningful(entries, translations):
        return None
    return translations


def _extract_marked_translations(result: str, indices: Iterable[int], target_lang: Optional[str] = None) -> Optional[dict[int, str]]:
    """Return translations only when every requested marker is preserved exactly once.

    Each translated cue is also passed through ``_compress_too_long_cue`` so
    the rendered subtitle stays inside the per-cue character budget the AI
    prompt told the model to respect.
    """
    if not result:
        return None

    requested = list(indices)
    markers = [_marker(index) for index in requested]
    if any(result.count(marker) != 1 for marker in markers):
        return None

    positions = sorted((result.index(marker), marker) for marker in markers)
    if [marker for _, marker in positions] != markers:
        return None

    translations: dict[int, str] = {}
    for position, (marker_start, marker) in enumerate(positions):
        content_start = marker_start + len(marker)
        content_end = positions[position + 1][0] if position + 1 < len(positions) else len(result)
        translated = _clean_subtitle_text(result[content_start:content_end])
        if not translated or MARKER_RE.search(translated):
            return None
        translated = _compress_too_long_cue(translated, target_lang)
        index = requested[markers.index(marker)]
        translations[index] = translated

    if len(translations) != len(requested):
        return None
    return translations


def _translation_is_meaningful(original: str, translated: str) -> bool:
    """Reject an unchanged alphabetic cue masquerading as a translation."""
    source_text = _clean_subtitle_text(original)
    translated_text = _clean_subtitle_text(translated)
    if not translated_text:
        return False
    if translated_text.casefold() != source_text.casefold():
        return True
    # Numbers, symbols, and names without translatable letters can legitimately
    # remain unchanged. Natural-language cues must not silently pass through.
    return not any(char.isalpha() for char in source_text)


def _translations_are_meaningful(entries: list, translations: dict[int, str]) -> bool:
    return all(
        _translation_is_meaningful(
            entries[index].get("original_text", ""),
            translated,
        )
        for index, translated in translations.items()
    )


def _extract_translations(result: str, entries: list, start_idx: int, count: int) -> bool:
    """Compatibility wrapper for callers/tests using the old extraction helper."""
    indices = range(start_idx, min(start_idx + count, len(entries)))
    translations = _extract_marked_translations(result, indices)
    if not translations or not _translations_are_meaningful(entries, translations):
        return False
    for index, translated in translations.items():
        entries[index]["translated_text"] = translated
    return True


def _detect_source_language(entries: list) -> str:
    sample = " ".join(
        _clean_subtitle_text(entry.get("original_text", ""))
        for entry in entries[:5]
    )
    if any("\u4e00" <= char <= "\u9fff" for char in sample):
        return "zh-CN"
    if any("\u3040" <= char <= "\u309f" or "\u30a0" <= char <= "\u30ff" for char in sample):
        return "ja"
    if any("\uac00" <= char <= "\ud7af" for char in sample):
        return "ko"
    return "auto"


def _context_groups(entries: list) -> list[list[int]]:
    """Group nearby cues so translation sees a short, coherent subtitle passage."""
    active_indices = [
        index for index, entry in enumerate(entries)
        if _clean_subtitle_text(entry.get("original_text", ""))
    ]
    groups: list[list[int]] = []
    current: list[int] = []
    current_chars = 0

    for index in active_indices:
        entry_text = _clean_subtitle_text(entries[index]["original_text"])
        entry_chars = len(entry_text) + len(_marker(index)) + 1
        gap = 0.0
        if current:
            previous = entries[current[-1]]
            gap = max(
                0.0,
                timestamp_to_seconds(entries[index]["start"])
                - timestamp_to_seconds(previous["end"]),
            )

        exceeds_limits = (
            current
            and (
                len(current) >= CONTEXT_CHUNK_SIZE
                or gap > CONTEXT_MAX_GAP_SECONDS
                or current_chars + entry_chars > CONTEXT_MAX_CHARS
            )
        )
        if exceeds_limits:
            groups.append(current)
            current = []
            current_chars = 0

        current.append(index)
        current_chars += entry_chars

    if current:
        groups.append(current)
    return groups


def _translate_marked_group(
    entries: list,
    indices: list[int],
    src: str,
    dest: str,
    max_retries: int = GOOGLE_MAX_RETRIES,
    translation_config: TranslationConfig | None = None,
) -> Optional[dict[int, str]]:
    """Try the configured AI route first, then the reliable Google fallback."""
    block = _build_contextual_block(entries, indices)
    if translation_config and translation_config.is_usable:
        ai_result = translate_marked_block(
            translation_config,
            block,
            src,
            dest,
            timeout_seconds=GROUP_AI_TIMEOUT_SECONDS,
        )
        ai_translations = _extract_marked_translations(ai_result or "", indices, target_lang=dest)
        if ai_translations and _translations_are_meaningful(entries, ai_translations):
            return ai_translations
        logger.warning(
            "AI translation response was unavailable, unchanged, or invalid for provider %s; using Google fallback",
            translation_config.provider,
        )

    result = _translate_with_retry(block, src, dest, max_retries=max_retries)
    translations = _extract_marked_translations(result, indices, target_lang=dest) if result else None
    if translations and _translations_are_meaningful(entries, translations):
        return translations

    public_translations = _translate_with_public_fallback(entries, indices, src, dest)
    if public_translations:
        logger.info("Public translation fallback completed for %s cues", len(indices))
    return public_translations


def _translate_with_neighbor_context(
    entries: list,
    index: int,
    src: str,
    dest: str,
    translation_config: TranslationConfig | None = None,
) -> Optional[str]:
    """Translate one cue with its immediate neighbors as semantic context."""
    neighbors = [candidate for candidate in (index - 1, index, index + 1)
                 if 0 <= candidate < len(entries)
                 and _clean_subtitle_text(entries[candidate].get("original_text", ""))]
    translations = _translate_marked_group(
        entries,
        neighbors,
        src,
        dest,
        max_retries=GOOGLE_MAX_RETRIES,
        translation_config=translation_config,
    )
    return translations.get(index) if translations else None


def _write_srt(entries: list, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        for number, entry in enumerate(entries, 1):
            text = entry.get("translated_text") or entry.get("original_text", "")
            f.write(f"{number}\n")
            f.write(f"{entry['start']} --> {entry['end']}\n")
            f.write(f"{text}\n\n")


def translate_srt_deep_translator(
    srt_path: str,
    target_lang: str,
    output_path: str,
    source_lang: Optional[str] = None,
    translation_config: TranslationConfig | None = None,
) -> str:
    """Translate an SRT with full-file AI context and a per-block fallback chain.

    A verified AI route first receives the entire subtitle file in one request,
    so tone, names, and terminology stay consistent across the whole video. Each
    marked block is accepted only when every marker is preserved exactly once,
    preventing line shifts or partial translations from corrupting SRT timing.
    When the full pass (or a later AI block) fails, translation degrades to the
    contextual groups of the Google route, then smaller blocks, then neighbor
    context, then the original cue text.
    """
    entries = parse_srt(srt_path)
    if not entries:
        logger.warning("No entries found in SRT file: %s", srt_path)
        _write_srt(entries, output_path)
        return output_path

    target = _normalize_language(target_lang) or target_lang
    source = _normalize_language(source_lang) or _detect_source_language(entries)
    logger.info(
        "Translating %s entries with context: %s -> %s (route=%s)",
        len(entries),
        source,
        target,
        translation_config.provider if translation_config else "google",
    )

    if source == target:
        for entry in entries:
            entry["translated_text"] = _clean_subtitle_text(entry.get("original_text", ""))
        _write_srt(entries, output_path)
        return output_path

    translatable_indices = [
        index for index, entry in enumerate(entries)
        if _clean_subtitle_text(entry.get("original_text", ""))
    ]

    if translation_config and translation_config.is_usable and translatable_indices:
        whole_file_translations = _translate_whole_file_with_ai(
            entries,
            translatable_indices,
            source,
            target,
            translation_config,
        )
        if whole_file_translations:
            for index, translated in whole_file_translations.items():
                entries[index]["translated_text"] = translated
            logger.info(
                "AI route %s translated all %s cues in one full-context pass",
                translation_config.provider,
                len(translatable_indices),
            )
            _write_srt(entries, output_path)
            return output_path
        logger.warning(
            "Full-context AI pass was unavailable or incomplete; falling back to grouped translation"
        )

    translated_indices: set[int] = set()
    fallback_indices: set[int] = set()

    for group in _context_groups(entries):
        translations = _translate_marked_group(
            entries,
            group,
            source,
            target,
            translation_config=translation_config,
        )
        if translations:
            for index, translated in translations.items():
                entries[index]["translated_text"] = translated
                translated_indices.add(index)
            continue

        # Once Google reports a rate limit, retrying the same group in smaller
        # shapes cannot recover it during the circuit cooldown.
        if _google_circuit_is_open():
            fallback_indices.update(group)
            continue

        # A malformed large response can still succeed with two or three cues.
        for offset in range(0, len(group), 2):
            smaller_group = group[offset:offset + 2]
            translations = _translate_marked_group(
                entries,
                smaller_group,
                source,
                target,
                max_retries=GOOGLE_MAX_RETRIES,
                translation_config=translation_config,
            )
            if translations:
                for index, translated in translations.items():
                    entries[index]["translated_text"] = translated
                    translated_indices.add(index)
            else:
                fallback_indices.update(smaller_group)

    # Translate only unresolved cues with previous/current/next context.
    for index in sorted(fallback_indices):
        if index in translated_indices:
            continue
        if _google_circuit_is_open():
            break
        translated = _translate_with_neighbor_context(
            entries,
            index,
            source,
            target,
            translation_config=translation_config,
        )
        original = _clean_subtitle_text(entries[index].get("original_text", ""))
        entries[index]["translated_text"] = translated or original
        if translated:
            translated_indices.add(index)
        else:
            logger.warning("Keeping original text for subtitle entry %s", index + 1)

    # Empty cues are preserved, and any unexpected unresolved cue is safe.
    for index, entry in enumerate(entries):
        if not entry.get("translated_text"):
            entry["translated_text"] = _clean_subtitle_text(entry.get("original_text", ""))

    translated_count = sum(
        1 for entry in entries
        if entry.get("translated_text") != _clean_subtitle_text(entry.get("original_text", ""))
    )
    translatable_count = sum(
        1 for entry in entries
        if _clean_subtitle_text(entry.get("original_text", ""))
    )
    unchanged_count = len(entries) - translated_count
    logger.info(
        "Translation complete: %s translated, %s unchanged/fallback out of %s",
        translated_count,
        unchanged_count,
        len(entries),
    )
    if source != target and len(translated_indices) < translatable_count:
        raise RuntimeError(
            f"Chỉ dịch được {len(translated_indices)}/{translatable_count} phụ đề; vui lòng kiểm tra kết nối AI/Google rồi thử lại."
        )
    _write_srt(entries, output_path)
    return output_path


def timestamp_to_seconds(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    hours = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds
