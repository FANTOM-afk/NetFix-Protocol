import base64
import json
from typing import Any, Dict
from urllib.parse import parse_qs, unquote, urlparse


def _decode_urlsafe_base64(value: str) -> bytes:
    value = value.strip()
    value += "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value.encode("utf-8"))


def _parse_vmess(link: str) -> Dict[str, Any]:
    payload = link[len("vmess://"):]
    data = json.loads(_decode_urlsafe_base64(payload).decode("utf-8"))
    net = data.get("net", "tcp") or "tcp"
    stream_settings: Dict[str, Any] = {"network": net}
    tls = data.get("tls", "")
    if tls:
        stream_settings["security"] = tls
        stream_settings["tlsSettings"] = {
            "serverName": data.get("sni") or data.get("host") or data.get("add", "")
        }
    if net == "ws":
        stream_settings["wsSettings"] = {
            "path": data.get("path", "/") or "/",
            "headers": {"Host": data.get("host", "")},
        }
    return {
        "protocol": "vmess",
        "settings": {
            "vnext": [{
                "address": data.get("add", ""),
                "port": int(data.get("port", 443)),
                "users": [{
                    "id": data.get("id", ""),
                    "alterId": int(data.get("aid", 0) or 0),
                    "security": data.get("scy", "auto") or "auto",
                }],
            }]
        },
        "streamSettings": stream_settings,
    }


def _parse_vless_or_trojan(link: str) -> Dict[str, Any]:
    parsed = urlparse(link)
    protocol = parsed.scheme
    query = parse_qs(parsed.query)
    address = parsed.hostname or ""
    port = parsed.port or 443
    user = unquote(parsed.username or "")
    network = query.get("type", ["tcp"])[0] or "tcp"
    security = query.get("security", ["none"])[0] or "none"
    stream_settings: Dict[str, Any] = {"network": network, "security": security}

    if security == "tls":
        stream_settings["tlsSettings"] = {"serverName": query.get("sni", [address])[0]}
    if network == "ws":
        stream_settings["wsSettings"] = {
            "path": query.get("path", ["/"])[0] or "/",
            "headers": {"Host": query.get("host", [""])[0]},
        }

    if protocol == "trojan":
        settings = {"servers": [{"address": address, "port": port, "password": user}]}
    else:
        settings = {
            "vnext": [{
                "address": address,
                "port": port,
                "users": [{"id": user, "encryption": query.get("encryption", ["none"])[0]}],
            }]
        }
    return {"protocol": protocol, "settings": settings, "streamSettings": stream_settings}


def extract_outbound(raw_config: str) -> Dict[str, Any]:
    text = raw_config.strip()
    if not text:
        raise ValueError("V2Ray config is empty.")
    if text.startswith("vmess://"):
        return _parse_vmess(text)
    if text.startswith("vless://") or text.startswith("trojan://"):
        return _parse_vless_or_trojan(text)

    parsed = json.loads(text)
    if "outbounds" in parsed:
        outbounds = parsed.get("outbounds") or []
        if not outbounds:
            raise ValueError("The V2Ray JSON config has no outbounds.")
        return outbounds[0]
    if "protocol" in parsed and "settings" in parsed:
        return parsed
    raise ValueError("Paste a vmess/vless/trojan link, a full V2Ray JSON config, or one outbound JSON object.")


def build_runtime_config(raw_config: str, local_port: int) -> Dict[str, Any]:
    outbound = extract_outbound(raw_config)
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "netfix-socks",
                "listen": "127.0.0.1",
                "port": local_port,
                "protocol": "socks",
                "settings": {"udp": True, "auth": "noauth"},
            },
            {
                "tag": "netfix-http",
                "listen": "127.0.0.1",
                "port": local_port + 1,
                "protocol": "http",
                "settings": {"timeout": 300},
            },
        ],
        "outbounds": [outbound, {"tag": "direct", "protocol": "freedom"}],
    }


def _name_from_raw_config(raw_config: str) -> str:
    text = raw_config.strip()
    if text.startswith(("vless://", "trojan://")):
        parsed = urlparse(text)
        if parsed.fragment:
            return unquote(parsed.fragment).strip()
    if text.startswith("vmess://"):
        try:
            payload = text[len("vmess://"):]
            data = json.loads(_decode_urlsafe_base64(payload).decode("utf-8"))
            return str(data.get("ps", "")).strip()
        except Exception:
            return ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if isinstance(data, dict):
        return str(data.get("tag") or data.get("name") or data.get("remarks") or "").strip()
    return ""


def describe_config(raw_config: str) -> Dict[str, Any]:
    outbound = extract_outbound(raw_config)
    protocol = str(outbound.get("protocol", "")).upper() or "UNKNOWN"
    settings = outbound.get("settings", {}) if isinstance(outbound.get("settings"), dict) else {}
    stream = outbound.get("streamSettings", {}) if isinstance(outbound.get("streamSettings"), dict) else {}

    address = ""
    port = ""
    if "vnext" in settings and settings["vnext"]:
        server = settings["vnext"][0]
        address = str(server.get("address", ""))
        port = str(server.get("port", ""))
    elif "servers" in settings and settings["servers"]:
        server = settings["servers"][0]
        address = str(server.get("address", ""))
        port = str(server.get("port", ""))

    network = str(stream.get("network", "tcp") or "tcp").upper()
    security = str(stream.get("security", "none") or "none").upper()
    tls = stream.get("tlsSettings", {}) if isinstance(stream.get("tlsSettings"), dict) else {}
    ws = stream.get("wsSettings", {}) if isinstance(stream.get("wsSettings"), dict) else {}
    name = _name_from_raw_config(raw_config) or address or protocol

    return {
        "name": name[:80],
        "protocol": protocol,
        "address": address,
        "port": port,
        "network": network,
        "security": security,
        "sni": str(tls.get("serverName", "")),
        "path": str(ws.get("path", "")),
    }
