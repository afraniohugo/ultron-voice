"""Ultron Voice CLI.

Usage:
  uv run python -m ultron_voice.cli check-health
  uv run python -m ultron_voice.cli engines
"""

from __future__ import annotations

import sys

from ultron_voice.cli import main as _main

if __name__ == "__main__":
    sys.exit(_main())
