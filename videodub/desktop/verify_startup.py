"""Launch a packaged app with a deadline and retain logs even if it crashes."""
import json
import os
import subprocess
import sys
from pathlib import Path


def verify(executable, report_dir):
    directory = Path(report_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / 'startup.json'
    report.unlink(missing_ok=True)
    env = dict(os.environ, PYTHONFAULTHANDLER='1')
    with (directory / 'process.log').open('w', encoding='utf-8') as log:
        subprocess.run([str(Path(executable).resolve()), '--startup-check', str(report)],
                       stdout=log, stderr=subprocess.STDOUT, env=env, check=True, timeout=180)
    result = json.loads(report.read_text(encoding='utf-8'))
    if result.get('ok') is not True:
        raise RuntimeError('Native startup failed: ' + str(result.get('error', result)))
    print('Native window loaded the production React frontend successfully.')


if __name__ == '__main__':
    verify(*sys.argv[1:])
