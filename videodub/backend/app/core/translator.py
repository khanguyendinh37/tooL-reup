import re


def parse_srt(srt_path: str) -> list:
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = content.strip().split("\n\n")
    entries = []

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            index = lines[0].strip()
            timestamp = lines[1].strip()
            text = "\n".join(lines[2:])

            start_match = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})", timestamp)
            end_match = re.search(r"(\d{2}:\d{2}:\d{2},\d{3})$", timestamp)

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
    """Parse SRT file and return segments with start, end, and text."""
    entries = parse_srt(srt_path)
    segments = []
    for entry in entries:
        start = _parse_timestamp(entry["start"])
        end = _parse_timestamp(entry["end"])
        text = entry["translated_text"] if entry["translated_text"] else entry["original_text"]
        segments.append({
            "start": start,
            "end": end,
            "text": text,
        })
    return segments


def _parse_timestamp(ts: str) -> float:
    """Parse SRT timestamp (HH:MM:SS,mmm) to seconds."""
    time_part, ms_part = ts.split(',')
    h, m, s = map(int, time_part.split(':'))
    return h * 3600 + m * 60 + s + int(ms_part) / 1000


def translate_srt_deep_translator(srt_path: str, target_lang: str,
                                   output_path: str) -> str:
    from deep_translator import GoogleTranslator

    entries = parse_srt(srt_path)
    lang_map = {
        "vi": "vi", "en": "en", "ja": "ja", "ko": "ko",
        "zh": "zh-CN", "th": "th", "fr": "fr", "de": "de",
        "es": "es", "pt": "pt", "it": "it", "ru": "ru",
        "ar": "ar", "hi": "hi", "id": "id", "ms": "ms",
    }
    dest = lang_map.get(target_lang, target_lang)

    translator = GoogleTranslator(source="auto", target=dest)

    texts_to_translate = [e["original_text"] for e in entries]

    batch_size = 50
    translated_texts = []
    for i in range(0, len(texts_to_translate), batch_size):
        batch = texts_to_translate[i:i + batch_size]
        joined = "\n".join(batch)
        try:
            result = translator.translate(joined)
            translated_batch = result.split("\n")
            if len(translated_batch) < len(batch):
                translated_batch.extend([""] * (len(batch) - len(translated_batch)))
            translated_texts.extend(translated_batch[:len(batch)])
        except Exception as e:
            translated_texts.extend(batch)

    for entry, translated in zip(entries, translated_texts):
        entry["translated_text"] = translated

    with open(output_path, "w", encoding="utf-8") as f:
        for i, entry in enumerate(entries, 1):
            f.write(f"{i}\n")
            f.write(f"{entry['start']} --> {entry['end']}\n")
            f.write(f"{entry['translated_text']}\n\n")

    return output_path


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


def timestamp_to_seconds(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    hours = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds
