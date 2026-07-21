import json
import os
import socket
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from typing import Callable, Optional

import v2ray_paths
from v2ray_config import build_runtime_config
from v2ray_proxy_windows import clear_proxy_snapshot, restore_system_proxy, set_system_proxy

V2RAY_RELEASE_ZIP_URL = "https://github.com/v2fly/v2ray-core/releases/latest/download/v2ray-windows-64.zip"
V2RAY_RELEASE_PAGE = "https://github.com/v2fly/v2ray-core/releases/latest"
MAX_CORE_DOWNLOAD_BYTES = 200 * 1024 * 1024

_process: Optional[subprocess.Popen] = None
_log_handle = None


def _normalize_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _process_exe_path(pid: int) -> str:
    if sys.platform != "win32":
        return ""

    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
    finally:
        kernel32.CloseHandle(handle)
    return ""


def _pid_is_our_v2ray(pid: int) -> bool:
    exe_path = _process_exe_path(pid)
    return bool(exe_path and _normalize_path(exe_path) == _normalize_path(v2ray_paths.v2ray_exe_path()))


def _pid_is_running(pid: int) -> bool:
    return pid > 0 and _pid_is_our_v2ray(pid)


def _listener_pid(port: int) -> Optional[int]:
    if sys.platform != "win32":
        return None
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    except Exception:
        return None

    needle = f"127.0.0.1:{port}"
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[1] == needle and parts[3].upper() == "LISTENING":
            try:
                return int(parts[4])
            except ValueError:
                return None
    return None


def _terminate_our_listener(port: int) -> bool:
    pid = _listener_pid(port)
    if not pid or not _pid_is_our_v2ray(pid):
        return False
    _terminate_pid(pid)
    return True


def _load_saved_pid() -> Optional[int]:
    try:
        with open(v2ray_paths.PROCESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        pid = int(data.get("pid", 0))
        return pid if pid > 0 else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _save_pid(pid: int) -> None:
    v2ray_paths.ensure_dirs()
    v2ray_paths.atomic_write_json(v2ray_paths.PROCESS_FILE, {"pid": pid}, indent=2)


def _clear_saved_pid() -> None:
    try:
        os.remove(v2ray_paths.PROCESS_FILE)
    except OSError:
        pass


def _terminate_pid(pid: int) -> None:
    if not _pid_is_our_v2ray(pid):
        return
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    except Exception:
        pass


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _read_recent_log() -> str:
    try:
        with open(v2ray_paths.CORE_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            return f.read()[-2000:].strip()
    except OSError:
        return ""


def _is_within_directory(parent: str, child: str) -> bool:
    parent_abs = os.path.abspath(parent)
    child_abs = os.path.abspath(child)
    try:
        return os.path.commonpath([parent_abs, child_abs]) == parent_abs
    except ValueError:
        return False


def _reset_child_dir(path: str, parent: str) -> None:
    path_abs = os.path.abspath(path)
    parent_abs = os.path.abspath(parent)
    if path_abs == parent_abs or not _is_within_directory(parent_abs, path_abs):
        raise RuntimeError("Refusing to reset a directory outside the V2Ray app data folder.")
    if os.path.exists(path_abs):
        shutil.rmtree(path_abs)
    os.makedirs(path_abs, exist_ok=True)


def _download_file(url: str, path: str, max_bytes: int = MAX_CORE_DOWNLOAD_BYTES) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    raise RuntimeError("Downloaded V2Ray archive is unexpectedly large.")
            except ValueError:
                pass

        total = 0
        with open(path, "wb") as f:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError("Downloaded V2Ray archive is unexpectedly large.")
                f.write(chunk)


def _safe_extract_zip(zf: zipfile.ZipFile, target_dir: str) -> None:
    target_abs = os.path.abspath(target_dir)
    for member in zf.infolist():
        member_path = os.path.abspath(os.path.join(target_abs, member.filename))
        if not _is_within_directory(target_abs, member_path):
            raise RuntimeError("Downloaded V2Ray archive contains an unsafe path.")
    zf.extractall(target_abs)


def _copy_installed_core(source_dir: str) -> None:
    core_abs = os.path.abspath(v2ray_paths.CORE_DIR)
    for name in os.listdir(source_dir):
        source = os.path.join(source_dir, name)
        target = os.path.abspath(os.path.join(core_abs, name))
        if not _is_within_directory(core_abs, target):
            raise RuntimeError("Refusing to copy a file outside the V2Ray core directory.")
        if os.path.isdir(source):
            if os.path.exists(target):
                shutil.rmtree(target)
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def is_core_installed() -> bool:
    return os.path.exists(v2ray_paths.v2ray_exe_path())


def is_running() -> bool:
    if _process is not None and _process.poll() is None:
        return True
    saved_pid = _load_saved_pid()
    return bool(saved_pid and _pid_is_running(saved_pid))


def install_core(progress: Optional[Callable[[str], None]] = None) -> None:
    v2ray_paths.ensure_dirs()
    zip_path = os.path.join(v2ray_paths.APP_DIR, "v2ray-windows-64.zip")
    tmp_dir = os.path.join(v2ray_paths.APP_DIR, "_download")

    try:
        if progress:
            progress("Downloading v2ray-core from GitHub releases...")
        _download_file(V2RAY_RELEASE_ZIP_URL, zip_path)

        _reset_child_dir(tmp_dir, v2ray_paths.APP_DIR)

        if progress:
            progress("Extracting v2ray-core...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            _safe_extract_zip(zf, tmp_dir)

        extracted_exe = None
        for root, _dirs, files in os.walk(tmp_dir):
            if "v2ray.exe" in files:
                extracted_exe = os.path.join(root, "v2ray.exe")
                break

        if not extracted_exe:
            raise RuntimeError("v2ray.exe was not found in the downloaded archive.")

        _copy_installed_core(os.path.dirname(extracted_exe))
    finally:
        try:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except OSError:
            pass
        try:
            os.remove(zip_path)
        except OSError:
            pass


def start(raw_config: str, local_port: int, enable_system_proxy: bool = True) -> None:
    global _process, _log_handle
    local_port = v2ray_paths.normalize_local_port(local_port)
    if is_running():
        if enable_system_proxy:
            set_system_proxy(local_port)
        return
    if sys.platform != "win32":
        raise RuntimeError("V2Ray support is currently Windows-only.")
    if not is_core_installed():
        raise RuntimeError("V2Ray core is not installed yet.")
    if not _port_is_free(local_port) or not _port_is_free(local_port + 1):
        saved_pid = _load_saved_pid()
        if saved_pid and _pid_is_our_v2ray(saved_pid):
            _terminate_pid(saved_pid)
            time.sleep(0.5)
        if _terminate_our_listener(local_port) or _terminate_our_listener(local_port + 1):
            time.sleep(0.5)
        if not _port_is_free(local_port) or not _port_is_free(local_port + 1):
            raise RuntimeError(
                f"Local ports {local_port}/{local_port + 1} are already in use. "
                "Press STOP, close the other proxy app, or choose another port."
            )

    runtime = build_runtime_config(raw_config, local_port)
    v2ray_paths.ensure_dirs()
    v2ray_paths.atomic_write_json(v2ray_paths.RUNTIME_CONFIG, runtime, indent=2)

    _log_handle = open(v2ray_paths.CORE_LOG_FILE, "w", encoding="utf-8", errors="replace")
    _process = subprocess.Popen(
        [v2ray_paths.v2ray_exe_path(), "run", "-config", v2ray_paths.RUNTIME_CONFIG],
        cwd=v2ray_paths.CORE_DIR,
        stdout=_log_handle,
        stderr=_log_handle,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    _save_pid(_process.pid)
    time.sleep(0.5)
    if _process.poll() is not None:
        error = _read_recent_log()
        _process = None
        _clear_saved_pid()
        raise RuntimeError(error or "v2ray.exe exited immediately. Check the pasted config.")
    if enable_system_proxy:
        try:
            set_system_proxy(local_port)
        except Exception:
            stop()
            raise


def stop() -> None:
    global _process, _log_handle
    if _process is not None:
        try:
            if _process.poll() is None:
                _process.terminate()
                _process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            _process.kill()
        finally:
            _process = None
    saved_pid = _load_saved_pid()
    if saved_pid:
        _terminate_pid(saved_pid)
    state = v2ray_paths.load_state()
    local_port = v2ray_paths.normalize_local_port(state.get("local_port"))
    _terminate_our_listener(local_port)
    _terminate_our_listener(local_port + 1)
    _clear_saved_pid()
    if _log_handle is not None:
        try:
            _log_handle.close()
        except OSError:
            pass
        _log_handle = None
    restore_system_proxy()
    clear_proxy_snapshot()
