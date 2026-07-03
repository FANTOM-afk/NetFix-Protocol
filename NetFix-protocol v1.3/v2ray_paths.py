import json
import os
from typing import Any, Dict

import config

APP_DIR = os.path.join(config.APP_DATA_DIR, "v2ray")
CORE_DIR = os.path.join(APP_DIR, "core")
RUNTIME_CONFIG = os.path.join(APP_DIR, "runtime-config.json")
USER_CONFIG = os.path.join(APP_DIR, "user-config.txt")
STATE_FILE = os.path.join(APP_DIR, "state.json")
PROFILES_FILE = os.path.join(APP_DIR, "profiles.json")
PROCESS_FILE = os.path.join(APP_DIR, "process.json")
CORE_LOG_FILE = os.path.join(APP_DIR, "core.log")
PROXY_SNAPSHOT_FILE = os.path.join(APP_DIR, "proxy-snapshot.json")


def ensure_dirs() -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    os.makedirs(CORE_DIR, exist_ok=True)


def atomic_write_json(path: str, data: Dict[str, Any], indent: int = 4, ensure_ascii: bool = True) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
    os.replace(tmp_path, path)


def atomic_write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp_path, path)


def v2ray_exe_path() -> str:
    return os.path.join(CORE_DIR, "v2ray.exe")


def load_state() -> Dict[str, Any]:
    state = {
        "local_port": 10809,
        "selected_group": "Default",
        "last_subscription_name": "",
        "active_profile_id": "",
    }
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            state.update(data)
    except (OSError, json.JSONDecodeError):
        pass
    return state


def save_state(state: Dict[str, Any]) -> None:
    ensure_dirs()
    current = load_state()
    current.update(state)
    atomic_write_json(STATE_FILE, current, indent=4)


def load_user_config() -> str:
    try:
        with open(USER_CONFIG, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def save_user_config(raw_config: str) -> None:
    ensure_dirs()
    atomic_write_text(USER_CONFIG, raw_config)
