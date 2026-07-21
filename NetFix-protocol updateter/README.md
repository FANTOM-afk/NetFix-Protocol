# 🔧 NetFix Protocol 1.3.1

> **Automated Wi-Fi / LAN Connection Monitor, Repair Tool & Local Proxy Router**  
> **مانیتورینگ، تعمیر خودکار اتصال، مدیریت پروکسی محلی و ابزارهای Cloudflare / V2Ray برای ویندوز**

![Python](https://img.shields.io/badge/Python-3.8%2B-00FF41?style=flat&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-00BFFF?style=flat&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-FF003C?style=flat)
![Version](https://img.shields.io/badge/Version-1.3.1-00E5FF?style=flat)

---

## 📋 Overview | نمای کلی

NetFix Protocol monitors Wi-Fi/LAN connectivity by pinging domestic and international hosts, shows a live status/chart, and can repair Wi-Fi outages automatically. Version **1.3.1** keeps the full v1.3 feature set and adds UI polish, cleaner module boundaries, Cloudflare/WebView recovery fixes, safer persistence helpers, and updated build metadata.

NetFix Protocol اتصال Wi-Fi یا LAN را با پینگ گرفتن از هاست‌های داخلی و خارجی بررسی می‌کند، وضعیت را زنده نمایش می‌دهد و در صورت قطعی کامل می‌تواند اتصال Wi-Fi را تعمیر کند. در نسخه **1.3.1** امکانات V2Ray Router، پروکسی محلی پس‌زمینه، مرورگر داخلی Cloudflare، Tray Icon ویندوز، ذخیره‌سازی امن‌تر فایل‌ها و خروجی EXE آماده اضافه شده است.

### ✨ Features | ویژگی‌ها

| Feature | Description |
|---------|-------------|
| 🧠 **Auto-Reconnect** | Detects internet loss and reconnects Wi-Fi automatically |
| 📊 **Live Chart** | Real-time domestic vs international ping chart |
| 🌐 **Wi-Fi / LAN Monitoring** | Supports both Wi-Fi and LAN monitoring modes |
| 🚦 **Status Indicator** | Blinking LIVE indicator, status text, and ping display |
| 🧩 **V2Ray Router** | Manage V2Ray profiles, subscriptions, groups, ping tests, and start/stop routing |
| 🔁 **BG Proxy** | Keeps local SOCKS5/HTTP proxy available while system VPN stays OFF |
| ☁️ **Cloudflare WebView** | In-app Cloudflare browser with persistent login, fixed workflow tabs, and recovery guidance |
| 🧷 **System Tray** | Tray icon and tooltip for background/running state |
| 🚀 **Auto-Start** | Optional Windows startup shortcut |
| 🎨 **Dark/Light Theme** | Switch appearance from the GUI |
| 🛡️ **Hardening** | Safer zip extraction, shared atomic writes, safer subscription fetching, and repaired settings/state handling |
| ?? **Modular Runtime** | `main.py` is the only entry point; shared helpers keep storage, Windows commands, and WebView script logic separated |

---

## 🚀 Installation | نصب

### Option 1 — Ready EXE | اجرای نسخه آماده

For normal use, run the packaged executable:

```text
NetFix_PROTOCOL_v1.3.1_Release\NetFix_PROTOCOL_1.3.1.exe
```

Notes:

- Run on **Windows**.
- The app requests **Administrator** permission when needed.
- Settings and runtime data are stored in:

```text
%APPDATA%\NetFixProtocol
```

### Option 2 — Run From Source | اجرا از سورس

```bash
# Navigate to the project directory
cd NetFixProtocol

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Build Executable | ساخت فایل اجرایی

The project includes a PyInstaller spec for 1.3.1:

```bash
python -m PyInstaller --clean --noconfirm --distpath "C:\Users\User\Desktop\NetFixProtocol\NetFix_PROTOCOL_v1.3.1_Release" --workpath "build\NetFix_PROTOCOL_1.3.1" NetFix_PROTOCOL_1.3.1.spec
```

Output:

```text
NetFix_PROTOCOL_v1.3.1_Release\NetFix_PROTOCOL_1.3.1.exe
```

---

## 🏗️ Project Structure | ساختار پروژه

```text
NetFixProtocol/
|
`-- NetFix-protocol updateter/
    |
    |-- README.md                 # Main documentation, usage guide, and 1.3.1 update log
    |-- LICENSE                   # Main license file
    |-- lic.txt                   # License copy kept with the updater package
    |-- requirements.txt          # Shared Python dependency list
    |
    |-- NetFix-protocol v1.2/     # Previous source package kept for comparison/reference
    |
    `-- NetFix_PROTOCOL_v1.3.1/  # Current 1.3.1 source folder prepared for GitHub
        |
        |-- .gitignore           # Build/cache ignores and packaged spec allow-list
        |-- main.py              # Only runnable entry point, admin elevation, single-instance guard
        |-- app.py               # Main GUI, monitoring orchestration, tray + router wiring
        |-- config.py            # Default settings, AppData paths, theme colors, safe settings save
        |-- utils.py             # resource_path, admin check, startup shortcut helpers
        |-- storage.py           # Shared atomic JSON/text write helpers
        |-- windows_cmd.py       # Shared hidden Windows subprocess wrappers for netsh/ping
        |-- wifi.py              # Ping, Wi-Fi scan/connect/reconnect helpers
        |-- chart_widget.py      # Live ping chart widget
        |-- ui_theme.py          # Theme palettes, shared fonts, and reusable UI styling helpers
        |-- settings_windows.py  # Network settings, appearance settings, About dialog
        |-- tray_icon.py         # Windows tray icon integration
        |-- cloudflare.py        # In-app Cloudflare WebView runner and window lifecycle
        |-- cloudflare_tab_script.py
        |                         # Injected WebView tab bar, wait guard, and bilingual recovery tip
        |
        |-- v2ray_manager.py     # Public facade for V2Ray modules
        |-- v2ray_window.py      # V2Ray Router GUI, group actions, profile table, shortcuts
        |-- v2ray_core.py        # V2Ray core install/start/stop/runtime config
        |-- v2ray_config.py      # vmess/vless/trojan/outbound parsing
        |-- v2ray_profiles.py    # Profile/group/subscription store with atomic persistence
        |-- v2ray_paths.py       # V2Ray AppData paths and runtime state files
        |-- v2ray_ping.py        # TCP ping for V2Ray profiles
        |-- v2ray_proxy_windows.py
        |                         # Windows system proxy snapshot/enable/restore helpers
        |-- v2ray_subscription.py
        |                         # Subscription fetch, config extraction, and URL cleanup
        |
        |-- requirements.txt     # Python dependencies for source runs/builds
        |-- NetFix_PROTOCOL_1.3.1.spec
        |                         # PyInstaller build config for the 1.3.1 EXE
        |-- logo.ico             # Application icon
        `-- settings.json        # Default bundled settings template
```

### Module Responsibilities | وظایف ماژول‌ها

| Module | Responsibility |
|--------|---------------|
| `main.py` | Handles admin elevation, Cloudflare child-process mode, single-instance mutex, global error logging |
| `app.py` | Builds the main UI, starts/stops monitoring, coordinates BG Proxy, tray, settings, Cloudflare, and V2Ray Router |
| `wifi.py` | Contains Wi-Fi/LAN network helpers without UI dependency |
| `windows_cmd.py` | Centralizes hidden Windows command execution for `netsh` and `ping` |
| `storage.py` | Provides shared atomic JSON/text writes for settings and runtime state |
| `chart_widget.py` | Renders the live domestic/international ping chart |
| `settings_windows.py` | Provides reusable settings/about windows |
| `cloudflare.py` | Runs Cloudflare inside a persistent pywebview window with workflow tabs |
| `cloudflare_tab_script.py` | Keeps injected Cloudflare tab UI, wait guard, and bilingual recovery tip separate from Python runtime code |
| `v2ray_window.py` | GUI for profiles, groups, subscriptions, ping tests, BG Proxy, and start/stop actions |
| `v2ray_core.py` | Installs and launches V2Ray safely, writes runtime config, manages local ports |
| `v2ray_proxy_windows.py` | Enables/restores Windows system proxy with snapshot protection |
| `v2ray_profiles.py` | Stores profiles/groups/subscription URLs and latency results |

---

## 🎮 Usage | نحوه استفاده

### Main App | صفحه اصلی

1. Open `NetFix_PROTOCOL_1.3.1.exe` or run `python main.py`.
2. Accept the Windows UAC prompt if it appears.
3. Choose the connection type:
   - **Wi-Fi** for wireless monitoring and reconnect repair.
   - **LAN** for cable/network monitoring.
4. For Wi-Fi, select or type the target SSID.
5. Click **Start Monitor** to start monitoring.
6. Watch the live status, ping display, and chart.
7. Click **Stop** to stop monitoring.

### BG Proxy | پروکسی پس‌زمینه

The main screen includes:

```text
BG Proxy (SOCKS5 :10809 / HTTP :10810)
```

Behavior:

- When **BG Proxy is ON**, NetFix keeps local proxy ports open.
- SOCKS5 listens on `127.0.0.1:10809`.
- HTTP listens on `127.0.0.1:10810`.
- Windows/System VPN proxy stays **OFF**.
- On a fresh install, BG Proxy is enabled by default while system VPN remains off.
- If the user disables BG Proxy, NetFix preserves that saved preference on the next launch.
- The BG Proxy checkbox on the main screen and the one inside V2Ray Router stay synced.

Use these local ports in browsers/tools that support manual proxy settings.

### V2Ray Router | روتر V2Ray

Open from:

```text
Menu -> V2Ray Router
```

Common workflow:

1. Paste a `vmess://`, `vless://`, `trojan://`, outbound JSON, or full V2Ray JSON config.
2. Click **SAVE**, or paste one/multiple configs and let the router auto-save/import them.
3. Use groups to organize profiles.
4. Use **ADD SUB** to import a subscription URL, or **REFRESH GROUP** to reload the saved group subscription.
5. Double-click any config in the list to ping only that config.
6. Use `Ctrl + A` to select all configs in the current group.
7. Use `Ctrl + R` to ping selected configs.
8. Click **START** to run the selected profile.
9. If BG Proxy is ON, START runs in proxy-only mode.
10. If BG Proxy is OFF, START enables Windows system proxy mode.
11. Click **STOP** to stop V2Ray and restore Windows proxy. If BG Proxy is ON, background proxy mode can restart automatically.

Notes:

- The old **PING SELECTED** action-panel button was removed.
- Double-click ping is now the fastest per-config test.
- `SELECT GROUP` selects the current group for bulk actions.
- V2Ray core is installed from the official release zip when the user confirms installation.
- Local port values are normalized before start so invalid saved state cannot break routing.

### Cloudflare Account | حساب Cloudflare

Open from:

```text
Menu -> Cloudflare Account
```

The in-app browser includes fixed workflow tabs:

| Tab | Purpose |
|-----|---------|
| `Cloudflare` | Opens Cloudflare dashboard/login |
| `API Tokens` | Opens Nova token deep link |
| `NovaProxy` | Opens NovaProxy installer page (`https://novaproxy.online/install`) |
| `AtomicMail` | Opens AtomicMail |

Behavior:

- Login/session is persisted in `%APPDATA%\NetFixProtocol\CloudflareWebView`.
- Links stay inside the in-app WebView where possible.
- If pywebview is missing, a fallback window explains the missing dependency.
- If Chrome/WebView shows a loading or browser error panel, NetFix displays a Farsi/English recovery tip and a Retry / Refresh action.
- Tab UI and recovery guidance are injected from `cloudflare_tab_script.py` to keep the Python WebView runner smaller.
- JavaScript URL polling was removed to avoid pywebview callback errors during refresh/navigation.
- The app does not create, read, copy, or transmit Cloudflare token secrets automatically.

### Create Config with Cloudflare / Nova

This section explains how to create a config and import the final sublink into NetFix. A tutorial video will be uploaded soon.

Special thanks to [IRNova/Nova-Proxy](https://github.com/IRNova/Nova-Proxy) for their work and effort toward free internet access.

1. Open **Cloudflare Account** from the Burger Menu:

```text
Menu -> Cloudflare Account
```

2. In the in-app Cloudflare browser, open the **AtomicMail** tab and create a new email address or open your existing AtomicMail inbox.

3. Log in to Cloudflare or create a new Cloudflare account using that AtomicMail address.

4. Verify the Cloudflare email from inside AtomicMail.

5. After logging in to Cloudflare, open the following tab:

```text
API Tokens
```

6. The API page already has the required permissions prepared. Do not manually change the permissions; scroll to the bottom of the page and click **Create**.

7. After the API Token is created, copy the token.

8. Open the following tab:

```text
NovaProxy
```

9. Paste the API Token into the NovaProxy installer page and wait until the installation completes. Do not close the page while installation is running.

10. If Chrome/WebView shows an error, wait 2-3 minutes and use **Retry / Refresh**. If the panel still does not open, fully close the app or the in-app browser, then open it again. Minimizing is not enough; close it completely.

11. After reopening, go back to **Cloudflare Account** and click the Worker link to enter the Nginx page.

12. Add this path at the end of the page URL and press Enter:

```text
/admin
```

Example:

```text
https://your-worker-url.workers.dev/admin
```

13. Create a password on the admin page. After the password is created, the panel opens.

14. Copy the **sublink** from the panel.

15. Return to NetFix and open:

```text
Menu -> V2Ray Router
```

16. Click **ADD SUB**.

17. Choose a name for the subscription.

18. Paste the copied sublink and import it.

19. After import, the configs appear in V2Ray Router. Double-click any config to ping-test it.

### Network Settings | تنظیمات شبکه

Open from:

```text
Menu -> Network Settings
```

You can configure:

- domestic ping hosts
- international ping hosts
- ping interval
- reset defaults
- clear fields
- apply/save changes

### Appearance | ظاهر برنامه

Open from:

```text
Menu -> Appearance
```

Available themes:

- dark
- light

---

## ⚙️ Configuration | تنظیمات

Settings are stored in `%APPDATA%\NetFixProtocol\settings.json`.

Default settings:

```json
{
    "domestic_hosts": ["web.bale.ai", "zarebin.ir", "ble.ir"],
    "international_hosts": ["8.8.8.8", "1.1.1.1"],
    "ping_interval": 4,
    "theme": "dark",
    "v2ray_background_enabled": true,
    "v2ray_background_port": 10809
}
```

| Key | Description | Default |
|-----|-------------|---------|
| `domestic_hosts` | Domestic hosts used for local connectivity checks | `web.bale.ai`, `zarebin.ir`, `ble.ir` |
| `international_hosts` | Global hosts used for international connectivity checks | `8.8.8.8`, `1.1.1.1` |
| `ping_interval` | Seconds between monitor checks | `4` |
| `theme` | UI appearance | `dark` |
| `v2ray_background_enabled` | Keeps local BG Proxy enabled on fresh install; user preference is preserved after changes | `true` |
| `v2ray_background_port` | SOCKS5 local port; HTTP uses port + 1 | `10809` |

V2Ray runtime data is stored in:

```text
%APPDATA%\NetFixProtocol\v2ray
```

Cloudflare WebView session data is stored in:

```text
%APPDATA%\NetFixProtocol\CloudflareWebView
```

Cloudflare tab state is stored in:

```text
%APPDATA%\NetFixProtocol\cloudflare_tabs.json
```

---

## 🔄 How It Works | نحوه عملکرد

```text
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Monitor    │────▶│  Ping Hosts      │────▶│  All Failed?    │
│  Thread     │     │  Domestic +      │     │  No Internet    │
│  Loop       │     │  International   │     │                 │
└─────────────┘     └──────────────────┘     └────────┬────────┘
                                                       │
                                            ┌──────────▼──────────┐
                                            │  Reconnect Sequence │
                                            │  1. Disconnect      │
                                            │  2. Optional toggle │
                                            │  3. Connect SSID    │
                                            └─────────────────────┘
```

- The monitor thread runs every `ping_interval` seconds.
- Domestic and international hosts are tested separately.
- If all hosts fail, Wi-Fi reconnect repair is triggered.
- If at least one host responds, the status stays live and the chart updates.
- V2Ray BG Proxy runs independently from monitoring.
- System proxy is only enabled when BG Proxy is OFF and VPN mode is started.
- `main.py` owns startup, admin elevation, Cloudflare child-process mode, single-instance mutex, and global error handling.
- `app.py` owns the main GUI and orchestration only; it is no longer a runnable entry point.
- Shared persistence goes through `storage.py`; hidden Windows command execution goes through `windows_cmd.py`.

---

## 🛠️ Dependencies | وابستگی‌ها

| Package | Purpose |
|---------|---------|
| `customtkinter` | Main GUI widgets |
| `pillow` | Icon/logo image loading |
| `matplotlib` | Live ping chart |
| `pywin32` | Windows API helpers |
| `winshell` | Windows startup shortcut |
| `pywebview` | In-app Cloudflare browser |
| `pyinstaller` | Build one-file Windows executable |

Runtime helper modules shipped with the app:

| Module | Purpose |
|--------|---------|
| `storage.py` | Shared atomic JSON/text writes |
| `windows_cmd.py` | Hidden `netsh`/`ping` subprocess wrappers |
| `cloudflare_tab_script.py` | Injected WebView tab UI, wait guard, and recovery tip |

---

## 📝 Notes | نکات

- **Windows-only** — uses `netsh`, Windows registry proxy settings, and `ctypes.windll`.
- **Run as Admin** — required for Wi-Fi repair and adapter actions.
- **WebView2 Runtime** may be required for the Cloudflare in-app browser on some systems.
- **V2Ray Core** is installed separately by the app when needed.
- **Entry point** is `main.py`; do not run `app.py` directly.
- **Cloudflare token storage** is still plaintext if saved through the legacy token config path; do not store sensitive tokens on shared Windows accounts.
- `workers.dev` TLS/filtering issues are outside NetFix; use VPN or Cloudflare Custom Domain when needed.

---

## 🧪 Development

```bash
# Run in development mode
python main.py

# Compile-check core modules
python -m py_compile app.py cloudflare.py cloudflare_tab_script.py main.py storage.py windows_cmd.py v2ray_window.py

# Build 1.3.1 EXE
python -m PyInstaller --clean --noconfirm --distpath "C:\Users\User\Desktop\NetFixProtocol\NetFix_PROTOCOL_v1.3.1_Release" --workpath "build\NetFix_PROTOCOL_1.3.1" NetFix_PROTOCOL_1.3.1.spec
```

---

## 📦 Changelog | تغییرات

### 1.3.1 (Latest) — Update Log from v1.3

#### Graphic / UI Polish
- **Version Label Refresh**: Updated the main window title, About dialog, README badge, build spec name, and packaged executable name to `1.3.1`.
- **Cloudflare Recovery Panel**: Reworked the Chrome/WebView error recovery panel into a cleaner multi-line card so the message does not feel cramped.
- **Farsi + English Tip**: Added a bilingual recovery tip explaining that the panel may still be preparing and should be refreshed after 2-3 minutes.
- **Retry / Refresh Action**: Added a clearer `Retry / Refresh` action for Cloudflare/WebView error states.
- **Build Name Consistency**: Release folder, EXE name, and PyInstaller command now use the same `1.3.1` naming.

#### Code Structure / Modularity
- **Single Entry Point Rule**: `main.py` is now the only runtime entry point; `app.py` no longer runs the app directly when executed/imported.
- **Import-Safe Main Module**: Importing `main.py` no longer launches the GUI; runtime work only starts through `main()` when `main.py` is executed.
- **Logging Moved to Main**: App-wide logging setup now lives in `main.py`, keeping `app.py` focused on UI/application behavior.
- **Shared Storage Module**: Added `storage.py` for atomic JSON/text writes used by settings, Cloudflare, and V2Ray state.
- **Shared Windows Command Module**: Added `windows_cmd.py` to centralize hidden `netsh`/`ping` subprocess behavior.
- **Cloudflare Script Split**: Moved the injected Cloudflare tab-bar/recovery JavaScript into `cloudflare_tab_script.py` so `cloudflare.py` stays smaller and easier to maintain.

#### Cloudflare / WebView Fixes
- **Tab State Save Fix**: Fixed the old `_atomic_write_json` call left inside `save_tabs_state()`, which could crash Cloudflare tab persistence after the storage refactor.
- **pywebview Callback Crash Fix**: Removed periodic JavaScript `remember_url` polling and `beforeunload` callback usage to prevent `window.pywebview._returnValuesCallbacks... is not a function` errors during refresh/navigation.
- **WebView Error Guidance**: Chrome/WebView error states now tell users to wait 2-3 minutes, refresh, or fully restart the app if the panel still does not open.
- **Hidden Imports Updated**: PyInstaller hidden imports now include `storage`, `windows_cmd`, and `cloudflare_tab_script`.

#### Network / V2Ray Stability
- **BG Proxy Preference Preserved**: The app no longer forces BG Proxy back ON if the user disabled it in settings.
- **Safer Wi-Fi Profile Matching**: Wi-Fi profile detection now parses profile names instead of relying on loose substring checks.
- **Safer Current SSID Parsing**: Current SSID detection avoids matching `BSSID` or unrelated netsh lines.
- **V2Ray Port Normalization**: V2Ray local ports are normalized to the safe `1024-65534` range before use.
- **Settings Repair**: Empty host lists and invalid stored settings are repaired back to safe defaults.

#### Verification
- **Compile Check**: All Python modules were compile-checked after the 1.3.1 cleanup.
- **Smoke Tests**: Cloudflare URL/script behavior, storage helpers, settings validation, Wi-Fi parsing helpers, and V2Ray port normalization were smoke-tested.


### v1.3 — Update Log from v1.2

#### Core App / Main Window
- **Version Bump**: Updated app title, About window, badge, build spec, and executable name to `v1.3`.
- **BG Proxy Default ON**: BG Proxy is enabled when the app opens, while Windows/System VPN remains OFF.
- **BG Proxy Launch Recovery**: After startup reset, the app starts proxy-only background mode instead of leaving V2Ray idle.
- **Main/Router BG Sync**: The BG Proxy checkbox on the main screen and the router checkbox stay synchronized live.
- **System VPN Separation**: Local proxy mode and Windows system proxy mode are now clearly separated.
- **Tray Tooltip Updates**: Tooltip reflects monitoring/background/proxy mode more accurately.

#### V2Ray Router
- **V2Ray Router Integration**: Added profile manager, group tabs, subscription import, and active profile state.
- **Supported Configs**: Supports `vmess://`, `vless://`, `trojan://`, outbound JSON, and full V2Ray JSON.
- **Local Proxy Ports**: SOCKS5 runs on `10809`; HTTP runs on `10810` by default.
- **BG Proxy Router Toggle**: Router can switch between proxy-only mode and system VPN mode.
- **Double-Click Ping**: Double-click any config in the list to ping that single config.
- **Removed PING SELECTED Button**: The old action-panel button was removed for a cleaner UI.
- **Keyboard Shortcuts**: `Ctrl + A` selects the current group; `Ctrl + R` pings selected configs.
- **Shortcut Reliability**: Shortcuts now work even when focus is inside entry/text fields.
- **Ping Result Sorting**: Profiles with latency are sorted above untested/unreachable profiles.
- **V2Ray Core Installer Prompt**: App prompts to install V2Ray core when missing.
- **Safe V2Ray Start/Stop**: Existing NetFix-owned V2Ray listeners are detected and cleaned before restart.

#### Cloudflare / In-App Browser
- **Cloudflare Side Menu**: Added Cloudflare Account entry in the main menu.
- **In-App WebView**: Cloudflare opens inside a pywebview window instead of the system browser.
- **Separate WebView Process**: `--cloudflare-webview` mode prevents Tkinter/WebView main-thread conflicts.
- **Persistent Login**: Cloudflare session is stored under `%APPDATA%\NetFixProtocol\CloudflareWebView`.
- **Fixed Workflow Tabs**: Added `Cloudflare`, `API Tokens`, `NovaProxy`, and `AtomicMail` tabs.
- **Nova Token Deep Link**: API Tokens tab opens a prefilled Nova installer token URL.
- **URL Bar**: Added lightweight address field and Go button.
- **Internal Link Handling**: Attempts to keep external/new-window links inside the in-app WebView.
- **Fallback Window**: If pywebview is missing, the app shows a clear fallback message.
- **Removed Experimental Tabs**: Removed add-new-tab, close-tab, and custom search page experiments.

#### Monitoring / UX
- **Single Instance Enforcement**: Windows named mutex prevents multiple main app instances.
- **System Tray Icon**: App can continue in the Windows tray with state tooltip.
- **LAN Mode Unlock**: LAN monitoring can start without requiring SSID entry.
- **Password Visibility Toggle**: Wi-Fi password dialog can show/hide password text.
- **Window Reuse**: Settings/About windows are reused/focused instead of duplicated.
- **Persistent AppData Path**: Runtime settings now live in `%APPDATA%\NetFixProtocol`.
- **Global Error Logging**: Unhandled errors are written to `error_log.txt`.

#### Security / Stability Hardening
- **Removed `shell=True`**: Wi-Fi adapter detection no longer uses shell execution.
- **Safe Wi-Fi XML**: SSID/password values are XML-escaped before writing temporary profiles.
- **Safer Temp Files**: Wi-Fi profile XML uses secure temp file creation.
- **Safe Zip Extraction**: V2Ray core zip extraction checks paths before extracting.
- **Download Size Limit**: V2Ray core archive download is capped.
- **Subscription Size Limit**: Subscription response size is capped at 5 MB.
- **Subscription URL Validation**: Subscription URLs must have `http`/`https` scheme and a valid host.
- **Atomic Writes**: Settings, V2Ray state, profiles, runtime config, proxy snapshots, Cloudflare state, and last SSID use atomic writes.
- **Proxy Snapshot Safety**: Windows proxy settings are snapshotted and restored carefully.
- **Dead Code Cleanup**: Removed unused state and debug-only variables.
- **Debug Cleanup**: Replaced a console `print` with `logging.debug`.

#### Build / Packaging
- **v1.3 Spec File**: Build config updated to `NetFix_PROTOCOL_v1.3.spec`.
- **One-File EXE**: Packaged output is `NetFix_PROTOCOL_v1.3.exe`.
- **Logo Embedded**: `logo.ico` is embedded into the executable.
- **Hidden Imports Updated**: V2Ray, Cloudflare, tray, pywebview, and UI modules are included in PyInstaller config.
- **Release Folder**: Build output goes to `Net Fix-protocol v1.3`.

### v1.2
- **SSID Dropdown + Scan**: Added network selection with real-time Wi-Fi scan.
- **Connection Awareness**: App checks whether it is already connected to the selected SSID.
- **Smart Connect**: Connects with saved Wi-Fi profile or creates a profile from password.
- **Clear/Reset Settings**: Added Clear Fields and Reset Defaults buttons.
- **Burger Menu Fix**: Main side-menu button positioning improved.
- **Live Indicator**: Added blinking LIVE dot while monitoring.
- **Window Size**: Optimized main window layout.
- **Theme Polish**: Improved dark/light colors and button styling.
- **Radio Lock**: Wi-Fi/LAN radio buttons are disabled during monitoring.

### v1.1
- Live ping chart with domestic/international visualization.
- Dark/Light theme toggle.
- Auto-start Windows registration.
- Persistent settings via `settings.json`.
- Admin auto-elevation via UAC.
- Last SSID auto-save/recall.

### v1.0
- Initial release.
- Basic Wi-Fi/LAN monitoring.
- Automatic reconnection on outage.
- Configurable ping hosts and interval.

---

## 📄 License

MIT License — feel free to use, modify, and distribute.

---

<div align="center">
  <sub>Built with ❤️ by <b>FANTOM</b></sub>
  <br>
  <sub>Version 1.3.1</sub>
</div>



