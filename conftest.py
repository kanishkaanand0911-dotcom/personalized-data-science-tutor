"""
Makes the project importable from anywhere pytest is run.

The original modules import `schemas`, `narrate_llm`, `quiz_generator` and
`rules` as top-level names (they were written to run from inside their own
folder), so those folders go on sys.path alongside the project root. This is
what run_full_demo.py does at runtime; doing it here means the tests do not
have to repeat it, and `pytest` works from the repo root with no PYTHONPATH.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

for path in (PROJECT_ROOT,
             os.path.join(PROJECT_ROOT, "app", "educator"),
             os.path.join(PROJECT_ROOT, "app", "gamification")):
    if path not in sys.path:
        sys.path.insert(0, path)
