"""Launch a packaged app with a deadline and retain logs even if it crashes."""
import json
import os
import subprocess
import sys
from pathlib import Path


def verify(executable, report_dir, finder=False):
    directory = Path(report_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / 'startup.json'
    report.unlink(missing_ok=True)
    env = dict(os.environ, PYTHONFAULTHANDLER='1')
    executable = Path(executable).resolve()
    command = [str(executable), '--startup-check', str(report)]
    if finder:
        if sys.platform != 'darwin':
            raise RuntimeError('Finder launch is only available on macOS')
        bundle = executable.parents[2]
        if bundle.suffix != '.app':
            raise RuntimeError('Expected an executable inside a macOS .app bundle')
        command = ['/usr/bin/open', '-W', '-n', str(bundle), '--args', '--startup-check', str(report)]
    with (directory / 'process.log').open('w', encoding='utf-8') as log:
        subprocess.run(command,
                       stdout=log, stderr=subprocess.STDOUT, env=env, check=True, timeout=180)
    result = json.loads(report.read_text(encoding='utf-8'))
    if result.get('ok') is not True:
        raise RuntimeError('Native startup failed: ' + str(result.get('error', result)))
    print('Native window loaded the production React frontend successfully.')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('executable')
    parser.add_argument('report_dir')
    parser.add_argument('--finder', action='store_true')
    options = parser.parse_args()
    verify(options.executable, options.report_dir, options.finder)
