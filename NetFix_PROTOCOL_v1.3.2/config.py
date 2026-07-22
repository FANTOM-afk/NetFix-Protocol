"""
config.py
=========
Application configuration: default settings, file paths, color theme,
and helpers to load/save settings.json.
"""

import os
import json
import logging
import sys
from typing import Any, Dict

import storage

DEFAULT_SETTINGS: Dict[str, Any] = {
    "domestic_hosts": ["web.bale.ai", "zarebin.ir", "ble.ir"],
    "international_hosts": ["8.8.8.8", "1.1.1.1"],
    "ping_interval": 4,
    "theme": "dark",
    "v2ray_background_enabled": True,
    "v2ray_background_port": 10809,
}

def _get_app_data_dir() -> str:
    """Get the persistent application data directory."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    
    # Use APPDATA for persistent settings on Windows
    if os.name == 'nt':
        appdata = os.environ.get('APPDATA', base)
        app_dir = os.path.join(appdata, 'NetFixProtocol')
    else:
        app_dir = os.path.join(os.path.expanduser('~'), '.netfixprotocol')
    
    os.makedirs(app_dir, exist_ok=True)
    return app_dir

APP_DATA_DIR = _get_app_data_dir()
SETTINGS_FILE = os.path.join(APP_DATA_DIR, "settings.json")
LAST_SSID_FILE = os.path.join(APP_DATA_DIR, ".last_ssid")

DARK_COLORS = {
    "BG": "#0F172A",
    "MAIN_BG": "#111827",
    "PANEL_BG": "#162033",
    "CARD_BG": "#1E293B",
    "INPUT_BG": "#0B1220",
    "BUTTON_BG": "#1E293B",
    "HOVER_BG": "#24344F",
    "FRAME_BORDER": "#334155",
    "SIDE_MENU_BG": "#0B1220",
    "PROGRESS_BG": "#1E293B",
    "PRIMARY": "#38BDF8",
    "PRIMARY_HOVER": "#0EA5E9",
    "PRIMARY_SOFT": "#0F2E45",
    "ON_PRIMARY": "#07111F",
    "ACCENT_GREEN": "#38BDF8",
    "BTN_HOVER_GREEN": "#24344F",
    "ACCENT_RED": "#F87171",
    "BTN_HOVER_RED": "#4A1E28",
    "DANGER_SOFT": "#4A1E28",
    "ACCENT_BLUE": "#60A5FA",
    "ACCENT_YELLOW": "#FBBF24",
    "WARNING_SOFT": "#4A3918",
    "ACCENT_CYAN": "#7DD3FC",
    "PING_GREEN": "#22C55E",
    "TEXT": "#E5EDF7",
    "DIM_TEXT": "#94A3B8",
    "MUTED_TEXT": "#64748B",
    "FONT": "Segoe UI",
    "MONO_FONT": "Cascadia Mono",
}

LIGHT_COLORS = {
    "BG": "#EEF4F8",
    "MAIN_BG": "#F8FAFC",
    "PANEL_BG": "#FFFFFF",
    "CARD_BG": "#F1F5F9",
    "INPUT_BG": "#FFFFFF",
    "BUTTON_BG": "#E8F2FA",
    "HOVER_BG": "#DCECF8",
    "FRAME_BORDER": "#CBD5E1",
    "SIDE_MENU_BG": "#E2E8F0",
    "PROGRESS_BG": "#E2E8F0",
    "PRIMARY": "#0EA5E9",
    "PRIMARY_HOVER": "#0284C7",
    "PRIMARY_SOFT": "#DDF2FD",
    "ON_PRIMARY": "#FFFFFF",
    "ACCENT_GREEN": "#0EA5E9",
    "BTN_HOVER_GREEN": "#DCECF8",
    "ACCENT_RED": "#DC2626",
    "BTN_HOVER_RED": "#FEE2E2",
    "DANGER_SOFT": "#FEE2E2",
    "ACCENT_BLUE": "#2563EB",
    "ACCENT_YELLOW": "#B7791F",
    "WARNING_SOFT": "#FEF3C7",
    "ACCENT_CYAN": "#0284C7",
    "PING_GREEN": "#15803D",
    "TEXT": "#0F172A",
    "DIM_TEXT": "#64748B",
    "MUTED_TEXT": "#94A3B8",
    "FONT": "Segoe UI",
    "MONO_FONT": "Cascadia Mono",
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
        hosts = [str(h).strip() for h in data["domestic_hosts"] if str(h).strip()]
        if hosts:
            result["domestic_hosts"] = hosts
    if "international_hosts" in data and isinstance(data["international_hosts"], list):
        hosts = [str(h).strip() for h in data["international_hosts"] if str(h).strip()]
        if hosts:
            result["international_hosts"] = hosts
    if "ping_interval" in data:
        try:
            val = int(data["ping_interval"])
            result["ping_interval"] = max(1, min(val, 300))
        except (ValueError, TypeError):
            pass
    if "theme" in data and str(data["theme"]) in VALID_THEMES:
        result["theme"] = str(data["theme"])
    if "v2ray_background_enabled" in data:
        result["v2ray_background_enabled"] = bool(data["v2ray_background_enabled"])
    if "v2ray_background_port" in data:
        try:
            val = int(data["v2ray_background_port"])
            result["v2ray_background_port"] = max(1024, min(val, 65534))
        except (ValueError, TypeError):
            pass
    return result


def load_settings() -> Dict[str, Any]:
    """Load settings.json, creating it with defaults if missing/corrupted."""
    if not os.path.exists(SETTINGS_FILE):
        try:
            storage.atomic_write_json(SETTINGS_FILE, DEFAULT_SETTINGS, ensure_ascii=False)
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
        storage.atomic_write_json(SETTINGS_FILE, data, ensure_ascii=False)
    except OSError as exc:
        logging.error("Could not save settings: %s", exc)
