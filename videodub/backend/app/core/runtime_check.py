"""Offline checks shared by source and frozen builds. No user data is read."""
import importlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from app.core.process_utils import hidden_subprocess_kwargs

PACKAGES = ('yt-dlp', 'curl_cffi', 'pytubefix', 'edge-tts', 'faster-whisper',
            'ctranslate2', 'av', 'demucs', 'torch', 'numpy', 'fastapi')


def run_checks(report_path: str) -> None:
    report = {'python': platform.python_version(), 'packages': {}, 'checks': {}}
    try:
        for package in PACKAGES:
            report['packages'][package] = importlib.metadata.version(package)
        for module in ('yt_dlp', 'curl_cffi', 'pytubefix', 'edge_tts',
                       'faster_whisper', 'demucs.separate', 'torch'):
            importlib.import_module(module)
        if getattr(sys, 'frozen', False) and sys.platform == 'win32':
            importlib.import_module('webview.platforms.winforms')
        if sys.platform == 'darwin':
            importlib.import_module('webview.platforms.cocoa')
        # Import the same API routes shipped in both modes.
        importlib.import_module('app.main')
        from app.core.downloader import _build_impersonate_target
        target = _build_impersonate_target('facebook')
        if target is None:
            raise RuntimeError('No browser impersonation handler available')
        report['checks']['impersonation'] = str(target)
        from app.core.vocal_remover import demucs_command
        subprocess.run(demucs_command(['--help']), capture_output=True, check=True,
                       timeout=60, **hidden_subprocess_kwargs())
        report['checks']['demucs_worker'] = 'ok'
        for command in ('ffmpeg', 'ffprobe'):
            result = subprocess.run([command, '-version'], capture_output=True,
                                    text=True, check=True, timeout=20,
                                    **hidden_subprocess_kwargs())
            report['checks'][command] = result.stdout.splitlines()[0]
        # Exercise actual packaged binaries and our extraction code, not mocks.
        with tempfile.TemporaryDirectory(prefix='videodub-check-') as directory:
            video = str(Path(directory) / 'sample.mp4')
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'color=c=black:s=160x90:r=10:d=1', '-f', 'lavfi', '-i',
                            'sine=frequency=440:duration=1', '-c:v', 'mpeg4',
                            '-c:a', 'aac', '-shortest', '-y', video],
                           capture_output=True, check=True, timeout=30,
                           **hidden_subprocess_kwargs())
            from app.core.transcriber import extract_audio
            audio = extract_audio(video, str(Path(directory) / 'audio.wav'))
            if Path(audio).stat().st_size < 1000:
                raise RuntimeError('Extracted audio is empty')
            report['checks']['audio_extraction'] = 'ok'
        report['ok'] = True
    except Exception as exc:
        report['ok'] = False
        report['error'] = str(exc)
        raise
    finally:
        destination = Path(report_path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    import sys
    run_checks(sys.argv[1])
