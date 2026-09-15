"""Exercise the real native window and production frontend, then close it."""
import json
import platform
import time
from pathlib import Path


def check_window(window, report_path, timeout=60):
    report = {'ok': False, 'machine': platform.machine(), 'macos': platform.mac_ver()[0]}
    try:
        if not window.events.loaded.wait(timeout):
            raise RuntimeError('Native window did not load its page')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # React must actually render: an HTTP 200 or blank WKWebView is not enough.
            result = window.evaluate_js("""(() => {
                const root = document.getElementById('root');
                return {ready: !!root && root.children.length > 0 && root.innerText.trim().length > 20,
                        title: document.title, url: location.href};
            })()""")
            if result and result.get('ready'):
                report.update(ok=True, page=result)
                break
            time.sleep(0.25)
        if not report['ok']:
            raise RuntimeError('React did not render inside the native window')
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        Path(report_path).write_text(json.dumps(report, indent=2), encoding='utf-8')
        window.destroy()
