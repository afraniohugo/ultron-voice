"""Deterministic, fail-closed check before local voice synthesis on Windows."""
from __future__ import annotations

import csv
import io
import os
import subprocess
import time

_GAME_NAMES = {"cod.exe", "warzone.exe", "modernwarfare.exe", "cod23.exe"}
# tasklist can take several seconds when the host is saturated. A short cache
# avoids spawning one process per call in a tight voice pipeline; any failure
# still fails closed. The cache is deliberately sub-second and is never used
# to override a positive game detection.
_CACHE_TTL = 0.5
_cached_at = 0.0
_cached_active = True


def game_active() -> bool:
    global _cached_at, _cached_active
    if os.name != "nt":
        return False
    now = time.monotonic()
    if now - _cached_at < _CACHE_TTL and _cached_active:
        return True
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
            text=True, errors="replace", timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            active = True
        else:
            active = any(row and row[0].strip().casefold() in _GAME_NAMES
                         for row in csv.reader(io.StringIO(result.stdout)))
    except (OSError, subprocess.TimeoutExpired, csv.Error):
        active = True
    _cached_at = now
    _cached_active = active
    return active
