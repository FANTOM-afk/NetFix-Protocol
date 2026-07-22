"""
app.py
======
The NetFixApp class: builds a modern terminal-inspired UI and wires it
together with the networking (wifi.py), chart (chart_widget.py), and
settings windows (settings_windows.py) modules.
"""

import time
import math
import logging
import threading
from typing import Optional, Dict, Any

import customtkinter as ctk
import tkinter.messagebox as messagebox
from PIL import Image, ImageDraw

import config
import ui_theme as ui
import utils
import wifi
import cloudflare
import v2ray_manager
import v2ray_paths
from tray_icon import TrayIcon
from chart_widget import LiveChart
from settings_windows import open_network_settings, open_appearance_settings, open_about


def _generate_logo(size: int = 128) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = size // 2
    r = size // 2 - 10

    for i in range(12, 0, -1):
        alpha = max(1, int(25 - i * 1.8))
        offset = int(i * 1.2)
        draw.ellipse(
            (cx - r - offset, cy - r - offset, cx + r + offset, cy + r + offset),
            outline=(0, 255, 65, alpha), width=1
        )

    for i in range(6, 0, -1):
        alpha = max(1, int(18 - i * 2))
        offset = int(i * 1.8 + 16)
        draw.ellipse(
            (cx - r - offset, cy - r - offset, cx + r + offset, cy + r + offset),
            outline=(0, 191, 255, alpha), width=1
        )

    draw.arc((cx - r, cy - r, cx + r, cy + r), start=-220, end=40, fill="#38BDF8", width=6)
    draw.arc((cx - r + 12, cy - r + 12, cx + r - 12, cy + r - 12), start=-220, end=40, fill="#60A5FA", width=5)
    draw.arc((cx - r + 24, cy - r + 24, cx + r - 24, cy + r - 24), start=-220, end=40, fill="#7DD3FC", width=4)

    draw.line((cx - r - 8, cy, cx + r + 8, cy), fill="#00BFFF", width=1)
    draw.line((cx, cy - r - 8, cx, cy + r + 8), fill="#00BFFF", width=1)

    for i in range(6, 0, -1):
        s = int(i * 2.5)
        draw.ellipse(
            (cx - s, cy - s, cx + s, cy + s),
            fill=(56, 189, 248, max(1, int(80 - i * 12)))
        )
    draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill="#FFFFFF")

    outer_r = int(r * 1.35)
    tick_len = 6
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1 = cx + int((outer_r - tick_len) * math.cos(rad))
        y1 = cy + int((outer_r - tick_len) * math.sin(rad))
        x2 = cx + int(outer_r * math.cos(rad))
        y2 = cy + int(outer_r * math.sin(rad))
        draw.line((x1, y1, x2, y2), fill="#38BDF8", width=1)

    return img


class NetFixApp:
    def __init__(self) -> None:
        self.settings: Dict[str, Any] = config.load_settings()

        self.domestic_hosts = self.settings["domestic_hosts"]
        self.international_hosts = self.settings["international_hosts"]
        self.ping_interval = self.settings["ping_interval"]

        ui.setup_customtkinter(self.settings["theme"])
        self.c: Dict[str, str] = config.get_colors(self.settings["theme"])

        self.running = False
        self._lock = threading.Lock()
        self.menu_open = False
        self._animating = False
        self.menu_width = 200
        self._network_list: list[str] = []
        self._display_list: list[str] = []
        self._tray: Optional[TrayIcon] = None
        self._quitting = False
        self._v2ray_background_running = False
        self._v2ray_install_prompt_open = False
        self._update_badge_state = "checking"
        self._update_check_result: Any = None
        self._update_install_handler = None
        self._update_installing = False

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def update_status(self, text: str, color: str) -> None:
        self.root.after(0, lambda: self.status_label.configure(text=text, text_color=color))
        logging.info("Status: %s", text)

    def _place_menu_button(self) -> None:
        if hasattr(self, "update_badge"):
            if self.menu_open:
                self.update_badge.place_forget()
            else:
                self.update_badge.place(relx=1.0, x=-78, y=31, anchor="ne")
                self.update_badge.lift()
        self.menu_btn.place(relx=1.0, x=-26, y=26, anchor="ne")
        self.menu_btn.lift()

    def set_update_badge(self, state: str, result: Any = None) -> None:
        self._update_badge_state = state
        if result is not None:
            self._update_check_result = result

        def apply() -> None:
            if not hasattr(self, "update_badge"):
                return
            states = {
                "checking": ("Checking...", self.c["DIM_TEXT"]),
                "up_to_date": ("Up to date", self.c["PING_GREEN"]),
                "update_available": ("Please update", self.c["ACCENT_YELLOW"]),
                "error": ("Check failed", self.c["DIM_TEXT"]),
                "downloading": ("Downloading...", self.c["ACCENT_CYAN"]),
                "installing": ("Installing...", self.c["ACCENT_CYAN"]),
                "restarting": ("Restarting...", self.c["PING_GREEN"]),
                "download_failed": ("Update failed", self.c["ACCENT_RED"]),
            }
            text, color = states.get(state, states["checking"])
            self.update_badge.configure(text=text, text_color=color)
            self._place_menu_button()

        self.root.after(0, apply)

    def set_update_install_handler(self, handler) -> None:
        self._update_install_handler = handler

    def _on_update_badge_click(self, _event=None) -> None:
        if self._update_badge_state != "update_available" or self._update_installing:
            return
        if self._update_install_handler is None or self._update_check_result is None:
            self.update_status("[!] Update installer is not ready.", self.c["ACCENT_RED"])
            return

        self._update_installing = True
        self.set_update_badge("downloading", self._update_check_result)
        self.update_status("[*] Downloading latest NetFix update...", self.c["ACCENT_CYAN"])

        def on_install_status(state: str, result: Any = None) -> None:
            self.set_update_badge(state, result)
            messages = {
                "downloading": ("[*] Downloading latest NetFix update...", self.c["ACCENT_CYAN"]),
                "installing": ("[*] Preparing update restart...", self.c["ACCENT_CYAN"]),
                "restarting": ("[+] Update downloaded. Restarting into the new EXE...", self.c["ACCENT_GREEN"]),
                "download_failed": ("[!] Update download/install failed.", self.c["ACCENT_RED"]),
            }
            if state == "download_failed":
                self._update_installing = False
            if state in messages:
                text, color = messages[state]
                self.update_status(text, color)

        def restart_current_app() -> None:
            self.quit_app()

        try:
            thread = self._update_install_handler(
                self._update_check_result,
                tk_root=self.root,
                status_callback=on_install_status,
                on_ready_to_restart=restart_current_app,
            )
            if thread is None:
                self._update_installing = False
        except Exception as exc:
            logging.warning("Update install could not start: %s", exc)
            self._update_installing = False
            self.set_update_badge("download_failed", self._update_check_result)
            self.update_status("[!] Update installer failed to start.", self.c["ACCENT_RED"])

    def _build_menu_icon_frames(self) -> list[ctk.CTkImage]:
        size = 36
        line_color = self.c["TEXT"]
        base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)
        for y in (12, 18, 24):
            draw.rounded_rectangle((9, y - 1, 27, y + 1), radius=1, fill=line_color)

        resampling = getattr(getattr(Image, "Resampling", Image), "BICUBIC")
        frames = []
        for angle in range(0, 360, 45):
            frame = base.rotate(-angle, resample=resampling)
            frames.append(ctk.CTkImage(light_image=frame, dark_image=frame, size=(24, 24)))
        return frames

    def _animate_menu_button(self, step: int = 0) -> None:
        frames = getattr(self, "menu_icon_frames", None)
        if not frames:
            return
        self.menu_btn.configure(image=frames[step % len(frames)])
        if step < len(frames):
            self.root.after(24, lambda: self._animate_menu_button(step + 1))

    def _slide_menu(self, opening: bool = True) -> None:
        if self._animating:
            return
        self._animating = True
        self._animate_menu_button()
        if opening:
            self.overlay.place(x=0, y=0, relwidth=1, relheight=1)
            self.side_menu.lift()
            self.menu_btn.lift()
            self.menu_open = True
            if hasattr(self, "update_badge"):
                self.update_badge.place_forget()
            self._animate_menu(-self.menu_width, 0)
        else:
            self.menu_open = False
            self._animate_menu(0, -self.menu_width)

    def _animate_menu(self, start: int, end: int, step: int = 0) -> None:
        total = 20
        if step <= total:
            progress = step / total
            eased = 1 - (1 - progress) ** 3
            x = int(start + (end - start) * eased)
            self.side_menu.place(x=x, y=0, relheight=1)
            self.root.after(16, lambda: self._animate_menu(start, end, step + 1))
        else:
            self.side_menu.place(x=end, y=0, relheight=1)
            self._animating = False
            if end < 0:
                self.overlay.place_forget()
            self._place_menu_button()
            self.menu_btn.lift()

    def toggle_menu(self) -> None:
        self._slide_menu(opening=not self.menu_open)

    def open_network_settings(self) -> None:
        def on_apply(domestic_hosts, international_hosts, ping_interval):
            self.domestic_hosts = domestic_hosts
            self.international_hosts = international_hosts
            self.ping_interval = ping_interval

        open_network_settings(
            self.root, self.settings, on_apply,
            status_callback=self.update_status,
        )

    def _initial_ssid_load(self) -> None:
        current = wifi.get_current_wifi_ssid()
        if current:
            self.ssid_entry.set(current)
            self.update_status(f"[+] Active SSID Detected: {current}", self.c["ACCENT_GREEN"])
        else:
            last = wifi.load_last_ssid(config.LAST_SSID_FILE)
            if last:
                self.ssid_entry.set(last)
                self.update_status("[*] Loaded last saved SSID.", self.c["DIM_TEXT"])

    def _on_conn_type_change(self, *_):
        if self.conn_type_var.get() == "lan":
            self.start_btn.configure(
                state="normal",
                border_color=self.c["ACCENT_GREEN"],
                text_color=self.c["ACCENT_GREEN"],
            )
        else:
            self.start_btn.configure(
                state="disabled",
                border_color=self.c["DIM_TEXT"],
                text_color=self.c["DIM_TEXT"],
            )

    def _scan_networks(self) -> None:
        self.scan_btn.configure(state="disabled", text="Scanning")
        self.update_status("[*] Scanning for networks...", self.c["ACCENT_CYAN"])
        self.root.update_idletasks()

        def scan_worker():
            networks = wifi.scan_available_networks()
            ssids = []
            seen = set()
            for n in networks:
                label = f"{n['ssid']}  ({n['signal']})" if n['signal'] else n['ssid']
                if n['ssid'] not in seen:
                    ssids.append(label)
                    seen.add(n['ssid'])
            w = [n['ssid'] for n in networks]
            self.root.after(0, lambda s=ssids, w=w: self._on_scan_done(s, w))

        threading.Thread(target=scan_worker, daemon=True).start()

    def _on_scan_done(self, display_list: list, raw_ssids: list) -> None:
        self.ssid_entry.configure(values=display_list)
        self.scan_btn.configure(state="normal", text="Scan")
        if display_list:
            self._network_list = raw_ssids
            self._display_list = display_list
            self.update_status(f"[+] Found {len(display_list)} networks", self.c["ACCENT_GREEN"])
        else:
            self._network_list = []
            self._display_list = []
            self.update_status("[!] No networks found", self.c["ACCENT_RED"])

    def _on_ssid_selected(self, selected: str) -> None:
        if not selected:
            self.update_status("[*] Please select an SSID first", self.c["DIM_TEXT"])
            return

        idx = self._display_list.index(selected) if hasattr(self, '_display_list') and selected in self._display_list else -1
        ssid = self._network_list[idx] if idx >= 0 and hasattr(self, '_network_list') else selected.split("  (")[0]
        self.ssid_entry.set(ssid)

        current = wifi.get_current_wifi_ssid()
        if current and current == ssid:
            self.start_btn.configure(
                state="normal",
                border_color=self.c["ACCENT_GREEN"],
                text_color=self.c["ACCENT_GREEN"],
            )
            self.update_status(f"[+] Connected to '{ssid}'", self.c["ACCENT_GREEN"])
            return

        if not wifi.profile_exists(ssid):
            password = self._ask_password(ssid)
            if not password:
                self.start_btn.configure(state="disabled", border_color=self.c["DIM_TEXT"], text_color=self.c["DIM_TEXT"])
                return
            self.update_status(f"[*] Connecting to '{ssid}'...", self.c["ACCENT_YELLOW"])
            def connect_worker():
                msg = wifi.connect_to_network(ssid, password)
                self.root.after(0, lambda m=msg: self._on_connect_result(m, ssid))
            threading.Thread(target=connect_worker, daemon=True).start()
        else:
            self.update_status(f"[*] Connecting to '{ssid}'...", self.c["ACCENT_YELLOW"])
            def connect_worker():
                msg = wifi.connect_to_network(ssid)
                self.root.after(0, lambda m=msg: self._on_connect_result(m, ssid))
            threading.Thread(target=connect_worker, daemon=True).start()

    def _on_connect_result(self, msg: str, ssid: str) -> None:
        self.update_status(msg, self.c["ACCENT_GREEN"] if "[+]" in msg else self.c["ACCENT_RED"])
        if "[+]" in msg:
            self.ssid_entry.set(ssid)
            self.start_btn.configure(
                state="normal",
                border_color=self.c["ACCENT_GREEN"],
                text_color=self.c["ACCENT_GREEN"],
            )

    def _ask_password(self, ssid: str) -> str | None:
        result: list[str] = []

        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Wi-Fi Password")
        dialog.geometry("420x270")
        dialog.resizable(True, True)
        dialog.minsize(360, 240)
        dialog.configure(fg_color=self.c["BG"])
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            icon_path = utils.resource_path("logo.ico")
            dialog.iconbitmap(icon_path)
            dialog.after(300, lambda: dialog.iconbitmap(icon_path))
        except Exception:
            pass

        frame = ctk.CTkFrame(dialog, fg_color=self.c["MAIN_BG"],
                             corner_radius=12, border_width=1, border_color=self.c["FRAME_BORDER"])
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            frame, text=f"> PASSWORD FOR",
            font=ctk.CTkFont(family=self.c["FONT"], size=12, weight="bold"),
            text_color=self.c["ACCENT_CYAN"],
        ).pack(anchor="w", padx=10, pady=(15, 2))
        ctk.CTkLabel(
            frame, text=f"'{ssid}'",
            font=ctk.CTkFont(family=self.c["FONT"], size=14, weight="bold"),
            text_color=self.c["ACCENT_GREEN"],
        ).pack(anchor="w", padx=10, pady=(0, 12))

        entry_container = ctk.CTkFrame(frame, fg_color="transparent")
        entry_container.pack(fill="x", padx=10, pady=(0, 6))

        entry = ctk.CTkEntry(
            entry_container, show="*", height=38, placeholder_text="Enter your Wi-Fi password...",
            font=ctk.CTkFont(family=self.c["FONT"], size=13),
            fg_color=self.c["BG"], border_color=self.c["FRAME_BORDER"],
            text_color=self.c["ACCENT_GREEN"],
            border_width=1, corner_radius=6,
        )
        entry.pack(side="left", fill="x", expand=True)

        self.show_password = False

        self.toggle_btn = ctk.CTkButton(
            entry_container, text="Show", width=54, height=38, corner_radius=6,
            command=lambda: self._toggle_password_visibility(entry),
            fg_color="transparent", border_width=1, border_color=self.c["ACCENT_CYAN"],
            text_color=self.c["ACCENT_CYAN"], hover_color=self.c["BTN_HOVER_GREEN"],
            font=ctk.CTkFont(family=self.c["FONT"], size=14),
        )
        self.toggle_btn.pack(side="right", padx=(8, 0))

        entry.focus_force()

        err_label = ctk.CTkLabel(
            frame, text="", text_color=self.c["ACCENT_RED"],
            font=ctk.CTkFont(family=self.c["FONT"], size=11),
        )
        err_label.pack()

        self._toggle_password_visibility(entry)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=(12, 8))

        def confirm():
            pw = entry.get()
            if not pw:
                err_label.configure(text="[!] Password cannot be empty")
                return
            result.append(pw)
            dialog.destroy()

        def cancel():
            dialog.destroy()

        entry.bind("<Return>", lambda e: confirm())

        ctk.CTkButton(
            btn_frame, text="Connect", width=100, height=34, corner_radius=8,
            command=confirm,
            fg_color="transparent", border_width=2, border_color=self.c["ACCENT_GREEN"],
            text_color=self.c["ACCENT_GREEN"], hover_color=self.c["BTN_HOVER_GREEN"],
            font=ctk.CTkFont(family=self.c["FONT"], size=12, weight="bold"),
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100, height=34, corner_radius=8,
            command=cancel,
            fg_color="transparent", border_width=2, border_color=self.c["ACCENT_RED"],
            text_color=self.c["ACCENT_RED"], hover_color=self.c["BTN_HOVER_RED"],
            font=ctk.CTkFont(family=self.c["FONT"], size=12, weight="bold"),
        ).pack(side="left", padx=6)

        self.root.wait_window(dialog)
        return result[0] if result else None

    def _toggle_password_visibility(self, entry: ctk.CTkEntry) -> None:
        self.show_password = not self.show_password
        entry.configure(show="" if self.show_password else "*")

    # ------------------------------------------------------------------
    # System tray icon
    # ------------------------------------------------------------------
    def _start_tray(self) -> None:
        if self._tray is not None:
            return
        try:
            self._tray = TrayIcon(
                tooltip="NetFix Protocol - Running",
                on_show=lambda: self.root.after(0, self.show_window),
                on_hide=lambda: self.root.after(0, self.hide_to_tray),
                on_quit=lambda: self.root.after(0, self.quit_app),
            )
            self._tray.start()
        except Exception as exc:
            logging.warning("Could not start tray icon: %s", exc)

    def _add_tray(self) -> None:
        self._start_tray()
        if self._tray:
            self._tray.update_tooltip("NetFix Protocol - Monitoring Active")

    def _remove_tray(self) -> None:
        if self._tray:
            self._tray.stop()
            self._tray = None

    def show_window(self) -> None:
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            if self._tray:
                self._tray.update_tooltip("NetFix Protocol - Running")
        except Exception:
            pass

    def hide_to_tray(self) -> None:
        if self._quitting:
            return
        try:
            self.root.withdraw()
            if self._tray:
                suffix = "Monitoring Active" if self.running else "Running in Background"
                self._tray.update_tooltip(f"NetFix Protocol - {suffix}")
            self.update_status("[*] NetFix is running in the system tray.", self.c["DIM_TEXT"])
        except Exception:
            pass

    def _ask_autostart(self) -> bool:
        return messagebox.askyesno("Auto Start", "Enable auto-start on Windows boot?")

    def _maybe_setup_autostart(self) -> None:
        if not utils.is_autostart_enabled() and self._ask_autostart():
            utils.create_startup_shortcut()
            self.update_status("[+] Auto-start enabled.", self.c["ACCENT_GREEN"])

    def _check_v2ray_core_on_launch(self) -> None:
        if self._quitting or self._v2ray_install_prompt_open:
            return
        if v2ray_manager.is_core_installed():
            return

        self._v2ray_install_prompt_open = True
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Install V2Ray Core")
        dialog.geometry("430x230")
        dialog.resizable(True, True)
        dialog.minsize(360, 220)
        dialog.configure(fg_color=self.c["BG"])
        dialog.transient(self.root)

        try:
            dialog.iconbitmap(utils.resource_path("logo.ico"))
        except Exception:
            pass

        frame = ctk.CTkFrame(
            dialog,
            fg_color=self.c["MAIN_BG"],
            border_width=1,
            border_color=self.c["FRAME_BORDER"],
            corner_radius=10,
        )
        frame.pack(fill="both", expand=True, padx=14, pady=14)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="V2Ray Core Missing",
            font=ctk.CTkFont(family=self.c["FONT"], size=16, weight="bold"),
            text_color=self.c["ACCENT_CYAN"],
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))

        msg_label = ctk.CTkLabel(
            frame,
            text="Install the core once to enable VPN profiles.",
            font=ctk.CTkFont(family=self.c["FONT"], size=12),
            text_color=self.c["TEXT"],
            anchor="w",
        )
        msg_label.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        btns.grid_columnconfigure((0, 1), weight=1)

        def close_prompt() -> None:
            self._v2ray_install_prompt_open = False
            try:
                dialog.destroy()
            except Exception:
                pass

        def install_worker() -> None:
            try:
                v2ray_manager.install_core(
                    lambda msg: self.root.after(
                        0,
                        lambda m=msg: (
                            msg_label.configure(text=m, text_color=self.c["ACCENT_CYAN"]),
                            self.update_status(f"[*] {m}", self.c["ACCENT_CYAN"]),
                        ),
                    )
                )
                self.root.after(0, lambda: msg_label.configure(text="V2Ray core installed.", text_color=self.c["ACCENT_GREEN"]))
                self.root.after(0, lambda: self.update_status("[+] V2Ray core installed.", self.c["ACCENT_GREEN"]))
                self.root.after(900, close_prompt)
            except Exception as exc:
                self.root.after(0, lambda e=exc: msg_label.configure(text=f"Install failed: {e}", text_color=self.c["ACCENT_RED"]))
                self.root.after(0, lambda e=exc: self.update_status(f"[!] V2Ray install failed: {e}", self.c["ACCENT_RED"]))
                self.root.after(0, lambda e=exc: messagebox.showerror("V2Ray Install", str(e), parent=dialog))

        def start_install() -> None:
            install_btn.configure(state="disabled", text="INSTALLING...")
            later_btn.configure(state="disabled")
            threading.Thread(target=install_worker, daemon=True).start()

        install_btn = ctk.CTkButton(
            btns,
            text="INSTALL CORE",
            height=36,
            command=start_install,
            fg_color="transparent",
            border_width=1,
            border_color=self.c["ACCENT_GREEN"],
            text_color=self.c["ACCENT_GREEN"],
            hover_color=self.c["FRAME_BORDER"],
            font=ctk.CTkFont(family=self.c["FONT"], size=12, weight="bold"),
        )
        install_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        later_btn = ctk.CTkButton(
            btns,
            text="LATER",
            height=36,
            command=close_prompt,
            fg_color="transparent",
            border_width=1,
            border_color=self.c["DIM_TEXT"],
            text_color=self.c["DIM_TEXT"],
            hover_color=self.c["FRAME_BORDER"],
            font=ctk.CTkFont(family=self.c["FONT"], size=12, weight="bold"),
        )
        later_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        dialog.protocol("WM_DELETE_WINDOW", close_prompt)
        dialog.lift()
        dialog.focus_force()

    def _reset_v2ray_on_launch(self) -> None:
        if self._quitting:
            return

        def worker() -> None:
            try:
                was_running = v2ray_manager.is_running()
                v2ray_manager.stop()
                self._v2ray_background_running = False
                if self.settings.get("v2ray_background_enabled", True):
                    self.root.after(0, self._start_bg_proxy_on_launch)
                    return
                if was_running:
                    self.root.after(
                        0,
                        lambda: self.update_status("[*] V2Ray is idle. Press START to connect.", self.c["DIM_TEXT"]),
                    )
            except Exception as exc:
                logging.warning("V2Ray launch reset failed: %s", exc)
                self.root.after(
                    0,
                    lambda e=exc: self.update_status(f"[!] V2Ray reset failed: {e}", self.c["ACCENT_RED"]),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _start_bg_proxy_on_launch(self) -> None:
        if self._quitting or not self.settings.get("v2ray_background_enabled", True):
            return
        if hasattr(self, "bg_proxy_var") and not self.bg_proxy_var.get():
            self.bg_proxy_var.set(True)
        self.update_status("[*] BG Proxy enabled on launch (system VPN OFF)", self.c["ACCENT_CYAN"])
        self._ensure_proxy_only_mode()

    def _on_bg_proxy_toggle(self) -> None:
        enabled = self.bg_proxy_var.get()
        self.settings["v2ray_background_enabled"] = enabled
        config.save_settings(self.settings)

        if enabled:
            self._ensure_proxy_only_mode()
            self.update_status("[*] BG Proxy: ON (only local proxy ports use VPN)", self.c["ACCENT_CYAN"])
        else:
            if self.running:
                if self._ensure_system_vpn_mode():
                    self.update_status("[*] BG Proxy: OFF (system VPN follows START)", self.c["ACCENT_GREEN"])
            else:
                self._disable_vpn_when_idle()
                self.update_status("[*] BG Proxy: OFF (VPN idle)", self.c["DIM_TEXT"])

    def _sync_bg_proxy_from_router(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self.settings["v2ray_background_enabled"] = enabled
        if hasattr(self, "bg_proxy_var") and self.bg_proxy_var.get() != enabled:
            self.bg_proxy_var.set(enabled)

        if enabled:
            self._v2ray_background_running = v2ray_manager.is_running()
            if self._v2ray_background_running:
                self.root.after(0, self._start_v2ray_keep_alive)
            return

        if self.running:
            if self._ensure_system_vpn_mode():
                self.update_status("[*] BG Proxy: OFF (system VPN follows START)", self.c["ACCENT_GREEN"])
            return

        self._v2ray_background_running = False

    def _ensure_proxy_only_mode(self) -> None:
        self._restore_system_proxy()
        if not v2ray_manager.is_running():
            self._start_v2ray_background()
            return

        self._v2ray_background_running = True
        self.root.after(0, self._start_v2ray_keep_alive)

    def _ensure_system_vpn_mode(self) -> bool:
        enabled = self._enable_system_proxy()
        self._v2ray_background_running = enabled
        if enabled and v2ray_manager.is_running():
            self.root.after(0, self._start_v2ray_keep_alive)
        return enabled

    def _disable_vpn_when_idle(self) -> None:
        self._v2ray_background_running = False
        if v2ray_manager.is_running():
            v2ray_manager.stop()
        else:
            self._restore_system_proxy()

    def _start_v2ray_background(self) -> None:
        if not v2ray_manager.is_core_installed():
            self.update_status("[!] V2Ray core not installed. Go to V2Ray Router.", self.c["ACCENT_RED"])
            return

        store = v2ray_manager.load_store()
        profile = v2ray_manager.active_profile(store)
        if not profile:
            self.update_status("[!] No V2Ray profile. Add one in V2Ray Router.", self.c["ACCENT_RED"])
            return

        def worker() -> None:
            try:
                local_port = v2ray_paths.normalize_local_port(self.settings.get("v2ray_background_port"))
                v2ray_manager.save_state({
                    "local_port": local_port,
                    "active_profile_id": profile["id"],
                    "selected_group": profile.get("group", "Default"),
                })
                v2ray_manager.save_user_config(profile["raw_config"])
                v2ray_manager.start(profile["raw_config"], local_port, enable_system_proxy=False)
                self._v2ray_background_running = bool(
                    self.settings.get("v2ray_background_enabled", True) or self.running
                )
                self.root.after(
                    0,
                    lambda: self.update_status(
                        f"[+] Background proxy on 127.0.0.1:{local_port}", self.c["ACCENT_GREEN"],
                    ),
                )
                if self._v2ray_background_running:
                    self.root.after(0, self._start_v2ray_keep_alive)
            except Exception as exc:
                logging.warning("Background proxy start failed: %s", exc)
                self.root.after(
                    0,
                    lambda e=exc: self.update_status(f"[!] Background proxy failed: {e}", self.c["ACCENT_RED"]),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _start_v2ray_system_proxy(self) -> bool:
        if not v2ray_manager.is_core_installed():
            self.update_status("[!] System proxy: V2Ray core not installed", self.c["ACCENT_RED"])
            return False

        store = v2ray_manager.load_store()
        profile = v2ray_manager.active_profile(store)
        if not profile:
            self.update_status("[!] No V2Ray profile. Add one in V2Ray Router.", self.c["ACCENT_RED"])
            return False

        try:
            local_port = v2ray_paths.normalize_local_port(self.settings.get("v2ray_background_port"))
            v2ray_manager.save_state({
                "local_port": local_port,
                "active_profile_id": profile["id"],
                "selected_group": profile.get("group", "Default"),
            })
            v2ray_manager.save_user_config(profile["raw_config"])
            v2ray_manager.start(profile["raw_config"], local_port, enable_system_proxy=True)
            self._v2ray_background_running = True
            self.root.after(0, self._start_v2ray_keep_alive)
            self.update_status(f"[+] VPN mode: system proxy ON (HTTP :{local_port + 1})", self.c["ACCENT_GREEN"])
            if self._tray:
                self._tray.update_tooltip("NetFix Protocol - VPN Mode (system proxy)")
            return True
        except Exception as exc:
            self._v2ray_background_running = False
            self.update_status(f"[!] System proxy failed: {exc}", self.c["ACCENT_RED"])
            return False

    def _start_v2ray_keep_alive(self) -> None:
        threading.Thread(target=self._keep_v2ray_alive_loop, daemon=True).start()

    def _keep_v2ray_alive_loop(self) -> None:
        while self._v2ray_background_running and not self._quitting:
            time.sleep(15)
            if not self._v2ray_background_running or self._quitting:
                break
            if not (self.settings.get("v2ray_background_enabled", True) or self._is_running()):
                continue
            if not v2ray_manager.is_running():
                logging.info("V2Ray background proxy not running, restarting...")
                self.root.after(0, lambda: self.update_status(
                    "[*] Restarting background proxy...", self.c["ACCENT_YELLOW"],
                ))
                self.root.after(0, self._start_v2ray_background)

    def _enable_system_proxy(self) -> bool:
        if not v2ray_manager.is_core_installed():
            self.update_status("[!] System proxy: V2Ray core not installed", self.c["ACCENT_RED"])
            return False
        if not v2ray_manager.is_running():
            return self._start_v2ray_system_proxy()
        try:
            state = v2ray_paths.load_state()
            local_port = v2ray_paths.normalize_local_port(state.get("local_port"))
            from v2ray_proxy_windows import set_system_proxy
            set_system_proxy(local_port)
            self.update_status(f"[+] VPN mode: system proxy ON (HTTP :{local_port + 1})", self.c["ACCENT_GREEN"])
            if self._tray:
                self._tray.update_tooltip("NetFix Protocol - VPN Mode (system proxy)")
            return True
        except Exception as exc:
            self.update_status(f"[!] System proxy failed: {exc}", self.c["ACCENT_RED"])
            return False

    def _restore_system_proxy(self) -> None:
        try:
            from v2ray_proxy_windows import restore_system_proxy
            restore_system_proxy()
            self.update_status("[*] System proxy restored to original", self.c["DIM_TEXT"])
            if self._tray:
                tooltip = "NetFix Protocol - Proxy port open (background)" if self.settings.get("v2ray_background_enabled", True) else "NetFix Protocol - Running in Background"
                self._tray.update_tooltip(tooltip)
        except Exception as exc:
            self.update_status(f"[!] Restore system proxy failed: {exc}", self.c["ACCENT_RED"])

    def start_monitor(self) -> None:
        with self._lock:
            if self.running:
                return

            connection_type = self.conn_type_var.get()

            if connection_type == "wifi":
                ssid = self.ssid_entry.get().strip()
                if not ssid:
                    self.update_status("[!] ERROR: TARGET_SSID MISSING!", self.c["ACCENT_RED"])
                    return

                wifi.save_last_ssid(ssid, config.LAST_SSID_FILE)
                self._maybe_setup_autostart()

                self.running = True
                if self.settings.get("v2ray_background_enabled", True):
                    self._ensure_proxy_only_mode()
                else:
                    if not self._ensure_system_vpn_mode():
                        self.running = False
                        return
                self._add_tray()
                self.start_btn.configure(state="disabled")
                self.stop_btn.configure(state="normal")
                self.ssid_entry.configure(state="disabled")
                self.wifi_radio.configure(state="disabled")
                self.lan_radio.configure(state="disabled")
                self._set_indicator(self.c["ACCENT_YELLOW"], "INITIALIZING")
                self.update_status("[*] INITIALIZING WIFI MONITOR...", self.c["TEXT"])

                threading.Thread(target=self._monitor_wifi, args=(ssid,), daemon=True).start()
            else:
                self._maybe_setup_autostart()

                self.running = True
                if self.settings.get("v2ray_background_enabled", True):
                    self._ensure_proxy_only_mode()
                else:
                    if not self._ensure_system_vpn_mode():
                        self.running = False
                        return
                self._add_tray()
                self.start_btn.configure(state="disabled")
                self.stop_btn.configure(state="normal")
                self.ssid_entry.configure(state="disabled")
                self.wifi_radio.configure(state="disabled")
                self.lan_radio.configure(state="disabled")
                self._set_indicator(self.c["ACCENT_YELLOW"], "INITIALIZING")
                self.update_status("[*] INITIALIZING LAN MONITOR...", self.c["TEXT"])

                threading.Thread(target=self._monitor_lan, daemon=True).start()

    def stop_monitor(self) -> None:
        with self._lock:
            self.running = False
        if self._blink_id:
            self.root.after_cancel(self._blink_id)
            self._blink_id = None
        self.live_label.configure(text_color=self.c["MAIN_BG"])
        self.live_dot.itemconfig(self._dot, fill=self.c["MAIN_BG"], outline=self.c["MAIN_BG"])
        if self.settings.get("v2ray_background_enabled", True):
            self._restore_system_proxy()
            if not v2ray_manager.is_running():
                self._start_v2ray_background()
        else:
            self._disable_vpn_when_idle()
        if self._tray:
            tooltip = "NetFix Protocol - Proxy port open (background)" if self.settings.get("v2ray_background_enabled", True) else "NetFix Protocol - Running in Background"
            self._tray.update_tooltip(tooltip)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.ssid_entry.configure(state="normal")
        self.wifi_radio.configure(state="normal")
        self.lan_radio.configure(state="normal")

        self.chart.reset()
        self._set_indicator(self.c["DIM_TEXT"], "SYSTEM IDLE")
        self.ping_display.configure(text="-- ms", text_color=self.c["DIM_TEXT"])
        self.update_status("> PROTOCOL TERMINATED.", self.c["DIM_TEXT"])
        logging.info("Monitor stopped by user")

    def _check_connection(self):
        domestic_ok, domestic_ping = wifi.get_first_success_ping(self.domestic_hosts)
        international_ok, intl_ping = wifi.get_first_success_ping(self.international_hosts)

        available_pings = [p for p in [domestic_ping, intl_ping] if p is not None]
        best_ping = min(available_pings) if available_pings else None

        self.root.after(0, lambda dp=domestic_ping, ip=intl_ping: self.chart.update(dp, ip))

        return domestic_ok, international_ok, best_ping

    def _is_running(self) -> bool:
        with self._lock:
            return self.running

    def _monitor_wifi(self, ssid: str) -> None:
        self.root.after(0, lambda: self._set_indicator(self.c["ACCENT_GREEN"], "MONITORING"))
        self.root.after(0, lambda: self._start_pb())

        while self._is_running():
            domestic_ok, international_ok, best_ping = self._check_connection()

            if best_ping is not None:
                self.root.after(0, lambda p=best_ping: self.ping_display.configure(
                    text=f"{p} ms", text_color=self.c["PING_GREEN"]
                ))

            if not domestic_ok and not international_ok:
                self.update_status("[!] No Internet Connection Detected.", self.c["ACCENT_RED"])
                self.root.after(0, lambda: self._set_indicator(self.c["ACCENT_RED"], "CONNECTION LOST"))
                wifi.reconnect_wifi(ssid, self.update_status, colors=self.c)
            else:
                msg, col = self._build_status_message(domestic_ok, international_ok)
                if best_ping is not None:
                    msg += f" | Ping: {best_ping}ms"
                self.update_status(msg, col)
                ind_color = self.c["ACCENT_GREEN"] if (domestic_ok and international_ok) else self.c["ACCENT_YELLOW"]
                self.root.after(0, lambda c=ind_color: self._set_indicator(c, "MONITORING"))

            time.sleep(self.ping_interval)

        self.root.after(0, self._stop_pb)

    def _monitor_lan(self) -> None:
        self.root.after(0, lambda: self._set_indicator(self.c["ACCENT_GREEN"], "MONITORING"))
        self.root.after(0, lambda: self._start_pb())

        while self._is_running():
            domestic_ok, international_ok, best_ping = self._check_connection()

            if best_ping is not None:
                self.root.after(0, lambda p=best_ping: self.ping_display.configure(
                    text=f"{p} ms", text_color=self.c["PING_GREEN"]
                ))

            if not domestic_ok and not international_ok:
                self.update_status("[!] LAN Lost.", self.c["ACCENT_RED"])
                self.root.after(0, lambda: self._set_indicator(self.c["ACCENT_RED"], "LAN LOST"))
            else:
                msg, col = self._build_status_message(domestic_ok, international_ok, lan=True)
                if best_ping is not None:
                    msg += f" | Ping: {best_ping}ms"
                self.update_status(msg, col)
                ind_color = self.c["ACCENT_GREEN"] if (domestic_ok and international_ok) else self.c["ACCENT_YELLOW"]
                self.root.after(0, lambda c=ind_color: self._set_indicator(c, "MONITORING"))

            time.sleep(self.ping_interval)

        self.root.after(0, self._stop_pb)

    def _build_status_message(self, domestic_ok: bool, international_ok: bool, lan: bool = False):
        if domestic_ok and international_ok:
            msg = "[+] LAN OK (Domestic + International)" if lan else "[+] Internet Available (Domestic & International)"
            col = self.c["ACCENT_GREEN"]
        elif domestic_ok:
            msg = "[!] LAN OK, INTL DOWN" if lan else "[!] Only Domestic Internet Accessible"
            col = self.c["ACCENT_YELLOW"]
        else:
            msg = "[!] LAN Unknown/Partial" if lan else "[!] International Down / Partial Access"
            col = self.c["ACCENT_RED"]
        return msg, col

    # ------------------------------------------------------------------
    # Modern presentation layer
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        import tkinter as tk

        try:
            test = tk.Tk()
            test.iconbitmap(utils.resource_path("logo.ico"))
            test.destroy()
        except Exception:
            pass

        self.root = ctk.CTk()
        self.root.title("NetFix Protocol 1.3.2")
        self.root.minsize(440, 620)
        self.root.configure(fg_color=self.c["BG"])

        try:
            self.root.iconbitmap(utils.resource_path("logo.ico"))
        except Exception:
            pass

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.main_frame = ui.frame(self.root, self.c, corner_radius=8)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(5, weight=1)

        self._build_side_menu()
        self._build_header()
        self._build_form()
        self._build_buttons()
        self._build_status_indicator()
        self._build_chart()
        self._build_status_label()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.after(10, self._center_window)
        self.root.after(50, self._start_tray)
        self.root.after(700, self._check_v2ray_core_on_launch)
        self.root.after(250, self._reset_v2ray_on_launch)
        self._initial_ssid_load()

    def _center_window(self) -> None:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(760, max(440, screen_width - 120))
        height = min(820, max(620, screen_height - 120))
        x = max(0, int((screen_width - width) / 2))
        y = max(0, int((screen_height - height) / 2) - 20)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _build_side_menu(self) -> None:
        self.menu_width = 260
        self.overlay = ctk.CTkFrame(self.root, fg_color="#000000", corner_radius=0)
        self.overlay.bind("<Button-1>", lambda _event: self.toggle_menu())

        self.side_menu = ctk.CTkFrame(
            self.root,
            fg_color=self.c["SIDE_MENU_BG"],
            corner_radius=0,
            width=self.menu_width,
        )
        self.side_menu.place(x=-self.menu_width, y=0, relheight=1)
        self.side_menu.grid_columnconfigure(0, weight=1)

        ui.label(
            self.side_menu,
            "NetFix Protocol",
            self.c,
            role="section",
            color="TEXT",
            weight="bold",
        ).pack(anchor="w", padx=20, pady=(28, 6))
        ui.label(
            self.side_menu,
            "Control Center",
            self.c,
            role="caption",
            color="DIM_TEXT",
        ).pack(anchor="w", padx=20, pady=(0, 22))

        self.menu_btn_settings = ui.button(
            self.side_menu, "Network Settings", self.c, variant="ghost",
            anchor="w", height=38, command=self.open_network_settings,
        )
        self.menu_btn_settings.pack(fill="x", padx=14, pady=4)

        self.menu_btn_appearance = ui.button(
            self.side_menu, "Appearance", self.c, variant="ghost",
            anchor="w", height=38,
            command=lambda: open_appearance_settings(
                self.root, self.settings, on_theme_changed=self._apply_theme
            ),
        )
        self.menu_btn_appearance.pack(fill="x", padx=14, pady=4)

        self.menu_btn_cloudflare = ui.button(
            self.side_menu, "Cloudflare Account", self.c, variant="ghost",
            anchor="w", height=38, command=lambda: cloudflare.open_cloudflare(self.root),
        )
        self.menu_btn_cloudflare.pack(fill="x", padx=14, pady=4)

        self.menu_btn_v2ray = ui.button(
            self.side_menu, "V2Ray Router", self.c, variant="ghost",
            anchor="w", height=38,
            command=lambda: v2ray_manager.open_v2ray(
                self.root, self.settings, status_callback=self.update_status,
                bg_proxy_var=self.bg_proxy_var,
                bg_proxy_callback=self._sync_bg_proxy_from_router,
            ),
        )
        self.menu_btn_v2ray.pack(fill="x", padx=14, pady=4)

        self.menu_btn_about = ui.button(
            self.side_menu, "About", self.c, variant="ghost",
            anchor="w", height=38,
            command=lambda: open_about(self.settings.get("theme", "dark")),
        )
        self.menu_btn_about.pack(fill="x", padx=14, pady=4)

        self.menu_btn_close = ui.button(
            self.side_menu, "Close Menu", self.c, variant="muted",
            anchor="w", height=38, command=self.toggle_menu,
        )
        self.menu_btn_close.pack(side="bottom", fill="x", padx=14, pady=20)

        self.menu_icon_frames = self._build_menu_icon_frames()
        self.menu_btn = ui.button(
            self.root, "", self.c, variant="secondary",
            image=self.menu_icon_frames[0],
            width=42, height=38, command=self.toggle_menu,
        )
        self.update_badge = ui.label(
            self.root,
            "Checking...",
            self.c,
            role="caption",
            color="DIM_TEXT",
            weight="bold",
            width=112,
            anchor="e",
        )
        self.update_badge.bind("<Button-1>", self._on_update_badge_click)
        self._place_menu_button()

    def _build_header(self) -> None:
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 12))
        header_frame.grid_columnconfigure(1, weight=1)

        try:
            logo_pil = Image.open(utils.resource_path("logo.ico"))
            self.logo_image = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(58, 58))
        except Exception:
            fallback = _generate_logo()
            self.logo_image = ctk.CTkImage(light_image=fallback, dark_image=fallback, size=(58, 58))

        ctk.CTkLabel(header_frame, image=self.logo_image, text="").grid(row=0, column=0, rowspan=2, sticky="w")
        self.header_label = ui.label(
            header_frame,
            "NetFix Protocol",
            self.c,
            role="title",
            color="TEXT",
            weight="bold",
            anchor="w",
        )
        self.header_label.grid(row=0, column=1, sticky="ew", padx=(16, 0))
        self.version_label = ui.label(
            header_frame,
            "Wi-Fi / LAN recovery and V2Ray telemetry",
            self.c,
            role="caption",
            color="DIM_TEXT",
            anchor="w",
        )
        self.version_label.grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=(2, 0))

    def _build_form(self) -> None:
        form_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        form_frame.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 12))
        form_frame.grid_columnconfigure(0, weight=1)

        self.ssid_label = ui.label(
            form_frame, "Target SSID", self.c, role="section", color="ACCENT_CYAN", weight="bold"
        )
        self.ssid_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        ssid_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        ssid_row.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        ssid_row.grid_columnconfigure(0, weight=1)

        self.ssid_entry = ui.combo(
            ssid_row,
            self.c,
            values=[],
            height=42,
            command=self._on_ssid_selected,
        )
        self.ssid_entry.grid(row=0, column=0, sticky="ew")

        self.scan_btn = ui.button(
            ssid_row,
            "Scan",
            self.c,
            variant="secondary",
            width=82,
            height=42,
            command=self._scan_networks,
        )
        self.scan_btn.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.conn_type_label = ui.label(
            form_frame, "Connection Type", self.c, role="section", color="ACCENT_CYAN", weight="bold"
        )
        self.conn_type_label.grid(row=2, column=0, sticky="w", pady=(0, 6))

        radio_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        radio_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        radio_frame.grid_columnconfigure((0, 1), weight=1)

        self.conn_type_var = ctk.StringVar(value="wifi")
        self.conn_type_var.trace_add("write", self._on_conn_type_change)
        self.wifi_radio = ui.radio(radio_frame, "Wi-Fi", self.conn_type_var, "wifi", self.c)
        self.wifi_radio.grid(row=0, column=0, sticky="w")
        self.lan_radio = ui.radio(radio_frame, "LAN", self.conn_type_var, "lan", self.c)
        self.lan_radio.grid(row=0, column=1, sticky="w")

        bg_enabled = bool(self.settings.get("v2ray_background_enabled", True))
        self.bg_proxy_var = ctk.BooleanVar(value=bg_enabled)
        self.bg_proxy_check = ui.checkbox(
            form_frame,
            "Background proxy (SOCKS5 :10809 / HTTP :10810)",
            self.c,
            variable=self.bg_proxy_var,
            command=self._on_bg_proxy_toggle,
        )
        self.bg_proxy_check.grid(row=4, column=0, sticky="w", pady=(2, 0))

    def _build_buttons(self) -> None:
        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=28, pady=(2, 12))
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self.start_btn = ui.button(
            btn_frame,
            "Start Monitor",
            self.c,
            variant="primary",
            height=46,
            command=self.start_monitor,
        )
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.stop_btn = ui.button(
            btn_frame,
            "Stop",
            self.c,
            variant="danger",
            height=46,
            state="disabled",
            command=self.stop_monitor,
        )
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        live_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        live_frame.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 8))
        self.live_label = ui.label(
            live_frame, "Live telemetry", self.c, role="caption", color="DIM_TEXT", weight="bold"
        )
        self.live_label.pack(side="left")
        self.live_dot = ctk.CTkCanvas(live_frame, width=12, height=12, highlightthickness=0, bg=self.c["MAIN_BG"], bd=0)
        self.live_dot.pack(side="left", padx=(8, 0))
        self._dot = self.live_dot.create_oval(2, 2, 12, 12, fill=self.c["DIM_TEXT"], outline=self.c["DIM_TEXT"], width=0)
        self._blink_id = None

    def _build_status_indicator(self) -> None:
        indicator_frame = ui.frame(self.main_frame, self.c, surface="PANEL_BG", corner_radius=8)
        self.indicator_frame = indicator_frame
        indicator_frame.grid(row=4, column=0, sticky="ew", padx=28, pady=(0, 12))
        indicator_frame.grid_columnconfigure(1, weight=1)

        self.indicator_canvas = ctk.CTkCanvas(indicator_frame, width=16, height=16, highlightthickness=0, bg=self.c["PANEL_BG"], bd=0)
        self.indicator_canvas.grid(row=0, column=0, sticky="w", padx=(14, 10), pady=12)
        self._indicator_dot = self.indicator_canvas.create_oval(3, 3, 15, 15, fill=self.c["DIM_TEXT"], outline=self.c["DIM_TEXT"], width=0)

        self.connection_status = ui.label(
            indicator_frame, "System idle", self.c, role="section", color="DIM_TEXT", weight="bold", anchor="w"
        )
        self.connection_status.grid(row=0, column=1, sticky="ew", pady=12)

        self.ping_display = ui.label(
            indicator_frame, "-- ms", self.c, role="mono", color="DIM_TEXT", weight="bold", anchor="e"
        )
        self.ping_display.grid(row=0, column=2, sticky="e", padx=(10, 14), pady=12)

    def _set_indicator(self, color: str, text: str) -> None:
        self.indicator_canvas.itemconfig(self._indicator_dot, fill=color, outline=color)
        self.connection_status.configure(text=text.title(), text_color=color)

    def _build_chart(self) -> None:
        chart_frame = ui.frame(self.main_frame, self.c, surface="PANEL_BG", corner_radius=8)
        self.chart_frame = chart_frame
        chart_frame.grid(row=5, column=0, sticky="nsew", padx=28, pady=(0, 12))
        chart_frame.grid_rowconfigure(0, weight=1)
        chart_frame.grid_columnconfigure(0, weight=1)

        self.chart = LiveChart(chart_frame)
        self.chart.get_widget().grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

    def _build_status_label(self) -> None:
        status_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        status_frame.grid(row=6, column=0, sticky="ew", padx=28, pady=(0, 18))
        status_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ui.label(
            status_frame,
            "System idle. Waiting for command.",
            self.c,
            role="caption",
            color="DIM_TEXT",
            justify="left",
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="ew")

    def _apply_theme(self, theme: str) -> None:
        self.settings["theme"] = theme
        self.c = config.get_colors(theme)
        ui.setup_customtkinter(theme)

        self.root.configure(fg_color=self.c["BG"])
        self.main_frame.configure(fg_color=self.c["MAIN_BG"], border_color=self.c["FRAME_BORDER"])
        self.side_menu.configure(fg_color=self.c["SIDE_MENU_BG"])
        self.overlay.configure(fg_color="#000000")
        self.indicator_frame.configure(fg_color=self.c["PANEL_BG"], border_color=self.c["FRAME_BORDER"])
        self.chart_frame.configure(fg_color=self.c["PANEL_BG"], border_color=self.c["FRAME_BORDER"])

        self.header_label.configure(text_color=self.c["TEXT"])
        self.version_label.configure(text_color=self.c["DIM_TEXT"])
        self.set_update_badge(self._update_badge_state)
        self.ssid_label.configure(text_color=self.c["ACCENT_CYAN"])
        self.conn_type_label.configure(text_color=self.c["ACCENT_CYAN"])
        self.ssid_entry.configure(
            fg_color=self.c["INPUT_BG"],
            border_color=self.c["FRAME_BORDER"],
            text_color=self.c["TEXT"],
            button_color=self.c["PRIMARY"],
            button_hover_color=self.c["PRIMARY_HOVER"],
            dropdown_fg_color=self.c["PANEL_BG"],
            dropdown_hover_color=self.c["HOVER_BG"],
            dropdown_text_color=self.c["TEXT"],
        )
        self.wifi_radio.configure(text_color=self.c["TEXT"], fg_color=self.c["PRIMARY"], hover_color=self.c["HOVER_BG"])
        self.lan_radio.configure(text_color=self.c["TEXT"], fg_color=self.c["PRIMARY"], hover_color=self.c["HOVER_BG"])
        self.bg_proxy_check.configure(text_color=self.c["TEXT"], fg_color=self.c["PRIMARY"], hover_color=self.c["HOVER_BG"])
        ui.configure_button(self.start_btn, self.c, "primary")
        ui.configure_button(self.stop_btn, self.c, "danger")
        ui.configure_button(self.scan_btn, self.c, "secondary")
        for btn in (
            self.menu_btn_settings,
            self.menu_btn_appearance,
            self.menu_btn_cloudflare,
            self.menu_btn_v2ray,
            self.menu_btn_about,
        ):
            ui.configure_button(btn, self.c, "ghost")
        ui.configure_button(self.menu_btn_close, self.c, "muted")
        ui.configure_button(self.menu_btn, self.c, "secondary")
        self.menu_icon_frames = self._build_menu_icon_frames()
        self.menu_btn.configure(image=self.menu_icon_frames[0])
        self._place_menu_button()
        self.live_label.configure(text_color=self.c["DIM_TEXT"])
        self.live_dot.configure(bg=self.c["MAIN_BG"])
        self.indicator_canvas.configure(bg=self.c["PANEL_BG"])
        self.connection_status.configure(text_color=self.c["DIM_TEXT"])
        self.ping_display.configure(text_color=self.c["DIM_TEXT"])
        self.status_label.configure(text_color=self.c["DIM_TEXT"])
        self.chart.set_theme_colors(theme)

    def _start_pb(self) -> None:
        self.live_label.configure(text_color=self.c["PRIMARY"])
        self._blink_dot(True)

    def _stop_pb(self) -> None:
        if self._blink_id:
            self.root.after_cancel(self._blink_id)
            self._blink_id = None
        self.live_label.configure(text_color=self.c["DIM_TEXT"])
        self.live_dot.itemconfig(self._dot, fill=self.c["DIM_TEXT"], outline=self.c["DIM_TEXT"])

    def _blink_dot(self, visible: bool) -> None:
        if not self.running:
            return
        color = self.c["PRIMARY"] if visible else self.c["DIM_TEXT"]
        self.live_dot.itemconfig(self._dot, fill=color, outline=color)
        self._blink_id = self.root.after(500, lambda: self._blink_dot(not visible))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_closing(self) -> None:
        self.hide_to_tray()

    def quit_app(self) -> None:
        self._quitting = True
        with self._lock:
            self.running = False
        try:
            v2ray_manager.stop()
        except Exception:
            pass
        self._remove_tray()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        self.root.mainloop()
