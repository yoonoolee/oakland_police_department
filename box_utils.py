"""
Shared helper for locating this machine's local Box Drive folder.

Import BOX_ROOT from this module in any notebook/script in this repo instead of
hardcoding a path — it auto-detects Box Drive's mount location so the same code
works for every collaborator, regardless of OS or username.
"""

import os
import glob
from pathlib import Path


def find_box_root() -> Path:
    """Locate the local Box Drive sync folder.

    Resolution order:
    1. BOX_ROOT env var, if someone wants to override auto-detection.
    2. Common Box Drive mount locations on macOS / Windows.
    """
    env_override = os.environ.get("BOX_ROOT")
    if env_override:
        p = Path(env_override).expanduser()
        if p.is_dir():
            return p

    home = Path.home()
    candidates = []
    candidates += glob.glob(str(home / "Library/CloudStorage/Box-*"))  # macOS, Box Drive 2.x+
    candidates += [str(home / "Box"), str(home / "Box Sync")]          # Windows / older macOS

    for c in candidates:
        if os.path.isdir(c):
            return Path(c)

    raise FileNotFoundError(
        "Couldn't auto-detect a Box Drive folder. Make sure Box Drive is installed and "
        "signed in, or set it manually: os.environ['BOX_ROOT'] = '/path/to/your/Box/folder'"
    )


BOX_ROOT = find_box_root()
