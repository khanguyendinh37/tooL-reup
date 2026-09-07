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
GOOGLE_MAX_RETRIES = 3
GOOGLE_REQUEST_TIMEOUT_SECONDS = 15
GOOGLE_CIRCUIT_COOLDOWN_SECONDS = 60
MYMEMORY_REQUEST_TIMEOUT_SECONDS = 12
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


# Per-cue target length for the translated text lives next to ``_write_srt``
# at the bottom of this module so the split logic and the SRT writer share
# the same constants. Earlier versions dropped or truncated text to fit a
# hard cap; that approach lost meaning at the end of long sentences, so
# long cues are now split into multiple time-bounded sub-cues instead.


def _is_chinese_lang(lang: Optional[str]) -> bool:
    if not lang:
        return False
    return lang.lower().startswith("zh")


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
                          max_retries: int = GOOGLE_MAX_RETRIES, delay: float = 1.0) -> Optional[str]:
    """Translate with bounded exponential backoff.

    Backoff starts at ``delay`` seconds and doubles per attempt, capped at 10s
    so a single 429-spammed cue cannot stall the pipeline for more than ~17s
    across ``GOOGLE_MAX_RETRIES`` attempts.
    """
    for attempt in range(max_retries):
        result = _google_translate_http(text, src, dest)
        if result and result.strip():
            return result.strip()
        wait = min(10.0, delay * (2 ** attempt))
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
        # Keep the full translation; if it is too long for a single subtitle
        # line, write_subtitle_srt will split it into multiple time-bounded cues.
        return translated
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
        # Keep the full translation; if it is too long for a single subtitle
        # line, _write_srt will split it into multiple time-bounded cues.
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


# Per-cue target length for the translated text. The aim is one line on a
# vertical short-form video so the subtitle never overflows or covers the
# visual. When a translated cue exceeds TARGET_CUE_CHARS the renderer splits
# it into multiple time-bounded sub-cues so the full meaning is preserved
# and the viewer has time to read each line. A cue is never truncated just to
# satisfy this budget.
TARGET_CUE_CHARS = 28
MAX_CUE_CHARS = 40
# Reading speed budget per sub-cue line (chars/second). 13 is the standard
# reading speed for subtitles and keeps each line comfortably readable.
SUBTITLE_READING_CPS = 13.0
# Hard floor so very short cues still get at least this much time.
SUBTITLE_MIN_DURATION_SECONDS = 0.8


def _seconds_to_timestamp(seconds: float) -> str:
    """Format a float second count as ``HH:MM:SS,mmm`` for SRT output."""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _split_long_cue_into_subentries(entry: dict) -> list:
    """Expand one SRT entry into one or more time-bounded sub-entries.

    If the translated text fits within ``MAX_CUE_CHARS``, the entry is
    returned unchanged. If it is longer, the text is split at the `` / ``
    soft-break markers the translator emits, falling back to word boundaries
    when the markers do not exist. The original cue's [start, end] window is
    divided evenly across the resulting sub-cues (proportional to character
    count), with a ``SUBTITLE_MIN_DURATION_SECONDS`` floor so a 0.4s cue
    does not collapse to invisible frames.

    Splitting here — instead of cutting characters at the translator — keeps
    the full meaning intact and gives the viewer time to read each line.
    """
    text = (entry.get("translated_text") or entry.get("original_text") or "").strip()
    if not text or len(text) <= MAX_CUE_CHARS:
        return [entry]

    start = timestamp_to_seconds(entry["start"])
    end = timestamp_to_seconds(entry["end"])
    total_duration = max(end - start, 0.0)
    if total_duration <= 0:
        return [entry]

    # 1) Prefer the translator's own soft-break markers (Rule 1 in the
    #    translation prompt) so we never break a phrase mid-word.
    parts = [p.strip() for p in text.split(" / ") if p.strip()]
    if len(parts) > 1 and all(len(p) <= MAX_CUE_CHARS for p in parts):
        chunks = parts
    else:
        # 2) Fall back to greedy word-packing so every chunk stays under the
        #    budget. A soft break is inserted as ' / ' so the on-screen
        #    subtitle wraps naturally.
        words = text.split()
        chunks = []
        current = []
        current_len = 0
        for word in words:
            added = len(word) + (1 if current else 0)
            if current and current_len + added > MAX_CUE_CHARS:
                chunks.append(" ".join(current))
                current = [word]
                current_len = len(word)
            else:
                current.append(word)
                current_len += added
        if current:
            chunks.append(" ".join(current))

    if len(chunks) <= 1:
        return [entry]

    # 3) Allocate time per chunk proportional to its character count, with
    #    a floor and a ceiling so no sub-cue is invisible or eats the whole
    #    original window.
    weights = [max(len(c), 1) for c in chunks]
    total_weight = sum(weights)
    # The shortest comfortable duration for a line of `weight` chars at
    # SUBTITLE_READING_CPS, with a floor of SUBTITLE_MIN_DURATION_SECONDS.
    raw_durations = [
        max(SUBTITLE_MIN_DURATION_SECONDS, weight / SUBTITLE_READING_CPS)
        for weight in weights
    ]
    raw_total = sum(raw_durations)
    # Scale so the chunks fit inside the original window when there is room;
    # otherwise use the comfortable reading time (longer window is preferred
    # but the original duration is the hard cap to keep TTS in sync).
    if raw_total <= total_duration:
        scale = 1.0
    else:
        scale = total_duration / raw_total
    durations = [d * scale for d in raw_durations]

    # If the scaled durations leave unused time, give it to the last chunk so
    # the on-screen window is fully covered.
    leftover = total_duration - sum(durations)
    if leftover > 0:
        durations[-1] += leftover

    sub_entries = []
    cursor = start
    for i, chunk in enumerate(chunks):
        chunk_start = cursor
        chunk_end = cursor + durations[i]
        if i == len(chunks) - 1:
            chunk_end = end  # never overshoot the original end
        sub_entries.append({
            "index": entry.get("index"),
            "start": _seconds_to_timestamp(chunk_start),
            "end": _seconds_to_timestamp(chunk_end),
            "original_text": chunk,
            "translated_text": chunk,
        })
        cursor = chunk_end

    return sub_entries


def write_subtitle_srt(entries: list, output_path: str) -> None:
    """Write the subtitle file used for on-screen burn-in.

    Long cues are split into multiple time-bounded sub-cues so the viewer can
    read each line without scrolling. The TTS pipeline uses a different
    SRT (see ``write_tts_srt``) where each cue keeps its full text and the
    original timing window, so the spoken voice flows naturally without
    artificial pauses between split lines.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        number = 0
        for entry in entries:
            for sub_entry in _split_long_cue_into_subentries(entry):
                number += 1
                text = sub_entry.get("translated_text") or sub_entry.get("original_text", "")
                f.write(f"{number}\n")
                f.write(f"{sub_entry['start']} --> {sub_entry['end']}\n")
                f.write(f"{text}\n\n")


def write_tts_srt(entries: list, output_path: str) -> None:
    """Write the SRT the TTS engine reads.

    Unlike ``write_subtitle_srt``, this file keeps the original cue windows
    intact and uses the full translated text for every cue. The TTS engine
    then produces one MP3 per cue, so the voice reads each sentence
    continuously rather than breaking at the subtitle split points.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for number, entry in enumerate(entries, 1):
            text = entry.get("translated_text") or entry.get("original_text", "")
            f.write(f"{number}\n")
            f.write(f"{entry['start']} --> {entry['end']}\n")
            f.write(f"{text}\n\n")


# Backwards-compatible alias: older callers that still pass a single SRT path
# get the subtitle variant, which is what they historically used to do both.
_write_srt = write_subtitle_srt


def write_both_srt_variants(tts_srt_path: str, subtitle_srt_path: str) -> None:
    """Derive the burn-in subtitle SRT from the TTS SRT.

    The TTS SRT keeps every cue with its original timing window and the full
    translated text, so each spoken sentence flows naturally. The subtitle SRT
    is generated on demand by splitting long cues into multiple time-bounded
    sub-cues, which is what the on-screen renderer (and human readers) want.
    """
    entries = parse_srt(tts_srt_path)
    write_subtitle_srt(entries, subtitle_srt_path)


def build_subtitle_srt_from_actual_timing(
    tts_srt_path: str,
    actual_segments: list[tuple[int, float, float]],
    output_path: str,
) -> None:
    """Build the burn-in SRT from the actual TTS audio timing.

    The original ``subtitle.srt`` is derived from the SRT cue window, but the
    translated voice is usually longer than the source phrase, so the audio
    often runs past the cue's nominal ``end``. This function rebuilds the
    subtitle file using the absolute time each segment actually occupies in
    the merged dubbed track: ``actual_start = start_seconds``,
    ``actual_end = start_seconds + probed_audio_duration``. Long cues are
    then split into sub-lines sized to the real audio window so on-screen
    text stays in lock-step with the voice.

    A segment whose TTS call failed is not in ``actual_segments``; the
    function keeps its original cue window for those entries so the subtitle
    still appears (silently) at the expected position.
    """
    entries = parse_srt(tts_srt_path)
    if not entries:
        # Defensive: nothing to write, but clear any stale file.
        open(output_path, "w", encoding="utf-8").close()
        return

    # Audio indices are zero-based positions in srt_to_segments, not SRT
    # cue labels (which are usually one-based and can be nonconsecutive).
    timing_by_idx: dict[int, tuple[float, float]] = {}
    for raw_idx, actual_start, actual_end in actual_segments:
        try:
            timing_by_idx[int(raw_idx)] = (float(actual_start), float(actual_end))
        except (TypeError, ValueError):
            continue

    with open(output_path, "w", encoding="utf-8") as f:
        number = 0
        for entry_idx, entry in enumerate(entries):
            actual = timing_by_idx.get(entry_idx)
            if actual is None:
                # TTS failed for this cue. Fall back to the original timing
                # so the subtitle still appears (the audio at that point is
                # silent, but the on-screen text remains useful as a
                # reference for the viewer).
                actual_start = timestamp_to_seconds(entry["start"])
                actual_end = timestamp_to_seconds(entry["end"])
            else:
                actual_start, actual_end = actual

            # Build a pseudo-entry carrying the actual audio window, then
            # re-use the standard splitter so character budgets and the
            # `` / `` soft-break rules apply identically.
            pseudo_entry = {
                **entry,
                "start": _seconds_to_timestamp(actual_start),
                "end": _seconds_to_timestamp(max(actual_end, actual_start)),
            }
            for sub_entry in _split_long_cue_into_subentries(pseudo_entry):
                number += 1
                text = (
                    sub_entry.get("translated_text")
                    or sub_entry.get("original_text", "")
                )
                f.write(f"{number}\n")
                f.write(f"{sub_entry['start']} --> {sub_entry['end']}\n")
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
        write_tts_srt(entries, output_path)
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
        write_tts_srt(entries, output_path)
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
            write_tts_srt(entries, output_path)
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
        missing = translatable_count - len(translated_indices)
        logger.warning(
            "Translation incomplete: %d/%d cues translated; %d cues kept as original text "
            "(AI/Google provider was rate-limited). The job will still finish so the "
            "user gets a watchable video; those few cues will show the source language.",
            len(translated_indices),
            translatable_count,
            missing,
        )
    write_tts_srt(entries, output_path)
    return output_path


def timestamp_to_seconds(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    hours = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds
