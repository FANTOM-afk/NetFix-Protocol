"""
Responsive live telemetry chart for domestic and international ping samples.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, Optional

import matplotlib

matplotlib.use("Agg")

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

import config


class LiveChart:
    def __init__(self, master, max_points: int = 40) -> None:
        self.max_points = max_points
        self.time_index = 0
        self._theme = "dark"
        self._colors = config.get_colors("dark")

        self.domestic_data: Deque[float] = deque(maxlen=max_points)
        self.international_data: Deque[float] = deque(maxlen=max_points)

        self.fig = Figure(figsize=(5.2, 3.1), dpi=120)
        self.fig.subplots_adjust(left=0.075, right=0.985, top=0.86, bottom=0.16)
        self.ax = self.fig.add_subplot(111)

        self.domestic_line: Line2D
        self.intl_line: Line2D
        self.domestic_line, = self.ax.plot(
            [], [], label="Domestic", linewidth=2.2, antialiased=True,
            solid_capstyle="round", solid_joinstyle="round",
        )
        self.intl_line, = self.ax.plot(
            [], [], label="International", linewidth=2.2, antialiased=True,
            solid_capstyle="round", solid_joinstyle="round",
        )
        self.domestic_fill = None
        self.intl_fill = None

        self._apply_theme_colors("dark")
        self.reset()
        self.canvas = FigureCanvasTkAgg(self.fig, master=master)

    def get_widget(self):
        return self.canvas.get_tk_widget()

    def _theme_value(self, key: str) -> str:
        return self._colors[key]

    def _apply_theme_colors(self, theme: str) -> None:
        self._theme = theme
        self._colors = config.get_colors(theme)
        dark = theme == "dark"

        axis_bg = "#111827" if dark else "#FFFFFF"
        figure_bg = self._theme_value("MAIN_BG")
        grid = "#334155" if dark else "#D6E0EA"
        tick = "#94A3B8" if dark else "#64748B"
        spine = "#334155" if dark else "#CBD5E1"

        self.ax.set_facecolor(axis_bg)
        self.fig.patch.set_facecolor(figure_bg)
        self.ax.tick_params(colors=tick, labelsize=7, length=0)
        for spine_name in ("bottom", "top", "left", "right"):
            self.ax.spines[spine_name].set_color(spine)
            self.ax.spines[spine_name].set_linewidth(0.8)
        self.ax.grid(True, color=grid, linestyle="-", linewidth=0.55, alpha=0.55)
        self.ax.set_axisbelow(True)

        self.ax.set_xlabel("Samples", color=tick, fontsize=7, labelpad=4)
        self.ax.set_ylabel("Ping (ms)", color=tick, fontsize=7, labelpad=4)
        self.domestic_line.set_color(self._theme_value("PRIMARY"))
        self.intl_line.set_color(self._theme_value("ACCENT_BLUE"))
        self._style_legend()
        self._set_title()

    def _style_legend(self) -> None:
        legend = self.ax.legend(
            loc="upper right",
            facecolor=self._theme_value("PANEL_BG"),
            edgecolor=self._theme_value("FRAME_BORDER"),
            labelcolor=self._theme_value("TEXT"),
            fontsize=8,
            framealpha=0.92,
            handlelength=2.6,
            borderpad=0.65,
        )
        legend.get_frame().set_linewidth(0.8)

    def _set_title(self, domestic_ping=None, intl_ping=None) -> None:
        if domestic_ping is not None or intl_ping is not None:
            d = f"{domestic_ping}ms" if domestic_ping is not None else "--"
            i = f"{intl_ping}ms" if intl_ping is not None else "--"
            text = f"Domestic {d}   |   International {i}"
        else:
            text = "Live Connection Telemetry"
        self.ax.set_title(
            text,
            color=self._theme_value("TEXT"),
            fontsize=9,
            fontweight="bold",
            pad=8,
        )

    def _clear_fills(self) -> None:
        for fill in (self.domestic_fill, self.intl_fill):
            if fill is None:
                continue
            try:
                fill.remove()
            except Exception:
                pass
        self.domestic_fill = None
        self.intl_fill = None

    def _smooth_line(self, x_values: list[int], y_values: list[float]):
        x = np.asarray(x_values, dtype=float)
        y = np.asarray(y_values, dtype=float)
        valid = ~np.isnan(y)
        if valid.sum() < 3:
            return x[valid], y[valid]

        x_valid = x[valid]
        y_valid = y[valid]
        smooth_x = np.linspace(x_valid.min(), x_valid.max(), valid.sum() * 8)
        smooth_y = np.interp(smooth_x, x_valid, y_valid)
        if len(smooth_y) >= 5:
            kernel = np.array([1, 2, 3, 2, 1], dtype=float)
            kernel /= kernel.sum()
            smooth_y = np.convolve(smooth_y, kernel, mode="same")
            smooth_y[:2] = np.interp(smooth_x[:2], x_valid, y_valid)
            smooth_y[-2:] = np.interp(smooth_x[-2:], x_valid, y_valid)
        return smooth_x, smooth_y

    def _update_fills(self, dom_x, dom_y, intl_x, intl_y) -> None:
        self._clear_fills()
        if len(dom_x) >= 2:
            self.domestic_fill = self.ax.fill_between(
                dom_x, dom_y, 0, color=self._theme_value("PRIMARY"), alpha=0.10, linewidth=0
            )
        if len(intl_x) >= 2:
            self.intl_fill = self.ax.fill_between(
                intl_x, intl_y, 0, color=self._theme_value("ACCENT_BLUE"), alpha=0.08, linewidth=0
            )

    def reset(self) -> None:
        self.time_index = 0
        self.domestic_data.clear()
        self.international_data.clear()
        self.domestic_line.set_data([], [])
        self.intl_line.set_data([], [])
        self._clear_fills()
        self.ax.set_xlim(0, self.max_points)
        self.ax.set_ylim(0, 300)
        self.ax.set_xticks(range(0, self.max_points + 1, 10))
        self._set_title()
        self.canvas.draw_idle() if hasattr(self, "canvas") else None

    def set_theme_colors(self, theme: str) -> None:
        self._apply_theme_colors(theme)
        self._style_legend()
        self.canvas.draw_idle()

    def update(self, domestic_ping: Optional[int], intl_ping: Optional[int]) -> None:
        self.domestic_data.append(
            float(domestic_ping) if domestic_ping is not None else float("nan")
        )
        self.international_data.append(
            float(intl_ping) if intl_ping is not None else float("nan")
        )
        self.time_index += 1
        self._set_title(domestic_ping, intl_ping)

        x = list(range(self.time_index - len(self.domestic_data) + 1, self.time_index + 1))
        domestic_y = list(self.domestic_data)
        intl_y = list(self.international_data)

        dom_x, dom_smooth = self._smooth_line(x, domestic_y)
        intl_x, intl_smooth = self._smooth_line(x, intl_y)
        self.domestic_line.set_data(dom_x, dom_smooth)
        self.intl_line.set_data(intl_x, intl_smooth)
        self._update_fills(dom_x, dom_smooth, intl_x, intl_smooth)

        start = max(0, self.time_index - self.max_points)
        end = start + self.max_points
        self.ax.set_xlim(start, end)
        self.ax.set_xticks(range(start, end + 1, 10))

        values = [v for v in domestic_y + intl_y if not math.isnan(v)]
        self.ax.set_ylim(0, max(120, max(values) + 35) if values else 300)
        self.canvas.draw_idle()
