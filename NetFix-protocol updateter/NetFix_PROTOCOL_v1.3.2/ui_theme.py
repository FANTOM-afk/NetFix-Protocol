"""
Shared presentation helpers for the NetFix Protocol desktop UI.

The app is still CustomTkinter-based, but this module gives every screen a
single set of design tokens and component recipes. Green is intentionally
reserved for latency/ping values only.
"""

from __future__ import annotations

from typing import Literal

import customtkinter as ctk


FontRole = Literal["title", "section", "body", "caption", "mono", "button"]
ButtonVariant = Literal["primary", "secondary", "danger", "warning", "ghost", "muted"]

FONT_FAMILY = "Segoe UI"
MONO_FONT_FAMILY = "Cascadia Mono"

RADIUS = {
    "sm": 6,
    "md": 8,
    "lg": 8,
}

SPACING = {
    "page": 18,
    "panel": 16,
    "section": 12,
    "control": 8,
}


def setup_customtkinter(theme: str) -> None:
    """Apply app-level CustomTkinter settings."""
    ctk.set_appearance_mode(theme)
    ctk.set_default_color_theme("blue")
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)


def font(role: FontRole = "body", weight: str = "normal") -> ctk.CTkFont:
    sizes = {
        "title": 24,
        "section": 13,
        "body": 12,
        "caption": 11,
        "mono": 12,
        "button": 12,
    }
    family = MONO_FONT_FAMILY if role == "mono" else FONT_FAMILY
    return ctk.CTkFont(family=family, size=sizes[role], weight=weight)


def frame(parent, colors: dict, *, surface: str = "MAIN_BG", **kwargs):
    defaults = {
        "fg_color": colors[surface],
        "corner_radius": RADIUS["lg"],
        "border_width": 1,
        "border_color": colors["FRAME_BORDER"],
    }
    defaults.update(kwargs)
    return ctk.CTkFrame(parent, **defaults)


def scroll_frame(parent, colors: dict, **kwargs):
    defaults = {
        "fg_color": colors["PANEL_BG"],
        "corner_radius": RADIUS["md"],
        "border_width": 1,
        "border_color": colors["FRAME_BORDER"],
    }
    defaults.update(kwargs)
    return ctk.CTkScrollableFrame(parent, **defaults)


def label(parent, text: str, colors: dict, *, role: FontRole = "body",
          color: str = "TEXT", weight: str = "normal", **kwargs):
    defaults = {
        "text": text,
        "text_color": colors[color],
        "font": font(role, weight),
    }
    defaults.update(kwargs)
    return ctk.CTkLabel(parent, **defaults)


def entry(parent, colors: dict, *, mono: bool = False, **kwargs):
    defaults = {
        "fg_color": colors["INPUT_BG"],
        "border_color": colors["FRAME_BORDER"],
        "text_color": colors["TEXT"],
        "placeholder_text_color": colors["MUTED_TEXT"],
        "border_width": 1,
        "corner_radius": RADIUS["sm"],
        "font": font("mono" if mono else "body"),
    }
    defaults.update(kwargs)
    return ctk.CTkEntry(parent, **defaults)


def textbox(parent, colors: dict, **kwargs):
    defaults = {
        "fg_color": colors["INPUT_BG"],
        "text_color": colors["TEXT"],
        "border_color": colors["FRAME_BORDER"],
        "border_width": 1,
        "corner_radius": RADIUS["sm"],
        "font": font("mono"),
    }
    defaults.update(kwargs)
    return ctk.CTkTextbox(parent, **defaults)


def combo(parent, colors: dict, **kwargs):
    defaults = {
        "fg_color": colors["INPUT_BG"],
        "border_color": colors["FRAME_BORDER"],
        "text_color": colors["TEXT"],
        "button_color": colors["PRIMARY"],
        "button_hover_color": colors["PRIMARY_HOVER"],
        "dropdown_fg_color": colors["PANEL_BG"],
        "dropdown_hover_color": colors["HOVER_BG"],
        "dropdown_text_color": colors["TEXT"],
        "border_width": 1,
        "corner_radius": RADIUS["sm"],
        "font": font("body"),
        "dropdown_font": font("body"),
    }
    defaults.update(kwargs)
    return ctk.CTkComboBox(parent, **defaults)


def button(parent, text: str, colors: dict, *, variant: ButtonVariant = "secondary",
           **kwargs):
    palette = {
        "primary": {
            "fg_color": colors["PRIMARY"],
            "hover_color": colors["PRIMARY_HOVER"],
            "text_color": colors["ON_PRIMARY"],
            "border_width": 0,
            "border_color": colors["PRIMARY"],
        },
        "secondary": {
            "fg_color": colors["BUTTON_BG"],
            "hover_color": colors["HOVER_BG"],
            "text_color": colors["TEXT"],
            "border_width": 1,
            "border_color": colors["FRAME_BORDER"],
        },
        "danger": {
            "fg_color": "transparent",
            "hover_color": colors["DANGER_SOFT"],
            "text_color": colors["ACCENT_RED"],
            "border_width": 1,
            "border_color": colors["ACCENT_RED"],
        },
        "warning": {
            "fg_color": "transparent",
            "hover_color": colors["WARNING_SOFT"],
            "text_color": colors["ACCENT_YELLOW"],
            "border_width": 1,
            "border_color": colors["ACCENT_YELLOW"],
        },
        "ghost": {
            "fg_color": "transparent",
            "hover_color": colors["HOVER_BG"],
            "text_color": colors["TEXT"],
            "border_width": 0,
            "border_color": colors["FRAME_BORDER"],
        },
        "muted": {
            "fg_color": "transparent",
            "hover_color": colors["HOVER_BG"],
            "text_color": colors["DIM_TEXT"],
            "border_width": 1,
            "border_color": colors["FRAME_BORDER"],
        },
    }
    defaults = {
        "text": text,
        "corner_radius": RADIUS["md"],
        "font": font("button", "bold"),
    }
    defaults.update(palette[variant])
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def checkbox(parent, text: str, colors: dict, **kwargs):
    defaults = {
        "text": text,
        "fg_color": colors["PRIMARY"],
        "hover_color": colors["HOVER_BG"],
        "border_color": colors["FRAME_BORDER"],
        "text_color": colors["TEXT"],
        "font": font("caption", "bold"),
    }
    defaults.update(kwargs)
    return ctk.CTkCheckBox(parent, **defaults)


def radio(parent, text: str, variable, value: str, colors: dict, **kwargs):
    defaults = {
        "text": text,
        "variable": variable,
        "value": value,
        "fg_color": colors["PRIMARY"],
        "hover_color": colors["HOVER_BG"],
        "border_color": colors["FRAME_BORDER"],
        "text_color": colors["TEXT"],
        "font": font("body"),
    }
    defaults.update(kwargs)
    return ctk.CTkRadioButton(parent, **defaults)


def configure_button(widget, colors: dict, variant: ButtonVariant = "secondary", **kwargs) -> None:
    palette = {
        "primary": {
            "fg_color": colors["PRIMARY"],
            "hover_color": colors["PRIMARY_HOVER"],
            "text_color": colors["ON_PRIMARY"],
            "border_width": 0,
            "border_color": colors["PRIMARY"],
        },
        "secondary": {
            "fg_color": colors["BUTTON_BG"],
            "hover_color": colors["HOVER_BG"],
            "text_color": colors["TEXT"],
            "border_width": 1,
            "border_color": colors["FRAME_BORDER"],
        },
        "danger": {
            "fg_color": "transparent",
            "hover_color": colors["DANGER_SOFT"],
            "text_color": colors["ACCENT_RED"],
            "border_width": 1,
            "border_color": colors["ACCENT_RED"],
        },
        "warning": {
            "fg_color": "transparent",
            "hover_color": colors["WARNING_SOFT"],
            "text_color": colors["ACCENT_YELLOW"],
            "border_width": 1,
            "border_color": colors["ACCENT_YELLOW"],
        },
        "ghost": {
            "fg_color": "transparent",
            "hover_color": colors["HOVER_BG"],
            "text_color": colors["TEXT"],
            "border_width": 0,
            "border_color": colors["FRAME_BORDER"],
        },
        "muted": {
            "fg_color": "transparent",
            "hover_color": colors["HOVER_BG"],
            "text_color": colors["DIM_TEXT"],
            "border_width": 1,
            "border_color": colors["FRAME_BORDER"],
        },
    }
    payload = palette[variant]
    payload.update(kwargs)
    widget.configure(**payload)
