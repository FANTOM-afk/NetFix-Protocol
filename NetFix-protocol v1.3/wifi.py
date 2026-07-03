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
import tempfile
from typing import Optional, Tuple, Callable
from xml.sax.saxutils import escape


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
            ["netsh", "interface", "show", "interface"], text=True,
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
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(ssid)
        os.replace(tmp_path, path)
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


def scan_available_networks() -> list[dict]:
    try:
        output = subprocess.check_output(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        networks = []
        current = None
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("SSID"):
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    ssid = parts[1].strip()
                    if ssid:
                        current = {"ssid": ssid, "signal": None}
                        networks.append(current)
            elif stripped.startswith("Signal") and current:
                sig_match = re.search(r"(\d+)%", stripped)
                if sig_match:
                    current["signal"] = sig_match.group(1) + "%"
        return networks
    except subprocess.SubprocessError:
        return []
    except Exception as exc:
        logging.debug("scan_available_networks error: %s", exc)
        return []


def connect_to_network(ssid: str, password: str | None = None) -> str:
    try:
        if password:
            ssid_xml = escape(ssid)
            password_xml = escape(password)
            profile_xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid_xml}</name>
    <SSIDConfig>
        <SSID>
            <name>{ssid_xml}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{password_xml}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>"""
            xml_file = tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", delete=False, prefix="netfix_", suffix=".xml"
            )
            xml_path = xml_file.name
            with xml_file as f:
                f.write(profile_xml)
            try:
                subprocess.run(
                    ["netsh", "wlan", "add", "profile", f"filename={xml_path}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            finally:
                try:
                    os.remove(xml_path)
                except OSError:
                    pass

        subprocess.run(
            ["netsh", "wlan", "connect", f"name={ssid}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        time.sleep(5)

        current = get_current_wifi_ssid()
        if current and current.lower() == ssid.lower():
            return f"[+] Connected to '{ssid}'"
        return f"[!] Failed to connect to '{ssid}'"
    except Exception as exc:
        logging.error("connect_to_network error: %s", exc)
        return f"[!] Connection error: {exc}"


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
