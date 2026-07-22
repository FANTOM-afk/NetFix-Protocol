"""
Net-fix-updater.py
==================
Startup update checker for NetFix Protocol.

The filename intentionally keeps the project naming style. Because hyphens are
not valid Python module names, main.py loads this file with importlib.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from typing import Any, Callable, Optional


CURRENT_VERSION = "1.3.2"
RELEASES_PAGE_URL = "https://github.com/FANTOM-afk/NetFix-Protocol/releases"
LATEST_RELEASE_API_URL = "https://api.github.com/repos/FANTOM-afk/NetFix-Protocol/releases/latest"
USER_AGENT = "NetFixProtocol-Updater/1.3.2"

_CHECK_LOCK = threading.Lock()
_CHECK_STARTED = False


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    release_name: str
    release_url: str
    asset_name: str
    asset_url: str


@dataclass(frozen=True)
class UpdateCheckResult:
    ok: bool
    update_available: bool
    current_version: str
    latest_version: Optional[str] = None
    release_url: str = RELEASES_PAGE_URL
    asset_name: Optional[str] = None
    asset_url: Optional[str] = None
    error: Optional[str] = None

    @property
    def info(self) -> Optional[UpdateInfo]:
        if not self.update_available or not self.latest_version or not self.asset_name or not self.asset_url:
            return None
        return UpdateInfo(
            current_version=self.current_version,
            latest_version=self.latest_version,
            release_name=f"NetFix Protocol {self.latest_version}",
            release_url=self.release_url,
            asset_name=self.asset_name,
            asset_url=self.asset_url,
        )


def _extract_version(value: Any) -> Optional[str]:
    match = re.search(r"\d+(?:\.\d+){0,3}", str(value or ""))
    return match.group(0) if match else None


def _version_key(value: str) -> tuple[int, int, int, int]:
    version = _extract_version(value)
    if not version:
        return (0, 0, 0, 0)
    parts = [int(part) for part in version.split(".")]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])  # type: ignore[return-value]


def is_newer_version(latest_version: str, current_version: str = CURRENT_VERSION) -> bool:
    return _version_key(latest_version) > _version_key(current_version)


def _request_json(url: str, timeout: int = 8) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("GitHub response was not a JSON object")
    return data


def _find_windows_exe_asset(assets: Any) -> Optional[dict[str, Any]]:
    if not isinstance(assets, list):
        return None

    exe_assets = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if name.lower().endswith(".exe") and url:
            exe_assets.append(asset)

    if not exe_assets:
        return None

    def score(asset: dict[str, Any]) -> tuple[int, str]:
        name = str(asset.get("name") or "").lower()
        priority = 0
        if "netfix" in name or "netfix_protocol" in name or "netfix-protocol" in name:
            priority += 10
        return (-priority, name)

    return sorted(exe_assets, key=score)[0]


def check_for_update(
    current_version: str = CURRENT_VERSION,
    api_url: str = LATEST_RELEASE_API_URL,
    timeout: int = 8,
) -> UpdateCheckResult:
    try:
        release = _request_json(api_url, timeout=timeout)
        tag_name = str(release.get("tag_name") or "")
        release_name = str(release.get("name") or tag_name)
        latest_version = _extract_version(tag_name) or _extract_version(release_name)
        release_url = str(release.get("html_url") or RELEASES_PAGE_URL)

        if not latest_version:
            return UpdateCheckResult(
                ok=True,
                update_available=False,
                current_version=current_version,
                release_url=release_url,
                error="Latest release has no parsable version",
            )

        if not is_newer_version(latest_version, current_version):
            return UpdateCheckResult(
                ok=True,
                update_available=False,
                current_version=current_version,
                latest_version=latest_version,
                release_url=release_url,
            )

        exe_asset = _find_windows_exe_asset(release.get("assets"))
        if not exe_asset:
            return UpdateCheckResult(
                ok=True,
                update_available=False,
                current_version=current_version,
                latest_version=latest_version,
                release_url=release_url,
                error="New release exists, but no EXE asset is attached yet",
            )

        return UpdateCheckResult(
            ok=True,
            update_available=True,
            current_version=current_version,
            latest_version=latest_version,
            release_url=release_url,
            asset_name=str(exe_asset.get("name") or "NetFix Protocol update.exe"),
            asset_url=str(exe_asset.get("browser_download_url") or release_url),
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
        return UpdateCheckResult(
            ok=False,
            update_available=False,
            current_version=current_version,
            error=str(exc),
        )


def _build_update_message(info: UpdateInfo) -> str:
    return (
        "A new NetFix Protocol update is available.\n"
        f"Current version: {info.current_version}\n"
        f"New version: {info.latest_version}\n"
        f"EXE file: {info.asset_name}\n\n"
        "Do you want to open the download page now?\n\n"
        "آپدیت جدید NetFix Protocol آماده است.\n"
        f"نسخه فعلی: {info.current_version}\n"
        f"نسخه جدید: {info.latest_version}\n"
        f"فایل EXE: {info.asset_name}\n\n"
        "می‌خواهید صفحه دانلود الان باز شود؟"
    )


def _prompt_with_tk(info: UpdateInfo, tk_root: Any) -> None:
    import tkinter.messagebox as messagebox

    answer = messagebox.askyesno(
        "NetFix Protocol Update",
        _build_update_message(info),
        parent=tk_root,
    )
    if answer:
        webbrowser.open(info.asset_url or info.release_url)


def _prompt_with_windows_messagebox(info: UpdateInfo) -> None:
    result = ctypes.windll.user32.MessageBoxW(
        0,
        _build_update_message(info),
        "NetFix Protocol Update",
        0x00000004 | 0x00000020,
    )
    if result == 6:
        webbrowser.open(info.asset_url or info.release_url)


def prompt_for_update(info: UpdateInfo, tk_root: Any = None) -> None:
    try:
        if tk_root is not None:
            _prompt_with_tk(info, tk_root)
        else:
            _prompt_with_windows_messagebox(info)
    except Exception as exc:
        logging.warning("Could not show update prompt: %s", exc)


def _is_frozen_exe() -> bool:
    return bool(getattr(sys, "frozen", False)) and sys.executable.lower().endswith(".exe")


def _current_exe_path() -> Optional[str]:
    if not _is_frozen_exe():
        return None
    return os.path.abspath(sys.executable)


def _safe_asset_name(asset_name: str, latest_version: str) -> str:
    fallback = f"NetFix_PROTOCOL_{latest_version}.exe"
    name = str(asset_name or fallback).strip() or fallback
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip(". ")
    if not name:
        name = fallback
    if not name.lower().endswith(".exe"):
        name = f"{name}.exe"
    return name


def _download_directory() -> str:
    current_exe = _current_exe_path()
    if current_exe:
        return os.path.dirname(current_exe)
    path = os.path.join(tempfile.gettempdir(), "NetFixProtocol", "updates")
    os.makedirs(path, exist_ok=True)
    return path


def _target_update_path(info: UpdateInfo) -> str:
    download_dir = _download_directory()
    os.makedirs(download_dir, exist_ok=True)
    filename = _safe_asset_name(info.asset_name, info.latest_version)
    target = os.path.abspath(os.path.join(download_dir, filename))
    current_exe = _current_exe_path()
    if current_exe and os.path.normcase(target) == os.path.normcase(current_exe):
        stem, ext = os.path.splitext(filename)
        target = os.path.abspath(os.path.join(download_dir, f"{stem}_{info.latest_version}_new{ext}"))
    return target


def _download_exe(info: UpdateInfo, timeout: int = 120) -> str:
    target = _target_update_path(info)
    part = f"{target}.part"
    request = urllib.request.Request(
        info.asset_url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        with open(part, "wb") as file:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                file.write(chunk)

    if os.path.getsize(part) <= 0:
        raise ValueError("Downloaded update file is empty")
    with open(part, "rb") as file:
        if file.read(2) != b"MZ":
            raise ValueError("Downloaded update is not a valid Windows EXE")

    try:
        os.replace(part, target)
    except OSError:
        stem, ext = os.path.splitext(target)
        target = f"{stem}_{int(time.time())}{ext}"
        os.replace(part, target)
    return target


def _powershell_path() -> str:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    path = os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    return path if os.path.exists(path) else "powershell"


def _write_update_helper(new_exe_path: str, old_exe_path: Optional[str]) -> str:
    helper_dir = os.path.join(tempfile.gettempdir(), "NetFixProtocol", "update-helper")
    os.makedirs(helper_dir, exist_ok=True)
    helper_path = os.path.join(helper_dir, f"netfix_update_{os.getpid()}_{int(time.time())}.ps1")
    log_path = os.path.join(helper_dir, "netfix_update.log")
    delete_old = bool(old_exe_path and os.path.exists(old_exe_path))
    script = r'''param(
    [int]$OldPid,
    [string]$OldExe,
    [string]$NewExe,
    [string]$LogPath,
    [bool]$DeleteOld
)

function Write-NetFixLog([string]$Message) {
    try {
        Add-Content -LiteralPath $LogPath -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message)
    } catch {}
}

try {
    Write-NetFixLog "helper-start oldPid=$OldPid newExe=$NewExe"
    for ($i = 0; $i -lt 90; $i++) {
        $oldProcess = Get-Process -Id $OldPid -ErrorAction SilentlyContinue
        if ($null -eq $oldProcess) { break }
        Start-Sleep -Seconds 1
    }

    if (-not (Test-Path -LiteralPath $NewExe)) {
        Write-NetFixLog "new-exe-missing"
        exit 2
    }

    $workDir = Split-Path -Parent $NewExe
    $newProcess = Start-Process -FilePath $NewExe -WorkingDirectory $workDir -PassThru
    Start-Sleep -Seconds 4
    $running = $false
    if ($null -ne $newProcess) {
        $running = $null -ne (Get-Process -Id $newProcess.Id -ErrorAction SilentlyContinue)
    }

    if ($running -and $DeleteOld -and $OldExe -and (Test-Path -LiteralPath $OldExe) -and ($OldExe -ne $NewExe)) {
        for ($i = 0; $i -lt 30; $i++) {
            try {
                Remove-Item -LiteralPath $OldExe -Force -ErrorAction Stop
                Write-NetFixLog "old-exe-deleted"
                break
            } catch {
                Start-Sleep -Seconds 1
            }
        }
    } elseif ($running) {
        Write-NetFixLog "new-exe-running-no-old-delete"
    } else {
        Write-NetFixLog "new-exe-not-running"
    }
} catch {
    Write-NetFixLog ("helper-error " + $_.Exception.Message)
} finally {
    Start-Sleep -Seconds 1
    try { Remove-Item -LiteralPath $PSCommandPath -Force } catch {}
}
'''
    with open(helper_path, "w", encoding="utf-8", newline="\r\n") as file:
        file.write(script)
    return helper_path


def _start_update_helper(new_exe_path: str) -> None:
    old_exe_path = _current_exe_path()
    helper_path = _write_update_helper(new_exe_path, old_exe_path)
    log_path = os.path.join(os.path.dirname(helper_path), "netfix_update.log")
    creationflags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    subprocess.Popen(
        [
            _powershell_path(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            helper_path,
            "-OldPid",
            str(os.getpid()),
            "-OldExe",
            old_exe_path or "",
            "-NewExe",
            new_exe_path,
            "-LogPath",
            log_path,
            "-DeleteOld",
            "$true" if old_exe_path else "$false",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
    )


def install_latest_update(
    update_result: UpdateCheckResult,
    tk_root: Any = None,
    status_callback: Optional[Callable[[str, Optional[UpdateCheckResult]], None]] = None,
    on_ready_to_restart: Optional[Callable[[], None]] = None,
) -> Optional[threading.Thread]:
    info = update_result.info if update_result else None
    if info is None:
        _send_status(status_callback, "download_failed", update_result)
        return None

    def worker() -> None:
        try:
            _send_status(status_callback, "downloading", update_result)
            new_exe_path = _download_exe(info)
            _send_status(status_callback, "installing", update_result)
            _start_update_helper(new_exe_path)
            _send_status(status_callback, "restarting", update_result)
            if on_ready_to_restart is not None:
                if tk_root is not None:
                    try:
                        tk_root.after(800, on_ready_to_restart)
                    except Exception:
                        on_ready_to_restart()
                else:
                    on_ready_to_restart()
        except Exception as exc:
            logging.warning("Update install failed: %s", exc)
            _send_status(status_callback, "download_failed", update_result)

    thread = threading.Thread(target=worker, name="NetFixUpdateInstall", daemon=True)
    thread.start()
    return thread


def _send_status(
    status_callback: Optional[Callable[[str, Optional[UpdateCheckResult]], None]],
    state: str,
    result: Optional[UpdateCheckResult] = None,
) -> None:
    if status_callback is None:
        return
    try:
        status_callback(state, result)
    except Exception as exc:
        logging.warning("Could not update update-check badge: %s", exc)


def start_update_check(
    current_version: str = CURRENT_VERSION,
    tk_root: Any = None,
    delay_seconds: float = 2.0,
    status_callback: Optional[Callable[[str, Optional[UpdateCheckResult]], None]] = None,
    prompt_on_update: bool = False,
) -> Optional[threading.Thread]:
    global _CHECK_STARTED

    with _CHECK_LOCK:
        if _CHECK_STARTED:
            return None
        _CHECK_STARTED = True

    def worker() -> None:
        _send_status(status_callback, "checking")
        if delay_seconds > 0:
            time.sleep(delay_seconds)

        result = check_for_update(current_version=current_version)
        if not result.ok:
            _send_status(status_callback, "error", result)
            logging.info("Update check skipped: %s", result.error)
            return
        if not result.update_available:
            _send_status(status_callback, "up_to_date", result)
            if result.error:
                logging.info("Update check: %s", result.error)
            return

        _send_status(status_callback, "update_available", result)
        if not prompt_on_update:
            return

        info = result.info
        if info is None:
            return

        def notify() -> None:
            prompt_for_update(info, tk_root=tk_root)

        if tk_root is not None:
            try:
                tk_root.after(0, notify)
                return
            except Exception as exc:
                logging.warning("Could not schedule update prompt on UI thread: %s", exc)
        notify()

    thread = threading.Thread(target=worker, name="NetFixUpdateCheck", daemon=True)
    thread.start()
    return thread
