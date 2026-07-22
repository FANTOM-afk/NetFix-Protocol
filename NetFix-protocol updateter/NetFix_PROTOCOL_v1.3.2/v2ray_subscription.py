import base64
import re
import urllib.request
from urllib.parse import urlparse
from typing import Callable, List, Optional

from v2ray_config import describe_config

SUPPORTED_PREFIXES = ("vmess://", "vless://", "trojan://")
MAX_SUBSCRIPTION_BYTES = 5 * 1024 * 1024


def _decode_base64_text(text: str) -> str:
    compact = "".join(text.split())
    if not compact:
        return text
    try:
        compact += "=" * (-len(compact) % 4)
        decoded = base64.urlsafe_b64decode(compact.encode("utf-8"))
        return decoded.decode("utf-8", errors="replace")
    except Exception:
        return text


def _candidate_texts(text: str) -> List[str]:
    decoded = _decode_base64_text(text)
    if decoded != text:
        return [text, decoded]
    return [text]


def extract_configs(subscription_text: str) -> List[str]:
    configs = []
    seen = set()
    pattern = re.compile(r"(?:vmess|vless|trojan)://[^\s\"'<>]+", re.IGNORECASE)

    for text in _candidate_texts(subscription_text):
        for line in text.replace("\r", "\n").split("\n"):
            item = line.strip().strip(",").strip()
            if not item:
                continue
            if item.startswith(SUPPORTED_PREFIXES):
                value = item
            else:
                matches = pattern.findall(item)
                if not matches:
                    continue
                for match in matches:
                    clean = match.strip().strip(",")
                    if clean not in seen:
                        configs.append(clean)
                        seen.add(clean)
                continue

            if value not in seen:
                configs.append(value)
                seen.add(value)

    valid = []
    for raw_config in configs:
        try:
            describe_config(raw_config)
        except Exception:
            continue
        valid.append(raw_config)
    return valid


def fetch_subscription(url: str, progress: Optional[Callable[[str], None]] = None) -> List[str]:
    url = url.strip()
    if not url:
        raise ValueError("Subscription URL is empty.")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ValueError("Subscription URL must start with http:// or https://.")

    if progress:
        progress("Fetching subscription...")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NetFixProtocol/1.2",
            "Accept": "text/plain, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        content = response.read(MAX_SUBSCRIPTION_BYTES + 1)
    if len(content) > MAX_SUBSCRIPTION_BYTES:
        raise ValueError("Subscription response is too large.")

    text = content.decode("utf-8", errors="replace")
    configs = extract_configs(text)
    if not configs:
        raise ValueError("No supported vmess/vless/trojan configs were found in this subscription.")
    return configs
