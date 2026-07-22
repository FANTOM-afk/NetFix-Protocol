"""
main.py
=======
Entry point for NET_FIX_PROTOCOL.

Admin elevation is checked BEFORE importing the app module, so the UAC
prompt happens before any GUI libraries (customtkinter, matplotlib) are
loaded. Runtime work belongs here; the rest of the project should stay
importable without launching the app.

Single-instance enforcement via Windows named mutex.
"""

import ctypes
import importlib.util
import logging
import os
import sys
import traceback

import utils

ERROR_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_log.txt")
MUTEX_NAME = "Local\\NetFixProtocol_SingleInstanceMutex"
UPDATER_FILE = "Net-fix-updater.py"


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def _show_error(title: str, message: str) -> None:
    with open(ERROR_LOG, "w", encoding="utf-8") as f:
        f.write(f"{title}\n{'=' * 60}\n{message}\n")
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        print(message, file=sys.stderr)


def _acquire_single_instance_mutex() -> tuple[bool, int]:
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    last_error = kernel32.GetLastError()
    return (mutex != 0, last_error)


def _bring_existing_window_to_front() -> None:
    user32 = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)
    def enum_windows_proc(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            if "NET_FIX_PROTOCOL" in buff.value:
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
                return 0
        return 1

    user32.EnumWindows(enum_windows_proc, 0)


def _run_cloudflare_webview(argv: list[str]) -> bool:
    if len(argv) < 3 or argv[1] != "--cloudflare-webview":
        return False

    import cloudflare

    cloudflare.run_cloudflare_window(argv[2])
    return True


def _load_update_checker():
    updater_path = utils.resource_path(UPDATER_FILE)
    if not os.path.exists(updater_path):
        logging.info("Update checker file not found: %s", updater_path)
        return None

    spec = importlib.util.spec_from_file_location("net_fix_updater_runtime", updater_path)
    if spec is None or spec.loader is None:
        logging.info("Could not load update checker from: %s", updater_path)
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _start_update_check(root, status_callback=None, install_handler_callback=None) -> None:
    try:
        updater = _load_update_checker()
        if updater is None:
            return
        if install_handler_callback is not None:
            install_handler_callback(updater.install_latest_update)
        updater.start_update_check(
            current_version=getattr(updater, "CURRENT_VERSION", "1.3.2"),
            tk_root=root,
            delay_seconds=2.0,
            status_callback=status_callback,
            prompt_on_update=False,
        )
    except Exception as exc:
        logging.warning("Update checker failed to start: %s", exc)


def main() -> None:
    _configure_logging()

    if _run_cloudflare_webview(sys.argv):
        return

    if not utils.check_admin():
        utils.elevate_and_restart()

    from app import NetFixApp  # noqa: E402  (must come after the admin check)

    acquired, last_error = _acquire_single_instance_mutex()
    if not acquired or last_error == 183:
        _bring_existing_window_to_front()
        sys.exit(0)

    app = NetFixApp()
    _start_update_check(app.root, app.set_update_badge, app.set_update_install_handler)
    app.run()


def _main_with_error_dialog() -> None:
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        _show_error("NetFixProtocol - ERROR", err)
        sys.exit(1)


if __name__ == "__main__":
    _main_with_error_dialog()
