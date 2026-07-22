import socket
import time
from typing import Dict, Optional


def tcp_ping_profile(profile: Dict, timeout: float = 3.0) -> Optional[int]:
    meta = profile.get("meta", {}) if isinstance(profile.get("meta"), dict) else {}
    host = str(meta.get("address") or "").strip()
    port_raw = str(meta.get("port") or "").strip()
    if not host or not port_raw:
        return None
    try:
        port = int(port_raw)
    except ValueError:
        return None

    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return int((time.perf_counter() - start) * 1000)
    except OSError:
        return None
