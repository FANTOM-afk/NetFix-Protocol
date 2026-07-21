"""
Small subprocess wrappers for Windows command-line tools.

Low-level modules use these helpers instead of repeating CREATE_NO_WINDOW,
encoding, and quiet-output plumbing around every netsh/ping call.
"""

from __future__ import annotations

import locale
import subprocess
from typing import Sequence

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TEXT_ENCODING = locale.getpreferredencoding(False) or "utf-8"


def check_output_text(args: Sequence[str], *, timeout: float | None = None) -> str:
    return subprocess.check_output(
        list(args),
        stderr=subprocess.STDOUT,
        text=True,
        encoding=TEXT_ENCODING,
        errors="replace",
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )


def run_quiet(args: Sequence[str], *, check: bool = False, timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
        check=check,
        timeout=timeout,
    )
