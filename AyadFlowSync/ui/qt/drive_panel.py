#!/usr/bin/env python3
"""ui.qt.drive_panel — إدارة الفلاشة/النسخ الاحتياطي."""

import os
import json
import shutil
import threading
from pathlib import Path
from datetime import datetime

from ...lang.lang import Lang
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QFrame, QProgressBar,
    QMessageBox, QHeaderView, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor

from ...core.app_config import AppConfig
from ...core.device_profiler import DeviceProfiler
from ...core.constants import Theme


class DriveSignals(QObject):
    refreshed = pyqtSignal(list)
    log_line = pyqtSignal(str)


class DrivePanel(QWidget):
    """لوحة إدارة الفلاشة — عرض المشاريع المخزنة + حالتها + المساحة."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._signals = DriveSignals()
        self._signals.refreshed.connect(self._populate)
        self._signals.log_line.connect(self._on_log)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ── Header ────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel(Lang.t("drv_title"))
        title.setObjectName("SectionTitle")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        btn_refresh = QPushButton(Lang.t("drv_refresh"))
        btn_refresh.setObjectName("PrimaryBtn")
        btn_refresh.clicked.connect(self._refresh)
        header.addWidget(btn_refresh)

        btn_change = QPushButton(Lang.t("drv_change_folder"))
        btn_change.clicked.connect(self._change_vault)
        header.addWidget(btn_change)

        root.addLayout(header)

        # ── Drive Info Card ───────────────────────────────────────
        info_card = QFrame()
        info_card.setObjectName("Card")
        info_ly = QHBoxLayout(info_card)
        info_ly.setContentsMargins(16, 12, 16, 12)
        info_ly.setSpacing(20)

        self._path_lbl = QLabel(f"📁  {AppConfig.VAULT_DIR}")
        self._path_lbl.setObjectName("Dim")
        self._path_lbl.setWordWrap(True)
        info_ly.addWidget(self._path_lbl, 1)

        self._space_lbl = QLabel("—")
        self._space_lbl.setFont(QFont("Cascadia Code", 14))
        info_ly.addWidget(self._space_lbl)

        self._speed_lbl = QLabel("—")
        self._speed_lbl.setFont(QFont("Cascadia Code", 14))
        self._speed_lbl.setObjectName("Dim")
        info_ly.addWidget(self._speed_lbl)

        root.addWidget(info_card)

        # ── Space Bar ─────────────────────────────────────────────
        self._space_bar = QProgressBar()
        self._space_bar.setRange(0, 100)
        self._space_bar.setFixedHeight(8)
        self._space_bar.setTextVisible(False)
        root.addWidget(self._space_bar)

        # ── Projects Tree ─────────────────────────────────────────
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([Lang.t("drv_col_project"), Lang.t("drv_col_status"), Lang.t("drv_col_size"), Lang.t("drv_col_sync"), Lang.t("drv_col_files")])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSortingEnabled(True)

        hdr = self._tree.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        root.addWidget(self._tree, 1)

        # ── Action Buttons ────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        btn_drive = QPushButton(Lang.t("drv_upload_drive"))
        btn_drive.setObjectName("PrimaryBtn")
        btn_drive.setToolTip("ضغط المشروع ZIP + فتح Google Drive")
        btn_drive.clicked.connect(self._zip_and_open_drive)
        btn_row.addWidget(btn_drive)

        btn_open = QPushButton(Lang.t("drv_open_btn"))
        btn_open.clicked.connect(self._open_selected)
        btn_row.addWidget(btn_open)

        btn_explore = QPushButton(Lang.t("drv_explore_btn"))
        btn_explore.clicked.connect(self._explore_vault)
        btn_row.addWidget(btn_explore)

        btn_row.addStretch()

        btn_delete = QPushButton(Lang.t("drv_delete_btn"))
        btn_delete.setObjectName("DangerBtn")
        btn_delete.clicked.connect(self._delete_selected)
        btn_row.addWidget(btn_delete)

        root.addLayout(btn_row)

        # ── Device History ─────────────────────────────────────
        dev_title = QLabel(Lang.t("drv_devices_title"))
        dev_title.setObjectName("SectionTitle")
        root.addWidget(dev_title)

        self._dev_tree = QTreeWidget()
        self._dev_tree.setHeaderLabels([Lang.t("drv_dev_col_device"), Lang.t("drv_dev_col_sync"), Lang.t("drv_dev_col_count"), Lang.t("drv_dev_col_proj")])
        self._dev_tree.setRootIsDecorated(True)
        self._dev_tree.setMaximumHeight(180)
        self._dev_tree.setAlternatingRowColors(True)
        root.addWidget(self._dev_tree)

        # ── Status ────────────────────────────────────────────────
        self._status = QLabel(Lang.t("drv_status_default"))
        self._status.setObjectName("Dim")
        root.addWidget(self._status)

        # Initial load
        self._refresh()

    def _refresh(self):
        threading.Thread(target=self._scan_vault, daemon=True).start()
        self._load_device_history()

    def _scan_vault(self):
        vault = AppConfig.VAULT_DIR
        projects = []

        if not vault.exists():
            self._signals.refreshed.emit([])
            return

        try:
            for entry in sorted(vault.iterdir()):
                if not entry.is_dir():
                    continue
                if entry.name.startswith('.'):
                    continue

                info = {
                    "name": entry.name,
                    "path": str(entry),
                    "size": 0,
                    "files": 0,
                    "last_sync": "—",
                    "status": "🟡",
                    "status_text": "غير معروف",
                }

                # Count files and size — ⚡ v4.0: scandir بدل rglob
                try:
                    import os as _os
                    _stack = [str(entry)]
                    while _stack:
                        _d = _stack.pop()
                        try:
                            with _os.scandir(_d) as _entries:
                                for _e in _entries:
                                    if _e.is_file(follow_symlinks=False):
                                        info["files"] += 1
                                        try:
                                            info["size"] += _e.stat().st_size
                                        except OSError:
                                            pass
                                    elif _e.is_dir(follow_symlinks=False):
                                        if not _e.name.startswith('.'):
                                            _stack.append(_e.path)
                        except OSError:
                            pass
                except Exception:
                    pass

                # Read sync meta
                meta_file = entry / ".ayadsync_meta.json"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding='utf-8'))
                        last = meta.get("last_sync", "")
                        if last:
                            dt = datetime.fromisoformat(last)
                            diff = datetime.now() - dt
                            if diff.days == 0:
                                info["last_sync"] = f"اليوم {dt.strftime('%H:%M')}"
                            elif diff.days == 1:
                                info["last_sync"] = "أمس"
                            elif diff.days < 7:
                                info["last_sync"] = f"منذ {diff.days} أيام"
                            else:
                                info["last_sync"] = dt.strftime("%Y-%m-%d")

                            pc = meta.get("pc_name", "")
                            copied = meta.get("copied", 0)
                            failed = meta.get("failed", 0)

                            if failed > 0:
                                info["status"] = "⚠️"
                                info["status_text"] = f"أخطاء: {failed}"
                            elif diff.days > 7:
                                info["status"] = "🟡"
                                info["status_text"] = "قديم"
                            else:
                                info["status"] = "✅"
                                info["status_text"] = "جيد"

                            if pc:
                                info["status_text"] += f" ({pc})"
                    except Exception:
                        pass
                else:
                    info["status"] = "🔴"
                    info["status_text"] = "بدون meta"

                projects.append(info)

        except OSError:
            pass

        self._signals.refreshed.emit(projects)

    def _populate(self, projects: list):
        self._tree.clear()

        total_size = 0
        total_files = 0

        for p in projects:
            size_mb = p["size"] / (1024 * 1024)
            total_size += p["size"]
            total_files += p["files"]

            if size_mb >= 1024:
                size_str = f"{size_mb / 1024:.1f} GB"
            else:
                size_str = f"{size_mb:.1f} MB"

            item = QTreeWidgetItem([
                f"  {p['name']}",
                f" {p['status']} {p['status_text']} ",
                f" {size_str} ",
                f" {p['last_sync']} ",
                f" {p['files']:,} ",
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, p["path"])

            # Color the status
            if p["status"] == "✅":
                item.setForeground(1, QColor(Theme.SUCCESS))
            elif p["status"] == "⚠️":
                item.setForeground(1, QColor(Theme.WARNING))
            elif p["status"] == "🔴":
                item.setForeground(1, QColor(Theme.ERROR))

            self._tree.addTopLevelItem(item)

        # Update space info
        self._update_space_info(total_size, total_files, len(projects))

    def _update_space_info(self, used: int, files: int, projects: int):
        vault = AppConfig.VAULT_DIR
        self._path_lbl.setText(f"📁  {vault}")

        try:
            if vault.exists():
                usage = shutil.disk_usage(vault)
                free_gb = usage.free / (1024 ** 3)
                total_gb = usage.total / (1024 ** 3)
                used_pct = int(usage.used / max(usage.total, 1) * 100)

                self._space_lbl.setText(
                    f"💾 {free_gb:.1f} GB حر / {total_gb:.0f} GB"
                )
                self._space_bar.setValue(used_pct)

                color = Theme.SUCCESS if used_pct < 70 else (Theme.WARNING if used_pct < 90 else Theme.ERROR)
                self._space_bar.setStyleSheet(
                    f"QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}"
                )
            else:
                self._space_lbl.setText(Lang.t("drv_not_connected"))
                self._space_bar.setValue(0)
        except OSError:
            self._space_lbl.setText("—")

        spd = AppConfig.USB_SPEED_MBS
        if spd > 0:
            icon = "🟢" if spd >= 100 else ("🟡" if spd >= 30 else "🔴")
            self._speed_lbl.setText(f"⚡ {icon} {spd:.0f} MB/s")
        else:
            self._speed_lbl.setText("⚡ —")

        used_mb = used / (1024 * 1024)
        self._status.setText(
            f"📊 {projects} مشروع | {files:,} ملف | {used_mb:,.0f} MB مستخدم"
        )

    def _zip_and_open_drive(self):
        """
        ⚡ v4.0: ضغط المشروع ZIP + فتح Google Drive.
        تحسينات: تقدير الحجم قبل الضغط، شريط تقدم، اختيار مجلد الحفظ.
        """
        item = self._tree.currentItem()
        if item:
            folder = item.data(0, Qt.ItemDataRole.UserRole)
        else:
            folder = QFileDialog.getExistingDirectory(self, "اختر مجلد المشروع لضغطه ورفعه")
        
        if not folder:
            QMessageBox.information(self, "💡", "اختر مشروعاً من القائمة أو اضغط لاختيار مجلد")
            return
        
        src = Path(folder)
        if not src.exists():
            QMessageBox.warning(self, "⚠️", f"المجلد غير موجود:\n{src}")
            return

        # ⚡ v4.0: تقدير الحجم أولاً
        total_size = 0
        total_files = 0
        try:
            import os as _os
            for root_dir, dirs, files in _os.walk(src):
                for f in files:
                    try:
                        total_size += _os.path.getsize(_os.path.join(root_dir, f))
                        total_files += 1
                    except OSError:
                        pass
        except Exception:
            pass

        size_mb = total_size / (1024 * 1024)
        est_zip = size_mb * 0.4   # تقدير تقريبي: 40% من الأصل

        # ⚡ v4.0: اسأل المستخدم قبل الضغط
        reply = QMessageBox.question(
            self, "📦 ضغط ورفع",
            f"المشروع: {src.name}\n"
            f"الحجم: {size_mb:.1f} MB ({total_files:,} ملف)\n"
            f"الحجم المقدّر بعد الضغط: ~{est_zip:.0f} MB\n\n"
            f"هل تريد ضغطه وفتح Google Drive للرفع؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._status.setText(f"📦 جاري ضغط {src.name} ({total_files:,} ملف)...")
        threading.Thread(
            target=self._worker_zip_drive,
            args=(src, total_files),
            daemon=True,
        ).start()

    def _worker_zip_drive(self, src: Path, total_files: int = 0):
        import zipfile
        import webbrowser
        import subprocess
        from datetime import datetime
        
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            out = AppConfig.VAULT_DIR / f"{src.name}_{ts}.zip"
            out.parent.mkdir(parents=True, exist_ok=True)
            
            self._signals.log_line.emit(f"📦 ضغط {src.name}...")
            
            files_count = 0
            excluded = AppConfig.EXCLUDED_NAMES
            excluded_dirs = AppConfig.EXCLUDED_DIRS
            
            with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                for item in sorted(src.rglob('*')):
                    # ⚡ v4.0: تخطي المجلدات المستثناة
                    skip = False
                    for parent in item.parents:
                        if parent.name in excluded_dirs:
                            skip = True
                            break
                    if skip or item.name in excluded:
                        continue
                        
                    rel = item.relative_to(src.parent)
                    if item.is_file():
                        zf.write(item, rel)
                        files_count += 1
                        if files_count % 500 == 0:
                            pct = int(files_count / max(total_files, 1) * 100)
                            self._signals.log_line.emit(
                                f"  📦 {files_count:,} ملف ({pct}%)..."
                            )
                    elif item.is_dir():
                        dir_entry = str(rel).replace('\\', '/') + '/'
                        zi = zipfile.ZipInfo(dir_entry)
                        zi.external_attr = 0o40755 << 16
                        zf.writestr(zi, '')
            
            size_mb = out.stat().st_size / (1024 * 1024)
            self._signals.log_line.emit(
                f"✅ {out.name} ({size_mb:.1f} MB — {files_count:,} ملف)"
            )
            
            # ① فتح مجلد ZIP
            import sys as _sys
            try:
                if _sys.platform == 'win32':
                    subprocess.run(
                        ['explorer', '/select,', str(out.resolve())],
                        shell=False, timeout=5
                    )
                elif _sys.platform == 'darwin':
                    subprocess.run(['open', '-R', str(out)], timeout=5)
                else:
                    subprocess.run(['xdg-open', str(out.parent)], timeout=5)
            except Exception:
                pass
            
            # ② فتح Google Drive
            webbrowser.open("https://drive.google.com/drive/my-drive")
            self._signals.log_line.emit(
                "🌐 Google Drive مفتوح — اسحب ملف ZIP لرفعه"
            )
            self._signals.log_line.emit(
                f"📁 مسار الملف: {out}"
            )
            
        except Exception as e:
            self._signals.log_line.emit(f"❌ خطأ في الضغط: {e}")

    def _open_selected(self):
        item = self._tree.currentItem()
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            import subprocess, sys
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])

    def _explore_vault(self):
        import subprocess, sys
        path = str(AppConfig.VAULT_DIR)
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def _delete_selected(self):
        item = self._tree.currentItem()
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        name = Path(path).name if path else "?"

        reply = QMessageBox.question(
            self, "⚠️ تأكيد الحذف",
            f"هل تريد حذف النسخة الاحتياطية:\n\n{name}\n\nلا يمكن التراجع!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(path, ignore_errors=True)
                self._refresh()
            except Exception as e:
                QMessageBox.critical(self, "خطأ", str(e))

    def _change_vault(self):
        folder = QFileDialog.getExistingDirectory(self, Lang.t("drv_change_folder"))
        if folder:
            AppConfig.VAULT_DIR = Path(folder)
            self._path_lbl.setText(f"📁  {folder}")
            self._refresh()
            # Calibrate USB speed
            threading.Thread(
                target=AppConfig.calibrate_usb,
                args=(Path(folder),),
                daemon=True,
            ).start()

    def _load_device_history(self):
        """تحميل سجل الأجهزة من pc_names.json."""
        self._dev_tree.clear()

        registry_file = AppConfig.DATA_DIR / "pc_names.json"
        if not registry_file.exists():
            # Try to build from meta files
            self._build_registry_from_meta()
            if not registry_file.exists():
                item = QTreeWidgetItem([Lang.t("drv_no_history"), "—", "—", "زامِن مشروعاً لبدء التتبع"])
                item.setForeground(0, QColor(Theme.TEXT_DIM))
                self._dev_tree.addTopLevelItem(item)
                return

        try:
            import json
            registry = json.loads(registry_file.read_text(encoding="utf-8"))

            for pc_name, info in sorted(registry.items(), key=lambda x: x[1].get("last_sync", ""), reverse=True):
                last = info.get("last_sync", "—")
                count = info.get("sync_count", 0)
                projects = info.get("projects", [])

                # Format last sync time
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(last)
                    diff = datetime.now() - dt
                    if diff.days == 0:
                        if diff.seconds < 3600:
                            last_str = f"منذ {diff.seconds // 60} دقيقة"
                        else:
                            last_str = f"منذ {diff.seconds // 3600} ساعة"
                    elif diff.days == 1:
                        last_str = "أمس"
                    elif diff.days < 30:
                        last_str = f"منذ {diff.days} يوم"
                    else:
                        last_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    last_str = last[:16] if len(last) > 16 else last

                # Is this the current device?
                is_current = (pc_name == AppConfig.PC_NAME)
                icon = "💻" if is_current else "🖥️"
                _lbl  = Lang.t('drv_this_device')
                _this = f' {_lbl}' if is_current else ''
                label = f"{icon}  {pc_name}" + _this

                proj_names = ", ".join(p.get("name", "?") for p in projects[:5])
                if len(projects) > 5:
                    proj_names += f" +{len(projects)-5}"

                parent_item = QTreeWidgetItem([
                    label,
                    f" {last_str} ",
                    f" {count:,} ",
                    f" {proj_names} ",
                ])

                if is_current:
                    parent_item.setForeground(0, QColor(Theme.ACCENT2))

                # Child items: each project
                for proj in projects[:10]:
                    p_name = proj.get("name", "?")
                    p_last = proj.get("last_sync", "—")
                    try:
                        p_dt = datetime.fromisoformat(p_last)
                        p_last_str = p_dt.strftime("%m-%d %H:%M")
                    except Exception:
                        p_last_str = p_last[:16]

                    child = QTreeWidgetItem([f"  📁 {p_name}", p_last_str, "", ""])
                    child.setForeground(0, QColor(Theme.TEXT_DIM))
                    parent_item.addChild(child)

                self._dev_tree.addTopLevelItem(parent_item)

            # Expand current device
            for i in range(self._dev_tree.topLevelItemCount()):
                item = self._dev_tree.topLevelItem(i)
                if "هذا الجهاز" in item.text(0):
                    item.setExpanded(True)

        except Exception:
            item = QTreeWidgetItem(["خطأ في قراءة السجل", "—", "—", ""])
            item.setForeground(0, QColor(Theme.ERROR))
            self._dev_tree.addTopLevelItem(item)

    def _build_registry_from_meta(self):
        """يبني سجل الأجهزة من .ayadsync_meta.json الموجودة في الباكاب."""
        import json
        vault = AppConfig.VAULT_DIR
        if not vault.exists():
            return

        registry = {}
        try:
            for entry in vault.iterdir():
                if not entry.is_dir():
                    continue
                meta_file = entry / ".ayadsync_meta.json"
                if not meta_file.exists():
                    continue
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    pc = meta.get("pc_name", "")
                    if not pc:
                        continue
                    last = meta.get("last_sync", "")

                    if pc not in registry:
                        registry[pc] = {
                            "first_seen": last,
                            "last_sync": last,
                            "sync_count": 1,
                            "projects": [],
                        }
                    else:
                        if last > registry[pc]["last_sync"]:
                            registry[pc]["last_sync"] = last
                        registry[pc]["sync_count"] += 1

                    registry[pc]["projects"].append({
                        "name": entry.name,
                        "last_sync": last,
                    })
                except Exception:
                    pass

            if registry:
                reg_file = AppConfig.DATA_DIR / "pc_names.json"
                reg_file.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _on_log(self, msg):
        pass

    def retranslateUi(self):
        """يُحدّث نصوص drive_panel — يُعيد تحميل القائمة."""
        self._refresh()

