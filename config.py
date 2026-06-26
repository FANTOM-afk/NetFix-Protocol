"""
config.py
=========
Application configuration: default settings, file paths, color theme,
and helpers to load/save settings.json.
"""

import os
import json
import logging
from typing import Any, Dict

from utils import resource_path

DEFAULT_SETTINGS: Dict[str, Any] = {
    "domestic_hosts": ["web.bale.ai", "zarebin.ir", "ble.ir"],
    "international_hosts": ["8.8.8.8", "1.1.1.1"],
    "ping_interval": 4,
    "theme": "dark",
}

SCRIPT_DIR = resource_path("")
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.json")
LAST_SSID_FILE = os.path.join(SCRIPT_DIR, ".last_ssid")

DARK_COLORS = {
    "BG": "#0C0C0E",
    "MAIN_BG": "#141418",
    "FRAME_BORDER": "#2C2C32",
    "SIDE_MENU_BG": "#0F0F12",
    "PROGRESS_BG": "#1C1C22",
    "BTN_HOVER_GREEN": "#003A1A",
    "BTN_HOVER_RED": "#3A0011",
    "ACCENT_GREEN": "#00FF41",
    "ACCENT_RED": "#FF3355",
    "ACCENT_BLUE": "#00BFFF",
    "ACCENT_YELLOW": "#FFB300",
    "ACCENT_CYAN": "#00E5FF",
    "TEXT": "#EAEAEA",
    "DIM_TEXT": "#7A7A7A",
    "FONT": "Consolas",
}

LIGHT_COLORS = {
    "BG": "#EBEBEB",
    "MAIN_BG": "#FFFFFF",
    "FRAME_BORDER": "#C8C8D0",
    "SIDE_MENU_BG": "#DEDEE2",
    "PROGRESS_BG": "#D2D2D8",
    "BTN_HOVER_GREEN": "#A0E0A0",
    "BTN_HOVER_RED": "#E0A0A0",
    "ACCENT_GREEN": "#008A2A",
    "ACCENT_RED": "#CC1133",
    "ACCENT_BLUE": "#0055BB",
    "ACCENT_YELLOW": "#CC8800",
    "ACCENT_CYAN": "#0088AA",
    "TEXT": "#1A1A1A",
    "DIM_TEXT": "#888888",
    "FONT": "Consolas",
}

THEMES = {"dark": DARK_COLORS, "light": LIGHT_COLORS}

VALID_THEMES = set(THEMES.keys())


def get_colors(theme: str = "dark") -> Dict[str, str]:
    """Return the color dict for the given theme name."""
    return THEMES.get(theme, DARK_COLORS).copy()


def _validate_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and repair loaded settings, falling back to defaults."""
    result = DEFAULT_SETTINGS.copy()
    if not isinstance(data, dict):
        return result
    if "domestic_hosts" in data and isinstance(data["domestic_hosts"], list):
        result["domestic_hosts"] = [str(h).strip() for h in data["domestic_hosts"] if h]
    if "international_hosts" in data and isinstance(data["international_hosts"], list):
        result["international_hosts"] = [str(h).strip() for h in data["international_hosts"] if h]
    if "ping_interval" in data:
        try:
            val = int(data["ping_interval"])
            result["ping_interval"] = max(1, min(val, 300))
        except (ValueError, TypeError):
            pass
    if "theme" in data and str(data["theme"]) in VALID_THEMES:
        result["theme"] = str(data["theme"])
    return result


def load_settings() -> Dict[str, Any]:
    """Load settings.json, creating it with defaults if missing/corrupted."""
    if not os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SETTINGS, f, indent=4)
        except OSError as exc:
            logging.warning("Could not create settings file: %s", exc)
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return _validate_settings(raw)
    except (json.JSONDecodeError, OSError) as exc:
        logging.warning("Settings file corrupt, using defaults: %s", exc)
        return DEFAULT_SETTINGS.copy()


def save_settings(data: Dict[str, Any]) -> None:
    """Validate and save settings to disk."""
    data = _validate_settings(data)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except OSError as exc:
        logging.error("Could not save settings: %s", exc)
