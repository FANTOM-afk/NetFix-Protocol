"""
settings_windows.py
====================
Secondary windows: network host/interval settings, appearance (theme)
settings, and the About dialog.
"""

from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

import config
from utils import resource_path

import os
import sys

def set_window_icon(win):
    icon_path = resource_path("logo.ico")
    print("ICON:", icon_path, os.path.exists(icon_path))

    try:
        win.iconbitmap(icon_path)
    except Exception as e:
        print("iconbitmap error:", e)

    win.after(300, lambda: win.iconbitmap(icon_path))

def _apply_theme_to_window(win: ctk.CTkToplevel, colors: dict) -> None:
    win.configure(fg_color=colors["BG"])
    for child in win.winfo_children():
        if isinstance(child, (ctk.CTkFrame, ctk.CTkScrollableFrame)):
            child.configure(fg_color=colors["MAIN_BG"])
        elif isinstance(child, ctk.CTkLabel):
            child.configure(text_color=colors["TEXT"])
        elif isinstance(child, ctk.CTkEntry):
            child.configure(
                fg_color=colors["BG"],
                border_color=colors["FRAME_BORDER"],
                text_color=colors["ACCENT_GREEN"],
            )
        elif isinstance(child, ctk.CTkButton):
            child.configure(fg_color=colors["ACCENT_GREEN"], text_color=colors["BG"],
                           hover_color=colors["BTN_HOVER_GREEN"])


def open_network_settings(
    root: ctk.CTk,
    settings: dict,
    on_apply: Callable,
    status_callback: Optional[Callable] = None,
) -> None:
    colors = config.get_colors(settings.get("theme", "dark"))

    win = ctk.CTkToplevel(root)
    win.title("Network Settings")
    win.attributes("-topmost", True)
    win.geometry("480x520")
    win.resizable(False, False)
    win.configure(fg_color=colors["BG"])
    
    try:
        icon_path = resource_path("logo.ico")
       
        set_window_icon(win)
    except Exception as e:
        print(f"Error loading icon: {e}")
    main_frame = ctk.CTkFrame(win, fg_color=colors["MAIN_BG"],
                               corner_radius=12, border_width=1, border_color=colors["FRAME_BORDER"])
    main_frame.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(
        main_frame, text="> DOMESTIC HOSTS",
        font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
        text_color=colors["ACCENT_CYAN"],
    ).pack(anchor="w", padx=15, pady=(18, 5))

    domestic_box = ctk.CTkTextbox(main_frame, height=85,
                                    fg_color=colors["BG"], text_color=colors["TEXT"],
                                    border_width=1, border_color=colors["FRAME_BORDER"],
                                    corner_radius=6)
    domestic_box.pack(fill="x", padx=15)
    domestic_box.insert("0.0", "\n".join(settings.get("domestic_hosts", [])))

    ctk.CTkLabel(
        main_frame, text="> INTERNATIONAL HOSTS",
        font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
        text_color=colors["ACCENT_CYAN"],
    ).pack(anchor="w", padx=15, pady=(15, 5))

    intl_box = ctk.CTkTextbox(main_frame, height=85,
                                fg_color=colors["BG"], text_color=colors["TEXT"],
                                border_width=1, border_color=colors["FRAME_BORDER"],
                                corner_radius=6)
    intl_box.pack(fill="x", padx=15)
    intl_box.insert("0.0", "\n".join(settings.get("international_hosts", [])))

    ctk.CTkLabel(
        main_frame, text="> PING INTERVAL (seconds)",
        font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
        text_color=colors["ACCENT_CYAN"],
    ).pack(anchor="w", padx=15, pady=(15, 5))

    interval_entry = ctk.CTkEntry(
        main_frame,
        font=ctk.CTkFont(family="Consolas", size=14),
        fg_color=colors["BG"], text_color=colors["ACCENT_GREEN"],
        border_color=colors["FRAME_BORDER"], border_width=1, corner_radius=6,
    )
    interval_entry.pack(padx=15, fill="x")
    interval_entry.insert(0, str(settings.get("ping_interval", 4)))

    error_label = ctk.CTkLabel(main_frame, text="", text_color=colors["ACCENT_RED"],
                                font=ctk.CTkFont(family="Consolas", size=11))
    error_label.pack(pady=(5, 0))

    def apply_changes() -> None:
        error_label.configure(text="")
        domestic = [h.strip() for h in domestic_box.get("0.0", "end").strip().split("\n") if h.strip()]
        international = [h.strip() for h in intl_box.get("0.0", "end").strip().split("\n") if h.strip()]

        interval_raw = interval_entry.get().strip()
        try:
            ping_int = int(interval_raw)
            if ping_int < 1 or ping_int > 300:
                raise ValueError
        except ValueError:
            error_label.configure(text="[!] Interval must be 1-300 (integer)")
            return

        settings["domestic_hosts"] = domestic
        settings["international_hosts"] = international
        settings["ping_interval"] = ping_int

        on_apply(domestic, international, ping_int)

        if status_callback:
            status_callback("[*] Settings Applied (Not Saved)", colors["TEXT"])

    def save_changes() -> None:
        apply_changes()
        config.save_settings(settings)
        if status_callback:
            status_callback("[+] Settings Saved", colors["ACCENT_GREEN"])
        win.destroy()

    btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    btn_frame.pack(pady=(20, 18))

    ctk.CTkButton(
        btn_frame, text="Apply", width=100, height=36, corner_radius=8,
        command=apply_changes,
        fg_color="transparent", border_width=2, border_color=colors["ACCENT_GREEN"],
        text_color=colors["ACCENT_GREEN"], hover_color=colors["BTN_HOVER_GREEN"],
        font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
    ).pack(side="left", padx=6)

    ctk.CTkButton(
        btn_frame, text="Save & Close", width=130, height=36, corner_radius=8,
        command=save_changes,
        fg_color=colors["ACCENT_GREEN"], text_color=colors["BG"],
        hover_color=colors["BTN_HOVER_GREEN"],
        font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
    ).pack(side="left", padx=6)

    ctk.CTkButton(
        btn_frame, text="Cancel", width=100, height=36, corner_radius=8,
        command=win.destroy,
        fg_color="transparent", border_width=2, border_color=colors["ACCENT_RED"],
        text_color=colors["ACCENT_RED"], hover_color=colors["BTN_HOVER_RED"],
        font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
    ).pack(side="left", padx=6)


def open_appearance_settings(
    root: ctk.CTk,
    settings: dict,
    on_theme_changed: Optional[Callable] = None,
) -> None:
    colors = config.get_colors(settings.get("theme", "dark"))

    win = ctk.CTkToplevel(root)
    win.title("Appearance")
    win.geometry("340x280")
    win.resizable(False, False)
    win.configure(fg_color=colors["BG"])
    
    try:
        icon_path = resource_path("logo.ico")
        set_window_icon(win)

    except Exception:
        pass
    main_frame = ctk.CTkFrame(win, fg_color=colors["MAIN_BG"],
                               corner_radius=12, border_width=1, border_color=colors["FRAME_BORDER"])
    main_frame.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(
        main_frame, text="> THEME MODE",
        font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
        text_color=colors["ACCENT_CYAN"],
    ).pack(pady=(22, 18))

    theme_var = ctk.StringVar(value=settings.get("theme", "dark"))

    ctk.CTkRadioButton(
        main_frame, text="  Dark", variable=theme_var, value="dark",
        text_color=colors["TEXT"], fg_color=colors["ACCENT_GREEN"],
        font=ctk.CTkFont(family="Consolas", size=13),
    ).pack(pady=6)

    ctk.CTkRadioButton(
        main_frame, text="  Light", variable=theme_var, value="light",
        text_color=colors["TEXT"], fg_color=colors["ACCENT_GREEN"],
        font=ctk.CTkFont(family="Consolas", size=13),
    ).pack(pady=6)

    def save_theme() -> None:
        settings["theme"] = theme_var.get()
        config.save_settings(settings)
        if on_theme_changed:
            on_theme_changed(settings["theme"])
        else:
            ctk.set_appearance_mode(settings["theme"])
        win.destroy()

    ctk.CTkButton(
        main_frame, text="Save Theme", height=38, corner_radius=8,
        command=save_theme,
        fg_color=colors["ACCENT_GREEN"], text_color=colors["BG"],
        hover_color=colors["BTN_HOVER_GREEN"],
        font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
    ).pack(pady=(25, 18))


def open_about(theme: str = "dark") -> None:
    colors = config.get_colors(theme)

    win = ctk.CTkToplevel()
    win.title("About")
    win.geometry("360x380")
    win.resizable(False, False)
    win.configure(fg_color=colors["BG"])
    
    try:
        icon_path = resource_path("logo.ico")
        set_window_icon(win)
    except Exception:
        pass

    main_frame = ctk.CTkFrame(win, fg_color=colors["MAIN_BG"],
                               corner_radius=12, border_width=1, border_color=colors["FRAME_BORDER"])
    main_frame.pack(fill="both", expand=True, padx=16, pady=16)

    try:
        icon_path = resource_path("logo.ico")
        logo_pil = Image.open(icon_path)
        logo_image = ctk.CTkImage(
            light_image=logo_pil,
            dark_image=logo_pil,
            size=(64, 64),
        )
        ctk.CTkLabel(main_frame, image=logo_image, text="").pack(pady=(8, 2))
    except Exception:
        pass

    ctk.CTkLabel(
        main_frame,
        text="NET FIX PROTOCOL",
        font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
        text_color=colors["ACCENT_GREEN"],
    ).pack(pady=(5, 2))

    ctk.CTkLabel(
        main_frame,
        text="v1.1",
        font=ctk.CTkFont(family="Consolas", size=11),
        text_color=colors["DIM_TEXT"],
    ).pack(pady=(0, 15))

    info_text = (
        "Automated Wi-Fi / LAN\n"
        "Connection Monitor & Repair\n"
    )
    ctk.CTkLabel(
        main_frame,
        text=info_text,
        font=ctk.CTkFont(family="Consolas", size=12),
        text_color=colors["TEXT"],
        justify="center",
    ).pack(pady=(0, 15))

    sep = ctk.CTkFrame(main_frame, height=1, fg_color=colors["FRAME_BORDER"])
    sep.pack(fill="x", padx=20, pady=(0, 10))

    ctk.CTkLabel(
        main_frame,
        text="Developer: Soheil",
        font=ctk.CTkFont(family="Consolas", size=12),
        text_color=colors["DIM_TEXT"],
    ).pack(pady=(0, 5))

    ctk.CTkLabel(
        main_frame,
        text="© 2024-2026",
        font=ctk.CTkFont(family="Consolas", size=10),
        text_color=colors["DIM_TEXT"],
    ).pack(pady=(0, 10))

    ctk.CTkButton(
        main_frame, text="Close", width=100, height=34, corner_radius=8,
        command=win.destroy,
        fg_color="transparent", border_width=2, border_color=colors["ACCENT_GREEN"],
        text_color=colors["ACCENT_GREEN"], hover_color=colors["BTN_HOVER_GREEN"],
        font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
    ).pack(pady=(5, 15))
