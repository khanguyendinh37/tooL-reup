import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.api.dubbing import _map_blur_region, _map_subtitle_config
from app.api.settings import _build_subtitle_config, _parse_subtitle_config
from app.core.pipeline import burn_subtitles_with_blur_mask


class SubtitleRoiTests(unittest.TestCase):
    def test_blur_region_is_clamped_to_the_video_bounds(self):
        mapped = _map_blur_region({
            "blur_region": {"x": 0.9, "y": -0.2, "width": 0.8, "height": 2},
        })
        self.assertAlmostEqual(mapped["x"], 0.2)
        self.assertEqual(mapped["y"], 0.0)
        self.assertEqual(mapped["width"], 0.8)
        self.assertEqual(mapped["height"], 1.0)

    def test_subtitle_config_preserves_custom_region_and_y(self):
        config = _map_subtitle_config({
            "enabled": True,
            "position": "bottom",
            "position_y": 0.61,
            "blur_existing_subtitles": True,
            "blur_region": {"x": 0.2, "y": 0.65, "width": 0.7, "height": 0.2},
        })
        self.assertEqual(config["position"], "bottom")
        self.assertEqual(config["position_y"], 0.61)
        self.assertEqual(config["blur_region"], {"x": 0.2, "y": 0.65, "width": 0.7, "height": 0.2})

    def test_saved_custom_settings_round_trip_position_and_blur_region(self):
        config_text = _build_subtitle_config(
            "custom",
            "small",
            "white",
            True,
            position_y=0.88,
            blur_region={"x": 0.12, "y": 0.64, "width": 0.72, "height": 0.18},
        )
        config = _parse_subtitle_config(config_text)

        self.assertEqual(config["position"], "custom")
        self.assertAlmostEqual(config["position_y"], 0.88)
        self.assertEqual(config["blur_region"], {
            "x": 0.12,
            "y": 0.64,
            "width": 0.72,
            "height": 0.18,
        })
        self.assertTrue(config["blur_existing_subtitles"])

    def test_legacy_custom_y_is_used_when_position_y_is_missing(self):
        config = _parse_subtitle_config(
            '{"position":"custom","custom_y":0.81,"use_custom_position":false}'
        )

        self.assertEqual(config["position"], "custom")
        self.assertAlmostEqual(config["position_y"], 0.81)

    def test_ffmpeg_uses_pixel_crop_from_normalized_region(self):
        with tempfile.TemporaryDirectory() as directory:
            srt_path = Path(directory) / "translated.srt"
            srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8")
            output_path = Path(directory) / "result.mp4"
            config = {
                "enabled": True,
                "position_y": 0.5,
                "blur_existing_subtitles": True,
                "blur_region": {"x": 0.25, "y": 0.6, "width": 0.5, "height": 0.2},
            }
            with patch("app.core.pipeline.subprocess.run") as run:
                success = burn_subtitles_with_blur_mask(
                    "input.mp4",
                    str(srt_path),
                    str(output_path),
                    1920,
                    1080,
                    config,
                )

            self.assertTrue(success)
            command = run.call_args.args[0]
            filter_complex = command[command.index("-filter_complex") + 1]
            self.assertIn("crop=w=960:h=216:x=480:y=648", filter_complex)
            self.assertIn("overlay=x=480:y=648", filter_complex)

    def test_ass_positions_text_on_the_configured_video_coordinate(self):
        """The ASS canvas matches the video so the editor's center is preserved."""
        with tempfile.TemporaryDirectory() as directory:
            srt_path = Path(directory) / "translated.srt"
            srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8")
            output_path = Path(directory) / "result.mp4"
            with patch("app.core.pipeline.subprocess.run") as run:
                success = burn_subtitles_with_blur_mask(
                    "input.mp4",
                    str(srt_path),
                    str(output_path),
                    720,
                    1280,
                    {"enabled": True, "position_y": 0.73},
                )

            self.assertTrue(success)
            ass_path = srt_path.with_suffix(".ass")
            ass_content = ass_path.read_text(encoding="utf-8")
            self.assertIn("PlayResX: 720", ass_content)
            self.assertIn("PlayResY: 1280", ass_content)
            self.assertIn("Style: Default,Arial,58", ass_content)
            self.assertIn(r"{\an5\pos(360,934)}Xin chao", ass_content)

            command = run.call_args.args[0]
            filter_complex = command[command.index("-filter_complex") + 1]
            self.assertIn("ass=filename=", filter_complex)
            self.assertNotIn("MarginV=", filter_complex)

    def test_legacy_config_keeps_full_width_lower_band(self):
        with tempfile.TemporaryDirectory() as directory:
            srt_path = Path(directory) / "translated.srt"
            srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8")
            with patch("app.core.pipeline.subprocess.run") as run:
                success = burn_subtitles_with_blur_mask(
                    "input.mp4",
                    str(srt_path),
                    str(Path(directory) / "result.mp4"),
                    1000,
                    1000,
                    {"enabled": True, "blur_existing_subtitles": True},
                )

            self.assertTrue(success)
            command = run.call_args.args[0]
            filter_complex = command[command.index("-filter_complex") + 1]
            self.assertIn("crop=w=1000:h=240:x=0:y=760", filter_complex)


if __name__ == "__main__":
    unittest.main()
