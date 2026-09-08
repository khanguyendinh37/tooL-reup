"""Compare source and frozen runtime reports; fail release on mismatch."""
import json
import subprocess
import sys
from pathlib import Path


def compare_reports(source, frozen):
    if not source.get('ok') or not frozen.get('ok'):
        raise RuntimeError('Runtime checks did not complete successfully')
    for field in ('python', 'packages', 'checks'):
        if source[field] != frozen[field]:
            raise RuntimeError(f'Source/frozen runtime mismatch: {field}')


if __name__ == '__main__':
    executable, source_path, frozen_path = sys.argv[1:]
    subprocess.run([str(Path(executable).resolve()), '--self-test',
                    str(Path(frozen_path).resolve())], check=True, timeout=180)
    compare_reports(json.loads(Path(source_path).read_text()),
                    json.loads(Path(frozen_path).read_text()))
    print('Source and packaged runtime checks match.')
