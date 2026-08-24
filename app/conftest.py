"""Makes `from app import ...` work in the tests, however pytest is started.

Without this, `pytest -q` fails at collection with `ModuleNotFoundError: No module named
'app'` — which is what CI runs, and it has been failing there.

The reason it is easy to miss: `python -m pytest` puts the current directory on `sys.path`
and bare `pytest` does not. So the same tests pass locally when run one way and fail in CI
when run the other, and the failure looks like a broken test rather than a path.

pytest imports the rootdir `conftest.py` before collecting anything and, in the default
import mode, puts its directory on `sys.path`. Simply existing here is therefore enough —
the explicit insert below is belt and braces for anyone running from another directory.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
