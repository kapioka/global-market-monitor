import os
import sys
import tempfile
from pathlib import Path

workspace_root = Path(__file__).resolve().parent
runtime_root = workspace_root / 'project' / '.runtime'
pycache_root = runtime_root / 'pycache'
pytest_cache_root = runtime_root / 'pytest_cache'
temp_root = runtime_root / 'tmp'

for directory in (runtime_root, pycache_root, pytest_cache_root, temp_root):
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        pass

for env_name in ('TMP', 'TEMP', 'TMPDIR'):
    try:
        os.environ[env_name] = str(temp_root)
    except Exception:
        pass

try:
    tempfile.tempdir = str(temp_root)
except Exception:
    pass

try:
    sys.pycache_prefix = str(pycache_root)
except Exception:
    pass

candidates = [
    Path.home() / 'AppData' / 'Roaming' / 'Python' / f'Python{sys.version_info.major}{sys.version_info.minor}' / 'site-packages',
    Path.home() / 'AppData' / 'Local' / 'Programs' / 'Python' / f'Python{sys.version_info.major}{sys.version_info.minor}' / 'Lib' / 'site-packages',
]

for candidate in candidates:
    path = str(candidate)
    if path in sys.path:
        continue
    try:
        if candidate.exists():
            sys.path.append(path)
    except PermissionError:
        continue
