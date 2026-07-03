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
import os
from typing import Optional, Dict, Any

import customtkinter as ctk
import tkinter.messagebox as messagebox
from PIL import Image, ImageDraw

import config
import utils
import wifi
import cloudflare
import v2ray_manager
import v2ray_paths
from tray_icon import TrayIcon
from chart_widget import LiveChart
from settings_windows import open_network_settings, open_appearance_settings, open_about

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)


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

    draw.arc((cx - r, cy - r, cx + r, cy + r), start=-220, end=40, fill="#00FF41", width=6)
    draw.arc((cx - r + 12, cy - r + 12, cx + r - 12, cy + r - 12), start=-220, end=40, fill="#00BFFF", width=5)
    draw.arc((cx - r + 24, cy - r + 24, cx + r - 24, cy + r - 24), start=-220, end=40, fill="#00FF41", width=4)

    draw.line((cx - r - 8, cy, cx + r + 8, cy), fill="#00BFFF", width=1)
    draw.line((cx, cy - r - 8, cx, cy + r + 8), fill="#00BFFF", width=1)

    for i in range(6, 0, -1):
        s = int(i * 2.5)
        draw.ellipse(
            (cx - s, cy - s, cx + s, cy + s),
            fill=(0, 255, 65, max(1, int(80 - i * 12)))
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
        draw.line((x1, y1, x2, y2), fill="#00FF41", width=1)

    return img


class NetFixApp:
    def __init__(self) -> None:
        self.settings: Dict[str, Any] = config.load_settings()
        if not self.settings.get("v2ray_background_enabled", True):
            self.settings["v2ray_background_enabled"] = True
            config.save_settings(self.settings)

        self.domestic_hosts = self.settings["domestic_hosts"]
        self.international_hosts = self.settings["international_hosts"]
        self.ping_interval = self.settings["ping_interval"]

        ctk.set_appearance_mode(self.settings["theme"])
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

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        import tkinter as tk

        test = tk.Tk()
        test.iconbitmap(utils.resource_path("logo.ico"))
        test.destroy()

        self.root = ctk.CTk()
        self.root.title("NET_FIX_PROTOCOL v1.3")
        self.root.minsize(480, 680)
        self.root.configure(fg_color=self.c["BG"])

        try:
            icon_path = utils.resource_path("logo.ico")
            self.root.iconbitmap(icon_path)
        except Exception:
            pass

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(
            self.root, fg_color=self.c["MAIN_BG"],
            corner_radius=18, border_width=1, border_color=self.c["FRAME_BORDER"],
        )
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        self.main_frame.grid_rowconfigure(5, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

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
        width = 540
        height = 780

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = int((screen_width - width) / 2)
        y = int((screen_height - height) / 2) - 30

        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _build_side_menu(self) -> None:
        self.overlay = ctk.CTkFrame(self.root, fg_color="#000000", corner_radius=0)
        self.overlay.bind("<Button-1>", lambda e: self.toggle_menu())

        self.side_menu = ctk.CTkFrame(
            self.root, fg_color=self.c["SIDE_MENU_BG"],
            corner_radius=0, width=self.menu_width,
        )
        self.side_menu.place(x=-self.menu_width, y=0, relheight=1)

        ctk.CTkLabel(
            self.side_menu, text="☰ MENU",
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color=self.c["ACCENT_CYAN"],
        ).pack(pady=(25, 30))

        self.menu_btn_settings = ctk.CTkButton(
            self.side_menu, text="⚙ Network Settings", anchor="w",
            command=self.open_network_settings,
            fg_color="transparent", text_color=self.c["TEXT"],
            hover_color=self.c["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=13),
        )
        self.menu_btn_settings.pack(fill="x", padx=15, pady=8)

        self.menu_btn_appearance = ctk.CTkButton(
            self.side_menu, text="🎨 Appearance", anchor="w",
            command=lambda: open_appearance_settings(
                self.root, self.settings, on_theme_changed=self._apply_theme
            ),
            fg_color="transparent", text_color=self.c["TEXT"],
            hover_color=self.c["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=13),
        )
        self.menu_btn_appearance.pack(fill="x", padx=15, pady=8)

        self.menu_btn_cloudflare = ctk.CTkButton(
            self.side_menu, text="☁ Cloudflare Account", anchor="w",
            command=lambda: cloudflare.open_cloudflare(self.root),
            fg_color="transparent", text_color=self.c["TEXT"],
            hover_color=self.c["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=13),
        )
        self.menu_btn_cloudflare.pack(fill="x", padx=15, pady=8)

        self.menu_btn_v2ray = ctk.CTkButton(
            self.side_menu, text="V2Ray Router", anchor="w",
            command=lambda: v2ray_manager.open_v2ray(
                self.root, self.settings, status_callback=self.update_status,
                bg_proxy_var=self.bg_proxy_var,
                bg_proxy_callback=self._sync_bg_proxy_from_router,
            ),
            fg_color="transparent", text_color=self.c["TEXT"],
            hover_color=self.c["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=13),
        )
        self.menu_btn_v2ray.pack(fill="x", padx=15, pady=8)

        self.menu_btn_about = ctk.CTkButton(
            self.side_menu, text="ℹ About", anchor="w",
            command=lambda: open_about(self.settings.get("theme", "dark")),
            fg_color="transparent", text_color=self.c["TEXT"],
            hover_color=self.c["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=13),
        )
        self.menu_btn_about.pack(fill="x", padx=15, pady=8)

        self.menu_btn_close = ctk.CTkButton(
            self.side_menu, text="✕ Close Menu", anchor="w",
            command=self.toggle_menu,
            fg_color="transparent", text_color=self.c["ACCENT_RED"],
            hover_color=self.c["BTN_HOVER_RED"],
            font=ctk.CTkFont(family="Consolas", size=13),
        )
        self.menu_btn_close.pack(side="bottom", fill="x", padx=15, pady=20)

        self.menu_btn = ctk.CTkButton(
            self.root, text="☰", width=40, height=32,
            command=self.toggle_menu,
            fg_color=self.c["FRAME_BORDER"], hover_color=self.c["SIDE_MENU_BG"],
            text_color=self.c["ACCENT_CYAN"],
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
        )
        self.menu_btn.place(relx=0.58, y=50)

    def _build_header(self) -> None:
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, pady=(18, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        try:
            icon_path = utils.resource_path("logo.ico")
            logo_pil = Image.open(icon_path)
            logo_image = ctk.CTkImage(
                light_image=logo_pil,
                dark_image=logo_pil,
                size=(72, 72),
            )
        except Exception:
            logo_image = ctk.CTkImage(
                light_image=_generate_logo(),
                dark_image=_generate_logo(),
                size=(72, 72),
            )

        ctk.CTkLabel(header_frame, image=logo_image, text="").grid(row=0, column=0)

        self.header_label = ctk.CTkLabel(
            header_frame,
            text="WIFI AUTO-FIX\nTERMINAL",
            font=ctk.CTkFont(family="Consolas", size=24, weight="bold"),
            text_color=self.c["ACCENT_GREEN"],
            justify="center",
        )
        self.header_label.grid(row=1, column=0, pady=(10, 0))

        ctk.CTkLabel(
            header_frame,
            text="═══ v1.3 ═══",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=self.c["DIM_TEXT"],
        ).grid(row=2, column=0, pady=(3, 8))

    def _build_form(self) -> None:
        form_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        form_frame.grid(row=1, column=0, sticky="ew", padx=30, pady=(5, 5))
        form_frame.grid_columnconfigure(0, weight=1)

        self.ssid_label = ctk.CTkLabel(
            form_frame, text="> TARGET_SSID:",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color=self.c["ACCENT_CYAN"],
        )
        self.ssid_label.grid(row=0, column=0, sticky="w")

        ssid_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        ssid_row.grid(row=1, column=0, sticky="ew", pady=(6, 14))
        ssid_row.grid_columnconfigure(0, weight=1)

        self.ssid_entry = ctk.CTkComboBox(
            ssid_row,
            values=[],
            height=42,
            font=ctk.CTkFont(family="Consolas", size=14),
            fg_color=self.c["BG"], border_color=self.c["FRAME_BORDER"],
            text_color=self.c["ACCENT_GREEN"],
            button_color=self.c["ACCENT_CYAN"],
            button_hover_color=self.c["ACCENT_BLUE"],
            dropdown_font=ctk.CTkFont(family="Consolas", size=13),
            border_width=1, corner_radius=8,
            command=self._on_ssid_selected,
        )
        self.ssid_entry.grid(row=0, column=0, sticky="ew")

        self.scan_btn = ctk.CTkButton(
            ssid_row, text="⟳ Scan", width=70, height=42, corner_radius=8,
            command=self._scan_networks,
            fg_color="transparent", border_width=1, border_color=self.c["ACCENT_GREEN"],
            text_color=self.c["ACCENT_GREEN"], hover_color=self.c["BTN_HOVER_GREEN"],
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        )
        self.scan_btn.grid(row=0, column=1, padx=(8, 0))

        self.conn_type_label = ctk.CTkLabel(
            form_frame, text="> CONNECTION TYPE:",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color=self.c["ACCENT_CYAN"],
        )
        self.conn_type_label.grid(row=2, column=0, sticky="w")

        radio_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        radio_frame.grid(row=3, column=0, sticky="w", pady=(4, 8))

        self.conn_type_var = ctk.StringVar(value="wifi")
        self.conn_type_var.trace_add("write", self._on_conn_type_change)
        self.wifi_radio = ctk.CTkRadioButton(
            radio_frame, text="Wi-Fi",
            variable=self.conn_type_var, value="wifi",
            text_color=self.c["ACCENT_GREEN"],
            fg_color=self.c["ACCENT_GREEN"],
        )
        self.wifi_radio.pack(side="left", padx=(20, 30))

        self.lan_radio = ctk.CTkRadioButton(
            radio_frame, text="LAN",
            variable=self.conn_type_var, value="lan",
            text_color=self.c["ACCENT_BLUE"],
            fg_color=self.c["ACCENT_BLUE"],
        )
        self.lan_radio.pack(side="left")

        bg_enabled = bool(self.settings.get("v2ray_background_enabled", True))
        self.bg_proxy_var = ctk.BooleanVar(value=bg_enabled)
        self.bg_proxy_check = ctk.CTkCheckBox(
            form_frame,
            text="BG Proxy (SOCKS5 :10809 / HTTP :10810)",
            variable=self.bg_proxy_var,
            command=self._on_bg_proxy_toggle,
            text_color=self.c["ACCENT_CYAN"],
            fg_color=self.c["ACCENT_CYAN"],
            hover_color=self.c["BTN_HOVER_GREEN"],
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.bg_proxy_check.grid(row=4, column=0, sticky="w", pady=(4, 2))

    def _build_buttons(self) -> None:
        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=(8, 10))
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self.start_btn = ctk.CTkButton(
            btn_frame, text="▶ INITIALIZE", height=50, corner_radius=10,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            fg_color="transparent", border_width=2, border_color=self.c["ACCENT_GREEN"],
            text_color=self.c["ACCENT_GREEN"],
            hover_color=self.c["BTN_HOVER_GREEN"],
            command=self.start_monitor,
        )
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="■ TERMINATE", height=50, corner_radius=10,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            fg_color="transparent", border_width=2, border_color=self.c["ACCENT_RED"],
            text_color=self.c["ACCENT_RED"],
            hover_color=self.c["BTN_HOVER_RED"],
            state="disabled",
            command=self.stop_monitor,
        )
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.live_label = ctk.CTkLabel(
            self.main_frame, text="● LIVE",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=self.c["MAIN_BG"],
        )
        self.live_label.grid(row=3, column=0, padx=(30, 0), pady=(18, 8), sticky="w")
        self.live_dot = ctk.CTkCanvas(
            self.main_frame, width=14, height=14, highlightthickness=0,
            bg=self.c["MAIN_BG"], bd=0,
        )
        self.live_dot.grid(row=3, column=0, padx=(82, 0), pady=(18, 8), sticky="w")
        self._dot = self.live_dot.create_oval(2, 2, 14, 14, fill=self.c["MAIN_BG"], outline=self.c["MAIN_BG"], width=0)
        self._blink_id = None

    def _build_status_indicator(self) -> None:
        indicator_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        indicator_frame.grid(row=4, column=0, sticky="ew", padx=30, pady=(5, 5))
        indicator_frame.grid_columnconfigure(0, weight=1)

        self.indicator_canvas = ctk.CTkCanvas(
            indicator_frame, width=14, height=14, highlightthickness=0,
            bg=self.c["MAIN_BG"], bd=0,
        )
        self.indicator_canvas.pack(side="left", padx=(0, 10))
        self._indicator_dot = self.indicator_canvas.create_oval(
            2, 2, 14, 14, fill=self.c["DIM_TEXT"], outline=self.c["DIM_TEXT"], width=1
        )

        self.connection_status = ctk.CTkLabel(
            indicator_frame, text="SYSTEM IDLE",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=self.c["DIM_TEXT"],
        )
        self.connection_status.pack(side="left")

        self.ping_display = ctk.CTkLabel(
            indicator_frame, text="-- ms",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=self.c["DIM_TEXT"],
        )
        self.ping_display.pack(side="right")

    def _set_indicator(self, color: str, text: str) -> None:
        self.indicator_canvas.itemconfig(self._indicator_dot, fill=color, outline=color)
        self.connection_status.configure(text=text, text_color=color)

    def _build_chart(self) -> None:
        chart_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        chart_frame.grid(row=5, column=0, sticky="nsew", padx=12, pady=(12, 8))
        chart_frame.grid_rowconfigure(0, weight=1)
        chart_frame.grid_columnconfigure(0, weight=1)

        self.chart = LiveChart(chart_frame)
        self.chart.get_widget().grid(row=0, column=0, sticky="nsew")

    def _build_status_label(self) -> None:
        status_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        status_frame.grid(row=6, column=0, sticky="ew", padx=20, pady=(5, 12))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="> SYSTEM IDLE. WAITING FOR COMMAND...",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color=self.c["DIM_TEXT"],
            justify="left",
        )
        self.status_label.pack(side="left", fill="x", expand=True)

    # ------------------------------------------------------------------
    # Status / side menu helpers
    # ------------------------------------------------------------------
    def update_status(self, text: str, color: str) -> None:
        self.root.after(0, lambda: self.status_label.configure(text=text, text_color=color))
        logging.info("Status: %s", text)

    def _slide_menu(self, opening: bool = True) -> None:
        if self._animating:
            return
        self._animating = True
        if opening:
            self.menu_btn.place_forget()
            self.overlay.place(x=0, y=0, relwidth=1, relheight=1)
            self.side_menu.lift()
            self.menu_open = True
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
                self.menu_btn.place(relx=0.58, y=50)

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

    def _apply_theme(self, theme: str) -> None:
        self.settings["theme"] = theme
        self.c = config.get_colors(theme)
        ctk.set_appearance_mode(theme)

        self.root.configure(fg_color=self.c["BG"])
        self.main_frame.configure(fg_color=self.c["MAIN_BG"], border_color=self.c["FRAME_BORDER"])
        self.side_menu.configure(fg_color=self.c["SIDE_MENU_BG"])
        self.overlay.configure(fg_color="#000000")

        self.header_label.configure(text_color=self.c["ACCENT_GREEN"])
        self.ssid_label.configure(text_color=self.c["ACCENT_CYAN"])
        self.conn_type_label.configure(text_color=self.c["ACCENT_CYAN"])

        self.ssid_entry.configure(
            fg_color=self.c["BG"], border_color=self.c["FRAME_BORDER"],
            text_color=self.c["ACCENT_GREEN"],
        )
        self.wifi_radio.configure(text_color=self.c["ACCENT_GREEN"])
        self.lan_radio.configure(text_color=self.c["ACCENT_BLUE"])
        self.bg_proxy_check.configure(
            text_color=self.c["ACCENT_CYAN"],
            fg_color=self.c["ACCENT_CYAN"],
        )

        self.start_btn.configure(
            border_color=self.c["ACCENT_GREEN"], text_color=self.c["ACCENT_GREEN"],
            hover_color=self.c["BTN_HOVER_GREEN"],
        )
        self.stop_btn.configure(
            border_color=self.c["ACCENT_RED"], text_color=self.c["ACCENT_RED"],
            hover_color=self.c["BTN_HOVER_RED"],
        )

        self.menu_btn.configure(fg_color=self.c["FRAME_BORDER"], text_color=self.c["ACCENT_CYAN"])

        self.menu_btn_settings.configure(text_color=self.c["TEXT"], hover_color=self.c["FRAME_BORDER"])
        self.menu_btn_appearance.configure(text_color=self.c["TEXT"], hover_color=self.c["FRAME_BORDER"])
        self.menu_btn_cloudflare.configure(text_color=self.c["TEXT"], hover_color=self.c["FRAME_BORDER"])
        self.menu_btn_v2ray.configure(text_color=self.c["TEXT"], hover_color=self.c["FRAME_BORDER"])
        self.menu_btn_about.configure(text_color=self.c["TEXT"], hover_color=self.c["FRAME_BORDER"])
        self.menu_btn_close.configure(text_color=self.c["ACCENT_RED"], hover_color=self.c["BTN_HOVER_RED"])

        self.live_dot.configure(bg=self.c["MAIN_BG"])

        self.indicator_canvas.configure(bg=self.c["MAIN_BG"])
        self.status_label.configure(text_color=self.c["DIM_TEXT"])

        self.chart.set_theme_colors(theme)

    # ------------------------------------------------------------------
    # Wi-Fi / LAN monitoring
    # ------------------------------------------------------------------
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
        self.scan_btn.configure(state="disabled", text="⟳ ...")
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
        self.scan_btn.configure(state="normal", text="⟳ Scan")
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
        dialog.resizable(False, False)
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
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=self.c["ACCENT_CYAN"],
        ).pack(anchor="w", padx=10, pady=(15, 2))
        ctk.CTkLabel(
            frame, text=f"'{ssid}'",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color=self.c["ACCENT_GREEN"],
        ).pack(anchor="w", padx=10, pady=(0, 12))

        entry_container = ctk.CTkFrame(frame, fg_color="transparent")
        entry_container.pack(fill="x", padx=10, pady=(0, 6))

        entry = ctk.CTkEntry(
            entry_container, show="*", height=38, placeholder_text="Enter your Wi-Fi password...",
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=self.c["BG"], border_color=self.c["FRAME_BORDER"],
            text_color=self.c["ACCENT_GREEN"],
            border_width=1, corner_radius=6,
        )
        entry.pack(side="left", fill="x", expand=True)

        self.show_password = False

        self.toggle_btn = ctk.CTkButton(
            entry_container, text="👁", width=38, height=38, corner_radius=6,
            command=lambda: self._toggle_password_visibility(entry),
            fg_color="transparent", border_width=1, border_color=self.c["ACCENT_CYAN"],
            text_color=self.c["ACCENT_CYAN"], hover_color=self.c["BTN_HOVER_GREEN"],
            font=ctk.CTkFont(family="Consolas", size=14),
        )
        self.toggle_btn.pack(side="right", padx=(8, 0))

        entry.focus_force()

        err_label = ctk.CTkLabel(
            frame, text="", text_color=self.c["ACCENT_RED"],
            font=ctk.CTkFont(family="Consolas", size=11),
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
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100, height=34, corner_radius=8,
            command=cancel,
            fg_color="transparent", border_width=2, border_color=self.c["ACCENT_RED"],
            text_color=self.c["ACCENT_RED"], hover_color=self.c["BTN_HOVER_RED"],
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
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
        dialog.resizable(False, False)
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
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color=self.c["ACCENT_CYAN"],
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))

        msg_label = ctk.CTkLabel(
            frame,
            text="Install the core once to enable VPN profiles.",
            font=ctk.CTkFont(family="Consolas", size=12),
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
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
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
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
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
                local_port = int(self.settings.get("v2ray_background_port", 10809))
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
            local_port = int(self.settings.get("v2ray_background_port", 10809))
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
            local_port = int(state.get("local_port", 10809))
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
        self.ping_display.configure(text="-- ms")
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
                    text=f"{p} ms", text_color=self.c["ACCENT_GREEN"]
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
                    text=f"{p} ms", text_color=self.c["ACCENT_GREEN"]
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

    def _start_pb(self) -> None:
        self.live_label.configure(text_color=self.c["ACCENT_GREEN"])
        self._blink_dot(True)

    def _stop_pb(self) -> None:
        if self._blink_id:
            self.root.after_cancel(self._blink_id)
            self._blink_id = None
        self.live_label.configure(text_color=self.c["MAIN_BG"])
        self.live_dot.itemconfig(self._dot, fill=self.c["MAIN_BG"], outline=self.c["MAIN_BG"])

    def _blink_dot(self, visible: bool) -> None:
        if not self.running:
            return
        color = self.c["ACCENT_GREEN"] if visible else self.c["MAIN_BG"]
        self.live_dot.itemconfig(self._dot, fill=color, outline=color)
        self._blink_id = self.root.after(500, lambda: self._blink_dot(not visible))

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
