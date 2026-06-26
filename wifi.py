"""
wifi.py
=======
Low-level networking helpers: ping checks, Wi-Fi adapter / profile
inspection, SSID persistence, and the reconnect ("fix") sequence.

None of these functions touch the UI directly - status updates are
reported through a `status_callback(text, color)` so this module stays
reusable outside of the GUI.
"""

import os
import re
import time
import subprocess
import logging
from typing import Optional, Tuple, Callable


def ping_host(host: str, timeout_ms: int = 1500) -> Tuple[bool, Optional[int]]:
    try:
        output = subprocess.check_output(
            ["ping", "-n", "1", "-w", str(timeout_ms), host],
            text=True, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        match = re.search(r"time[=<](\d+)ms", output, re.IGNORECASE)
        if match:
            return True, int(match.group(1))
    except subprocess.SubprocessError:
        pass
    except Exception as exc:
        logging.debug("ping_host(%s) error: %s", host, exc)
    return False, None


def get_first_success_ping(hosts, timeout_ms: int = 1500) -> Tuple[bool, Optional[int]]:
    for host in hosts:
        ok, delay = ping_host(host, timeout_ms)
        if ok:
            return True, delay
    return False, None


def get_wifi_adapter() -> Optional[str]:
    try:
        output = subprocess.check_output(
            "netsh interface show interface", shell=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in output.splitlines():
            if any(k in line for k in ("Wi-Fi", "Wireless", "WLAN")):
                return re.split(r"\s{2,}", line.strip())[-1]
    except subprocess.SubprocessError:
        pass
    except Exception as exc:
        logging.debug("get_wifi_adapter error: %s", exc)
    return None


def profile_exists(ssid: str) -> bool:
    try:
        output = subprocess.check_output(
            ["netsh", "wlan", "show", "profiles"], text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).lower()
        return ssid.lower() in output
    except subprocess.SubprocessError:
        return False
    except Exception as exc:
        logging.debug("profile_exists error: %s", exc)
        return False


def get_current_wifi_ssid() -> Optional[str]:
    try:
        output = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"], text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in output.splitlines():
            if "SSID" in line and ":" in line:
                ssid = line.split(":", 1)[1].strip()
                if ssid:
                    return ssid
    except subprocess.SubprocessError:
        pass
    except Exception as exc:
        logging.debug("get_current_wifi_ssid error: %s", exc)
    return None


def save_last_ssid(ssid: str, path: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(ssid)
    except OSError as exc:
        logging.warning("Could not save last SSID: %s", exc)


def load_last_ssid(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


StatusCallback = Callable[[str, str], None]


def reconnect_wifi(
    ssid: str,
    status_callback: StatusCallback,
    force_disable_enable: bool = False,
    colors: Optional[dict] = None,
) -> None:
    if colors is None:
        colors = {}

    accent_red = colors.get("ACCENT_RED", "#FF3355")
    accent_green = colors.get("ACCENT_GREEN", "#00FF41")
    accent_yellow = colors.get("ACCENT_YELLOW", "#FFB300")

    adapter = get_wifi_adapter()
    if not adapter:
        status_callback("[!] No Wi-Fi adapter detected", accent_red)
        return
    if not profile_exists(ssid):
        status_callback(f"[!] Profile '{ssid}' not found", accent_red)
        return

    status_callback("[*] Executing Fix Sequence...", accent_yellow)
    try:
        subprocess.run(
            ["netsh", "wlan", "disconnect"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        time.sleep(2)

        if force_disable_enable:
            state_check = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"], text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            ).lower()
            if "disconnected" in state_check:
                status_callback("[*] Disabling network adapter...", accent_yellow)
                subprocess.run(
                    ["netsh", "interface", "set", "interface", adapter, "disable"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                time.sleep(3)
                status_callback("[*] Enabling network adapter...", accent_yellow)
                subprocess.run(
                    ["netsh", "interface", "set", "interface", adapter, "enable"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                time.sleep(5)

        subprocess.run(
            ["netsh", "wlan", "connect", f"name={ssid}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        time.sleep(5)

        verify = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"], text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).lower()

        if ssid.lower() in verify and "connected" in verify:
            status_callback("[+] Reconnected Successfully.", accent_green)
        else:
            status_callback("[!] Reconnect Failed.", accent_red)

    except Exception as exc:
        status_callback(f"[!] Error: {exc}", accent_red)
        logging.error("reconnect_wifi error: %s", exc)
