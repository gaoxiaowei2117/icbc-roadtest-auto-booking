# ICBC Road Test Auto-Booking

🚗 **An automated ICBC road test booking assistant** — monitors slot availability, books a matching slot, and exits cleanly when done.

> 中文版请见 [README.zh.md](README.zh.md)
>
> 💡 **Non-technical Windows user?** A step-by-step Chinese walkthrough is at [**WINDOWS_SETUP.zh.md**](WINDOWS_SETUP.zh.md).

## 📋 Table of Contents

- [Features](#-features)
- [Requirements](#-requirements)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Troubleshooting](#-troubleshooting)
- [Project Files](#-project-files)

## ✨ Features

### Core
- **Fully automatic booking** — submits a reservation as soon as a matching slot is found
- **Gmail integration** — reads the ICBC verification code from your inbox via IMAP
- **Smart slot selection** — picks the earliest or best-matching slot based on your preferences
- **Auto-exit on success** — the program shuts down once the booking is confirmed

### Reliability
- **Conflict detection** — avoids double-booking
- **Retry with backoff** — retries on transient network errors
- **Persistent state** — booking status is saved to `booking_status.json`
- **Detailed logging** — every step is recorded for later review

### Usability
- **One-line launcher** (`start.sh`)
- **Live status check** (`status.py`)
- **Single YAML config file**

## 🖥️ Requirements

- **OS**: Linux / macOS / Windows
- **Python**: 3.7+
- **Network**: must be able to reach `onlinebusiness.icbc.com` and `imap.gmail.com`
- **Gmail account**: 2-step verification enabled, with an app password generated

## 📦 Pre-built Binaries (no Python required)

If you'd rather not install Python, grab a single-file executable from the
[**Releases page**](https://github.com/gaoxiaowei2117/icbc-roadtest-auto-booking/releases):

| OS | Asset |
|----|-------|
| Windows (x64) | `icbc-control-panel-windows.zip` |
| macOS (Apple Silicon) | `icbc-control-panel-macos.zip` |
| Linux (x64) | `icbc-control-panel-linux.zip` |

Unzip, double-click `icbc-control-panel(.exe)`, and the control panel will open
in your browser. First run auto-creates `config.yml` next to the executable —
fill it in via the **Configure** tab, then start monitoring.

> The binaries are unsigned. Windows SmartScreen and macOS Gatekeeper will
> warn on first launch — see `README.txt` inside the zip for the bypass steps.
> Intel Mac and 32-bit Windows users should run from source instead.

## 🚀 Quick Start (from source)

### 1. Clone the repository

```bash
git clone https://github.com/gaoxiaowei2117/icbc-roadtest-auto-booking.git
cd icbc-roadtest-auto-booking
```

### 2. Install dependencies

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y python3 python3-pip

# macOS
brew install python3

# Windows: install Python 3.7+ from python.org
```

Install the Python packages:

```bash
pip3 install -r requirements.txt
```

### 3. Create a Gmail app password

1. Sign in to your Google account
2. Go to **Account settings → Security**
3. Enable **2-Step Verification**
4. Under 2-Step Verification, open **App passwords**
5. Choose **Mail** and **Other device**
6. Copy the 16-character app password (e.g. `abcd efgh ijkl mnop`) — you will paste it into the config below

### 4. Prepare your config

`config.yml` is git-ignored. Start from the template:

```bash
cp config.example.yml config.yml
```

Then edit `config.yml` and fill in your real values:

```yaml
icbc:
  drvrLastName: "Your_Last_Name"
  licenceNumber: "12345678"
  keyword: "123456"

gmail:
  enable: true
  email: "your-email@gmail.com"
  password: "abcd efgh ijkl mnop"   # 16-char Gmail app password

autoBooking:
  enable: true
  exitAfterSuccess: true
```

### 5. Run

```bash
# One-line launcher
chmod +x start.sh
./start.sh

# Or run directly
python3 road.py config.yml
```

## ⚙️ Configuration

Full annotated `config.yml`:

```yaml
# ICBC account
icbc:
  drvrLastName: "Your_Last_Name"      # last name
  licenceNumber: "12345678"           # driver's licence number
  keyword: "123456"                   # ICBC keyword / password
  examClass: "5"                      # exam class
  posID: "274"                        # test centre ID
  expactAfterDate: "2025-08-10"       # earliest acceptable date (YYYY-MM-DD)
  expactBeforeDate: "2025-09-22"      # latest acceptable date
  expactTimeRange: "10:00-11:30,13:00-14:10"   # acceptable time ranges
  prfDaysOfWeek: "[0,1,2,3,4,5,6]"    # preferred days (0 = Sunday)
  prfPartsOfDay: "[0,1]"              # 0 = morning, 1 = afternoon

# Gmail (required for auto-booking, used to fetch the verification code)
gmail:
  enable: true
  email: "your-email@gmail.com"
  password: "your-app-password"       # 16-character app password
  imap_server: "imap.gmail.com"
  imap_port: 993
  verification_timeout_minutes: 1
  check_interval_seconds: 10
  use_idle: false

# Auto-booking behaviour
autoBooking:
  enable: true
  timeSelectionStrategy: "earliest"   # "earliest" or "best_time_slot"
  maxRetryAttempts: 3
  retryIntervalSeconds: 30
  verificationCodeTimeoutMinutes: 10
  bookingTimeWindow: "00:00-23:59"    # only attempt booking within this window
  exitAfterSuccess: true

# Notifications (all optional)
pushdeer:
  enable: false
  key: ""

pushsms:
  enable: false
  accountSid: ""                      # Twilio
  authToken: ""
  fromNumber: ""
  toNumber: ""

ntfy:
  enable: false
  topic: ""

pushlocal:
  enable: false

pushsound:
  enable: false
  audio_file: ""                      # path to a custom audio file; empty = system beep

# Misc
pauseTimeMin: 5                       # minutes to pause polling after finding a slot
skip0Clock: false                     # skip 23:55–00:05 window
requestLimit:
  enable: false
  period: 20:15-23:15
  interval: 5

data_directory: "./log"               # where state and logs are stored
```

## 📖 Usage

### Launcher

```bash
./start.sh
```

It will prompt you to pick:
- `1` — 🚀 Live mode (connect to the real ICBC system)
- `2` — 📊 Show status
- `3` — 📋 Show recent logs
- `4` — ⚙️ Configure (edit config.yml interactively)
- `5` — 🖥️ Open control panel (web UI)

### Control panel (web UI)

```bash
python3 webui.py
```

Starts a local control panel and opens it in your browser. From there you
can edit the configuration, start and stop the monitor, and watch live
status and console output — no command line needed. Uses only the Python
standard library (no extra dependencies). The server binds to
`127.0.0.1` only.

![Control panel screenshot](docs/images/control-panel.png)

Note: stopping `webui.py` (Ctrl+C) also stops a running monitor. Closing
just the browser tab does not — the server keeps running in the background.

### Live mode

```bash
python3 road.py config.yml
```

Connects to ICBC, polls for slots, and books the first matching one. With `exitAfterSuccess: true` it exits cleanly after a successful booking.

### Status

```bash
python3 status.py
```

Shows current configuration, last booking outcome, and last-run timestamp.

### Logs

```bash
# Follow live
tail -f log_icbc_roadtest_checker.log

# Last 100 lines
tail -n 100 log_icbc_roadtest_checker.log

# Find errors
grep ERROR log_icbc_roadtest_checker.log
```

## 🔧 Troubleshooting

### Gmail connection fails

```
Failed to connect to Gmail
```

- Confirm you are using a **Gmail app password**, not your regular account password
- Confirm 2-Step Verification is enabled on the Google account
- The app password must be 16 characters

### Missing Python package

```
ModuleNotFoundError: No module named 'requests'
```

```bash
pip3 install -r requirements.txt

# Or with a virtual environment
python3 -m venv venv
source venv/bin/activate     # Linux / macOS
# venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### ICBC server errors (520 / 524)

These are upstream issues on ICBC's side. The program retries automatically — no action required.

```bash
ping onlinebusiness.icbc.com
python3 status.py
```

### Invalid configuration

```bash
# Check YAML syntax
python3 -c "import yaml; yaml.safe_load(open('config.yml'))"

# Inspect the parsed sections
python3 -c "
import yaml
c = yaml.safe_load(open('config.yml'))
print('icbc       :', c.get('icbc', {}))
print('gmail      :', c.get('gmail', {}))
print('autoBooking:', c.get('autoBooking', {}))
"
```

### Permission denied

```bash
chmod +x start.sh
ls -la *.py *.yml *.sh
```

## 📁 Project Files

```
icbc-roadtest-auto-booking/
├── README.md            # this file (English, default)
├── README.zh.md         # Chinese version
├── AUTO_BOOKING_GUIDE.md
├── PROJECT_SUMMARY.md
├── road.py              # main program (live mode)
├── status.py            # status / health check
├── start.sh             # interactive launcher
├── config.example.yml   # config template (commit-safe)
├── config.yml           # your local config (git-ignored)
├── requirements.txt
└── runtime files (git-ignored)
    ├── log_icbc_roadtest_checker.log
    ├── booking_status.json
    ├── processed_emails.txt
    └── last_run.txt
```

| File | Purpose |
|------|---------|
| `road.py` | Main program — connects to ICBC and books slots |
| `status.py` | Shows current state and last run |
| `config.example.yml` | Committed config template |
| `config.yml` | Your local config (ignored by git) |
| `start.sh` | Interactive launcher |
| `webui.py` | Web control panel server (stdlib only) |
| `webui_state.py` | Config + status data layer for the panel |
| `webui_monitor.py` | Manages the road.py subprocess for the panel |
| `webui/` | Control panel frontend (HTML/CSS/JS) |
| `requirements.txt` | Python dependencies |

## ⚠️ Important Notes

1. **Never commit `config.yml`** — it contains your Gmail app password, driver's licence number, and ICBC keyword. It is git-ignored by default; keep it that way.
2. **Gmail security** — always use an app password, never your real Google password.
3. **Verify the booking** — after a successful run, log in to the ICBC website and confirm the appointment manually.
4. **Watch the logs** — `tail -f log_icbc_roadtest_checker.log` while the program runs lets you spot issues early.
5. **Use responsibly** — the program polls ICBC's servers; please don't lower `requestLimit` aggressively or share your config with others.

## 🎯 Workflow

1. Install dependencies → 2. Generate Gmail app password → 3. `cp config.example.yml config.yml` and fill in → 4. Run `python3 road.py config.yml` → 5. Wait for the system to book a matching slot → 6. Confirm on the ICBC website.

---

Once a slot is booked, the program saves the result to `booking_status.json`, sends any configured notifications, and exits. No more manually refreshing the ICBC site.
