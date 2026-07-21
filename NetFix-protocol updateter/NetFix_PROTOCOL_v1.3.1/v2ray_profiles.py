import json
import time
import uuid
from typing import Any, Dict, List, Optional

import v2ray_paths
from v2ray_config import describe_config


def _empty_store() -> Dict[str, Any]:
    return {"active_profile_id": "", "profiles": [], "group_meta": {}}


def _normalize_group_name(group: str) -> str:
    return str(group or "Default").strip()[:40] or "Default"


def _normalize_profile(profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_config = str(profile.get("raw_config", "")).strip()
    if not raw_config:
        return None
    meta = profile.get("meta")
    if not isinstance(meta, dict):
        meta = describe_config(raw_config)
    normalized = {
        "id": str(profile.get("id") or uuid.uuid4()),
        "name": str(profile.get("name") or meta.get("name") or "V2Ray Profile").strip()[:80],
        "group": str(profile.get("group") or "Default").strip()[:40] or "Default",
        "raw_config": raw_config,
        "meta": meta,
        "created_at": float(profile.get("created_at") or time.time()),
        "updated_at": float(profile.get("updated_at") or time.time()),
    }
    if isinstance(profile.get("latency_ms"), int):
        normalized["latency_ms"] = profile["latency_ms"]
    return normalized


def load_store() -> Dict[str, Any]:
    try:
        with open(v2ray_paths.PROFILES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = _empty_store()

    profiles = []
    for raw_profile in data.get("profiles", []) if isinstance(data, dict) else []:
        if isinstance(raw_profile, dict):
            profile = _normalize_profile(raw_profile)
            if profile:
                profiles.append(profile)

    raw_group_meta = data.get("group_meta", {}) if isinstance(data, dict) else {}
    group_meta = {}
    if isinstance(raw_group_meta, dict):
        for group, meta in raw_group_meta.items():
            group_name = _normalize_group_name(str(group))
            if not isinstance(meta, dict):
                continue
            subscription_url = str(meta.get("subscription_url", "")).strip()
            group_meta[group_name] = {"subscription_url": subscription_url}

    store = {
        "active_profile_id": str(data.get("active_profile_id", "")) if isinstance(data, dict) else "",
        "profiles": profiles,
        "group_meta": group_meta,
    }
    if store["active_profile_id"] and not get_profile(store, store["active_profile_id"]):
        store["active_profile_id"] = ""
    return store


def save_store(store: Dict[str, Any]) -> None:
    v2ray_paths.ensure_dirs()
    v2ray_paths.atomic_write_json(v2ray_paths.PROFILES_FILE, store, indent=2, ensure_ascii=False)


def migrate_legacy_user_config() -> None:
    store = load_store()
    if store["profiles"]:
        return
    raw_config = v2ray_paths.load_user_config().strip()
    if not raw_config:
        return
    profile = create_profile(raw_config, group="Default")
    store = {"active_profile_id": profile["id"], "profiles": [profile], "group_meta": {}}
    save_store(store)


def create_profile(raw_config: str, name: str = "", group: str = "Default") -> Dict[str, Any]:
    meta = describe_config(raw_config)
    now = time.time()
    return {
        "id": str(uuid.uuid4()),
        "name": (name.strip() or str(meta.get("name") or "V2Ray Profile"))[:80],
        "group": (group.strip() or "Default")[:40],
        "raw_config": raw_config.strip(),
        "meta": meta,
        "created_at": now,
        "updated_at": now,
    }


def add_profile(store: Dict[str, Any], raw_config: str, name: str = "", group: str = "Default") -> Dict[str, Any]:
    profile = create_profile(raw_config, name=name, group=group)
    store.setdefault("profiles", []).append(profile)
    store["active_profile_id"] = profile["id"]
    save_store(store)
    return profile


def add_profiles(store: Dict[str, Any], raw_configs: List[str], group: str = "Subscription") -> List[Dict[str, Any]]:
    existing = {
        str(profile.get("raw_config", "")).strip(): profile
        for profile in store.get("profiles", [])
    }
    changed = []
    for raw_config in raw_configs:
        raw_config = raw_config.strip()
        if not raw_config:
            continue
        if raw_config in existing:
            profile = existing[raw_config]
            if profile.get("group") != group:
                profile["group"] = group
                profile["updated_at"] = time.time()
                changed.append(profile)
            continue
        profile = create_profile(raw_config, group=group)
        store.setdefault("profiles", []).append(profile)
        existing[raw_config] = profile
        changed.append(profile)
    if changed:
        store["active_profile_id"] = changed[0]["id"]
        save_store(store)
    return changed


def update_profile(store: Dict[str, Any], profile_id: str, raw_config: str, name: str, group: str) -> Dict[str, Any]:
    profile = get_profile(store, profile_id)
    if not profile:
        raise ValueError("Profile not found.")
    meta = describe_config(raw_config)
    profile["name"] = (name.strip() or str(meta.get("name") or "V2Ray Profile"))[:80]
    profile["group"] = (group.strip() or "Default")[:40]
    profile["raw_config"] = raw_config.strip()
    profile["meta"] = meta
    profile["updated_at"] = time.time()
    save_store(store)
    return profile


def delete_profile(store: Dict[str, Any], profile_id: str) -> None:
    store["profiles"] = [profile for profile in store.get("profiles", []) if profile.get("id") != profile_id]
    if store.get("active_profile_id") == profile_id:
        store["active_profile_id"] = store["profiles"][0]["id"] if store["profiles"] else ""
    save_store(store)


def delete_group(store: Dict[str, Any], group: str) -> int:
    group = _normalize_group_name(group)
    before = len(store.get("profiles", []))
    store["profiles"] = [
        profile for profile in store.get("profiles", [])
        if _normalize_group_name(str(profile.get("group", "Default"))) != group
    ]
    deleted = before - len(store["profiles"])
    active_profile_id = str(store.get("active_profile_id") or "")
    if active_profile_id and not get_profile(store, active_profile_id):
        store["active_profile_id"] = store["profiles"][0]["id"] if store["profiles"] else ""
    meta = store.get("group_meta", {})
    if isinstance(meta, dict):
        meta.pop(group, None)
    save_store(store)
    return deleted


def set_active_profile(store: Dict[str, Any], profile_id: str) -> None:
    if not get_profile(store, profile_id):
        raise ValueError("Profile not found.")
    store["active_profile_id"] = profile_id
    save_store(store)


def get_profile(store: Dict[str, Any], profile_id: str) -> Optional[Dict[str, Any]]:
    return next((profile for profile in store.get("profiles", []) if profile.get("id") == profile_id), None)


def active_profile(store: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    profile_id = str(store.get("active_profile_id") or "")
    if profile_id:
        profile = get_profile(store, profile_id)
        if profile:
            return profile
    profiles = store.get("profiles", [])
    return profiles[0] if profiles else None


def groups(store: Dict[str, Any]) -> List[str]:
    names = {
        _normalize_group_name(str(profile.get("group") or "Default"))
        for profile in store.get("profiles", [])
    }
    meta = store.get("group_meta", {})
    if isinstance(meta, dict):
        names.update(_normalize_group_name(str(group)) for group in meta.keys())
    names = sorted(names)
    return names or ["Default"]


def group_subscription_url(store: Dict[str, Any], group: str) -> str:
    meta = store.get("group_meta", {})
    if not isinstance(meta, dict):
        return ""
    group_meta = meta.get(_normalize_group_name(group), {})
    if not isinstance(group_meta, dict):
        return ""
    return str(group_meta.get("subscription_url", "")).strip()


def set_group_subscription_url(store: Dict[str, Any], group: str, subscription_url: str) -> None:
    group = _normalize_group_name(group)
    subscription_url = str(subscription_url or "").strip()
    meta = store.setdefault("group_meta", {})
    if not isinstance(meta, dict):
        meta = {}
        store["group_meta"] = meta
    group_meta = meta.setdefault(group, {})
    if not isinstance(group_meta, dict):
        group_meta = {}
        meta[group] = group_meta
    group_meta["subscription_url"] = subscription_url
    save_store(store)


def ensure_group(store: Dict[str, Any], group: str, subscription_url: str = "") -> str:
    group = _normalize_group_name(group)
    subscription_url = str(subscription_url or "").strip()
    meta = store.setdefault("group_meta", {})
    if not isinstance(meta, dict):
        meta = {}
        store["group_meta"] = meta
    group_meta = meta.setdefault(group, {})
    if not isinstance(group_meta, dict):
        group_meta = {}
        meta[group] = group_meta
    if subscription_url or "subscription_url" not in group_meta:
        group_meta["subscription_url"] = subscription_url
    save_store(store)
    return group


def update_group(store: Dict[str, Any], old_group: str, new_group: str, subscription_url: str) -> str:
    old_group = _normalize_group_name(old_group)
    new_group = _normalize_group_name(new_group)
    now = time.time()
    for profile in store.get("profiles", []):
        if _normalize_group_name(str(profile.get("group", "Default"))) == old_group:
            profile["group"] = new_group
            profile["updated_at"] = now

    meta = store.setdefault("group_meta", {})
    if not isinstance(meta, dict):
        meta = {}
        store["group_meta"] = meta
    old_meta = meta.pop(old_group, {}) if old_group != new_group else meta.get(old_group, {})
    if not isinstance(old_meta, dict):
        old_meta = {}
    subscription_url = str(subscription_url or "").strip()
    old_meta["subscription_url"] = subscription_url
    meta[new_group] = old_meta
    save_store(store)
    return new_group


def profiles_in_group(store: Dict[str, Any], group: str) -> List[Dict[str, Any]]:
    selected = [profile for profile in store.get("profiles", []) if profile.get("group", "Default") == group]
    def sort_key(profile: Dict[str, Any]):
        latency = profile.get("latency_ms")
        has_latency = isinstance(latency, int)
        return (
            0 if has_latency else 1,
            latency if has_latency else 999999,
            str(profile.get("name", "")).lower(),
        )

    return sorted(selected, key=sort_key)
