"""Deterministic, fail-closed check before local voice synthesis on Windows."""
from __future__ import annotations

import csv
import io
import os
import subprocess

_GAME_NAMES = {"cod.exe", "warzone.exe", "modernwarfare.exe", "cod23.exe"}


def game_active() -> bool:
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
            text=True, errors="replace", timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            return True
        return any(row and row[0].strip().casefold() in _GAME_NAMES
                   for row in csv.reader(io.StringIO(result.stdout)))
    except (OSError, subprocess.TimeoutExpired, csv.Error):
        return True
