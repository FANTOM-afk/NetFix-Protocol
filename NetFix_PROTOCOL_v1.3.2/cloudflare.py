import os
import json
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
import tkinter as tk
import tkinter.messagebox as messagebox
from urllib.parse import urljoin, urlparse
from cloudflare_tab_script import build_tab_bar_script
import config
import storage
import utils

CLOUDFLARE_DASHBOARD_URL = "https://dash.cloudflare.com/"
CLOUDFLARE_LOGIN_URL = "https://dash.cloudflare.com/login"
CLOUDFLARE_API_TOKENS_URL = "https://dash.cloudflare.com/profile/api-tokens"
CLOUDFLARE_NOVA_TOKEN_URL = "https://dash.cloudflare.com/profile/api-tokens?permissionGroupKeys=%5B%7B%22key%22%3A%22workers_scripts%22%2C%22type%22%3A%22edit%22%7D%2C%7B%22key%22%3A%22workers_kv_storage%22%2C%22type%22%3A%22edit%22%7D%2C%7B%22key%22%3A%22d1%22%2C%22type%22%3A%22edit%22%7D%2C%7B%22key%22%3A%22account_settings%22%2C%22type%22%3A%22read%22%7D%5D&accountId=*&zoneId=all&name=Nova"
NOVAPROXY_INSTALL_URL = "https://novaproxy.online/install"
ATOMICMAIL_URL = "https://atomicmail.io/"
WINDOW_TITLE = "Cloudflare Account - NetFix Protocol"
APP_ICON = "logo.ico"
FIXED_HOME_TAB_IDS = {"api", "novaproxy", "atomicmail"}
HTTP_SCHEMES = {"http", "https"}
EXTERNAL_SCHEMES = {"mailto", "tel", "sms", "tg", "whatsapp"}
WEBVIEW_ERROR_SCHEMES = {"chrome-error", "edge-error"}
BLOCKED_SCHEMES = {"javascript", "data", "file", "about", "edge", "chrome", *WEBVIEW_ERROR_SCHEMES}
LOCAL_URL_RE = re.compile(r"^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(/.*)?$", re.IGNORECASE)


def get_cloudflare_config_path() -> str:
    from config import APP_DATA_DIR
    return os.path.join(APP_DATA_DIR, "config.json")


def get_cloudflare_webview_storage_path() -> str:
    from config import APP_DATA_DIR

    storage_path = os.path.join(APP_DATA_DIR, "CloudflareWebView")
    os.makedirs(storage_path, exist_ok=True)
    return storage_path


def get_cloudflare_tabs_path() -> str:
    from config import APP_DATA_DIR

    return os.path.join(APP_DATA_DIR, "cloudflare_tabs.json")


def is_cloudflare_authenticated(config_path: str = None) -> bool:
    if config_path is None:
        config_path = get_cloudflare_config_path()
    if not os.path.exists(config_path):
        return False
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        token = data.get("api_token", "")
        return bool(token and token.strip())
    except (json.JSONDecodeError, OSError):
        return False


def _cloudflare_url(config_path: str = None) -> str:
    if config_path is None:
        config_path = get_cloudflare_config_path()

    if is_cloudflare_authenticated(config_path):
        return CLOUDFLARE_DASHBOARD_URL
    return CLOUDFLARE_LOGIN_URL


def normalize_browser_url(value: str, base_url: str = CLOUDFLARE_DASHBOARD_URL) -> str:
    """Normalize user/browser navigation the way a browser address bar would."""
    value = str(value or "").strip()
    if not value:
        return ""

    lowered = value.lower()
    if lowered.startswith("#"):
        return ""

    if value.startswith("//"):
        return f"https:{value}"

    parsed = urlparse(value)
    scheme = parsed.scheme.lower()

    if scheme:
        if scheme in HTTP_SCHEMES or scheme in EXTERNAL_SCHEMES:
            return value
        if scheme in BLOCKED_SCHEMES:
            return ""
        # Treat localhost:3000 as a host:port input, not as a custom scheme.
        if LOCAL_URL_RE.match(value):
            return f"http://{value}"
        return value

    if LOCAL_URL_RE.match(value):
        return f"http://{value}"

    if " " not in value and "." in value.split("/", 1)[0]:
        return f"https://{value}"

    try:
        return urljoin(base_url or CLOUDFLARE_DASHBOARD_URL, value)
    except Exception:
        return ""


def should_open_externally(url: str) -> bool:
    scheme = urlparse(url or "").scheme.lower()
    return scheme in EXTERNAL_SCHEMES


def is_webview_error_url(url: str) -> bool:
    scheme = urlparse(url or "").scheme.lower()
    return scheme in WEBVIEW_ERROR_SCHEMES


def _iter_preferred_browser_paths():
    seen = set()

    def add(path):
        if path and path not in seen:
            seen.add(path)
            yield path

    if sys.platform == "win32":
        roots = [
            os.environ.get("LOCALAPPDATA"),
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
        ]
        relative_paths = [
            os.path.join("Google", "Chrome", "Application", "chrome.exe"),
            os.path.join("Mozilla Firefox", "firefox.exe"),
        ]
        for root in roots:
            if not root:
                continue
            for relative_path in relative_paths:
                yield from add(os.path.join(root, relative_path))

    for command in ("chrome", "chrome.exe", "google-chrome", "firefox", "firefox.exe"):
        yield from add(shutil.which(command))


def open_in_preferred_browser(url: str) -> bool:
    target_url = normalize_browser_url(url)
    if not target_url:
        return False

    if should_open_externally(target_url):
        return bool(webbrowser.open(target_url))

    for browser_path in _iter_preferred_browser_paths():
        if browser_path and os.path.exists(browser_path):
            try:
                subprocess.Popen([browser_path, target_url], close_fds=True)
                return True
            except OSError:
                continue

    return bool(webbrowser.open(target_url))


def _set_windows_titlebar_icon(title: str) -> None:
    if sys.platform != "win32":
        return

    import ctypes
    import time

    user32 = ctypes.windll.user32
    icon_path = utils.resource_path(APP_ICON)

    hwnd = 0
    for _ in range(40):
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            break
        time.sleep(0.1)

    if not hwnd or not os.path.exists(icon_path):
        return

    image_icon = 1
    lr_loadfromfile = 0x0010
    wm_seticon = 0x0080
    icon_small = 0
    icon_big = 1

    big_icon = user32.LoadImageW(None, icon_path, image_icon, 32, 32, lr_loadfromfile)
    small_icon = user32.LoadImageW(None, icon_path, image_icon, 16, 16, lr_loadfromfile)

    if big_icon:
        user32.SendMessageW(hwnd, wm_seticon, icon_big, big_icon)
    if small_icon:
        user32.SendMessageW(hwnd, wm_seticon, icon_small, small_icon)


def run_cloudflare_window(url: str) -> None:
    import webview
    from webview.menu import Menu, MenuAction, MenuSeparator

    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False

    storage_path = get_cloudflare_webview_storage_path()
    tabs_path = get_cloudflare_tabs_path()

    main_window = None
    default_tabs = [
        {"id": "cloudflare", "title": "Cloudflare", "url": url, "closable": False},
        {"id": "api", "title": "API Tokens", "url": CLOUDFLARE_NOVA_TOKEN_URL, "closable": False},
        {"id": "novaproxy", "title": "NovaProxy", "url": NOVAPROXY_INSTALL_URL, "closable": False},
        {"id": "atomicmail", "title": "AtomicMail", "url": ATOMICMAIL_URL, "closable": False},
    ]
    default_tab_urls = {tab["id"]: tab["url"] for tab in default_tabs}
    active_tab_id = "cloudflare"
    next_custom_tab_id = 1
    tabs_state = [tab.copy() for tab in default_tabs]
    browser_fallbacks_opened = set()

    def normalize_saved_tab(tab):
        if not isinstance(tab, dict):
            return None
        tab_id = str(tab.get("id") or "").strip()
        tab_url = str(tab.get("url") or "").strip()
        if not tab_id or not tab_url or is_webview_error_url(tab_url):
            return None
        title = " ".join(str(tab.get("title") or "New Tab").split()) or "New Tab"
        return {
            "id": tab_id,
            "title": title[:32],
            "url": tab_url,
            "closable": bool(tab.get("closable", tab_id.startswith("custom-"))),
        }

    def load_tabs_state() -> None:
        nonlocal active_tab_id, next_custom_tab_id, tabs_state
        try:
            with open(tabs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return

        saved_tabs = data.get("tabs", []) if isinstance(data, dict) else []
        if not isinstance(saved_tabs, list):
            return

        merged_tabs = []
        by_id = {}
        for tab in default_tabs:
            by_id[tab["id"]] = tab.copy()

        for raw_tab in saved_tabs:
            tab = normalize_saved_tab(raw_tab)
            if not tab:
                continue
            if tab["id"] in FIXED_HOME_TAB_IDS:
                continue
            if tab["id"] in by_id:
                by_id[tab["id"]]["url"] = tab["url"]
            elif tab["id"].startswith("custom-"):
                by_id[tab["id"]] = tab

        for tab in default_tabs:
            merged_tabs.append(by_id[tab["id"]])
        custom_tabs = [tab for tab_id, tab in by_id.items() if tab_id.startswith("custom-")]
        custom_tabs.sort(key=lambda tab: int(tab["id"].split("-", 1)[1]) if tab["id"].split("-", 1)[1].isdigit() else 0)
        merged_tabs.extend(custom_tabs)
        tabs_state = merged_tabs

        saved_active = str(data.get("active_tab_id") or "").strip() if isinstance(data, dict) else ""
        if saved_active and any(tab["id"] == saved_active for tab in tabs_state):
            active_tab_id = saved_active

        custom_numbers = [
            int(tab["id"].split("-", 1)[1])
            for tab in tabs_state
            if tab["id"].startswith("custom-") and tab["id"].split("-", 1)[1].isdigit()
        ]
        next_custom_tab_id = (max(custom_numbers) + 1) if custom_numbers else 1

    def save_tabs_state() -> None:
        saved_tabs = []
        for tab in tabs_state:
            saved_tab = tab.copy()
            if saved_tab["id"] in FIXED_HOME_TAB_IDS:
                saved_tab["url"] = default_tab_urls.get(saved_tab["id"], saved_tab.get("url", ""))
            elif is_webview_error_url(saved_tab.get("url", "")):
                saved_tab["url"] = (
                    last_requested_urls.get(saved_tab["id"])
                    or default_tab_urls.get(saved_tab["id"])
                    or ""
                )
            if not saved_tab.get("url"):
                continue
            saved_tabs.append(saved_tab)

        try:
            storage.atomic_write_json(
                tabs_path,
                {
                    "active_tab_id": active_tab_id,
                    "tabs": saved_tabs,
                },
                ensure_ascii=False,
            )
        except OSError:
            pass

    load_tabs_state()
    last_requested_urls = {
        tab["id"]: tab["url"]
        for tab in tabs_state
        if tab.get("url") and not is_webview_error_url(tab.get("url", ""))
    }

    def find_tab(tab_id: str):
        return next((tab for tab in tabs_state if tab["id"] == tab_id), None)

    def remember_requested_url(tab_id: str, target_url: str) -> str:
        normalized_url = normalize_browser_url(target_url)
        if normalized_url and not is_webview_error_url(normalized_url):
            last_requested_urls[tab_id] = normalized_url
            return normalized_url
        return ""

    def target_for_tab(tab_id: str) -> str:
        if tab_id in FIXED_HOME_TAB_IDS:
            return default_tab_urls.get(tab_id, "")
        tab = find_tab(tab_id)
        candidates = [
            last_requested_urls.get(tab_id, ""),
            tab.get("url", "") if tab else "",
            default_tab_urls.get(tab_id, ""),
        ]
        for candidate in candidates:
            normalized_url = normalize_browser_url(candidate)
            if normalized_url and not is_webview_error_url(normalized_url):
                return normalized_url
        return ""

    def target_for_active_tab() -> str:
        return target_for_tab(active_tab_id) or normalize_browser_url(url) or CLOUDFLARE_DASHBOARD_URL

    def tab_key_for_url(current_url: str) -> str:
        clean_url = (current_url or "").lower()
        if "dash.cloudflare.com/profile/api-tokens" in clean_url:
            return "api"
        if "dash.cloudflare.com" in clean_url:
            return "cloudflare"
        if "novaproxy.online" in clean_url:
            return "novaproxy"
        if "atomicmail.io" in clean_url:
            return "atomicmail"
        return "cloudflare"

    def remember_current_tab_url() -> None:
        if main_window is None:
            return
        tab = find_tab(active_tab_id)
        if not tab:
            return
        try:
            current_url = main_window.get_current_url()
        except Exception:
            return
        if current_url and not is_webview_error_url(current_url):
            target_url = normalize_browser_url(current_url)
            if not target_url:
                return
            if active_tab_id in FIXED_HOME_TAB_IDS:
                tab["url"] = default_tab_urls.get(active_tab_id, tab["url"])
                remember_requested_url(active_tab_id, tab["url"])
            else:
                tab["url"] = target_url
                remember_requested_url(active_tab_id, target_url)
            save_tabs_state()

    def select_tab(tab_key: str) -> str:
        nonlocal active_tab_id
        tab = find_tab(tab_key)
        if not tab:
            return ""
        remember_current_tab_url()
        active_tab_id = tab_key
        target_url = target_for_tab(tab_key)
        if target_url:
            remember_requested_url(tab_key, target_url)
        save_tabs_state()
        return target_url or tab["url"]

    def open_tab(tab_key: str) -> None:
        target_url = select_tab(tab_key)
        if target_url:
            schedule_nova_browser_fallback(target_url, tab_key)
            main_window.load_url(target_url)

    def open_browser_fallback_once(target_url: str) -> bool:
        normalized_url = normalize_browser_url(target_url)
        if not normalized_url:
            return False
        fallback_key = (active_tab_id, normalized_url)
        if fallback_key in browser_fallbacks_opened:
            return True
        browser_fallbacks_opened.add(fallback_key)
        return open_in_preferred_browser(normalized_url)

    def schedule_nova_browser_fallback(target_url: str, tab_id: str = None) -> None:
        normalized_url = normalize_browser_url(target_url)
        if not normalized_url or "novaproxy.online" not in normalized_url.lower():
            return
        expected_tab_id = tab_id or active_tab_id

        def check_after_wait() -> None:
            if active_tab_id != expected_tab_id or main_window is None:
                return
            try:
                current_url = main_window.get_current_url()
            except Exception:
                current_url = ""
            current_lower = (current_url or "").lower()
            if is_webview_error_url(current_url) or "novaproxy.online" not in current_lower:
                open_browser_fallback_once(normalized_url)

        timer = threading.Timer(5.0, check_after_wait)
        timer.daemon = True
        timer.start()

    class CloudflareTabsApi:
        def open_tab(self, tab_id: str) -> str:
            return select_tab(tab_id)

        def open_new_tab(self, url: str, title: str = None) -> str:
            nonlocal active_tab_id, next_custom_tab_id
            target_url = normalize_browser_url(url)
            if not target_url:
                return ""
            if should_open_externally(target_url):
                open_in_preferred_browser(target_url)
                return ""
            remember_current_tab_url()
            clean_title = " ".join((title or "New Tab").split()) or "New Tab"
            tab_id = f"custom-{next_custom_tab_id}"
            next_custom_tab_id += 1
            tabs_state.append({
                "id": tab_id,
                "title": clean_title[:32],
                "url": target_url,
                "closable": True,
            })
            active_tab_id = tab_id
            remember_requested_url(tab_id, target_url)
            save_tabs_state()
            schedule_nova_browser_fallback(target_url, tab_id)
            return target_url

        def normalize_url(self, url: str, base_url: str = None) -> str:
            return normalize_browser_url(url, base_url or CLOUDFLARE_DASHBOARD_URL)

        def open_external(self, url: str) -> bool:
            target_url = normalize_browser_url(url)
            if not target_url:
                return False
            return open_in_preferred_browser(target_url)

        def open_browser_fallback(self, url: str, reason: str = None) -> bool:
            return open_browser_fallback_once(url)

        def remember_url(self, url: str, title: str = None) -> bool:
            tab = find_tab(active_tab_id)
            target_url = normalize_browser_url(url)
            if not tab or not target_url or is_webview_error_url(target_url):
                return False
            if active_tab_id in FIXED_HOME_TAB_IDS:
                tab["url"] = default_tab_urls.get(active_tab_id, tab["url"])
                remember_requested_url(active_tab_id, tab["url"])
                save_tabs_state()
                return False
            tab["url"] = target_url
            remember_requested_url(active_tab_id, target_url)
            if title:
                tab["title"] = " ".join(str(title).split())[:32] or tab["title"]
            save_tabs_state()
            return True

        def close_tab(self, tab_id: str) -> str:
            nonlocal active_tab_id, tabs_state
            tab = find_tab(tab_id)
            if not tab or not tab.get("closable"):
                return ""

            was_active = tab_id == active_tab_id
            tabs_state = [item for item in tabs_state if item["id"] != tab_id]
            last_requested_urls.pop(tab_id, None)
            if was_active:
                active_tab_id = tabs_state[0]["id"] if tabs_state else "cloudflare"
                save_tabs_state()
                return target_for_tab(active_tab_id)

            save_tabs_state()
            try:
                inject_tab_bar(main_window)
            except Exception:
                pass
            return "closed"

    def inject_tab_bar(window) -> None:
        remember_current_tab_url()
        tabs = json.dumps(tabs_state)
        try:
            current_url = window.get_current_url()
        except Exception:
            current_url = ""
        actual_active_tab = active_tab_id if find_tab(active_tab_id) else tab_key_for_url(current_url)
        active_tab = json.dumps(actual_active_tab)
        active_target_url = target_for_tab(actual_active_tab) or normalize_browser_url(current_url) or CLOUDFLARE_DASHBOARD_URL
        target_url = json.dumps(active_target_url)
        current_is_error = json.dumps(is_webview_error_url(current_url))
        needs_launch_guard = json.dumps(
            actual_active_tab == "novaproxy"
            or is_webview_error_url(current_url)
            or "novaproxy.online" in active_target_url.lower()
        )
        script = build_tab_bar_script(
            tabs=tabs,
            active_tab=active_tab,
            target_url=target_url,
            current_is_error=current_is_error,
            needs_launch_guard=needs_launch_guard,
        )
        try:
            window.evaluate_js(script)
        except Exception:
            pass

    def reload_current_page() -> None:
        if main_window is None:
            return
        try:
            current = main_window.get_current_url()
        except Exception:
            current = ""
        if is_webview_error_url(current):
            target_url = target_for_active_tab()
            if target_url:
                main_window.load_url(target_url)
            return
        try:
            main_window.evaluate_js("window.location.reload()")
        except Exception:
            if current:
                try:
                    main_window.load_url(current)
                except Exception:
                    pass

    def open_current_in_browser() -> None:
        if main_window is None:
            return
        try:
            current = main_window.get_current_url()
        except Exception:
            current = ""
        target_url = target_for_active_tab() if is_webview_error_url(current) else normalize_browser_url(current or initial_url)
        if target_url:
            open_in_preferred_browser(target_url)

    cloudflare_menu = [
        Menu(
            "Cloudflare",
            [
                MenuAction("Cloudflare Dashboard", lambda: open_tab("cloudflare")),
                MenuAction("API Tokens", lambda: open_tab("api")),
                MenuAction("NovaProxy", lambda: open_tab("novaproxy")),
                MenuAction("AtomicMail", lambda: open_tab("atomicmail")),
                MenuSeparator(),
                MenuAction("Reload Current Page", reload_current_page),
                MenuAction("Open Current URL in Browser", open_current_in_browser),
                MenuSeparator(),
                MenuAction("Open API Tokens", lambda: open_tab("api")),
            ],
        )
    ]

    initial_tab = find_tab(active_tab_id) or tabs_state[0]
    initial_url = target_for_tab(active_tab_id) or initial_tab["url"]
    remember_requested_url(active_tab_id, initial_url)

    def persist_tabs_on_close(*_args) -> None:
        remember_current_tab_url()
        save_tabs_state()

    main_window = webview.create_window(
        WINDOW_TITLE,
        initial_url,
        js_api=CloudflareTabsApi(),
        width=1120,
        height=760,
        min_size=(820, 560),
        resizable=True,
        text_select=True,
        menu=cloudflare_menu,
    )
    schedule_nova_browser_fallback(initial_url, active_tab_id)
    main_window.events.loaded += lambda: inject_tab_bar(main_window)
    try:
        main_window.events.closing += persist_tabs_on_close
    except Exception:
        pass
    icon_path = utils.resource_path(APP_ICON)
    webview.start(
        _set_windows_titlebar_icon,
        args=(WINDOW_TITLE,),
        gui="edgechromium",
        debug=False,
        icon=icon_path,
        private_mode=False,
        storage_path=storage_path,
    )


def _launch_webview_process(url: str) -> None:
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--cloudflare-webview", url]
    else:
        main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        cmd = [sys.executable, main_path, "--cloudflare-webview", url]

    subprocess.Popen(cmd, close_fds=True)


def _show_fallback_window(parent, url: str, reason: str) -> None:
    colors = config.get_colors(config.load_settings().get("theme", "dark"))
    win = tk.Toplevel(parent) if parent is not None else tk.Tk()
    win.title(WINDOW_TITLE)
    win.geometry("520x220")
    win.minsize(420, 210)
    win.resizable(True, True)
    win.configure(bg=colors["MAIN_BG"])
    try:
        win.iconbitmap(utils.resource_path(APP_ICON))
    except Exception:
        pass
    if parent is not None:
        win.transient(parent)

    label = tk.Label(
        win,
        text=(
            "Cloudflare needs the in-app WebView package.\n\n"
            "Install requirements again, then this page will open inside NetFix.\n"
            f"{reason}"
        ),
        bg=colors["MAIN_BG"],
        fg=colors["TEXT"],
        justify="center",
        wraplength=460,
        font=(colors["FONT"], 10),
    )
    label.pack(padx=24, pady=(24, 14), fill="x")

    btn_frame = tk.Frame(win, bg=colors["MAIN_BG"])
    btn_frame.pack(pady=(0, 20))

    tk.Button(
        btn_frame,
        text="Open in Browser",
        command=lambda: open_in_preferred_browser(url),
        width=18,
        bg=colors["PRIMARY"],
        fg=colors["ON_PRIMARY"],
        activebackground=colors["PRIMARY_HOVER"],
        activeforeground=colors["ON_PRIMARY"],
        relief="flat",
    ).pack(side="left", padx=6)
    tk.Button(
        btn_frame,
        text="Close",
        command=win.destroy,
        width=12,
        bg=colors["BUTTON_BG"],
        fg=colors["TEXT"],
        activebackground=colors["HOVER_BG"],
        activeforeground=colors["TEXT"],
        relief="flat",
    ).pack(side="left", padx=6)


def open_cloudflare(parent=None, config_path: str = None) -> None:
    if isinstance(parent, str) and config_path is None:
        config_path = parent
        parent = None

    url = _cloudflare_url(config_path)

    try:
        import webview  # noqa: F401
    except ImportError:
        _show_fallback_window(parent, url, "Missing package: pywebview")
        return

    try:
        _launch_webview_process(url)
    except Exception as exc:
        messagebox.showerror(
            WINDOW_TITLE,
            f"Could not open the in-app Cloudflare window.\n\n{exc}",
            parent=parent,
        )


def save_cloudflare_token(token: str, config_path: str = None) -> None:
    if config_path is None:
        config_path = get_cloudflare_config_path()
    data = {"api_token": token.strip()}
    storage.atomic_write_json(config_path, data, ensure_ascii=False)
