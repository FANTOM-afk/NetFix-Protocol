import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Optional

import customtkinter as ctk
import tkinter.messagebox as messagebox

import config
import v2ray_paths
import v2ray_ping
import v2ray_profiles
import v2ray_subscription
from settings_windows import set_window_icon
from v2ray_config import describe_config
from v2ray_core import is_core_installed, is_running, start, stop
from v2ray_proxy_windows import restore_system_proxy, set_system_proxy

_open_window: Optional[ctk.CTkToplevel] = None
PROFILE_RENDER_BATCH = 60
PING_WORKERS = 16
PING_TIMEOUT = 1.5


def _set_widget_state(widget, enabled: bool) -> None:
    try:
        widget.configure(state="normal" if enabled else "disabled")
    except Exception:
        pass


def _meta_line(profile: Dict) -> str:
    meta = profile.get("meta", {})
    host = meta.get("address", "-")
    port = meta.get("port", "-")
    proto = meta.get("protocol", "-")
    network = meta.get("network", "-")
    security = meta.get("security", "-")
    return f"{proto} | {host}:{port} | {network}/{security}"


def _ping_text(profile: Dict) -> str:
    latency = profile.get("latency_ms")
    return f"{latency}ms" if isinstance(latency, int) else "--"


def open_v2ray(
    parent,
    settings: dict,
    status_callback: Optional[Callable[[str, str], None]] = None,
    bg_proxy_var=None,
    bg_proxy_callback: Optional[Callable[[bool], None]] = None,
) -> None:
    global _open_window
    if _open_window is not None:
        try:
            if _open_window.winfo_exists():
                _open_window.lift()
                _open_window.focus_force()
                return
        except Exception:
            pass

    v2ray_profiles.migrate_legacy_user_config()
    store = v2ray_profiles.load_store()
    colors = config.get_colors(settings.get("theme", "dark"))
    state = v2ray_paths.load_state()
    remembered_profile_id = str(state.get("active_profile_id") or "")
    selected_profile_id = remembered_profile_id or str(store.get("active_profile_id") or "")
    selected_group = v2ray_profiles.active_profile(store)
    remembered_group = str(state.get("selected_group") or "")
    available_groups = v2ray_profiles.groups(store)
    if remembered_group in available_groups:
        selected_group_name = remembered_group
    else:
        selected_group_name = selected_group.get("group", "Default") if selected_group else "Default"
    group_profiles = v2ray_profiles.profiles_in_group(store, selected_group_name)
    if group_profiles and not any(profile.get("id") == selected_profile_id for profile in group_profiles):
        selected_profile_id = group_profiles[0]["id"]
    profile_widget_ids: Dict[int, str] = {}
    selected_profile_ids = set()
    visible_profile_limit = PROFILE_RENDER_BATCH
    bg_var = None
    bg_trace_id = None

    win = ctk.CTkToplevel(parent)
    _open_window = win
    win.title("V2Ray - NetFix Protocol")
    win.geometry("1040x780")
    win.minsize(940, 700)
    win.configure(fg_color=colors["BG"])
    set_window_icon(win)

    def close_window() -> None:
        global _open_window
        _open_window = None
        if bg_var is not None and bg_trace_id:
            try:
                bg_var.trace_remove("write", bg_trace_id)
            except Exception:
                pass
        win.unbind_all("<Control-KeyPress>")
        win.unbind_all("<Control-a>")
        win.unbind_all("<Control-A>")
        win.unbind_all("<Control-r>")
        win.unbind_all("<Control-R>")
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", close_window)

    main = ctk.CTkFrame(
        win,
        fg_color=colors["MAIN_BG"],
        corner_radius=12,
        border_width=1,
        border_color=colors["FRAME_BORDER"],
    )
    main.pack(fill="both", expand=True, padx=16, pady=16)
    main.grid_columnconfigure(0, weight=1, minsize=620)
    main.grid_columnconfigure(1, weight=0)
    main.grid_rowconfigure(5, weight=2)

    ctk.CTkLabel(
        main,
        text="> V2RAY PROFILES",
        font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
        text_color=colors["ACCENT_CYAN"],
    ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 6))

    status_text = "RUNNING" if is_running() else ("CORE READY" if is_core_installed() else "CORE NOT INSTALLED")
    status_label = ctk.CTkLabel(
        main,
        text=status_text,
        font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        text_color=colors["ACCENT_GREEN"] if is_running() or is_core_installed() else colors["ACCENT_YELLOW"],
    )
    status_label.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 6))

    top_frame = ctk.CTkFrame(main, fg_color="transparent")
    top_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 6))
    top_frame.grid_columnconfigure(3, weight=1)

    ctk.CTkLabel(
        top_frame,
        text="SOCKS5 PORT (10809)",
        font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
        text_color=colors["ACCENT_CYAN"],
    ).grid(row=0, column=0, sticky="w", padx=(0, 10))

    port_entry = ctk.CTkEntry(
        top_frame,
        width=110,
        fg_color=colors["BG"],
        border_color=colors["FRAME_BORDER"],
        text_color=colors["ACCENT_GREEN"],
        font=ctk.CTkFont(family="Consolas", size=13),
    )
    port_entry.grid(row=0, column=1, sticky="w", padx=(0, 16))
    port_entry.insert(0, str(state.get("local_port", 10809)))
    started_from_router = {"value": False}

    def _sync_bg_check_style(*_args) -> None:
        try:
            enabled = bool(bg_var.get())
            bg_check.configure(text_color=colors["ACCENT_GREEN"] if enabled else colors["DIM_TEXT"])
        except Exception:
            pass

    def _notify_bg_proxy_changed(enabled: bool) -> None:
        if bg_proxy_callback is None:
            return
        try:
            bg_proxy_callback(bool(enabled))
        except Exception as exc:
            ui_message(f"[!] BG Proxy sync failed: {exc}", colors["ACCENT_RED"])

    def _toggle_bg_proxy() -> None:
        enabled = bool(bg_var.get())
        settings["v2ray_background_enabled"] = enabled
        config.save_settings(settings)
        _sync_bg_check_style()
        try:
            if enabled:
                if not is_running():
                    profile = selected_profile()
                    if profile:
                        local_port = read_port()
                        if local_port is not None:
                            try:
                                start(profile["raw_config"], local_port, enable_system_proxy=False)
                                started_from_router["value"] = False
                                start_btn.configure(text="SWITCH", border_color=colors["ACCENT_YELLOW"], text_color=colors["ACCENT_YELLOW"])
                                stop_btn.configure(state="normal")
                                ui_message(f"[+] BG Proxy: port {local_port} open (SOCKS) / {local_port + 1} (HTTP)", colors["ACCENT_GREEN"])
                            except Exception as exc:
                                ui_message(f"[!] BG Proxy start failed: {exc}", colors["ACCENT_RED"])
                    else:
                        ui_message("[*] Select or save a profile first", colors["ACCENT_CYAN"])
                else:
                    try:
                        restore_system_proxy()
                        ui_message("[*] BG Proxy: proxy-only mode (system proxy OFF)", colors["ACCENT_CYAN"])
                    except Exception as exc:
                        ui_message(f"[!] Restore system proxy failed: {exc}", colors["ACCENT_RED"])
                return

            if started_from_router["value"] and is_running():
                local_port = read_port()
                if local_port is None:
                    return
                try:
                    set_system_proxy(local_port)
                    ui_message("[+] BG Proxy disabled: system VPN mode", colors["ACCENT_GREEN"])
                except Exception as exc:
                    ui_message(f"[!] System proxy failed: {exc}", colors["ACCENT_RED"])
                return

            stop()
            start_btn.configure(text="START", border_color=colors["ACCENT_GREEN"], text_color=colors["ACCENT_GREEN"])
            stop_btn.configure(state="disabled")
            started_from_router["value"] = False
            ui_message("[*] BG Proxy disabled (VPN idle)", colors["DIM_TEXT"])
        finally:
            _notify_bg_proxy_changed(enabled)

    bg_enabled = bool(settings.get("v2ray_background_enabled", True) if settings else True)
    bg_var = bg_proxy_var if bg_proxy_var is not None else ctk.BooleanVar(value=bg_enabled)
    if bool(bg_var.get()) != bg_enabled:
        bg_var.set(bg_enabled)
    bg_check = ctk.CTkCheckBox(
        top_frame,
        text="BG Proxy",
        variable=bg_var,
        command=_toggle_bg_proxy,
        font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        text_color=colors["ACCENT_GREEN"] if bg_var.get() else colors["DIM_TEXT"],
        fg_color=colors["ACCENT_CYAN"],
        hover_color=colors["BTN_HOVER_GREEN"],
    )
    bg_check.grid(row=0, column=2, sticky="w", padx=(0, 16))
    try:
        bg_trace_id = bg_var.trace_add("write", _sync_bg_check_style)
    except Exception:
        bg_trace_id = None
    _sync_bg_check_style()

    left = ctk.CTkFrame(main, fg_color="transparent")
    left.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=18, pady=(0, 8))
    left.grid_columnconfigure(0, weight=1)
    left.grid_rowconfigure(1, weight=1)

    right = ctk.CTkFrame(main, fg_color="transparent")
    right.grid(row=4, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 6))
    right.grid_columnconfigure(0, weight=1)
    right.grid_rowconfigure(6, weight=0)

    group_var = ctk.StringVar(value=selected_group_name)
    group_bar = ctk.CTkFrame(left, fg_color="transparent")
    group_bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
    group_bar.grid_columnconfigure(0, weight=1)

    group_tabs = ctk.CTkScrollableFrame(
        group_bar,
        height=38,
        orientation="horizontal",
        fg_color=colors["BG"],
        border_width=1,
        border_color=colors["FRAME_BORDER"],
        corner_radius=6,
    )
    group_tabs.grid(row=0, column=0, sticky="ew", padx=(0, 8))

    add_group_btn = ctk.CTkButton(
        group_bar,
        text="+",
        width=38,
        height=38,
        corner_radius=19,
        command=lambda: open_new_group_window(),
        fg_color="transparent",
        border_width=1,
        border_color=colors["ACCENT_CYAN"],
        text_color=colors["ACCENT_CYAN"],
        hover_color=colors["FRAME_BORDER"],
        font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
    )
    add_group_btn.grid(row=0, column=1, sticky="e")

    profile_list = ctk.CTkScrollableFrame(
        left,
        fg_color=colors["BG"],
        border_width=1,
        border_color=colors["FRAME_BORDER"],
        corner_radius=6,
        height=360,
    )
    profile_list.grid(row=1, column=0, sticky="nsew")
    profile_list.grid_columnconfigure(0, weight=1)

    selected_title = ctk.CTkLabel(
        right,
        text="No profile selected",
        text_color=colors["ACCENT_GREEN"],
        font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
    )
    selected_title.grid(row=0, column=0, sticky="w", pady=(0, 2))

    selected_specs = ctk.CTkLabel(
        right,
        text="-",
        text_color=colors["TEXT"],
        font=ctk.CTkFont(family="Consolas", size=12),
    )
    selected_specs.grid(row=1, column=0, sticky="w", pady=(0, 6))

    detail_grid = ctk.CTkFrame(right, fg_color=colors["BG"], corner_radius=6)
    detail_grid.grid(row=2, column=0, sticky="ew", pady=(0, 8))
    detail_grid.grid_columnconfigure((1, 3), weight=1)
    detail_labels: Dict[str, ctk.CTkLabel] = {}
    detail_items = [("protocol", "PROTO"), ("address", "HOST"), ("port", "PORT"), ("network", "NET"), ("security", "SEC"), ("ping", "PING")]
    for idx, (key, label) in enumerate(detail_items):
        row = idx // 2
        col = (idx % 2) * 2
        ctk.CTkLabel(
            detail_grid,
            text=label,
            text_color=colors["ACCENT_CYAN"],
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=row, column=col, sticky="w", padx=(10, 4), pady=4)
        value_label = ctk.CTkLabel(
            detail_grid,
            text="-",
            text_color=colors["TEXT"],
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        value_label.grid(row=row, column=col + 1, sticky="w", padx=(0, 10), pady=4)
        detail_labels[key] = value_label

    form = ctk.CTkFrame(right, fg_color="transparent")
    form.grid(row=3, column=0, sticky="ew", pady=(0, 6))
    form.grid_columnconfigure(1, weight=1)

    name_entry = ctk.CTkEntry(
        form,
        placeholder_text="Profile name",
        fg_color=colors["BG"],
        border_color=colors["FRAME_BORDER"],
        text_color=colors["TEXT"],
    )
    name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 4))

    group_entry = ctk.CTkEntry(
        form,
        placeholder_text="Group",
        fg_color=colors["BG"],
        border_color=colors["FRAME_BORDER"],
        text_color=colors["TEXT"],
    )
    group_entry.grid(row=0, column=1, sticky="ew", pady=(0, 4))

    raw_box = ctk.CTkTextbox(
        right,
        height=58,
        fg_color=colors["BG"],
        text_color=colors["TEXT"],
        border_width=1,
        border_color=colors["FRAME_BORDER"],
        corner_radius=6,
        font=ctk.CTkFont(family="Consolas", size=12),
    )
    raw_box.grid(row=6, column=0, sticky="ew", pady=(0, 6))

    raw_placeholder = "Paste vmess://, vless://, trojan://, or outbound JSON here. Empty means keep selected config."
    raw_placeholder_visible = True
    auto_save_after_id = None

    def show_raw_placeholder() -> None:
        nonlocal raw_placeholder_visible
        raw_box.edit_modified(False)
        raw_box.delete("0.0", "end")
        raw_box.insert("0.0", raw_placeholder)
        raw_box.configure(text_color=colors["DIM_TEXT"])
        raw_box.edit_modified(False)
        raw_placeholder_visible = True

    def clear_raw_placeholder(_event=None) -> None:
        nonlocal raw_placeholder_visible
        if raw_placeholder_visible:
            raw_box.delete("0.0", "end")
            raw_box.configure(text_color=colors["TEXT"])
            raw_placeholder_visible = False
            name_entry.delete(0, "end")
            group_entry.delete(0, "end")
            group_entry.insert(0, group_var.get() or "Default")
            selected_title.configure(text="New profile")
            selected_specs.configure(text="Paste config, then Save")
            for label in detail_labels.values():
                label.configure(text="-")

    def get_raw_input() -> str:
        if raw_placeholder_visible:
            return ""
        return raw_box.get("0.0", "end").strip()

    raw_box.bind("<FocusIn>", clear_raw_placeholder)
    def schedule_auto_save_config(_event=None):
        nonlocal auto_save_after_id
        if raw_placeholder_visible:
            return
        if auto_save_after_id:
            try:
                win.after_cancel(auto_save_after_id)
            except Exception:
                pass
        auto_save_after_id = win.after(180, auto_save_pasted_config)

    def on_raw_modified(_event=None):
        if raw_box.edit_modified():
            raw_box.edit_modified(False)
            schedule_auto_save_config()

    raw_box.bind("<<Paste>>", schedule_auto_save_config)
    raw_box.bind("<Control-v>", schedule_auto_save_config)
    raw_box.bind("<Control-V>", schedule_auto_save_config)
    raw_box.bind("<<Modified>>", on_raw_modified)
    show_raw_placeholder()

    error_label = ctk.CTkLabel(
        right,
        text="",
        font=ctk.CTkFont(family="Consolas", size=11),
        text_color=colors["ACCENT_RED"],
    )
    error_label.grid(row=7, column=0, sticky="w", pady=(0, 8))

    btn_frame = ctk.CTkFrame(main, fg_color="transparent")
    btn_frame.grid(row=0, column=1, rowspan=2, sticky="ne", padx=18, pady=(16, 0))
    btn_frame.grid_columnconfigure((0, 1, 2), weight=0)

    action_panel = ctk.CTkFrame(
        main,
        fg_color=colors["BG"],
        border_width=1,
        border_color=colors["FRAME_BORDER"],
        corner_radius=6,
    )
    action_panel.grid(row=3, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 10))
    action_panel.grid_remove()
    for col in range(4):
        action_panel.grid_columnconfigure(col, weight=1)

    action_panel_open = False
    action_buttons = []

    def toggle_action_panel() -> None:
        nonlocal action_panel_open
        action_panel_open = not action_panel_open
        if action_panel_open:
            action_panel.grid()
            more_btn.configure(border_color=colors["ACCENT_CYAN"])
        else:
            action_panel.grid_remove()
            more_btn.configure(border_color=colors["DIM_TEXT"])

    def hide_action_panel() -> None:
        nonlocal action_panel_open
        action_panel_open = False
        action_panel.grid_remove()
        more_btn.configure(border_color=colors["DIM_TEXT"])

    def ui_message(text: str, color: str) -> None:
        error_label.configure(text=text, text_color=color)
        status_label.configure(
            text=text.replace("[+] ", "").replace("[*] ", "").replace("[!] ", "")[:64],
            text_color=color,
        )
        if status_callback:
            status_callback(text, color)

    def read_port() -> Optional[int]:
        try:
            value = int(port_entry.get().strip())
            if value < 1024 or value > 65534:
                raise ValueError
            return value
        except ValueError:
            ui_message("[!] Local port must be 1024-65534.", colors["ACCENT_RED"])
            return None

    def selected_profile() -> Optional[Dict]:
        return v2ray_profiles.get_profile(store, selected_profile_id)

    def set_selected(profile_id: str) -> None:
        nonlocal selected_profile_id
        profile = v2ray_profiles.get_profile(store, profile_id)
        if not profile:
            return
        selected_profile_id = profile_id
        store["active_profile_id"] = profile_id
        group_var.set(profile.get("group", "Default"))
        sync_subscription_fields(profile.get("group", "Default"))
        v2ray_paths.save_state({"selected_group": profile.get("group", "Default"), "active_profile_id": profile_id})
        fill_form(profile)
        refresh_groups()
        refresh_profiles()

    def fill_form(profile: Optional[Dict]) -> None:
        name_entry.delete(0, "end")
        group_entry.delete(0, "end")
        show_raw_placeholder()
        if not profile:
            selected_title.configure(text="No profile selected")
            selected_specs.configure(text="-")
            for label in detail_labels.values():
                label.configure(text="-")
            return
        meta = profile.get("meta", {})
        selected_title.configure(text=profile.get("name", "V2Ray Profile"))
        selected_specs.configure(text=_meta_line(profile))
        for key, label in detail_labels.items():
            if key == "ping":
                value = _ping_text(profile)
            else:
                value = str(meta.get(key, "") or "-")
            label.configure(text=value[:80])
        name_entry.insert(0, profile.get("name", ""))
        group_entry.insert(0, profile.get("group", "Default"))

    def refresh_groups() -> None:
        values = v2ray_profiles.groups(store)
        for child in group_tabs.winfo_children():
            child.destroy()
        if group_var.get() not in values:
            group_var.set(values[0])
        active_group = group_var.get() or values[0]
        for col, group in enumerate(values):
            active = group == active_group
            btn = ctk.CTkButton(
                group_tabs,
                text=group,
                height=30,
                width=96,
                command=lambda value=group: change_group(value),
                fg_color=colors["FRAME_BORDER"] if active else "transparent",
                border_width=1,
                border_color=colors["ACCENT_CYAN"] if active else colors["FRAME_BORDER"],
                text_color=colors["ACCENT_GREEN"] if active else colors["TEXT"],
                hover_color=colors["FRAME_BORDER"],
                font=ctk.CTkFont(family="Consolas", size=11, weight="bold" if active else "normal"),
            )
            btn.grid(row=0, column=col, sticky="w", padx=(4 if col == 0 else 2, 2), pady=4)

    def sync_subscription_fields(group: str) -> None:
        v2ray_paths.save_state({"last_subscription_name": group})

    def change_group(value: str) -> None:
        nonlocal visible_profile_limit
        group = value or "Default"
        visible_profile_limit = PROFILE_RENDER_BATCH
        group_var.set(group)
        sync_subscription_fields(group)
        v2ray_paths.save_state({"selected_group": group})
        refresh_groups()
        refresh_profiles()

    def toggle_selected(profile_id: str, selected: bool) -> None:
        if selected:
            selected_profile_ids.add(profile_id)
        else:
            selected_profile_ids.discard(profile_id)

    def copy_profile(profile_id: str) -> None:
        profile = v2ray_profiles.get_profile(store, profile_id)
        if not profile:
            return
        win.clipboard_clear()
        win.clipboard_append(profile.get("raw_config", ""))
        ui_message(f"[+] Copied {profile.get('name', 'profile')}.", colors["ACCENT_GREEN"])

    def current_group_profiles():
        return v2ray_profiles.profiles_in_group(store, group_var.get() or "Default")

    def select_all_current_group(_event=None):
        selected_profile_ids.clear()
        selected_profile_ids.update(profile["id"] for profile in current_group_profiles())
        refresh_profiles()
        ui_message(f"[*] Selected {len(selected_profile_ids)} configs.", colors["ACCENT_CYAN"])
        return "break"

    def ping_selected(_event=None):
        profiles = [
            profile for profile in store.get("profiles", [])
            if profile.get("id") in selected_profile_ids
        ]
        if not profiles:
            ui_message("[!] Select configs first. Ctrl+A selects the current group.", colors["ACCENT_RED"])
            return "break"
        threading.Thread(target=ping_profiles_worker, args=(profiles,), daemon=True).start()
        return "break"

    def ping_profile(profile_id: str, _event=None):
        profile = v2ray_profiles.get_profile(store, profile_id)
        if not profile:
            return "break"
        threading.Thread(target=ping_profiles_worker, args=([profile], False), daemon=True).start()
        return "break"

    def profile_id_from_event(event=None) -> Optional[str]:
        widget = getattr(event, "widget", None)
        while widget is not None:
            profile_id = getattr(widget, "_netfix_profile_id", None) or profile_widget_ids.get(id(widget))
            if profile_id:
                return profile_id
            widget = getattr(widget, "master", None)
        return None

    def ping_profile_from_event(event=None):
        profile_id = profile_id_from_event(event)
        if not profile_id:
            return None
        return ping_profile(profile_id, event)

    def profile_widget_targets(widget):
        seen = set()
        for target in (
            widget,
            getattr(widget, "_canvas", None),
            getattr(widget, "_text_label", None),
            getattr(widget, "_image_label", None),
        ):
            if target is None or id(target) in seen:
                continue
            seen.add(id(target))
            yield target

    def register_profile_ping_widget(widget, profile_id: str) -> None:
        for target in profile_widget_targets(widget):
            profile_widget_ids[id(target)] = profile_id
            try:
                setattr(target, "_netfix_profile_id", profile_id)
            except Exception:
                pass
            try:
                target.bind("<Double-Button-1>", ping_profile_from_event, add=True)
            except TypeError:
                try:
                    target.bind("<Double-Button-1>", ping_profile_from_event)
                except Exception:
                    pass
            except Exception:
                pass

    def router_shortcut(event=None):
        keysym = str(getattr(event, "keysym", "") or "").lower()
        char = str(getattr(event, "char", "") or "").lower()
        try:
            keycode = int(getattr(event, "keycode", 0) or 0)
        except (TypeError, ValueError):
            keycode = 0

        if keysym == "a" or char == "\x01" or keycode == 65:
            return select_all_current_group(event)
        if keysym == "r" or char == "\x12" or keycode == 82:
            return ping_selected(event)
        return None

    def bind_router_shortcuts(*widgets) -> None:
        def bind_target(target) -> None:
            try:
                target.bind("<Control-KeyPress>", router_shortcut, add=True)
            except TypeError:
                try:
                    target.bind("<Control-KeyPress>", router_shortcut)
                except Exception:
                    pass
            except Exception:
                pass

        def widget_targets(widget):
            seen = set()
            for target in (
                widget,
                getattr(widget, "_entry", None),
                getattr(widget, "_textbox", None),
                getattr(widget, "_canvas", None),
                getattr(widget, "_parent_canvas", None),
            ):
                if target is None or id(target) in seen:
                    continue
                seen.add(id(target))
                yield target

        win.bind_all("<Control-KeyPress>", router_shortcut, add=True)
        for widget in widgets:
            for target in widget_targets(widget):
                bind_target(target)

    def ping_profiles_worker(profiles, clear_selection: bool = True):
        if len(profiles) == 1:
            title = profiles[0].get("name", "config")
            win.after(0, lambda name=title: ui_message(f"[*] Pinging {name}...", colors["ACCENT_CYAN"]))
        else:
            win.after(0, lambda: ui_message(f"[*] Pinging {len(profiles)} selected configs...", colors["ACCENT_CYAN"]))
        ok_count = 0
        results = {}
        with ThreadPoolExecutor(max_workers=PING_WORKERS) as executor:
            future_map = {
                executor.submit(v2ray_ping.tcp_ping_profile, profile, PING_TIMEOUT): profile
                for profile in profiles
            }
            for future in as_completed(future_map):
                profile = future_map[future]
                try:
                    results[profile["id"]] = future.result()
                except Exception:
                    results[profile["id"]] = None

        for profile in profiles:
            latency = results.get(profile["id"])
            if isinstance(latency, int):
                profile["latency_ms"] = latency
                ok_count += 1
            else:
                profile.pop("latency_ms", None)
        v2ray_profiles.save_store(store)

        def done() -> None:
            if clear_selection:
                selected_profile_ids.clear()
            refresh_profiles()
            active = selected_profile()
            if active:
                fill_form(active)
            if len(profiles) == 1:
                profile = profiles[0]
                latency = profile.get("latency_ms")
                if isinstance(latency, int):
                    ui_message(f"[+] {profile.get('name', 'config')} ping: {latency}ms", colors["ACCENT_GREEN"])
                else:
                    ui_message(f"[!] {profile.get('name', 'config')} unreachable.", colors["ACCENT_RED"])
            else:
                ui_message(f"[+] Ping complete: {ok_count}/{len(profiles)} reachable.", colors["ACCENT_GREEN"])

        win.after(0, done)

    def refresh_profiles() -> None:
        for child in profile_list.winfo_children():
            child.destroy()
        profile_widget_ids.clear()
        current_group = group_var.get() or "Default"
        profiles = v2ray_profiles.profiles_in_group(store, current_group)
        if not profiles:
            ctk.CTkLabel(
                profile_list,
                text="No profiles",
                text_color=colors["DIM_TEXT"],
                font=ctk.CTkFont(family="Consolas", size=12),
            ).grid(row=0, column=0, sticky="ew", padx=8, pady=10)
            return
        visible_profiles = profiles[:visible_profile_limit]
        for row, profile in enumerate(visible_profiles):
            active = profile.get("id") == selected_profile_id
            row_frame = ctk.CTkFrame(profile_list, fg_color="transparent")
            row_frame.grid(row=row, column=0, sticky="ew", padx=6, pady=4)
            row_frame.grid_columnconfigure(1, weight=1)
            row_frame.grid_columnconfigure(2, weight=0, minsize=74)
            row_frame.grid_columnconfigure(3, weight=0, minsize=54)

            selected_var = ctk.BooleanVar(value=profile["id"] in selected_profile_ids)
            check = ctk.CTkCheckBox(
                row_frame,
                text="",
                width=24,
                variable=selected_var,
                command=lambda pid=profile["id"], var=selected_var: toggle_selected(pid, var.get()),
                fg_color=colors["ACCENT_GREEN"],
                border_color=colors["FRAME_BORDER"],
            )
            check.grid(row=0, column=0, sticky="w", padx=(0, 4))

            btn = ctk.CTkButton(
                row_frame,
                text=f"{profile.get('name', 'Profile')}\n{_meta_line(profile)}",
                anchor="w",
                height=54,
                fg_color=colors["FRAME_BORDER"] if active else "transparent",
                text_color=colors["ACCENT_GREEN"] if active else colors["TEXT"],
                hover_color=colors["FRAME_BORDER"],
                font=ctk.CTkFont(family="Consolas", size=11),
                command=lambda pid=profile["id"]: set_selected(pid),
            )
            btn.grid(row=0, column=1, sticky="ew")

            ping_value = _ping_text(profile)
            ping_label = ctk.CTkLabel(
                row_frame,
                text=ping_value,
                width=70,
                text_color=colors["ACCENT_GREEN"] if ping_value != "--" else colors["DIM_TEXT"],
                font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            )
            ping_label.grid(row=0, column=2, sticky="ew", padx=(8, 4))

            copy_btn = ctk.CTkButton(
                row_frame,
                text="COPY",
                width=50,
                height=36,
                command=lambda pid=profile["id"]: copy_profile(pid),
                fg_color="transparent",
                border_width=1,
                border_color=colors["ACCENT_BLUE"],
                text_color=colors["ACCENT_BLUE"],
                hover_color=colors["FRAME_BORDER"],
                font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            )
            copy_btn.grid(row=0, column=3, sticky="e", padx=(4, 0))
            register_profile_ping_widget(row_frame, profile["id"])
            register_profile_ping_widget(btn, profile["id"])
            register_profile_ping_widget(ping_label, profile["id"])

        if len(profiles) > visible_profile_limit:
            remaining = len(profiles) - visible_profile_limit
            load_more_btn = ctk.CTkButton(
                profile_list,
                text=f"LOAD MORE ({remaining})",
                height=34,
                command=load_more_profiles,
                fg_color="transparent",
                border_width=1,
                border_color=colors["DIM_TEXT"],
                text_color=colors["DIM_TEXT"],
                hover_color=colors["FRAME_BORDER"],
                font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            )
            load_more_btn.grid(row=len(visible_profiles), column=0, sticky="ew", padx=6, pady=(6, 4))

    def load_more_profiles() -> None:
        nonlocal visible_profile_limit
        visible_profile_limit += PROFILE_RENDER_BATCH
        refresh_profiles()

    def auto_save_pasted_config() -> None:
        raw = get_raw_input()
        if not raw:
            return
        configs = v2ray_subscription.extract_configs(raw)
        if not configs:
            try:
                describe_config(raw)
            except Exception:
                return
        save_profile()

    def save_profile() -> bool:
        raw = get_raw_input()
        raw_was_entered = bool(raw)
        selected = selected_profile()
        name = name_entry.get().strip()
        group = group_entry.get().strip() or group_var.get() or "Default"
        selected_raw = str(selected.get("raw_config", "")).strip() if selected else ""
        selected_name = str(selected.get("name", "")).strip() if selected else ""

        if raw:
            configs = v2ray_subscription.extract_configs(raw)
            if not configs:
                try:
                    describe_config(raw)
                    configs = [raw]
                except Exception as exc:
                    ui_message(f"[!] Invalid config: {exc}", colors["ACCENT_RED"])
                    return False

            if len(configs) > 1:
                try:
                    synced = v2ray_profiles.add_profiles(store, configs, group=group)
                    refresh_groups()
                    if synced:
                        v2ray_paths.save_user_config(synced[0]["raw_config"])
                        set_selected(synced[0]["id"])
                        show_raw_placeholder()
                        ui_message(f"[+] Added {len(synced)} profiles.", colors["ACCENT_GREEN"])
                    else:
                        show_raw_placeholder()
                        ui_message("[*] These profiles already exist.", colors["DIM_TEXT"])
                    return True
                except Exception as exc:
                    ui_message(f"[!] Save failed: {exc}", colors["ACCENT_RED"])
                    return False

            raw = configs[0]
        elif selected:
            raw = selected.get("raw_config", "")
        else:
            ui_message("[!] Paste a config first.", colors["ACCENT_RED"])
            return False

        try:
            describe_config(raw)
        except Exception as exc:
            ui_message(f"[!] Invalid config: {exc}", colors["ACCENT_RED"])
            return False

        try:
            should_update_selected = bool(
                selected
                and (not raw_was_entered or raw.strip() == selected_raw)
            )
            if should_update_selected:
                profile = v2ray_profiles.update_profile(store, selected_profile_id, raw, name, group)
            else:
                profile_name = "" if raw_was_entered and name == selected_name else name
                profile = v2ray_profiles.add_profile(store, raw, profile_name, group)
            v2ray_paths.save_user_config(profile["raw_config"])
            refresh_groups()
            set_selected(profile["id"])
            show_raw_placeholder()
            ui_message("[+] Profile saved.", colors["ACCENT_GREEN"])
            return True
        except Exception as exc:
            ui_message(f"[!] Save failed: {exc}", colors["ACCENT_RED"])
            return False

    def new_profile() -> None:
        nonlocal selected_profile_id
        selected_profile_id = ""
        name_entry.delete(0, "end")
        group_entry.delete(0, "end")
        group_entry.insert(0, group_var.get() or "Default")
        show_raw_placeholder()
        selected_title.configure(text="New profile")
        selected_specs.configure(text="Paste config, then Save")
        for label in detail_labels.values():
            label.configure(text="-")
        refresh_profiles()

    def delete_selected() -> None:
        nonlocal selected_profile_id
        profile = selected_profile()
        if not profile:
            ui_message("[!] No profile selected.", colors["ACCENT_RED"])
            return
        if not messagebox.askyesno(
            "Delete Profile",
            f"Delete profile '{profile.get('name', 'V2Ray Profile')}'?",
            parent=win,
        ):
            return
        if is_running():
            stop()
        v2ray_profiles.delete_profile(store, profile["id"])
        selected_profile_id = str(store.get("active_profile_id") or "")
        v2ray_paths.save_state({"active_profile_id": selected_profile_id})
        refresh_groups()
        fill_form(selected_profile())
        refresh_profiles()
        ui_message("[+] Profile deleted.", colors["DIM_TEXT"])

    def open_new_group_window() -> None:
        dialog = ctk.CTkToplevel(win)
        dialog.title("New Group")
        dialog.geometry("520x235")
        dialog.resizable(False, False)
        dialog.configure(fg_color=colors["BG"])
        dialog.transient(win)
        dialog.grab_set()
        set_window_icon(dialog)

        frame = ctk.CTkFrame(
            dialog,
            fg_color=colors["MAIN_BG"],
            border_width=1,
            border_color=colors["FRAME_BORDER"],
            corner_radius=8,
        )
        frame.pack(fill="both", expand=True, padx=14, pady=14)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="NEW GROUP",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color=colors["ACCENT_CYAN"],
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))

        name_entry = ctk.CTkEntry(
            frame,
            placeholder_text="Group name",
            fg_color=colors["BG"],
            border_color=colors["FRAME_BORDER"],
            text_color=colors["TEXT"],
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        name_entry.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        url_entry = ctk.CTkEntry(
            frame,
            placeholder_text="Subscription URL",
            fg_color=colors["BG"],
            border_color=colors["FRAME_BORDER"],
            text_color=colors["TEXT"],
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        url_entry.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 8))

        msg_label = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=colors["ACCENT_RED"],
        )
        msg_label.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 8))

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 14))
        btns.grid_columnconfigure((0, 1), weight=1)

        def save_new_group() -> None:
            group = name_entry.get().strip()
            subscription_url = url_entry.get().strip()
            if not group:
                msg_label.configure(text="[!] Group name is required")
                return
            if subscription_url and not subscription_url.lower().startswith(("http://", "https://")):
                msg_label.configure(text="[!] Subscription URL must start with http:// or https://")
                return
            try:
                group = v2ray_profiles.ensure_group(store, group, subscription_url)
                group_var.set(group)
                sync_subscription_fields(group)
                refresh_groups()
                refresh_profiles()
                v2ray_paths.save_state({"selected_group": group, "last_subscription_name": group})
                dialog.destroy()
                ui_message(f"[+] Group added: {group}", colors["ACCENT_GREEN"])
            except Exception as exc:
                msg_label.configure(text=f"[!] Save failed: {exc}")

        ctk.CTkButton(
            btns,
            text="CREATE",
            height=34,
            command=save_new_group,
            fg_color="transparent",
            border_width=1,
            border_color=colors["ACCENT_GREEN"],
            text_color=colors["ACCENT_GREEN"],
            hover_color=colors["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            btns,
            text="CANCEL",
            height=34,
            command=dialog.destroy,
            fg_color="transparent",
            border_width=1,
            border_color=colors["DIM_TEXT"],
            text_color=colors["DIM_TEXT"],
            hover_color=colors["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        name_entry.focus_set()

    def open_edit_group_window() -> None:
        current_group = group_var.get() or "Default"
        current_url = v2ray_profiles.group_subscription_url(store, current_group)

        dialog = ctk.CTkToplevel(win)
        dialog.title("Edit Group")
        dialog.geometry("560x275")
        dialog.resizable(False, False)
        dialog.configure(fg_color=colors["BG"])
        dialog.transient(win)
        dialog.grab_set()
        set_window_icon(dialog)

        frame = ctk.CTkFrame(
            dialog,
            fg_color=colors["MAIN_BG"],
            border_width=1,
            border_color=colors["FRAME_BORDER"],
            corner_radius=8,
        )
        frame.pack(fill="both", expand=True, padx=14, pady=14)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text=f"EDIT GROUP: {current_group}",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color=colors["ACCENT_CYAN"],
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))

        name_entry = ctk.CTkEntry(
            frame,
            placeholder_text="Group name",
            fg_color=colors["BG"],
            border_color=colors["FRAME_BORDER"],
            text_color=colors["TEXT"],
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        name_entry.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        name_entry.insert(0, current_group)

        url_entry = ctk.CTkEntry(
            frame,
            placeholder_text="Subscription URL",
            fg_color=colors["BG"],
            border_color=colors["FRAME_BORDER"],
            text_color=colors["TEXT"],
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        url_entry.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 8))
        if current_url:
            url_entry.insert(0, current_url)

        msg_label = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=colors["ACCENT_RED"],
        )
        msg_label.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 8))

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 14))
        btns.grid_columnconfigure((0, 1, 2), weight=1)

        def save_group() -> None:
            new_group = name_entry.get().strip() or current_group
            subscription_url = url_entry.get().strip()
            if subscription_url and not subscription_url.lower().startswith(("http://", "https://")):
                msg_label.configure(text="[!] Subscription URL must start with http:// or https://")
                return
            try:
                updated_group = v2ray_profiles.update_group(store, current_group, new_group, subscription_url)
                group_var.set(updated_group)
                sync_subscription_fields(updated_group)
                refresh_groups()
                refresh_profiles()
                fill_form(selected_profile())
                v2ray_paths.save_state({
                    "selected_group": updated_group,
                    "last_subscription_name": updated_group,
                })
                dialog.destroy()
                ui_message(f"[+] Group saved: {updated_group}", colors["ACCENT_GREEN"])
            except Exception as exc:
                msg_label.configure(text=f"[!] Save failed: {exc}")

        def delete_current_group() -> None:
            nonlocal selected_profile_id
            if not messagebox.askyesno(
                "Delete Group",
                f"Delete group '{current_group}' and all profiles inside it?",
                parent=dialog,
            ):
                return
            try:
                if is_running():
                    stop()
                deleted = v2ray_profiles.delete_group(store, current_group)
                selected_profile_id = str(store.get("active_profile_id") or "")
                active = selected_profile()
                next_group = active.get("group", "Default") if active else v2ray_profiles.groups(store)[0]
                group_var.set(next_group)
                sync_subscription_fields(next_group)
                refresh_groups()
                fill_form(active)
                refresh_profiles()
                v2ray_paths.save_state({
                    "selected_group": next_group,
                    "active_profile_id": selected_profile_id,
                    "last_subscription_name": next_group,
                })
                dialog.destroy()
                ui_message(f"[+] Deleted group '{current_group}' ({deleted} profiles).", colors["DIM_TEXT"])
            except Exception as exc:
                msg_label.configure(text=f"[!] Delete failed: {exc}")

        ctk.CTkButton(
            btns,
            text="SAVE",
            height=34,
            command=save_group,
            fg_color="transparent",
            border_width=1,
            border_color=colors["ACCENT_GREEN"],
            text_color=colors["ACCENT_GREEN"],
            hover_color=colors["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            btns,
            text="DELETE GROUP",
            height=34,
            command=delete_current_group,
            fg_color="transparent",
            border_width=1,
            border_color=colors["ACCENT_RED"],
            text_color=colors["ACCENT_RED"],
            hover_color=colors["BTN_HOVER_RED"],
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=0, column=1, sticky="ew", padx=6)

        ctk.CTkButton(
            btns,
            text="CANCEL",
            height=34,
            command=dialog.destroy,
            fg_color="transparent",
            border_width=1,
            border_color=colors["DIM_TEXT"],
            text_color=colors["DIM_TEXT"],
            hover_color=colors["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))

        name_entry.focus_set()

    def open_add_subscription_window() -> None:
        current_group = group_var.get() or "Default"
        current_url = v2ray_profiles.group_subscription_url(store, current_group)

        dialog = ctk.CTkToplevel(win)
        dialog.title("Add Subscription")
        dialog.geometry("560x245")
        dialog.resizable(False, False)
        dialog.configure(fg_color=colors["BG"])
        dialog.transient(win)
        dialog.grab_set()
        set_window_icon(dialog)

        frame = ctk.CTkFrame(
            dialog,
            fg_color=colors["MAIN_BG"],
            border_width=1,
            border_color=colors["FRAME_BORDER"],
            corner_radius=8,
        )
        frame.pack(fill="both", expand=True, padx=14, pady=14)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="ADD SUBSCRIPTION",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color=colors["ACCENT_CYAN"],
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))

        group_entry = ctk.CTkEntry(
            frame,
            placeholder_text="Group name",
            fg_color=colors["BG"],
            border_color=colors["FRAME_BORDER"],
            text_color=colors["TEXT"],
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        group_entry.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        group_entry.insert(0, current_group)

        url_entry = ctk.CTkEntry(
            frame,
            placeholder_text="Subscription URL",
            fg_color=colors["BG"],
            border_color=colors["FRAME_BORDER"],
            text_color=colors["TEXT"],
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        url_entry.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 8))
        if current_url:
            url_entry.insert(0, current_url)

        msg_label = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=colors["ACCENT_RED"],
        )
        msg_label.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 8))

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 14))
        btns.grid_columnconfigure((0, 1), weight=1)

        def import_from_dialog() -> None:
            group = group_entry.get().strip() or "Subscription"
            url = url_entry.get().strip()
            if not url:
                msg_label.configure(text="[!] Enter a subscription URL")
                return
            if not url.lower().startswith(("http://", "https://")):
                msg_label.configure(text="[!] Subscription URL must start with http:// or https://")
                return
            dialog.destroy()
            threading.Thread(target=import_subscription_worker, args=(url, group), daemon=True).start()

        ctk.CTkButton(
            btns,
            text="IMPORT",
            height=34,
            command=import_from_dialog,
            fg_color="transparent",
            border_width=1,
            border_color=colors["ACCENT_GREEN"],
            text_color=colors["ACCENT_GREEN"],
            hover_color=colors["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            btns,
            text="CANCEL",
            height=34,
            command=dialog.destroy,
            fg_color="transparent",
            border_width=1,
            border_color=colors["DIM_TEXT"],
            text_color=colors["DIM_TEXT"],
            hover_color=colors["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        url_entry.focus_set()

    def import_subscription_worker(url: str, group: str) -> None:
        for widget in action_buttons + [start_btn, stop_btn, more_btn]:
            win.after(0, lambda w=widget: _set_widget_state(w, False))
        try:
            configs = v2ray_subscription.fetch_subscription(
                url,
                progress=lambda msg: win.after(0, lambda m=msg: ui_message(f"[*] {m}", colors["ACCENT_CYAN"])),
            )
            v2ray_profiles.set_group_subscription_url(store, group, url)
            synced = v2ray_profiles.add_profiles(store, configs, group=group)

            def done() -> None:
                nonlocal selected_profile_id
                refresh_groups()
                if synced:
                    selected_profile_id = synced[0]["id"]
                    group_var.set(synced[0].get("group", group))
                    sync_subscription_fields(group)
                    v2ray_paths.save_state({
                        "selected_group": group,
                        "last_subscription_name": group,
                        "active_profile_id": selected_profile_id,
                    })
                    fill_form(synced[0])
                    ui_message(f"[+] Synced {len(synced)} configs into '{group}'.", colors["ACCENT_GREEN"])
                else:
                    sync_subscription_fields(group)
                    v2ray_paths.save_state({"selected_group": group, "last_subscription_name": group})
                    ui_message("[*] Subscription loaded; no new configs to add.", colors["DIM_TEXT"])
                refresh_profiles()

            win.after(0, done)
        except Exception as exc:
            win.after(0, lambda e=exc: ui_message(f"[!] Subscription import failed: {e}", colors["ACCENT_RED"]))
            win.after(0, lambda e=exc: messagebox.showerror("V2Ray Subscription", str(e)))
        finally:
            for widget in action_buttons + [start_btn, stop_btn, more_btn]:
                win.after(0, lambda w=widget: _set_widget_state(w, True))

    def import_subscription_clicked() -> None:
        open_add_subscription_window()

    def start_clicked() -> None:
        profile = selected_profile()
        if not profile:
            ui_message("[!] Select or save a profile first.", colors["ACCENT_RED"])
            return
        local_port = read_port()
        if local_port is None:
            return
        try:
            if is_running():
                stop()
            v2ray_profiles.set_active_profile(store, profile["id"])
            v2ray_paths.save_state({
                "local_port": local_port,
                "selected_group": profile.get("group", "Default"),
                "active_profile_id": profile["id"],
            })
            v2ray_paths.save_user_config(profile["raw_config"])
            system_proxy = not bg_var.get()
            start(profile["raw_config"], local_port, enable_system_proxy=system_proxy)
            started_from_router["value"] = True
            mode = "system VPN" if system_proxy else "proxy-only"
            ui_message(f"[+] {profile['name']} enabled on 127.0.0.1:{local_port} ({mode}).", colors["ACCENT_GREEN"])
            start_btn.configure(text="SWITCH", border_color=colors["ACCENT_YELLOW"], text_color=colors["ACCENT_YELLOW"])
            stop_btn.configure(state="normal")
        except Exception as exc:
            ui_message(f"[!] Start failed: {exc}", colors["ACCENT_RED"])
            messagebox.showerror("V2Ray", str(exc))

    def stop_clicked() -> None:
        stop()
        started_from_router["value"] = False
        ui_message("[+] V2Ray stopped and Windows proxy restored.", colors["DIM_TEXT"])
        start_btn.configure(text="START", border_color=colors["ACCENT_GREEN"], text_color=colors["ACCENT_GREEN"])
        stop_btn.configure(state="disabled")
        if bg_var.get():
            ui_message("[*] Background proxy will restart automatically.", colors["ACCENT_CYAN"])

    bind_router_shortcuts(win, main, group_tabs, profile_list, port_entry, name_entry, group_entry, raw_box)

    start_btn = ctk.CTkButton(
        btn_frame,
        text="SWITCH" if is_running() else "START",
        width=64,
        height=64,
        corner_radius=32,
        command=start_clicked,
        fg_color="transparent",
        border_width=2,
        border_color=colors["ACCENT_YELLOW"] if is_running() else colors["ACCENT_GREEN"],
        text_color=colors["ACCENT_YELLOW"] if is_running() else colors["ACCENT_GREEN"],
        hover_color=colors["FRAME_BORDER"],
        font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
    )
    start_btn.grid(row=0, column=0, padx=(0, 8))

    stop_btn = ctk.CTkButton(
        btn_frame,
        text="STOP",
        width=64,
        height=64,
        corner_radius=32,
        command=stop_clicked,
        state="normal" if is_running() else "disabled",
        fg_color="transparent",
        border_width=2,
        border_color=colors["ACCENT_RED"],
        text_color=colors["ACCENT_RED"],
        hover_color=colors["BTN_HOVER_RED"],
        font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
    )
    stop_btn.grid(row=0, column=1, padx=(0, 8))

    more_btn = ctk.CTkButton(
        btn_frame,
        text="...",
        width=42,
        height=42,
        corner_radius=21,
        command=toggle_action_panel,
        fg_color="transparent",
        border_width=2,
        border_color=colors["DIM_TEXT"],
        text_color=colors["TEXT"],
        hover_color=colors["FRAME_BORDER"],
        font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
    )
    more_btn.grid(row=0, column=2, padx=(0, 0))

    def action_command(callback) -> Callable[[], None]:
        def run() -> None:
            callback()
            hide_action_panel()
        return run

    def make_action_btn(text: str, command, color: str, row: int, col: int):
        btn = ctk.CTkButton(
            action_panel,
            text=text,
            height=34,
            command=command,
            fg_color="transparent",
            border_width=1,
            border_color=color,
            text_color=color,
            hover_color=colors["FRAME_BORDER"],
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
        )
        btn.grid(row=row, column=col, sticky="ew", padx=6, pady=6)
        action_buttons.append(btn)
        return btn

    import_btn = make_action_btn("ADD SUB", action_command(import_subscription_clicked), colors["ACCENT_CYAN"], 0, 0)
    edit_group_btn = make_action_btn("EDIT GROUP", action_command(open_edit_group_window), colors["ACCENT_CYAN"], 0, 1)
    delete_btn = make_action_btn("DELETE", action_command(delete_selected), colors["ACCENT_RED"], 1, 0)
    select_btn = make_action_btn("SELECT GROUP", action_command(select_all_current_group), colors["ACCENT_YELLOW"], 1, 1)

    active = selected_profile()
    if active:
        group_var.set(active.get("group", selected_group_name))
    sync_subscription_fields(group_var.get() or selected_group_name)
    fill_form(active)
    refresh_groups()
    refresh_profiles()
