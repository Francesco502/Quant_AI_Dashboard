"""Launcher for the background daemon process."""

from __future__ import annotations

import os
import sys


REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

from core.daemon import main


if __name__ == "__main__":
    print("Starting background daemon...")
    print("Press Ctrl+C to stop.")
    try:
        main()
    except KeyboardInterrupt:
        print("Daemon stopped.")
