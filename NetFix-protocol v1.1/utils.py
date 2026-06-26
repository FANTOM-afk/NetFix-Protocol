"""
utils.py
========
System-level helpers: PyInstaller-safe resource paths, Windows admin
elevation, and Windows startup shortcut management.
"""

import sys
import os
import subprocess
import ctypes
import logging
from typing import Optional


def resource_path(relative_path: str) -> str:
    """Resolve a path that works both in dev and inside a PyInstaller bundle."""
    try:
        base_path: str = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def check_admin() -> bool:
    """Return True if the current process is running with admin rights."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except AttributeError:
        return False


def elevate_and_restart() -> None:
    """Relaunch the current script with administrator privileges and exit."""
    quoted_args = " ".join(f'"{a}"' for a in sys.argv)
    try:
        subprocess.run(
            ["powershell", "-Command",
             f'Start-Process -Verb RunAs -FilePath "{sys.executable}" -ArgumentList \'{quoted_args}\''],
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    except Exception as exc:
        logging.error("Failed to elevate: %s", exc)
    sys.exit()


def is_autostart_enabled(shortcut_name: str = "NetFixProtocol.lnk") -> bool:
    try:
        from winshell import startup
        return os.path.exists(os.path.join(startup(), shortcut_name))
    except Exception as exc:
        logging.warning("Could not check autostart: %s", exc)
        return False


def create_startup_shortcut(
    shortcut_name: str = "NetFixProtocol.lnk",
    description: str = "Auto start Net Fix Protocol",
) -> None:
    import winshell
    try:
        startup = winshell.startup()
        path = os.path.abspath(sys.argv[0])
        shortcut = os.path.join(startup, shortcut_name)
        with winshell.shortcut(shortcut) as link:
            link.path = sys.executable
            link.arguments = f'"{path}"'
            link.description = description
            link.working_directory = os.path.dirname(path)
    except Exception as exc:
        logging.error("Could not create startup shortcut: %s", exc)
