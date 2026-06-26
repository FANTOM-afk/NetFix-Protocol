# 🔧 NetFix Protocol v1.1

> **Automated Wi-Fi / LAN Connection Monitor & Repair Tool**  
> مانیتورینگ و تعمیر خودکار اتصال وای‌فای و LAN

![Python](https://img.shields.io/badge/Python-3.8%2B-00FF41?style=flat&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-00BFFF?style=flat&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-FF003C?style=flat)

---

## 📋 Overview | نمای کلی

NetFix Protocol continuously monitors your internet connection by pinging both domestic and international hosts. When a complete outage is detected, it automatically executes a repair sequence: disconnects from Wi-Fi, optionally toggles the adapter, and reconnects — all in real-time with a live ping chart.

این برنامه به‌صورت مداوم اتصال اینترنت شما را با پینگ کردن هاست‌های داخلی و خارجی بررسی می‌کند. در صورت قطعی کامل، به‌طور خودکار دنباله تعمیر را اجرا می‌کند.

### ✨ Features | ویژگی‌ها

| Feature | Description |
|---------|-------------|
| 🧠 **Auto-Reconnect** | Detects internet loss & automatically reconnects to Wi-Fi |
| 📊 **Live Chart** | Real-time ping graph for domestic vs international hosts |
| 🌐 **Dual Monitoring** | Supports both Wi-Fi and LAN connections |
| ⚙️ **Customizable** | Configure hosts, ping interval, theme via GUI |
| 🚀 **Auto-Start** | Optional Windows startup registration |
| 🎨 **Dark/Light Theme** | Switch between dark and light appearance |

---

## 🚀 Installation | نصب

### Prerequisites | پیش‌نیازها

- **Windows** (required for `netsh`, `winshell`, `ctypes`)
- **Python 3.8+**
- Administrator privileges (for Wi-Fi control)

### Setup

```bash
# Clone or navigate to the project directory
cd NetFixProtocol

# Install dependencies
pip install -r requirements.txt

# Run the application (will prompt for admin elevation)
python main.py
```

### Build Executable | ساخت فایل اجرایی

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --icon=logo.ico --add-data "logo.ico;." main.py
```

---

## 🏗️ Project Structure | ساختار پروژه

```
NetFixProtocol/
│
├── main.py               # Entry point — admin check then launch
├── app.py                # NetFixApp class — UI + monitoring orchestration
├── config.py             # Default settings, file paths, color theme
├── utils.py              # resource_path, admin check, startup shortcut
├── wifi.py               # Ping, adapter detection, reconnect logic
├── chart_widget.py       # LiveChart — real-time ping visualization
├── settings_windows.py   # Network settings, appearance, about dialogs
├── requirements.txt      # Python dependencies
├── logo.ico              # Application icon (optional)
└── .last_ssid            # (auto-generated) Last connected SSID
```

### Module Responsibilities | وظایف ماژول‌ها

| Module | Responsibility |
|--------|---------------|
| `main.py` | Checks for admin rights, re-launches with elevation if needed, starts the app |
| `app.py` | Builds the UI (customtkinter), starts/stops monitoring threads, wires everything together |
| `config.py` | Loads/saves `settings.json`, defines color scheme and default hosts |
| `utils.py` | `resource_path()` for PyInstaller compat, `check_admin()`, startup shortcut via `winshell` |
| `wifi.py` | `ping_host()`, `get_first_success_ping()`, `reconnect_wifi()` — no UI imports |
| `chart_widget.py` | Matplotlib-based `LiveChart` widget that plots domestic & international ping history |
| `settings_windows.py` | Toplevel windows for editing hosts, interval, theme, and About dialog |

---

## 🎮 Usage | نحوه استفاده

1. **Launch** the app (admin privileges required for Wi-Fi control).
2. **Enter SSID** — the app auto-detects the current Wi-Fi network.
3. **Select Connection Type** — Wi-Fi or LAN.
4. **Click "INITIALIZE ▶"** — monitoring begins.
5. Watch the **live chart** and **status bar** for real-time updates.
6. **Click "TERMINATE ■"** — stops monitoring.

### Network Settings

Configure domestic/international hosts and ping interval via:
- **Settings Menu → Network Settings**
- Changes can be applied live or saved permanently.

---

## ⚙️ Configuration | تنظیمات

Settings are stored in `settings.json` (auto-created on first run):

```json
{
    "domestic_hosts": ["web.bale.ai", "zarebin.ir", "ble.ir"],
    "international_hosts": ["8.8.8.8", "1.1.1.1"],
    "ping_interval": 4,
    "theme": "dark"
}
```

| Key | Description | Default |
|-----|-------------|---------|
| `domestic_hosts` | Iranian hosts to ping | `web.bale.ai`, `zarebin.ir`, `ble.ir` |
| `international_hosts` | Global hosts to ping | `8.8.8.8`, `1.1.1.1` |
| `ping_interval` | Seconds between checks | `4` |
| `theme` | UI appearance | `"dark"` |

---

## 🔄 How It Works | نحوه عملکرد

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Monitor    │────▶│  Ping Hosts      │────▶│  All Failed?    │
│  Thread     │     │  (domestic +     │     │  (no internet)  │
│  (loop)     │     │   international) │     │                 │
└─────────────┘     └──────────────────┘     └───────┬─────────┘
                                                      │
                                           ┌──────────▼──────────┐
                                           │  Reconnect Sequence │
                                           │  1. Disconnect      │
                                           │  2. (Optional)      │
                                           │     Disable/Enable  │
                                           │     Adapter         │
                                           │  3. Connect to SSID │
                                           └─────────────────────┘
```

- The monitor thread runs on the configured `ping_interval`.
- Each cycle pings domestic hosts first, then international.
- If **all** hosts fail → `reconnect_wifi()` is triggered.
- If **any** host responds → status is shown (green/yellow/red).
- The chart updates every cycle with the best ping from each category.

---

## 🛠️ Dependencies | وابستگی‌ها

| Package | Purpose |
|---------|---------|
| `customtkinter` | Modern UI components |
| `pillow` | Logo image loading |
| `pywin32` | Windows API access |
| `winshell` | Startup shortcut creation |
| `matplotlib` | Live ping chart rendering |

---

## 📝 Notes | نکات

- **Windows-only** — relies on `netsh wlan` commands and `ctypes.windll`.
- **Run as Admin** — required for Wi-Fi profile manipulation and adapter toggling (auto-elevated via UAC prompt).
- The `logo.ico` file is optional — if missing, the app runs without an icon.
- The app saves the last used SSID to `.last_ssid` for convenience.

---

## 🧪 Development

```bash
# Run in development mode
python main.py

# Check for any issues (run as admin)
python -c "import utils; print('Admin:', utils.check_admin())"
```

---

## 📦 Changelog | تغییرات

### v1.1 (Current)
- Live ping chart with domestic/international visualization
- Dark/Light theme toggle
- Auto-start Windows registration
- Persistent settings via `settings.json`
- Admin auto-elevation via UAC
- Last SSID auto-save/recall

### v1.0
- Initial release
- Basic Wi-Fi/LAN monitoring
- Automatic reconnection on outage
- Configurable ping hosts & interval

---

## 📄 License

MIT License — feel free to use, modify, and distribute.

---

<div align="center">
  <sub>Built with ❤️ by <b>FANTOM</b></sub>
  <br>
  <sub>Version 1.1</sub>
</div>

