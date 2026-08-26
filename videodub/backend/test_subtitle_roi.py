import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.api.dubbing import _map_blur_region, _map_subtitle_config
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
        self.assertEqual(config["position_y"], 0.61)
        self.assertEqual(config["blur_region"], {"x": 0.2, "y": 0.65, "width": 0.7, "height": 0.2})

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

    def test_margin_v_centers_text_on_the_configured_position(self):
        """The editor label is centered on position_y; the burn must match.

        1080p, position_y=0.5, FontSize=13 on the 288-line canvas renders a
        48.75px em, so the bottom-anchored margin is 540 - 48.75/2 = 516px,
        which is 138 on libass's 288-line script canvas.
        """
        with tempfile.TemporaryDirectory() as directory:
            srt_path = Path(directory) / "translated.srt"
            srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8")
            with patch("app.core.pipeline.subprocess.run") as run:
                success = burn_subtitles_with_blur_mask(
                    "input.mp4",
                    str(srt_path),
                    str(Path(directory) / "result.mp4"),
                    1920,
                    1080,
                    {"enabled": True, "position_y": 0.5},
                )

            self.assertTrue(success)
            command = run.call_args.args[0]
            filter_complex = command[command.index("-filter_complex") + 1]
            self.assertIn("MarginV=138", filter_complex)

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
