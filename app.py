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
import utils
import wifi
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
        self.root.title("NET_FIX_PROTOCOL v1.1")
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
        self.menu_btn.place(relx=0.6, y=50)

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
            text="═══ v1.1 ═══",
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

        self.ssid_entry = ctk.CTkEntry(
            form_frame,
            placeholder_text="Enter Network Name...",
            height=42,
            font=ctk.CTkFont(family="Consolas", size=14),
            fg_color=self.c["BG"], border_color=self.c["FRAME_BORDER"],
            text_color=self.c["ACCENT_GREEN"],
            border_width=1, corner_radius=8,
        )
        self.ssid_entry.grid(row=1, column=0, sticky="ew", pady=(6, 14))

        self.conn_type_label = ctk.CTkLabel(
            form_frame, text="> CONNECTION TYPE:",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color=self.c["ACCENT_CYAN"],
        )
        self.conn_type_label.grid(row=2, column=0, sticky="w")

        radio_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        radio_frame.grid(row=3, column=0, sticky="w", pady=(4, 8))

        self.conn_type_var = ctk.StringVar(value="wifi")
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

        self.pb = ctk.CTkProgressBar(
            self.main_frame, mode="indeterminate", height=6,
            fg_color=self.c["PROGRESS_BG"], progress_color=self.c["ACCENT_CYAN"],
            corner_radius=3,
        )
        self.pb.grid(row=3, column=0, sticky="ew", padx=30, pady=(18, 8))
        self.pb.set(0)

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
        self.menu_btn_about.configure(text_color=self.c["TEXT"], hover_color=self.c["FRAME_BORDER"])
        self.menu_btn_close.configure(text_color=self.c["ACCENT_RED"], hover_color=self.c["BTN_HOVER_RED"])

        self.pb.configure(fg_color=self.c["PROGRESS_BG"], progress_color=self.c["ACCENT_CYAN"])

        self.indicator_canvas.configure(bg=self.c["MAIN_BG"])
        self.status_label.configure(text_color=self.c["DIM_TEXT"])

        self.chart.set_theme_colors(theme)

    # ------------------------------------------------------------------
    # Wi-Fi / LAN monitoring
    # ------------------------------------------------------------------
    def _initial_ssid_load(self) -> None:
        current = wifi.get_current_wifi_ssid()
        if current:
            self.ssid_entry.insert(0, current)
            self.update_status(f"[+] Active SSID Detected: {current}", self.c["ACCENT_GREEN"])
        else:
            last = wifi.load_last_ssid(config.LAST_SSID_FILE)
            if last:
                self.ssid_entry.insert(0, last)
                self.update_status("[*] Loaded last saved SSID.", self.c["DIM_TEXT"])

    def _ask_autostart(self) -> bool:
        return messagebox.askyesno("Auto Start", "Enable auto-start on Windows boot?")

    def _maybe_setup_autostart(self) -> None:
        if not utils.is_autostart_enabled() and self._ask_autostart():
            utils.create_startup_shortcut()
            self.update_status("[+] Auto-start enabled.", self.c["ACCENT_GREEN"])

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
                self.start_btn.configure(state="disabled")
                self.stop_btn.configure(state="normal")
                self.ssid_entry.configure(state="disabled")
                self._set_indicator(self.c["ACCENT_YELLOW"], "INITIALIZING")
                self.update_status("[*] INITIALIZING WIFI MONITOR...", self.c["TEXT"])

                threading.Thread(target=self._monitor_wifi, args=(ssid,), daemon=True).start()
            else:
                self._maybe_setup_autostart()

                self.running = True
                self.start_btn.configure(state="disabled")
                self.stop_btn.configure(state="normal")
                self.ssid_entry.configure(state="disabled")
                self._set_indicator(self.c["ACCENT_YELLOW"], "INITIALIZING")
                self.update_status("[*] INITIALIZING LAN MONITOR...", self.c["TEXT"])

                threading.Thread(target=self._monitor_lan, daemon=True).start()

    def stop_monitor(self) -> None:
        with self._lock:
            self.running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.ssid_entry.configure(state="normal")

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
        if hasattr(self, 'pb'):
            self.pb.start()

    def _stop_pb(self) -> None:
        if hasattr(self, 'pb'):
            self.pb.stop()
            self.pb.set(0)

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
        with self._lock:
            self.running = False
        self.root.quit()

    def run(self) -> None:
        self.root.mainloop()
