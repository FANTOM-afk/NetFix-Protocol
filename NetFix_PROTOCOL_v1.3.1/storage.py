"""
Shared persistence helpers.

Keep atomic file writes in one place so settings, Cloudflare state, and V2Ray
state do not each carry their own copy of the same filesystem code.
"""

from __future__ import annotations

import json
import os
from typing import Any


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def atomic_write_json(
    path: str,
    data: Any,
    *,
    indent: int = 4,
    ensure_ascii: bool = True,
) -> None:
    ensure_parent_dir(path)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
    os.replace(tmp_path, path)


def atomic_write_text(path: str, text: str) -> None:
    ensure_parent_dir(path)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp_path, path)
