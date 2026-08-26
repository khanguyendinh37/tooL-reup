import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.translation_config import (
    TranslationConfig,
    mask_api_key_hint,
    validate_translation_config,
)
from app.core.translation_providers import translate_marked_block
from app.core.translator import (
    _full_pass_timeout_seconds,
    _translate_marked_group,
    translate_srt_deep_translator,
)


SAMPLE_SRT = """1
00:00:00,000 --> 00:00:01,000
Hello one

2
00:00:05,000 --> 00:00:06,000
Hello two

3
00:00:12,000 --> 00:00:13,000
Hello three
"""


def _gemini_config() -> TranslationConfig:
    return TranslationConfig(
        provider="gemini",
        model="gemini-2.0-flash",
        endpoint="https://example.test/v1beta",
        api_key="test-gemini-key",
        verified=True,
    )


def _write_sample_srt(directory: str) -> tuple[str, str]:
    srt_path = str(Path(directory) / "input.srt")
    output_path = str(Path(directory) / "translated.srt")
    Path(srt_path).write_text(SAMPLE_SRT, encoding="utf-8")
    return srt_path, output_path


class TranslationProviderTests(unittest.TestCase):
    def setUp(self):
        self.block = "<<<0>>> Hello there"

    def test_openai_compatible_response_is_extracted(self):
        config = TranslationConfig(
            provider="openai",
            model="gpt-4o-mini",
            endpoint="https://example.test/v1",
            api_key="test-openai-key",
        )
        with patch(
            "app.core.translation_providers._request_json",
            return_value={"choices": [{"message": {"content": "<<<0>>> Xin chào"}}]},
        ) as request:
            result = translate_marked_block(config, self.block, "en", "vi")

        self.assertEqual(result, "<<<0>>> Xin chào")
        request.assert_called_once()
        self.assertEqual(request.call_args.args[0], "openai")
        self.assertEqual(request.call_args.args[1], "https://example.test/v1/chat/completions")
        self.assertEqual(request.call_args.args[3]["Authorization"], "Bearer test-openai-key")

    def test_gemini_response_is_extracted(self):
        config = TranslationConfig(
            provider="gemini",
            model="gemini-2.0-flash",
            endpoint="https://example.test/v1beta",
            api_key="test-gemini-key",
        )
        with patch(
            "app.core.translation_providers._request_json",
            return_value={
                "candidates": [{
                    "content": {"parts": [{"text": "<<<0>>> Xin chào"}]},
                }],
            },
        ):
            result = translate_marked_block(config, self.block, "en", "vi")

        self.assertEqual(result, "<<<0>>> Xin chào")

    def test_anthropic_response_is_extracted(self):
        config = TranslationConfig(
            provider="anthropic",
            model="claude-3-5-haiku-latest",
            endpoint="https://example.test",
            api_key="test-anthropic-key",
        )
        with patch(
            "app.core.translation_providers._request_json",
            return_value={"content": [{"type": "text", "text": "<<<0>>> Xin chào"}]},
        ):
            result = translate_marked_block(config, self.block, "en", "vi")

        self.assertEqual(result, "<<<0>>> Xin chào")

    def test_invalid_ai_response_falls_back_to_google_for_the_block(self):
        entries = [{
            "start": "00:00:00,000",
            "end": "00:00:01,000",
            "original_text": "Hello there",
        }]
        config = TranslationConfig(
            provider="openai",
            model="gpt-4o-mini",
            endpoint="https://example.test/v1",
            api_key="test-key",
        )
        with patch("app.core.translator.translate_marked_block", return_value=None), patch(
            "app.core.translator._translate_with_retry",
            return_value="<<<0>>> Xin chào",
        ) as google:
            result = _translate_marked_group(entries, [0], "en", "vi", translation_config=config)

        self.assertEqual(result, {0: "Xin chào"})
        google.assert_called_once()

    def test_unchanged_ai_response_does_not_count_as_translation(self):
        entries = [{
            "start": "00:00:00,000",
            "end": "00:00:01,000",
            "original_text": "Hello there",
        }]
        config = TranslationConfig(
            provider="openai",
            model="gpt-4o-mini",
            endpoint="https://example.test/v1",
            api_key="test-key",
        )
        with patch(
            "app.core.translator.translate_marked_block",
            return_value="<<<0>>> Hello there",
        ), patch(
            "app.core.translator._translate_with_retry",
            return_value="<<<0>>> Xin chào",
        ) as google:
            result = _translate_marked_group(entries, [0], "en", "vi", translation_config=config)

        self.assertEqual(result, {0: "Xin chào"})
        google.assert_called_once()

    def test_missing_key_skips_ai_and_uses_google(self):
        entries = [{
            "start": "00:00:00,000",
            "end": "00:00:01,000",
            "original_text": "Hello there",
        }]
        config = TranslationConfig(
            provider="openai",
            model="gpt-4o-mini",
            endpoint="https://example.test/v1",
            api_key=None,
        )
        with patch("app.core.translator.translate_marked_block") as ai, patch(
            "app.core.translator._translate_with_retry",
            return_value="<<<0>>> Xin chào",
        ):
            result = _translate_marked_group(entries, [0], "en", "vi", translation_config=config)

        self.assertEqual(result, {0: "Xin chào"})
        ai.assert_not_called()


class FullContextTranslationTests(unittest.TestCase):
    def test_full_pass_timeout_scales_with_cue_count_and_is_capped(self):
        self.assertEqual(_full_pass_timeout_seconds(3), 96)
        self.assertEqual(_full_pass_timeout_seconds(100000), 600)

    def test_usable_ai_route_translates_the_whole_file_in_one_request(self):
        config = _gemini_config()
        with tempfile.TemporaryDirectory() as directory:
            srt_path, output_path = _write_sample_srt(directory)
            with patch(
                "app.core.translator.translate_marked_block",
                return_value=(
                    "<<<0>>> Xin chào một\n<<<1>>> Xin chào hai\n<<<2>>> Xin chào ba"
                ),
            ) as ai, patch("app.core.translator._translate_with_retry") as google:
                translate_srt_deep_translator(srt_path, "vi", output_path, "en", config)

            ai.assert_called_once()
            block = ai.call_args.args[1]
            for marker in ("<<<0>>>", "<<<1>>>", "<<<2>>>"):
                self.assertIn(marker, block)
            # The cues sit more than two seconds apart, so only a full-context
            # request can cover all three in a single call.
            self.assertEqual(ai.call_args.kwargs["timeout_seconds"], 96)
            google.assert_not_called()
            translated = Path(output_path).read_text(encoding="utf-8")
            for line in ("Xin chào một", "Xin chào hai", "Xin chào ba"):
                self.assertIn(line, translated)

    def test_failed_full_pass_falls_back_to_grouped_translation(self):
        config = _gemini_config()

        def fake_translate(block_block_config, block, source, target, timeout_seconds=20):
            markers = ["<<<0>>>", "<<<1>>>", "<<<2>>>"]
            if sum(marker in block for marker in markers) >= 3:
                return ""  # Full-context attempt failed.
            lines = []
            for marker in markers:
                if marker in block:
                    number = markers.index(marker) + 1
                    lines.append(f"{marker} Xin chào {['một', 'hai', 'ba'][number - 1]}")
            return "\n".join(lines)

        with tempfile.TemporaryDirectory() as directory:
            srt_path, output_path = _write_sample_srt(directory)
            with patch(
                "app.core.translator.translate_marked_block",
                side_effect=fake_translate,
            ), patch("app.core.translator._translate_with_retry") as google:
                translate_srt_deep_translator(srt_path, "vi", output_path, "en", config)

            google.assert_not_called()
            translated = Path(output_path).read_text(encoding="utf-8")
            for line in ("Xin chào một", "Xin chào hai", "Xin chào ba"):
                self.assertIn(line, translated)

    def test_openai_discovery_filters_and_normalizes_models(self):
        from app.core.translation_providers import discover_translation_models

        config = TranslationConfig(
            provider="openai",
            model="",
            endpoint="https://example.test/v1",
            api_key="test-key",
            verified=True,
        )
        with patch(
            "app.core.translation_providers._request_json_get",
            return_value={"data": [
                {"id": "gpt-4o-mini"},
                {"id": "text-embedding-3-small"},
                {"id": "gpt-4o-mini"},
            ]},
        ):
            models, source = discover_translation_models(config)

        self.assertEqual(source, "discovered")
        self.assertEqual([model["id"] for model in models], ["gpt-4o-mini"])

    def test_gemini_discovery_keeps_only_generation_models(self):
        from app.core.translation_providers import discover_translation_models

        config = TranslationConfig(
            provider="gemini",
            model="gemini-2.0-flash",
            endpoint="https://example.test/v1beta",
            api_key="test-key",
            verified=True,
        )
        with patch(
            "app.core.translation_providers._request_json_get",
            return_value={"models": [
                {"name": "models/gemini-2.0-flash", "displayName": "Gemini Flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
            ]},
        ):
            models, source = discover_translation_models(config)

        self.assertEqual(source, "discovered")
        self.assertEqual(models[0]["id"], "gemini-2.0-flash")

    def test_anthropic_discovery_uses_curated_models_after_probe(self):
        from app.core.translation_providers import discover_translation_models

        config = TranslationConfig(
            provider="anthropic",
            model="claude-3-5-haiku-latest",
            endpoint="https://example.test",
            api_key="test-key",
            verified=True,
        )
        with patch(
            "app.core.translation_providers._translate_anthropic",
            return_value="<<<0>>> Xin chào",
        ):
            models, source = discover_translation_models(config)

        self.assertEqual(source, "curated")
        self.assertTrue(models)


class TranslationConfigTests(unittest.TestCase):
    def test_custom_provider_requires_endpoint(self):
        self.assertIsNotNone(validate_translation_config("openai_compatible", "llama", ""))
        self.assertIsNone(validate_translation_config("openai_compatible", "llama", "https://localhost/v1"))

    def test_secret_hint_only_contains_last_four(self):
        self.assertEqual(mask_api_key_hint("super-secret-7K2P"), "••••7K2P")
        self.assertEqual(mask_api_key_hint(None), "")

    def test_unchanged_translation_is_not_meaningful_for_text(self):
        from app.core.translator import _translation_is_meaningful

        self.assertFalse(_translation_is_meaningful("你好", "你好"))
        self.assertTrue(_translation_is_meaningful("2026", "2026"))


if __name__ == "__main__":
    unittest.main()
