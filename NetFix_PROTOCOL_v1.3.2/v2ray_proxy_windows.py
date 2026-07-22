import sys
import json
import os
from typing import Any, Dict, Optional

import v2ray_paths

_proxy_snapshot: Optional[Dict[str, Any]] = None


def _local_proxy_tokens() -> list[str]:
    local_port = v2ray_paths.normalize_local_port(v2ray_paths.load_state().get("local_port"))
    return [f"127.0.0.1:{local_port}", f"127.0.0.1:{local_port + 1}"]


def _is_netfix_proxy(server: str) -> bool:
    return any(token in server for token in _local_proxy_tokens())


def _refresh_windows_proxy() -> None:
    import ctypes

    internet_option_settings_changed = 39
    internet_option_refresh = 37
    ctypes.windll.Wininet.InternetSetOptionW(0, internet_option_settings_changed, 0, 0)
    ctypes.windll.Wininet.InternetSetOptionW(0, internet_option_refresh, 0, 0)


def set_system_proxy(local_port: int) -> None:
    if sys.platform != "win32":
        raise RuntimeError("System proxy mode is currently Windows-only.")

    import winreg

    global _proxy_snapshot
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
        if _proxy_snapshot is None:
            def read_value(name: str, default: Any) -> Any:
                try:
                    return winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    return default

            _proxy_snapshot = {
                "ProxyEnable": read_value("ProxyEnable", 0),
                "ProxyServer": read_value("ProxyServer", ""),
                "ProxyOverride": read_value("ProxyOverride", ""),
            }
            v2ray_paths.ensure_dirs()
            v2ray_paths.atomic_write_json(v2ray_paths.PROXY_SNAPSHOT_FILE, _proxy_snapshot, indent=2)

        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(
            key,
            "ProxyServer",
            0,
            winreg.REG_SZ,
            f"127.0.0.1:{local_port + 1}",
        )
        winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
    _refresh_windows_proxy()


def restore_system_proxy() -> None:
    if sys.platform != "win32":
        return

    import winreg

    snapshot = _proxy_snapshot
    if snapshot is None:
        try:
            with open(v2ray_paths.PROXY_SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
        except (OSError, json.JSONDecodeError):
            snapshot = None
    if snapshot is not None and _is_netfix_proxy(str(snapshot.get("ProxyServer", ""))):
        snapshot = None

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
        if snapshot is not None:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, int(snapshot.get("ProxyEnable", 0)))
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, str(snapshot.get("ProxyServer", "")))
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, str(snapshot.get("ProxyOverride", "")))
        else:
            try:
                current_server = str(winreg.QueryValueEx(key, "ProxyServer")[0])
            except FileNotFoundError:
                current_server = ""
            if _is_netfix_proxy(current_server):
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "")
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "")
    _refresh_windows_proxy()
    try:
        os.remove(v2ray_paths.PROXY_SNAPSHOT_FILE)
    except OSError:
        pass


def clear_proxy_snapshot() -> None:
    global _proxy_snapshot
    _proxy_snapshot = None
