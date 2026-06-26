"""
chart_widget.py
================
Encapsulates the live ping chart (domestic vs. international) as a
self-contained widget with a modern terminal-inspired look.
"""

import math
from collections import deque
from typing import Deque, Optional

import matplotlib
matplotlib.use("Agg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.collections import PolyCollection
import numpy as np

import config


class LiveChart:
    def __init__(self, master, max_points: int = 25) -> None:
        self.max_points = max_points
        self.time_index = 0
        self._theme: str = "dark"
        self._title_color: str = "#00FF41"

        self.domestic_data: Deque[float] = deque(maxlen=max_points)
        self.international_data: Deque[float] = deque(maxlen=max_points)

        self.fig = Figure(figsize=(4.8, 2.6), dpi=110)
        self.fig.subplots_adjust(left=0.08, right=0.97, top=0.88, bottom=0.15)
        self.ax = self.fig.add_subplot(111)

        self._apply_theme_colors("dark")

        self.domestic_line: Line2D
        self.intl_line: Line2D
        self.domestic_fill: PolyCollection = None
        self.intl_fill: PolyCollection = None
        self._init_fills()

        self.domestic_line, = self.ax.plot([], [], color="#00FF41",
                                            label="Domestic", linewidth=2.4, alpha=0.95,
                                            solid_capstyle="round", solid_joinstyle="round")
        self.intl_line, = self.ax.plot([], [], color="#00BFFF",
                                        label="International", linewidth=2.4, alpha=0.95,
                                        solid_capstyle="round", solid_joinstyle="round")

        self.ax.legend(
            loc="upper right",
            facecolor="#1A1A1E",
            edgecolor="#333",
            labelcolor="white",
            fontsize=8,
            framealpha=0.9,
            handlelength=2.5,
        )

        self.canvas = FigureCanvasTkAgg(self.fig, master=master)

    def get_widget(self):
        return self.canvas.get_tk_widget()

    def _init_fills(self):
        if self.domestic_fill:
            try:
                self.domestic_fill.remove()
            except Exception:
                pass
        if self.intl_fill:
            try:
                self.intl_fill.remove()
            except Exception:
                pass
        self.domestic_fill = None
        self.intl_fill = None

    def _make_fill(self, x, y, color, alpha=0.15):
        if not x or len(x) < 2:
            return None
        verts = [(x[0], 0)] + list(zip(x, y)) + [(x[-1], 0)]
        poly = np.array(verts)
        return self.ax.fill(poly[:, 0], poly[:, 1],
                            color=color, alpha=alpha, linewidth=0)[0]

    def _apply_theme_colors(self, theme: str) -> None:
        self._theme = theme
        if theme == "light":
            self._title_color = "#008A2A"
            self.ax.set_facecolor("#F5F5F5")
            self.fig.patch.set_facecolor("#F5F5F5")
            self.ax.tick_params(colors="#999", labelsize=7)
            for spine in ("bottom", "top", "left", "right"):
                self.ax.spines[spine].set_color("#DDD")
                self.ax.spines[spine].set_linewidth(0.8)
            self.ax.grid(True, color="#DDD", linestyle="-", linewidth=0.5, alpha=0.7)
        else:
            self._title_color = "#00FF41"
            self.ax.set_facecolor("#0A0A0C")
            self.fig.patch.set_facecolor("#0A0A0C")
            self.ax.tick_params(colors="#555", labelsize=7)
            for spine in ("bottom", "top", "left", "right"):
                self.ax.spines[spine].set_color("#2A2A2E")
                self.ax.spines[spine].set_linewidth(0.6)
            self.ax.grid(True, color="#1A3A1A", linestyle="-", linewidth=0.4, alpha=0.5)

        self.ax.set_xlabel("Time (samples)", color="#777", fontsize=7, labelpad=2)
        self.ax.set_ylabel("Ping (ms)", color="#777", fontsize=7, labelpad=2)

    def _set_title(self, domestic_ping=None, intl_ping=None) -> None:
        if domestic_ping is not None or intl_ping is not None:
            d = f"{domestic_ping}ms" if domestic_ping is not None else "--"
            i = f"{intl_ping}ms" if intl_ping is not None else "--"
            text = f"Domestic: {d}  |  International: {i}"
        else:
            text = "LIVE CONNECTION STATUS"
        self.ax.set_title(text, color=self._title_color, fontsize=9, fontweight="bold", pad=8)

    def reset(self) -> None:
        self.time_index = 0
        self.domestic_data.clear()
        self.international_data.clear()

        self.domestic_line.set_data([], [])
        self.intl_line.set_data([], [])

        self._init_fills()

        self.ax.set_xlim(0, self.max_points)
        self.ax.set_ylim(0, 500)
        self.ax.set_xticks(range(0, self.max_points + 1, 5))
        self._set_title()

        self.canvas.draw_idle()

    def set_theme_colors(self, theme: str) -> None:
        colors = config.get_colors(theme)
        self._apply_theme_colors(theme)
        self.domestic_line.set_color(colors["ACCENT_GREEN"])
        self.intl_line.set_color(colors["ACCENT_BLUE"])
        if theme == "light":
            self.ax.legend(
                loc="upper right",
                facecolor="#F0F0F0",
                edgecolor="#CCC",
                labelcolor="black",
                fontsize=8,
                framealpha=0.9,
                handlelength=2.5,
            )
        else:
            self.ax.legend(
                loc="upper right",
                facecolor="#1A1A1E",
                edgecolor="#333",
                labelcolor="white",
                fontsize=8,
                framealpha=0.9,
                handlelength=2.5,
            )
        self.canvas.draw_idle()

    def _update_fills(self, x, domestic_y, intl_y):
        self._init_fills()
        if len(x) >= 2:
            self.domestic_fill = self._make_fill(x, domestic_y, "#00FF41", 0.12)
            self.intl_fill = self._make_fill(x, intl_y, "#00BFFF", 0.10)

    def update(self, domestic_ping: Optional[int], intl_ping: Optional[int]) -> None:
        self.domestic_data.append(
            float(domestic_ping) if domestic_ping is not None else float("nan")
        )
        self.international_data.append(
            float(intl_ping) if intl_ping is not None else float("nan")
        )

        self.time_index += 1

        self._set_title(domestic_ping, intl_ping)

        x = list(range(
            self.time_index - len(self.domestic_data) + 1,
            self.time_index + 1
        ))

        domestic_y = list(self.domestic_data)
        intl_y = list(self.international_data)

        self.domestic_line.set_data(x, domestic_y)
        self.intl_line.set_data(x, intl_y)

        self._update_fills(x, domestic_y, intl_y)

        start = max(0, self.time_index - self.max_points)
        end = start + self.max_points

        self.ax.set_xlim(start, end)
        ticks = range(start, end + 1, 5)
        self.ax.set_xticks(ticks)

        values = [
            v for v in domestic_y + intl_y
            if not math.isnan(v)
        ]

        if values:
            max_val = max(values)
            self.ax.set_ylim(0, max(100, max_val + 60))
        else:
            self.ax.set_ylim(0, 500)

        self.canvas.draw_idle()
