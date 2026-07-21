"""
Secondary windows for NetFix Protocol.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Optional

import customtkinter as ctk
from PIL import Image

import config
import ui_theme as ui
from utils import resource_path

_open_windows: Dict[str, ctk.CTkToplevel] = {}


def _focus_or_open(key: str, factory, *args, **kwargs) -> ctk.CTkToplevel:
    existing = _open_windows.get(key)
    if existing:
        try:
            if existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                return existing
        except Exception:
            pass
    win = factory(*args, **kwargs)
    win._nfp_key = key
    win.protocol("WM_DELETE_WINDOW", lambda: _close_window(win))
    _open_windows[key] = win
    return win


def _close_window(win: ctk.CTkToplevel) -> None:
    key = getattr(win, "_nfp_key", None)
    if key and key in _open_windows and _open_windows[key] is win:
        del _open_windows[key]
    try:
        win.destroy()
    except Exception:
        pass


def set_window_icon(win) -> None:
    icon_path = resource_path("logo.ico")
    try:
        win.iconbitmap(icon_path)
        win.after(300, lambda: win.iconbitmap(icon_path))
    except Exception:
        pass


def _dialog(root, title: str, colors: dict, geometry: str, minsize: tuple[int, int]):
    win = ctk.CTkToplevel(root) if root is not None else ctk.CTkToplevel()
    win.title(title)
    win.geometry(geometry)
    win.minsize(*minsize)
    win.configure(fg_color=colors["BG"])
    set_window_icon(win)
    win.grid_rowconfigure(0, weight=1)
    win.grid_columnconfigure(0, weight=1)
    main = ui.frame(win, colors, corner_radius=8)
    main.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
    main.grid_columnconfigure(0, weight=1)
    return win, main


def _network_settings_impl(
    root: ctk.CTk,
    settings: dict,
    on_apply: Callable,
    status_callback: Optional[Callable] = None,
) -> ctk.CTkToplevel:
    colors = config.get_colors(settings.get("theme", "dark"))
    win, main = _dialog(root, "Network Settings", colors, "560x620", (440, 520))
    win.attributes("-topmost", True)
    main.grid_rowconfigure(2, weight=1)
    main.grid_rowconfigure(4, weight=1)

    ui.label(main, "Network Settings", colors, role="title", weight="bold").grid(
        row=0, column=0, sticky="w", padx=18, pady=(18, 2)
    )
    ui.label(
        main,
        "Hosts are checked in order. Keep one host per line.",
        colors,
        role="caption",
        color="DIM_TEXT",
    ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))

    host_grid = ctk.CTkFrame(main, fg_color="transparent")
    host_grid.grid(row=2, column=0, sticky="nsew", padx=18)
    host_grid.grid_columnconfigure((0, 1), weight=1)
    host_grid.grid_rowconfigure(1, weight=1)

    ui.label(host_grid, "Domestic Hosts", colors, role="section", color="ACCENT_CYAN", weight="bold").grid(
        row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6)
    )
    ui.label(host_grid, "International Hosts", colors, role="section", color="ACCENT_CYAN", weight="bold").grid(
        row=0, column=1, sticky="w", padx=(8, 0), pady=(0, 6)
    )

    domestic_box = ui.textbox(host_grid, colors, height=170)
    domestic_box.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
    domestic_box.insert("0.0", "\n".join(settings.get("domestic_hosts", [])))

    intl_box = ui.textbox(host_grid, colors, height=170)
    intl_box.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
    intl_box.insert("0.0", "\n".join(settings.get("international_hosts", [])))

    interval_frame = ctk.CTkFrame(main, fg_color="transparent")
    interval_frame.grid(row=3, column=0, sticky="ew", padx=18, pady=(16, 8))
    interval_frame.grid_columnconfigure(1, weight=1)
    ui.label(
        interval_frame,
        "Ping Interval",
        colors,
        role="section",
        color="ACCENT_CYAN",
        weight="bold",
    ).grid(row=0, column=0, sticky="w", padx=(0, 12))
    interval_entry = ui.entry(interval_frame, colors, width=110)
    interval_entry.grid(row=0, column=1, sticky="w")
    interval_entry.insert(0, str(settings.get("ping_interval", 4)))
    ui.label(interval_frame, "seconds", colors, role="caption", color="DIM_TEXT").grid(
        row=0, column=2, sticky="w", padx=(8, 0)
    )

    error_label = ui.label(main, "", colors, role="caption", color="ACCENT_RED", anchor="w")
    error_label.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 8))

    def apply_changes() -> bool:
        error_label.configure(text="", text_color=colors["ACCENT_RED"])
        domestic_raw = domestic_box.get("0.0", "end").strip()
        international_raw = intl_box.get("0.0", "end").strip()
        interval_raw = interval_entry.get().strip()

        if not domestic_raw:
            error_label.configure(text="Domestic hosts cannot be empty")
            return False
        if not international_raw:
            error_label.configure(text="International hosts cannot be empty")
            return False
        if not interval_raw:
            error_label.configure(text="Ping interval cannot be empty")
            return False

        domestic = [h.strip() for h in domestic_raw.split("\n") if h.strip()]
        international = [h.strip() for h in international_raw.split("\n") if h.strip()]

        try:
            ping_int = int(interval_raw)
            if ping_int < 1 or ping_int > 300:
                raise ValueError
        except ValueError:
            error_label.configure(text="Interval must be an integer from 1 to 300")
            return False

        settings["domestic_hosts"] = domestic
        settings["international_hosts"] = international
        settings["ping_interval"] = ping_int
        on_apply(domestic, international, ping_int)
        if status_callback:
            status_callback("[*] Settings applied", colors["TEXT"])
        error_label.configure(text="Settings applied", text_color=colors["ACCENT_CYAN"])
        return True

    def save_changes() -> None:
        if not apply_changes():
            return
        config.save_settings(settings)
        if status_callback:
            status_callback("[+] Settings saved", colors["ACCENT_GREEN"])
        _close_window(win)

    def reset_to_default() -> None:
        domestic_box.delete("0.0", "end")
        domestic_box.insert("0.0", "\n".join(config.DEFAULT_SETTINGS["domestic_hosts"]))
        intl_box.delete("0.0", "end")
        intl_box.insert("0.0", "\n".join(config.DEFAULT_SETTINGS["international_hosts"]))
        interval_entry.delete(0, "end")
        interval_entry.insert(0, str(config.DEFAULT_SETTINGS["ping_interval"]))
        error_label.configure(text="Defaults restored. Apply or save to keep them.", text_color=colors["ACCENT_CYAN"])

    def clear_all() -> None:
        domestic_box.delete("0.0", "end")
        intl_box.delete("0.0", "end")
        interval_entry.delete(0, "end")
        error_label.configure(text="All fields cleared", text_color=colors["DIM_TEXT"])

    actions = ctk.CTkFrame(main, fg_color="transparent")
    actions.grid(row=5, column=0, sticky="ew", padx=18, pady=(6, 18))
    actions.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

    ui.button(actions, "Apply", colors, variant="secondary", command=apply_changes, height=38).grid(
        row=0, column=0, sticky="ew", padx=(0, 6)
    )
    ui.button(actions, "Save & Close", colors, variant="primary", command=save_changes, height=38).grid(
        row=0, column=1, sticky="ew", padx=6
    )
    ui.button(actions, "Cancel", colors, variant="muted", command=lambda: _close_window(win), height=38).grid(
        row=0, column=2, sticky="ew", padx=6
    )
    ui.button(actions, "Reset", colors, variant="muted", command=reset_to_default, height=38).grid(
        row=0, column=3, sticky="ew", padx=6
    )
    ui.button(actions, "Clear", colors, variant="danger", command=clear_all, height=38).grid(
        row=0, column=4, sticky="ew", padx=(6, 0)
    )
    return win


def open_network_settings(
    root: ctk.CTk,
    settings: dict,
    on_apply: Callable,
    status_callback: Optional[Callable] = None,
) -> None:
    _focus_or_open("network_settings", _network_settings_impl, root, settings, on_apply, status_callback)


def _appearance_settings_impl(
    root: ctk.CTk,
    settings: dict,
    on_theme_changed: Optional[Callable] = None,
) -> ctk.CTkToplevel:
    colors = config.get_colors(settings.get("theme", "dark"))
    win, main = _dialog(root, "Appearance", colors, "420x330", (360, 280))

    ui.label(main, "Appearance", colors, role="title", weight="bold").grid(
        row=0, column=0, sticky="w", padx=18, pady=(18, 4)
    )
    ui.label(main, "Choose a theme for every NetFix surface.", colors, role="caption", color="DIM_TEXT").grid(
        row=1, column=0, sticky="w", padx=18, pady=(0, 18)
    )

    theme_var = ctk.StringVar(value=settings.get("theme", "dark"))
    options = ui.frame(main, colors, surface="PANEL_BG", corner_radius=8)
    options.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
    options.grid_columnconfigure((0, 1), weight=1)
    ui.radio(options, "Dark", theme_var, "dark", colors).grid(row=0, column=0, sticky="w", padx=14, pady=14)
    ui.radio(options, "Light", theme_var, "light", colors).grid(row=0, column=1, sticky="w", padx=14, pady=14)

    def save_theme() -> None:
        settings["theme"] = theme_var.get()
        config.save_settings(settings)
        if on_theme_changed:
            on_theme_changed(settings["theme"])
        else:
            ui.setup_customtkinter(settings["theme"])
        _close_window(win)

    ui.button(main, "Save Theme", colors, variant="primary", command=save_theme, height=40).grid(
        row=3, column=0, sticky="ew", padx=18, pady=(0, 18)
    )
    return win


def open_appearance_settings(
    root: ctk.CTk,
    settings: dict,
    on_theme_changed: Optional[Callable] = None,
) -> None:
    _focus_or_open("appearance_settings", _appearance_settings_impl, root, settings, on_theme_changed)


def _about_impl(theme: str = "dark") -> ctk.CTkToplevel:
    colors = config.get_colors(theme)
    win, main = _dialog(None, "About NetFix Protocol", colors, "420x430", (360, 360))
    main.grid_columnconfigure(0, weight=1)

    try:
        logo_pil = Image.open(resource_path("logo.ico"))
        logo_image = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(72, 72))
        logo_label = ctk.CTkLabel(main, image=logo_image, text="")
        logo_label.image = logo_image
        logo_label.grid(row=0, column=0, pady=(22, 10))
    except Exception as exc:
        logging.debug("About logo failed: %s", exc)

    ui.label(main, "NetFix Protocol", colors, role="title", weight="bold", justify="center").grid(
        row=1, column=0, pady=(0, 2)
    )
    ui.label(main, "1.3.1", colors, role="caption", color="DIM_TEXT", justify="center").grid(
        row=2, column=0, pady=(0, 18)
    )
    ui.label(
        main,
        "Automated Wi-Fi and LAN connection monitor with V2Ray profile routing.",
        colors,
        role="body",
        color="TEXT",
        justify="center",
        wraplength=320,
    ).grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 18))

    divider = ctk.CTkFrame(main, height=1, fg_color=colors["FRAME_BORDER"])
    divider.grid(row=4, column=0, sticky="ew", padx=28, pady=(0, 16))

    ui.label(main, "Developer: Soheil", colors, role="caption", color="DIM_TEXT", justify="center").grid(
        row=5, column=0, pady=(0, 4)
    )
    ui.label(main, "Copyright 2024-2026", colors, role="caption", color="DIM_TEXT", justify="center").grid(
        row=6, column=0, pady=(0, 18)
    )
    ui.button(main, "Close", colors, variant="secondary", command=lambda: _close_window(win), width=120, height=36).grid(
        row=7, column=0, pady=(0, 22)
    )
    return win


def open_about(theme: str = "dark") -> None:
    _focus_or_open("about", _about_impl, theme)
