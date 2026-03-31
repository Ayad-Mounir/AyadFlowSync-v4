# ⚡ AyadFlowSync v4.0

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-41CD52?logo=qt)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-brightgreen)

> Portable USB ↔ PC sync + GitHub management tool with professional PyQt6 interface. Runs entirely from USB — program, data, and config all on the flash drive.

---

## ✨ Features

- **Smart bidirectional sync** — newest file always wins, zero-byte files fully supported
- **DirSnapshot indexing** — scans ~2,000 directories instead of 200,000 files (60-95% faster)
- **4-level device profiling** — Weak/Mid/Strong/Ultra with automatic thread tuning
- **Professional Dashboard** — animated score gauges, precise change detection, real-time status
- **GitHub integration** — upload, push, clone, batch, README AI generation (multi-provider)
- **SafeTrash** — deleted files go to recoverable trash, not permanent deletion
- **FAT32-aware** — handles USB FAT32 quirks (2s mtime tolerance, temp .git relocation)
- **Drag & Drop** — drag a folder onto the window to add it as a project
- **Toast notifications** — slide-in alerts with queue support
- **Keyboard shortcuts** — Ctrl+1-6 navigation, Ctrl+R refresh

## 🚀 Quick Start

```bash
git clone https://github.com/Ayad-Mounir/AyadFlowSync-v4.git
cd AyadFlowSync-v4
pip install -r requirements.txt
python -m AyadFlowSync.main
```

## 📦 Build EXE

```bash
pip install pyinstaller
pyinstaller AyadFlowSync.spec
```

## 👨‍💻 Author

**Mounir Ayad** — [@Ayad-Mounir](https://github.com/Ayad-Mounir)

---
<p align="center">Made with ❤️ by Mounir Ayad</p>
