import threading
from typing import Callable, Optional

import win32api
import win32con
import win32gui

import utils

WM_TRAYICON = win32con.WM_USER + 20
MENU_SHOW = 1001
MENU_HIDE = 1002
MENU_QUIT = 1003


class TrayIcon:
    def __init__(
        self,
        tooltip: str,
        on_show: Callable[[], None],
        on_hide: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self.tooltip = tooltip
        self.on_show = on_show
        self.on_hide = on_hide
        self.on_quit = on_quit
        self._hwnd: Optional[int] = None
        self._hicon: Optional[int] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._hwnd:
            try:
                win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass

    def update_tooltip(self, tooltip: str) -> None:
        self.tooltip = tooltip[:127]
        if not self._hwnd or not self._hicon:
            return
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, self._tray_data())
        except Exception:
            pass

    def _run(self) -> None:
        hinst = win32api.GetModuleHandle(None)
        class_name = "NetFixProtocolTrayWindow"

        message_map = {
            win32con.WM_DESTROY: self._on_destroy,
            win32con.WM_CLOSE: self._on_close,
            win32con.WM_COMMAND: self._on_command,
            WM_TRAYICON: self._on_tray,
        }
        wc = win32gui.WNDCLASS()
        wc.hInstance = hinst
        wc.lpszClassName = class_name
        wc.lpfnWndProc = message_map

        try:
            win32gui.RegisterClass(wc)
        except Exception:
            pass

        self._hwnd = win32gui.CreateWindow(
            class_name,
            "NetFixProtocolTray",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            hinst,
            None,
        )
        icon_path = utils.resource_path("logo.ico")
        self._hicon = win32gui.LoadImage(
            hinst,
            icon_path,
            win32con.IMAGE_ICON,
            16,
            16,
            win32con.LR_LOADFROMFILE,
        )
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, self._tray_data())
        self._ready.set()
        win32gui.PumpMessages()

    def _tray_data(self):
        return (
            self._hwnd,
            1,
            win32gui.NIF_ICON | win32gui.NIF_TIP | win32gui.NIF_MESSAGE,
            WM_TRAYICON,
            self._hicon,
            self.tooltip[:127],
        )

    def _on_close(self, hwnd, msg, wparam, lparam):
        self._delete_icon()
        win32gui.DestroyWindow(hwnd)
        return 0

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        self._delete_icon()
        win32gui.PostQuitMessage(0)
        return 0

    def _on_command(self, hwnd, msg, wparam, lparam):
        command = win32api.LOWORD(wparam)
        if command == MENU_SHOW:
            self.on_show()
        elif command == MENU_HIDE:
            self.on_hide()
        elif command == MENU_QUIT:
            self.on_quit()
        return 0

    def _on_tray(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_LBUTTONDBLCLK:
            self.on_show()
        elif lparam == win32con.WM_RBUTTONUP:
            self._show_menu()
        return 0

    def _show_menu(self) -> None:
        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(menu, win32con.MF_STRING, MENU_SHOW, "Show NetFix")
        win32gui.AppendMenu(menu, win32con.MF_STRING, MENU_HIDE, "Hide")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, MENU_QUIT, "Quit")
        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self._hwnd)
        win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_LEFTALIGN,
            pos[0],
            pos[1],
            0,
            self._hwnd,
            None,
        )
        win32gui.PostMessage(self._hwnd, win32con.WM_NULL, 0, 0)

    def _delete_icon(self) -> None:
        if self._hwnd and self._hicon:
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, self._tray_data())
            except Exception:
                pass
