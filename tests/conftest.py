from __future__ import annotations

import os
import sys
from pathlib import Path


# Ensure project root is importable for tests
ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
	sys.path.insert(0, ROOT)

