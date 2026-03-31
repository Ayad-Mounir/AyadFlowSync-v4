# AyadFlowSync-v4

![Python](https://img.shields.io/badge/Python-3.9%2B-3776ab?style=flat-square&logo=python) ![License](https://img.shields.io/badge/License-MIT-green?style=flat-square) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-blue?style=flat-square)

*USB ↔ PC file synchronization with GitHub integration, hardware-aware performance tuning, and encrypted secure storage — all in PyQt6.*

---

## 📖 Why This Exists

Syncing files between USB drives and PCs is slow and unreliable. Most tools ignore actual hardware capabilities — they use the same thread count and buffer sizes on a budget laptop as on a workstation. AyadFlowSync profiles your device's CPU, RAM, and USB speed on first run, then adjusts worker threads (2→16), batch sizes (50→2000), and hash algorithms automatically. The result: scanning 200,000 files in under 3 seconds using xxhash XXH3_128 instead of MD5.

Beyond sync, you can inspect local projects, upload entire repos to GitHub in batch, clone remote repositories, and generate professional README files. Everything stores secrets encrypted with AES-256-GCM — no plaintext tokens on your drive.

**AyadFlowSync** does this by combining 4-tier device profiling, xxhash-powered change detection, live hardware monitoring, and a PyQt6 GUI that shows real-time progress with 110 Python modules spanning 297 files.

---

## ✨ Key Features

- **4-tier device profiler** — Measures CPU cores, RAM, and USB bandwidth once at startup; automatically selects thread count (2/4/8/16) and queue size (50/500/2000) based on hardware class (Budget/Standard/Performance/Server)

- **xxhash XXH3_128 file detection** — Identifies changed files 30× faster than MD5; skips unchanged files via mtime-based cache with SQLite WAL and mmap acceleration

- **Live hardware monitor** — Daemon thread polls CPU/RAM/USB status every 500ms; updates registered callbacks in real-time without blocking UI

- **Automatic lock renewal** — Database locks include auto-renewal to prevent stale timeouts; solves the v3 bug where large folder syncs (>60s) lost lock

- **Batch GitHub upload** — Scans a parent folder, treats each subdirectory as an independent Git repository, uploads all in one operation while skipping folders with existing `.git/config`

- **Project Inspector** — Single-pass analysis 3× faster than separate scanner; detects project type, dependencies, language, and file count in one traversal

- **AES-256-GCM encrypted storage** — All secrets (GitHub tokens, API keys) use authenticated encryption; optional PIN-based PBKDF2+HMAC protection for USB drives

- **Smart README generation** — Generates professional project documentation with AI fallback or template-based structure

- **Git with cancellation support** — GitRunner executes Git commands with configurable timeout, automatic kill on cancel, and structured logging

- **FAT32-aware uploads** — Handles FAT32 limitations by temporarily relocating `.git` folder during push operations on USB drives

---

## 🖥️ Screenshots / Demo

> GUI panels coming soon. Current workflow: Launch app → Device profiler auto-runs → Select source/destination folders → Click "Sync" → Watch real-time progress bar with CPU/RAM/USB gauges → Inspect uploaded projects in GitHub tab.

---

## 🛠 Tech Stack

| Technology | Purpose | Why |
|---|---|---|
| **PyQt6** | Desktop GUI framework | Native widgets, thread-safe signals/slots for real-time hardware updates |
| **xxhash** | File hashing | XXH3_128 is 30× faster than MD5 for change detection |
| **psutil** | Hardware monitoring | Cross-platform CPU/RAM/USB metrics without OS syscalls |
| **cryptography** | Secret storage | AES-256-GCM provides authenticated encryption for GitHub tokens |
| **GitPython** | Git automation | Pythonic wrapper around Git commands with timeout/kill support |
| **requests** | GitHub REST API | Lightweight HTTP client for repo operations (list/create/delete) |
| **SQLite** | Hash cache + locks | WAL mode enables concurrent reads during active syncs |

---

## 📁 Project Structure

```
AyadFlowSync-v4/
├── AyadFlowSync/                    # Main package (110 .py files)
│   ├── main.py                      # Entry point: multiprocess setup, PyQt6 launch
│   ├── core/                        # Hardware & config layer
│   │   ├── app_config.py            # AppConfig: centralized settings, dir init, USB calibration
│   │   ├── constants.py             # AppInfo, Theme (Professional Slate Dark), formatting
│   │   ├── device_profiler.py       # DeviceProfiler: 4-tier CPU/RAM/USB scoring + cache
│   │   ├── hardware.py              # HardwareMonitor: daemon thread, live CPU/RAM/USB polling
│   │   └── hash_worker.py           # Hash processing pipeline
│   ├── db/                          # Data persistence
│   │   └── database.py              # DatabaseManager + LockManager (with auto-renewal)
│   ├── github/                      # GitHub operations
│   │   ├── client.py                # GitRunner (exec + timeout), GitHubAPI (REST v3)
│   │   ├── manager.py               # RepoMgr: list/create/delete repos
│   │   ├── ops.py                   # Uploader, Cloner, Batch, LFS, ProjectInspector, Auth
│   │   ├── analyzer.py              # ProjectAnalyzer: deep code inspection
│   │   ├── readme.py                # SmartReadmeGenerator
│   │   └── upload_log.py            # UploadLog: offline-capable project registry
│   ├── security/                    # Encryption & secrets
│   │   ├── secure_store.py          # SecureStore: AES-256-GCM key-value encryption
│   │   ├── hash.py                  # HashCache: xxhash + SQLite WAL + mmap
│   │   └── security.py              # MultiKeyStore, AppSettings, History, AnalysisCache
│   ├── lang/                        # Internationalization
│   │   ├── lang.py                  # Lang: translation loader
│   │   └── proxy.py                 # LangProxy: lazy loading for circular deps
│   ├── ui/                          # PyQt6 GUI
│   ├── sync/                        # Sync engine (not detailed in snapshot)
│   ├── logs/                        # Runtime logs directory
│   ├── data/                        # Config, cache, user data
│   │   ├── hash_cache.db            # SQLite WAL: file hashes + mtime_ns
│   │   ├── .ai_keys_enc             # Encrypted AI API keys (MultiKeyStore)
│   │   ├── excluded_dirs.json       # Folders to skip during sync
│   │   ├── accumark_mode.txt        # Accumulation mode setting
│   │   └── .flash_secret            # PIN/secret for removable media
│   ├── presync_snapshots/           # Pre-sync state snapshots
│   ├── sync_reports/                # Sync operation logs
│   ├── trash/                       # Deleted file staging
│   └── __init__.py
├── tests/                           # Test suite (pytest)
│   └── conftest.py                  # Fixtures: tmp_dir, src_dir, dst_dir, sample_project, sync_engine, db
├── assets/                          # UI resources (96 .qm translation files)
├── dist/                            # Build output (frozen EXE + DLLs)
├── BUILD_GUIDE.md                   # PyInstaller build instructions
├── README.md                        # This file
├── pyproject.toml                   # Poetry/setuptools config, deps, scripts
├── conftest.py                      # Central pytest setup
├── icon.ico                         # App icon
├── AyadFlowSync.spec                # PyInstaller spec file
└── build.bat                        # Windows build script
```

---

## ⚙️ Prerequisites

- **Python 3.9 or higher** (tested on 3.9+; earlier versions may not work)
- **pip** (comes with Python 3.9+)
- **Virtual environment** support (venv)
- **Git** (for GitHub operations, auto-detected at runtime)

### Linux-specific notes:
If using Tkinter/custom widgets, some Linux distributions require:
```bash
sudo apt install python3-tk
```

⚠️ **Warning:** Tested on Python 3.9+. Earlier versions may not work.

---

## 🚀 Installation

### 1. Clone the repository
```bash
git clone https://github.com/Ayad-Mounir/AyadFlowSync-v4.git
cd AyadFlowSync-v4
```

### 2. Create a virtual environment
```bash
python -m venv venv
```

### 3. Activate the virtual environment

**On Windows:**
```bash
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
source venv/bin/activate
```

### 4. Install dependencies
```bash
pip install .
```

Or for development with test tools:
```bash
pip install ".[dev]"
```

### 5. Run the application
```bash
python -m AyadFlowSync.main
```

Or use the installed command:
```bash
ayad-flowsync
```

---

## ▶️ Usage Guide

### Quick Start

1. **Launch the app:**
   ```bash
   python -m AyadFlowSync.main
   ```
   The device profiler auto-runs on first start. It benchmarks your hardware and caches the result in `data/hash_cache.db`.

2. **Select source and destination folders** in the GUI and click **Sync**.

3. **Monitor progress** — the hardware monitor updates CPU/RAM/USB gauges every 500ms while files transfer.

---

### Syncing Files Between USB and PC

**What happens:**
- xxhash scans files in 3 seconds (vs. 90s with MD5)
- Changed files are detected by mtime_ns + cached hash
- Worker threads scale automatically: 2 threads on budget hardware, up to 16 on high-end CPUs
- Lock renewal prevents sync loss on large operations (>60s)

**Steps:**
1. Plug in USB drive
2. Open AyadFlowSync, select USB as source
3. Choose destination folder on PC
4. Click **Sync** → watch live progress with hardware metrics
5. Eject USB safely when done

**Example output:**
```
[14:32:18] Device: Performance (Intel i7, 16GB RAM, USB 3.0)
[14:32:18] Scanning 45,230 files...
[14:32:21] ✅ Scan complete: 12,340 files changed (28.1 MB)
[14:32:21] Workers: 8 threads | Queue: 2000 items
[14:32:45] ✅ Sync complete: 12,340 files → 28.1 MB transferred
```

---

### Uploading Local Projects to GitHub

The **Batch Uploader** scans a parent folder and uploads each subfolder as an independent Git repository.

**Example folder structure:**
```
~/MyProjects/
  ├── web-app/          → Creates repo "web-app"
  ├── cli-tool/         → Creates repo "cli-tool"
  └── data-viz/         → Creates repo "data-viz"
```

**Steps:**
1. Go to **GitHub** tab → **Batch Upload**
2. Select parent folder (e.g., `~/MyProjects`)
3. Paste your GitHub token (stored encrypted in `data/.ai_keys_enc`)
4. Click **Upload All** → skips folders with existing `.git/config`

**What Uploader does (per project):**
1. Creates GitHub repository
2. Initializes local Git (if not present)
3. Adds GitHub remote
4. Pushes all commits
5. Handles FAT32 by relocating `.git` temporarily

**Output log** (`.ayadsync_push_log.json`):
```json
{
  "web-app": {
    "status": "success",
    "repo": "https://github.com/user/web-app",
    "files_pushed": 156,
    "size_mb": 42.3
  }
}
```

💡 **Tip:** Use **ProjectInspector** first to detect project type, dependencies, and language — generates metadata for README generation.

---

### Analyzing a Project

The **ProjectInspector** scans a folder in one pass and detects:
- Project type (Python, JavaScript, Java, etc.)
- Dependencies (from `requirements.txt`, `package.json`, etc.)
- Programming language
- File count by extension

**3× faster than separate scanner** because it traverses the directory tree once.

**Steps:**
1. Go to **GitHub** tab → **Inspect Project**
2. Select project folder
3. Wait 2-5 seconds → see results (type, dependencies, language, file count)

---

### Generating a Professional README

The **SmartReadmeGenerator** creates a README with:
- Project description (AI-generated or template-based)
- Installation instructions
- Usage examples
- Contributing guidelines

**Steps:**
1. Inspect project (above)
2. Click **Generate README**
3. Choose: **AI-powered** (uses cached API keys) or **Template-based**
4. Review and save to `README.md`

⚠️ **Warning:** AI mode requires a pre-configured API key (OpenAI, Claude, or Anthropic). Store it via **Settings** → **API Keys**.

---

### Managing GitHub Tokens Securely

Tokens are encrypted with **AES-256-GCM** and stored in `data/.ai_keys_enc`. Optional PIN protection uses PBKDF2+HMAC.

**Steps:**
1. Go to **Settings** → **GitHub Token**
2. Paste your token
3. (Optional) Enable PIN protection → choose a 4-6 digit PIN
4. Click **Save** → token encrypted automatically

**On USB drive with PIN:**
```
data/
├── .ai_keys_enc          # Encrypted token (requires PIN to decrypt)
└── .flash_secret         # PIN hash
```

💡 **Tip:** Without PIN, token is stored plaintext-equivalent in app memory but encrypted on disk. PIN adds HMAC verification.

---

### Checking Sync History

The **History** module logs every sync operation with timestamps, file counts, and errors.

**File:** `data/history.json` (debounced writes every 2 seconds)

**Example entry:**
```json
{
  "timestamp": "2024-01-15T14:32:45",
  "operation": "sync",
  "source": "/media/usb",
  "destination": "/home/user/backup",
  "files_changed": 12340,
  "size_mb": 28.1,
  "duration_seconds": 24,
  "status": "success"
}
```

---

### Monitoring Hardware in Real-Time

**HardwareMonitor** runs as a daemon thread and updates every 500ms. Visible in GUI status bar.

**Metrics:**
- CPU usage (%)
- RAM usage (%)
- USB speed (MB/s, measured during sync)

**Accessed via:**
```python
from AyadFlowSync.core.hardware import HardwareMonitor

monitor = HardwareMonitor()
monitor.register_callback(lambda cpu, ram, usb: print(f"CPU: {cpu}%"))
monitor.start()
```

---

## 🏗 Architecture

**AyadFlowSync** uses a layered architecture:

```
┌─────────────────────────────────────┐
│  UI Layer (PyQt6)                   │
│  ├─ MainWindow                      │
│  ├─ SyncTab, GitHubTab, SettingsTab │
│  └─ Real-time hardware gauges       │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  Operation Layer                    │
│  ├─ Uploader (batch to GitHub)      │
│  ├─ ProjectInspector (analyze)      │
│  ├─ SyncEngine (file sync)          │
│  └─ SmartReadmeGenerator            │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  Core Layer                         │
│  ├─ DeviceProfiler (4-tier scoring) │
│  ├─ HardwareMonitor (daemon polling)│
│  ├─ AppConfig (settings)            │
│  └─ DatabaseManager (locks + cache) │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  Security Layer                     │
│  ├─ SecureStore (AES-256-GCM)       │
│  ├─ HashCache (xxhash + SQLite WAL) │
│  └─ Auth (token encryption)         │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  External Services                  │
│  ├─ GitHub REST API (via requests)  │
│  ├─ Git CLI (via GitPython)         │
│  └─ Local filesystem (psutil)       │
└─────────────────────────────────────┘
```

**Key interactions:**
- DeviceProfiler → HardwareMonitor: hardware class determines thread count
- SyncEngine → HashCache: reads/writes cached file hashes
- Uploader → Auth + SecureStore: retrieves encrypted GitHub token
- UI → DatabaseManager: acquires lock before sync
- ProjectInspector → ProjectAnalyzer: deep code inspection

---

## 🧪 Tests

Tests are located in `tests/` and use **pytest** with fixtures for isolated testing.

**Run all tests:**
```bash
pytest tests/ -v
```

**Run with coverage:**
```bash
pytest tests/ --cov=AyadFlowSync --cov-report=html
```

**Available fixtures** (in `conftest.py`):
- `tmp_dir()` — temporary directory, auto-cleaned after each test
- `src_dir()` — source folder for testing sync
- `dst_dir()` — destination folder for testing sync
- `sample_project()` — Python project with files, for analyzer tests
- `sync_engine()` — pre-configured SyncEngine
- `db()` — temporary DatabaseManager

**Example test:**
```python
def test_sync_basic(src_dir, dst_dir, sync_engine):
    # Create 10 test files in src_dir
    (src_dir / "file1.txt").write_text("hello")
    
    # Sync
    sync_engine.sync(src_dir, dst_dir)
    
    # Verify
    assert (dst_dir / "file1.txt").read_text() == "hello"
```

---

## 🤝 Contributing

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/AyadFlowSync-v4.git
   cd AyadFlowSync-v4
   ```
3. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make your changes** and run tests:
   ```bash
   pytest tests/ -v
   ```
5. **Commit with clear messages:**
   ```bash
   git commit -m "feat: add xxhash XXH4 support for even faster scanning"
   ```
6. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Open a Pull Request** on the main repo with a description of changes

**Code style:** Uses **ruff** (line length 100, Python 3.9+) and **mypy** for type checking. Run before submitting:
```bash
ruff check AyadFlowSync/
mypy AyadFlowSync/ --ignore-missing-imports
```

---

## 📄 License

This project is licensed under the **MIT License** — see the LICENSE file for details.

---

## 👨‍💻 Author

| | |
|---|---|
| **Email** | [![Email](https://img.shields.io/badge/Email-contact.ayad.mounir%40gmail.com-blue?style=flat-square&logo=gmail)](mailto:contact.ayad.mounir@gmail.com) |
| **WhatsApp** | [![WhatsApp](https://img.shields.io/badge/WhatsApp-%2B212653867667-25D366?style=flat-square&logo=whatsapp)](https://wa.me/212653867667) |
| **Telegram** | [![Telegram](https://img.shields.io/badge/Telegram-Mounir_AyadD-0088cc?style=flat-square&logo=telegram)](https://t.me/Mounir_AyadD) |
| **GitHub** | [![GitHub](https://img.shields.io/badge/GitHub-Ayad--Mounir-black?style=flat-square&logo=github)](https://github.com/Ayad-Mounir) |

<p align="center">Made with ❤️ by Mounir Ayad</p>