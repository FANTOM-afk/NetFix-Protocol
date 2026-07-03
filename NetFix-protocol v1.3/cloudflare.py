import os
import json
import subprocess
import sys
import webbrowser
import tkinter as tk
import tkinter.messagebox as messagebox
import utils

CLOUDFLARE_DASHBOARD_URL = "https://dash.cloudflare.com/"
CLOUDFLARE_LOGIN_URL = "https://dash.cloudflare.com/login"
CLOUDFLARE_API_TOKENS_URL = "https://dash.cloudflare.com/profile/api-tokens"
CLOUDFLARE_NOVA_TOKEN_URL = "https://dash.cloudflare.com/profile/api-tokens?permissionGroupKeys=%5B%7B%22key%22%3A%22workers_scripts%22%2C%22type%22%3A%22edit%22%7D%2C%7B%22key%22%3A%22workers_kv_storage%22%2C%22type%22%3A%22edit%22%7D%2C%7B%22key%22%3A%22d1%22%2C%22type%22%3A%22edit%22%7D%2C%7B%22key%22%3A%22account_settings%22%2C%22type%22%3A%22read%22%7D%5D&accountId=*&zoneId=all&name=Nova%20Installer"
NOVAPROXY_INSTALL_URL = "https://novaproxy.online/install#"
ATOMICMAIL_URL = "https://atomicmail.io/"
WINDOW_TITLE = "Cloudflare Account - NetFix Protocol"
APP_ICON = "logo.ico"


def _atomic_write_json(path: str, data, indent: int = 4) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    os.replace(tmp_path, path)


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
    active_tab_id = "cloudflare"
    next_custom_tab_id = 1
    tabs_state = [tab.copy() for tab in default_tabs]

    def normalize_saved_tab(tab):
        if not isinstance(tab, dict):
            return None
        tab_id = str(tab.get("id") or "").strip()
        tab_url = str(tab.get("url") or "").strip()
        if not tab_id or not tab_url:
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
            if tab["id"] == "api":
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
            if saved_tab["id"] == "api":
                saved_tab["url"] = CLOUDFLARE_NOVA_TOKEN_URL
            saved_tabs.append(saved_tab)

        try:
            _atomic_write_json(tabs_path, {
                "active_tab_id": active_tab_id,
                "tabs": saved_tabs,
            })
        except OSError:
            pass

    load_tabs_state()

    def find_tab(tab_id: str):
        return next((tab for tab in tabs_state if tab["id"] == tab_id), None)

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
        if current_url:
            if active_tab_id == "api":
                tab["url"] = CLOUDFLARE_NOVA_TOKEN_URL
            else:
                tab["url"] = current_url
            save_tabs_state()

    def select_tab(tab_key: str) -> str:
        nonlocal active_tab_id
        tab = find_tab(tab_key)
        if not tab:
            return ""
        remember_current_tab_url()
        active_tab_id = tab_key
        save_tabs_state()
        return tab["url"]

    def open_tab(tab_key: str) -> None:
        target_url = select_tab(tab_key)
        if target_url:
            main_window.load_url(target_url)

    class CloudflareTabsApi:
        def open_tab(self, tab_id: str) -> str:
            return select_tab(tab_id)

        def open_new_tab(self, url: str, title: str = None) -> str:
            nonlocal active_tab_id, next_custom_tab_id
            if not url:
                return ""
            remember_current_tab_url()
            clean_title = " ".join((title or "New Tab").split()) or "New Tab"
            tab_id = f"custom-{next_custom_tab_id}"
            next_custom_tab_id += 1
            tabs_state.append({
                "id": tab_id,
                "title": clean_title[:32],
                "url": url,
                "closable": True,
            })
            active_tab_id = tab_id
            save_tabs_state()
            return url

        def close_tab(self, tab_id: str) -> str:
            nonlocal active_tab_id, tabs_state
            tab = find_tab(tab_id)
            if not tab or not tab.get("closable"):
                return ""

            was_active = tab_id == active_tab_id
            tabs_state = [item for item in tabs_state if item["id"] != tab_id]
            if was_active:
                active_tab_id = tabs_state[0]["id"] if tabs_state else "cloudflare"
                save_tabs_state()
                next_tab = find_tab(active_tab_id)
                return next_tab["url"] if next_tab else ""

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
        active_tab = json.dumps(active_tab_id if find_tab(active_tab_id) else tab_key_for_url(current_url))
        script = """
            (function () {
                if (document.getElementById('netfix-cloudflare-tabs')) {
                    return;
                }

                var tabs = __TABS__;
                var activeTab = __ACTIVE_TAB__;

                var bar = document.createElement('div');
                bar.id = 'netfix-cloudflare-tabs';
                bar.style.position = 'fixed';
                bar.style.top = '10px';
                bar.style.left = '50%';
                bar.style.transform = 'translateX(-50%)';
                bar.style.zIndex = '2147483647';
                bar.style.display = 'flex';
                bar.style.gap = '4px';
                bar.style.padding = '4px';
                bar.style.maxWidth = 'calc(100vw - 36px)';
                bar.style.overflowX = 'auto';
                bar.style.whiteSpace = 'nowrap';
                bar.style.border = '1px solid rgba(0, 229, 255, 0.55)';
                bar.style.borderRadius = '8px';
                bar.style.background = '#111827';
                bar.style.boxShadow = '0 8px 22px rgba(0,0,0,0.28)';

                function normalizeNavigationUrl(value) {
                    value = (value || '').trim();
                    if (!value || value.indexOf('javascript:') === 0 || value.indexOf('#') === 0) {
                        return '';
                    }
                    if (value.indexOf('//') === 0) {
                        return 'https:' + value;
                    }
                    if (!/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(value) && value.indexOf('.') !== -1 && value.indexOf(' ') === -1) {
                        return 'https://' + value;
                    }
                    try {
                        return new URL(value, window.location.href).href;
                    } catch (error) {
                        return '';
                    }
                }

                function go(url) {
                    var next = normalizeNavigationUrl(url);
                    if (next) {
                        window.location.href = next;
                    }
                }

                function openInNewNetfixTab(url, title) {
                    var next = normalizeNavigationUrl(url);
                    if (!next) {
                        return;
                    }
                    if (window.pywebview && window.pywebview.api && window.pywebview.api.open_new_tab) {
                        window.pywebview.api.open_new_tab(next, title || 'New Tab').then(function (targetUrl) {
                            if (targetUrl) {
                                window.location.href = targetUrl;
                            }
                        }).catch(function () {
                            window.location.href = next;
                        });
                    } else {
                        window.location.href = next;
                    }
                }

                function openExistingNetfixTab(tab) {
                    if (window.pywebview && window.pywebview.api && window.pywebview.api.open_tab) {
                        window.pywebview.api.open_tab(tab.id).then(function (targetUrl) {
                            if (targetUrl) {
                                window.location.href = targetUrl;
                            }
                        }).catch(function () {
                            go(tab.url);
                        });
                    } else {
                        go(tab.url);
                    }
                }

                function closeNetfixTab(tab, wrapper) {
                    if (window.pywebview && window.pywebview.api && window.pywebview.api.close_tab) {
                        window.pywebview.api.close_tab(tab.id).then(function (targetUrl) {
                            if (targetUrl && targetUrl !== 'closed') {
                                window.location.href = targetUrl;
                            } else if (targetUrl === 'closed' && wrapper) {
                                wrapper.remove();
                            }
                        }).catch(function () {});
                    }
                }

                function makeAddressBar() {
                    var form = document.createElement('form');
                    form.style.display = 'flex';
                    form.style.gap = '4px';
                    form.style.alignItems = 'center';
                    form.style.marginLeft = '6px';
                    form.onsubmit = function (event) {
                        event.preventDefault();
                        go(input.value);
                    };

                    var input = document.createElement('input');
                    input.value = window.location.href;
                    input.title = 'Current URL';
                    input.style.width = 'min(430px, 42vw)';
                    input.style.height = '32px';
                    input.style.border = '1px solid rgba(148,163,184,.45)';
                    input.style.borderRadius = '5px';
                    input.style.background = '#0f172a';
                    input.style.color = '#e5e7eb';
                    input.style.padding = '0 10px';
                    input.style.font = '500 12px Segoe UI, Arial, sans-serif';
                    input.onclick = function () {
                        input.select();
                    };

                    var button = document.createElement('button');
                    button.textContent = 'Go';
                    button.title = 'Open URL';
                    button.style.height = '32px';
                    button.style.padding = '0 10px';
                    button.style.border = '0';
                    button.style.borderRadius = '5px';
                    button.style.background = '#0f766e';
                    button.style.color = '#e5e7eb';
                    button.style.font = '700 12px Segoe UI, Arial, sans-serif';
                    button.style.cursor = 'pointer';

                    form.appendChild(input);
                    form.appendChild(button);
                    return form;
                }

                function makeTab(tab) {
                    var wrapper = document.createElement('div');
                    wrapper.style.display = 'flex';
                    wrapper.style.alignItems = 'center';
                    wrapper.style.height = '32px';
                    wrapper.style.flex = '0 0 auto';

                    var btn = document.createElement('button');
                    btn.textContent = tab.title;
                    btn.title = tab.url;
                    btn.style.height = '32px';
                    btn.style.padding = tab.closable ? '0 10px 0 12px' : '0 14px';
                    btn.style.border = '0';
                    btn.style.borderRadius = tab.closable ? '5px 0 0 5px' : '5px';
                    btn.style.background = tab.id === activeTab ? '#075985' : '#1f2937';
                    btn.style.color = '#e5e7eb';
                    btn.style.font = '600 12px Segoe UI, Arial, sans-serif';
                    btn.style.cursor = 'pointer';
                    btn.onmouseenter = function () { btn.style.background = '#374151'; };
                    btn.onmouseleave = function () { btn.style.background = tab.id === activeTab ? '#075985' : '#1f2937'; };
                    btn.onclick = function () { openExistingNetfixTab(tab); };
                    wrapper.appendChild(btn);

                    if (tab.closable) {
                        var closeTab = document.createElement('button');
                        closeTab.textContent = 'x';
                        closeTab.title = 'Close tab';
                        closeTab.style.height = '32px';
                        closeTab.style.width = '26px';
                        closeTab.style.padding = '0';
                        closeTab.style.border = '0';
                        closeTab.style.borderLeft = '1px solid rgba(255,255,255,0.08)';
                        closeTab.style.borderRadius = '0 5px 5px 0';
                        closeTab.style.background = tab.id === activeTab ? '#075985' : '#1f2937';
                        closeTab.style.color = '#ff8fa3';
                        closeTab.style.font = '700 12px Segoe UI, Arial, sans-serif';
                        closeTab.style.cursor = 'pointer';
                        closeTab.onmouseenter = function () { closeTab.style.background = '#7f1d1d'; };
                        closeTab.onmouseleave = function () { closeTab.style.background = tab.id === activeTab ? '#075985' : '#1f2937'; };
                        closeTab.onclick = function (event) {
                            event.preventDefault();
                            event.stopPropagation();
                            closeNetfixTab(tab, wrapper);
                        };
                        wrapper.appendChild(closeTab);
                    }

                    return wrapper;
                }

                tabs.forEach(function (tab) {
                    bar.appendChild(makeTab(tab));
                });
                bar.appendChild(makeAddressBar());

                var close = document.createElement('button');
                close.textContent = 'x';
                close.title = 'Hide tabs';
                close.style.height = '32px';
                close.style.width = '32px';
                close.style.padding = '0';
                close.style.border = '0';
                close.style.borderRadius = '5px';
                close.style.background = '#1f2937';
                close.style.color = '#ff6b81';
                close.style.font = '600 12px Segoe UI, Arial, sans-serif';
                close.style.cursor = 'pointer';
                close.onclick = function () {
                    bar.style.display = 'none';
                    toggle.style.display = 'block';
                };
                bar.appendChild(close);

                var toggle = document.createElement('button');
                toggle.textContent = 'Tabs';
                toggle.title = 'Show NetFix tabs';
                toggle.style.position = 'fixed';
                toggle.style.top = '10px';
                toggle.style.right = '12px';
                toggle.style.zIndex = '2147483647';
                toggle.style.display = 'none';
                toggle.style.height = '32px';
                toggle.style.padding = '0 12px';
                toggle.style.border = '1px solid rgba(0, 229, 255, 0.55)';
                toggle.style.borderRadius = '6px';
                toggle.style.background = '#111827';
                toggle.style.color = '#e5e7eb';
                toggle.style.font = '600 12px Segoe UI, Arial, sans-serif';
                toggle.style.cursor = 'pointer';
                toggle.onclick = function () {
                    bar.style.display = 'flex';
                    toggle.style.display = 'none';
                };

                function installLinkHandlers() {
                    window.open = function (url, target) {
                        if (url) {
                            openInNewNetfixTab(url, target || 'New Tab');
                        }
                        return null;
                    };

                    document.addEventListener('click', function (event) {
                        var link = event.target && event.target.closest ? event.target.closest('a[href]') : null;
                        if (!link || link.closest('#netfix-cloudflare-tabs')) {
                            return;
                        }
                        if (link.target === '_blank' || event.ctrlKey || event.metaKey || event.shiftKey) {
                            event.preventDefault();
                            event.stopPropagation();
                            openInNewNetfixTab(link.getAttribute('href'), link.textContent || link.title || 'New Tab');
                        }
                    }, true);

                    document.addEventListener('auxclick', function (event) {
                        if (event.button !== 1) {
                            return;
                        }
                        var link = event.target && event.target.closest ? event.target.closest('a[href]') : null;
                        if (!link || link.closest('#netfix-cloudflare-tabs')) {
                            return;
                        }
                        event.preventDefault();
                        event.stopPropagation();
                        openInNewNetfixTab(link.getAttribute('href'), link.textContent || link.title || 'New Tab');
                    }, true);
                }

                document.documentElement.appendChild(bar);
                document.documentElement.appendChild(toggle);
                installLinkHandlers();
            })();
        """.replace("__TABS__", tabs).replace("__ACTIVE_TAB__", active_tab)
        try:
            window.evaluate_js(script)
        except Exception:
            pass

    cloudflare_menu = [
        Menu(
            "Cloudflare",
            [
                MenuAction("Cloudflare Dashboard", lambda: open_tab("cloudflare")),
                MenuAction("API Tokens", lambda: open_tab("api")),
                MenuAction("NovaProxy Install", lambda: open_tab("novaproxy")),
                MenuAction("AtomicMail", lambda: open_tab("atomicmail")),
                MenuSeparator(),
                MenuAction("Open API Tokens", lambda: open_tab("api")),
            ],
        )
    ]

    initial_tab = find_tab(active_tab_id) or tabs_state[0]
    initial_url = initial_tab["url"]

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
    win = tk.Toplevel(parent) if parent is not None else tk.Tk()
    win.title(WINDOW_TITLE)
    win.geometry("520x220")
    win.resizable(False, False)
    win.configure(bg="#111827")
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
        bg="#111827",
        fg="#E5E7EB",
        justify="center",
        wraplength=460,
        font=("Consolas", 10),
    )
    label.pack(padx=24, pady=(24, 14), fill="x")

    btn_frame = tk.Frame(win, bg="#111827")
    btn_frame.pack(pady=(0, 20))

    tk.Button(
        btn_frame,
        text="Open in Browser",
        command=lambda: webbrowser.open(url),
        width=18,
    ).pack(side="left", padx=6)
    tk.Button(
        btn_frame,
        text="Close",
        command=win.destroy,
        width=12,
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
    _atomic_write_json(config_path, data)
