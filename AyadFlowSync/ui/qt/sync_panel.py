#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.qt.sync_panel
================
لوحة المزامنة — Backup / Restore / Full Sync / Verify
"""

import threading
from pathlib import Path
from typing import Optional, List

from ...lang.lang            import Lang
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QProgressBar,
    QFrame, QFileDialog, QMessageBox, QSplitter, QSizePolicy,
    QDialog, QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt6.QtCore    import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui     import QColor, QFont, QIcon

from ...core.app_config import AppConfig
from ...core.device_profiler import DeviceProfiler


class SyncSignals(QObject):
    log_line    = pyqtSignal(str)
    progress    = pyqtSignal(int, int)   # current, total
    status_msg  = pyqtSignal(str)
    done        = pyqtSignal(bool)       # success


class SyncPanel(QWidget):
    """
    لوحة المزامنة الكاملة:
    - قائمة المشاريع
    - مجلد الفلاشة/النسخ الاحتياطي
    - أزرار العمليات
    - سجل حي
    - شريط تقدم
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._signals    = SyncSignals()
        self._syncing    = False
        self._sync_lock  = threading.Lock()
        self._projects:  List[str] = []
        self._engine_ref = None

        self._signals.log_line.connect(self._append_log)
        self._signals.progress.connect(self._update_progress)
        self._signals.status_msg.connect(self._update_status)
        self._signals.done.connect(self._on_done)

        self._build_ui()
        self._load_projects()
        
        # Auto-refresh project status every 30 seconds
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_list)
        self._refresh_timer.start(30_000)

    # ── بناء الواجهة ──────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # ── الجانب الأيسر: المشاريع + العمليات ──────────────────
        left = QWidget()
        left.setFixedWidth(280)
        left_ly = QVBoxLayout(left)
        left_ly.setContentsMargins(12, 12, 8, 12)
        left_ly.setSpacing(8)

        # -- عنوان
        self._projects_title = QLabel(Lang.t("projects_title"))
        self._projects_title.setObjectName("SectionTitle")
        left_ly.addWidget(self._projects_title)

        # -- قائمة المشاريع
        self._proj_list = QListWidget()
        self._proj_list.setObjectName("ProjectList")
        self._proj_list.currentRowChanged.connect(self._on_project_selected)
        left_ly.addWidget(self._proj_list, 1)

        # -- أزرار المشاريع
        proj_btns = QHBoxLayout()
        proj_btns.setSpacing(4)

        self._btn_add = QPushButton(Lang.t("add_project"))
        self._btn_add.clicked.connect(self._add_project)
        self._btn_rem = QPushButton(Lang.t("remove_project"))
        self._btn_rem.clicked.connect(self._remove_project)

        proj_btns.addWidget(self._btn_add)
        proj_btns.addWidget(self._btn_rem)
        left_ly.addLayout(proj_btns)

        # -- فاصل
        left_ly.addWidget(self._sep())

        # -- مجلد الفلاشة
        self._vault_title_lbl = QLabel(Lang.t("vault_title"))
        self._vault_title_lbl.setObjectName("SectionTitle")
        left_ly.addWidget(self._vault_title_lbl)

        vault_row = QHBoxLayout()
        vault_row.setSpacing(4)
        self._vault_lbl = QLabel("—")
        self._vault_lbl.setObjectName("Dim")
        self._vault_lbl.setWordWrap(True)
        self._vault_lbl.setMaximumWidth(170)
        vault_row.addWidget(self._vault_lbl, 1)
        btn_vault = QPushButton("📂")
        btn_vault.setFixedWidth(36)
        btn_vault.setToolTip(Lang.t("vault_title"))
        btn_vault.clicked.connect(self._choose_vault)
        vault_row.addWidget(btn_vault)
        left_ly.addLayout(vault_row)

        # -- فاصل
        left_ly.addWidget(self._sep())

        # -- أزرار العمليات
        self._ops_title_lbl = QLabel(Lang.t("ops_title"))
        self._ops_title_lbl.setObjectName("SectionTitle")
        left_ly.addWidget(self._ops_title_lbl)

        self._btn_backup = QPushButton(Lang.t("btn_backup"))
        self._btn_backup.setObjectName("PrimaryBtn")
        self._btn_backup.clicked.connect(lambda: self._run_op("backup"))
        left_ly.addWidget(self._btn_backup)

        self._btn_restore = QPushButton(Lang.t("btn_restore"))
        self._btn_restore.setObjectName("SuccessBtn")
        self._btn_restore.clicked.connect(lambda: self._run_op("restore"))
        left_ly.addWidget(self._btn_restore)

        self._btn_sync = QPushButton(Lang.t("btn_smart_sync"))
        self._btn_sync.setObjectName("WarnBtn")
        self._btn_sync.setToolTip(Lang.t("btn_smart_sync"))
        self._btn_sync.clicked.connect(self._open_smart_sync_dialog)
        left_ly.addWidget(self._btn_sync)

        self._btn_verify = QPushButton(Lang.t("btn_verify"))
        self._btn_verify.clicked.connect(lambda: self._run_op("verify"))
        left_ly.addWidget(self._btn_verify)

        self._btn_stop = QPushButton(Lang.t("btn_stop"))
        self._btn_stop.setObjectName("DangerBtn")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_op)
        left_ly.addWidget(self._btn_stop)

        # ── فاصل ──────────────────────────────────────────────
        left_ly.addWidget(self._sep())

        self._btn_trash = QPushButton(Lang.t("btn_trash"))
        self._btn_trash.setObjectName("Muted")
        self._btn_trash.setToolTip(Lang.t("btn_trash"))
        self._btn_trash.clicked.connect(self._open_trash_dialog)
        left_ly.addWidget(self._btn_trash)

        # -- معلومات الجهاز
        self._device_info = QLabel()
        self._device_info.setObjectName("Muted")
        self._device_info.setWordWrap(True)
        left_ly.addWidget(self._device_info)
        self._refresh_device_info()

        splitter.addWidget(left)

        # ── الجانب الأيمن: السجل + التقدم ──────────────────────
        right = QWidget()
        right_ly = QVBoxLayout(right)
        right_ly.setContentsMargins(8, 12, 12, 12)
        right_ly.setSpacing(8)

        # -- عنوان السجل
        log_header = QHBoxLayout()
        self._log_title_lbl = QLabel(Lang.t("log_title"))
        self._log_title_lbl.setObjectName("SectionTitle")
        log_header.addWidget(self._log_title_lbl)
        log_header.addStretch()
        btn_clear = QPushButton("🗑️")
        btn_clear.setFixedSize(28, 28)
        btn_clear.setToolTip(Lang.t("clear_log"))
        btn_clear.clicked.connect(self._clear_log)
        log_header.addWidget(btn_clear)
        right_ly.addLayout(log_header)

        # -- صندوق السجل
        self._log_box = QTextEdit()
        self._log_box.setObjectName("LogBox")
        self._log_box.setReadOnly(True)
        self._log_box.setFont(QFont("Cascadia Code", 14))
        right_ly.addWidget(self._log_box, 1)

        # -- شريط التقدم
        prog_row = QHBoxLayout()
        self._prog_bar = QProgressBar()
        self._prog_bar.setRange(0, 100)
        self._prog_bar.setValue(0)
        self._prog_bar.setTextVisible(True)
        self._prog_bar.setFormat("%p%  (%v / %m)")
        self._prog_bar.setFixedHeight(22)
        prog_row.addWidget(self._prog_bar)

        self._status_lbl = QLabel(Lang.t("status_ready"))
        self._status_lbl.setObjectName("Dim")
        self._status_lbl.setFixedWidth(160)
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog_row.addWidget(self._status_lbl)
        right_ly.addLayout(prog_row)

        splitter.addWidget(right)
        splitter.setSizes([280, 700])

        root.addWidget(splitter)

        # -- vault label تحديث
        self._vault_lbl.setText(str(AppConfig.VAULT_DIR))


    def retranslateUi(self):
        """يُحدّث كل نصوص الواجهة عند تغيير اللغة — فوري."""
        self._projects_title.setText(Lang.t("projects_title"))
        self._btn_add.setText(Lang.t("add_project"))
        self._btn_rem.setText(Lang.t("remove_project"))
        self._vault_title_lbl.setText(Lang.t("vault_title"))
        self._ops_title_lbl.setText(Lang.t("ops_title"))
        self._btn_backup.setText(Lang.t("btn_backup"))
        self._btn_restore.setText(Lang.t("btn_restore"))
        self._btn_sync.setText(Lang.t("btn_smart_sync"))
        self._btn_verify.setText(Lang.t("btn_verify"))
        self._btn_stop.setText(Lang.t("btn_stop"))
        self._btn_trash.setText(Lang.t("btn_trash"))
        self._log_title_lbl.setText(Lang.t("log_title"))
        if not self._syncing:
            self._status_lbl.setText(Lang.t("status_ready"))

    # ── مساعدات البناء ────────────────────────────────────────────
    def _sep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        return f

    # ── المشاريع ──────────────────────────────────────────────────
    def _load_projects(self):
        """⚡ v4.0: تحميل مشاريع هذا الحاسوب فقط — لا هجرة تلقائية."""
        from ...db.database import DatabaseManager
        try:
            db = DatabaseManager(AppConfig.CONFIG_FILE)
            pc = AppConfig.PC_NAME or "default"
            self._projects = db.get(f"projects_{pc}", [])
        except Exception:
            self._projects = []
        self._refresh_list()

    def _refresh_list(self):
        self._proj_list.clear()
        for p in self._projects:
            pp = Path(p)
            if not pp.exists():
                icon, status = "⚠️", "غير موجود"
            else:
                icon, status = self._check_project_status(pp)
            name = pp.name
            item = QListWidgetItem(f"{icon}  {name}  [{status}]")
            item.setToolTip(f"{p}\n{status}")
            self._proj_list.addItem(item)

    def _check_project_status(self, project: Path) -> tuple:
        """فحص حالة المشروع مقارنة بالنسخة الاحتياطية."""
        backup = AppConfig.VAULT_DIR / project.name
        if not backup.exists():
            return "🔴", "لم يُزامَن بعد"
        
        # Check sync meta
        meta_file = backup / ".ayadsync_meta.json"
        if not meta_file.exists():
            return "🟡", "يحتاج مزامنة"
        
        try:
            import json, os
            meta = json.loads(meta_file.read_text(encoding='utf-8'))
            last_sync = meta.get("last_sync", "")
            
            if last_sync:
                from datetime import datetime
                dt = datetime.fromisoformat(last_sync)
                diff = datetime.now() - dt
                
                if diff.days == 0:
                    if diff.seconds < 3600:
                        time_str = f"منذ {diff.seconds // 60} دقيقة"
                    else:
                        time_str = f"منذ {diff.seconds // 3600} ساعة"
                elif diff.days == 1:
                    time_str = "أمس"
                else:
                    time_str = f"منذ {diff.days} يوم"
                
                # ⚡ v4.0: فحص سريع بـ scandir — يفحص المجلدات أولاً
                # بدل rglob على 200,000 ملف → scandir على المجلدات المباشرة
                sync_time = dt.timestamp()
                has_newer = False
                
                # المرحلة 1: فحص المجلدات المباشرة — سريع جداً
                try:
                    with os.scandir(project) as entries:
                        for entry in entries:
                            if entry.name in AppConfig.EXCLUDED_NAMES:
                                continue
                            try:
                                if entry.stat().st_mtime > sync_time:
                                    has_newer = True
                                    break
                            except OSError:
                                pass
                except OSError:
                    pass
                
                # المرحلة 2: لو ما لقينا شيء، فحص سريع بـ scandir عودي (حد 200)
                if not has_newer:
                    _excl = AppConfig.EXCLUDED_NAMES
                    _excl_dirs = AppConfig.EXCLUDED_DIRS
                    _checked = 0
                    _stack = [project]
                    while _stack and _checked < 200 and not has_newer:
                        d = _stack.pop()
                        try:
                            with os.scandir(d) as entries:
                                for entry in entries:
                                    if entry.name in _excl:
                                        continue
                                    if entry.is_dir(follow_symlinks=False):
                                        if entry.name not in _excl_dirs:
                                            _stack.append(Path(entry.path))
                                    elif entry.is_file(follow_symlinks=False):
                                        _checked += 1
                                        try:
                                            if entry.stat().st_mtime > sync_time:
                                                has_newer = True
                                                break
                                        except OSError:
                                            pass
                        except OSError:
                            pass
                
                if has_newer:
                    return "🔶", f"تغييرات جديدة ({time_str})"
                else:
                    return "✅", f"متزامن ({time_str})"
            
            return "🟡", "يحتاج فحص"
        except Exception:
            return "🟡", "يحتاج مزامنة"

    def _add_project(self):
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلد المشروع")
        if folder and folder not in self._projects:
            self._projects.append(folder)
            self._save_projects()
            self._refresh_list()
            name = Path(folder).name
            # ⚡ v4.0: كشف المشروع المشترك
            backup = AppConfig.VAULT_DIR / name
            if backup.exists():
                meta = backup / ".ayadsync_meta.json"
                if meta.exists():
                    try:
                        import json
                        d = json.loads(meta.read_text(encoding='utf-8'))
                        src_pc = d.get("pc_name", "")
                        if src_pc and src_pc != AppConfig.PC_NAME:
                            self.log(f"✅ أُضيف المشروع: {name} (مشترك مع {src_pc})")
                            return
                    except Exception:
                        pass
            self.log(f"✅ أُضيف المشروع: {name}")

    def _remove_project(self):
        row = self._proj_list.currentRow()
        if row < 0:
            return
        name = Path(self._projects[row]).name
        if QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل تريد إزالة المشروع:\n{name}\nمن القائمة؟\n(لن يُحذف الملف الفعلي)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self._projects.pop(row)
            self._save_projects()
            self._refresh_list()
            self.log(f"🗑️ تم حذف المشروع: {name}")

    def _save_projects(self):
        """⚡ v4.0: حفظ مشاريع هذا الحاسوب فقط."""
        from ...db.database import DatabaseManager
        try:
            db = DatabaseManager(AppConfig.CONFIG_FILE)
            pc = AppConfig.PC_NAME or "default"
            db.set(f"projects_{pc}", self._projects)
            db.save()
        except Exception:
            pass

    def _on_project_selected(self, row: int):
        if 0 <= row < len(self._projects):
            p = Path(self._projects[row])
            self._status_lbl.setText(f"📁 {p.name}")

    def _choose_vault(self):
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلد النسخ الاحتياطي")
        if folder:
            AppConfig.VAULT_DIR = Path(folder)
            self._vault_lbl.setText(folder)
            self.log(f"💾 مجلد النسخ الاحتياطي: {folder}")
            # قياس سرعة USB في الخلفية
            threading.Thread(
                target=AppConfig.calibrate_usb,
                args=(Path(folder),),
                daemon=True
            ).start()

    # ── العمليات ──────────────────────────────────────────────────
    def _run_op(self, op: str):
        if self._syncing:
            QMessageBox.warning(self, "تحذير", Lang.t("warn_syncing"))
            return

        row = self._proj_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تحذير", Lang.t("warn_select_project"))
            return

        if not AppConfig.VAULT_DIR.exists():
            QMessageBox.warning(self, "تحذير", Lang.t("warn_vault_missing"))
            return

        project_path = Path(self._projects[row])
        if not project_path.exists():
            QMessageBox.warning(self, "خطأ", f"مجلد المشروع غير موجود:\n{project_path}")
            return

        self._set_syncing(True)
        self._prog_bar.setValue(0)
        self._prog_bar.setRange(0, 0)  # indeterminate
        self.log(f"\n{'='*50}")
        self.log(f"▶️  بدء {op} — {project_path.name}")
        self.log(f"{'='*50}")

        t = threading.Thread(
            target=self._worker,
            args=(op, project_path),
            daemon=True
        )
        t.start()

    def _worker(self, op: str, project: Path):
        """Worker thread — لا يلمس الـ UI مباشرةً."""
        success = False
        try:
            from ...sync.engine import SyncEngine
            engine = SyncEngine(
                log_cb=lambda m: self._signals.log_line.emit(m),
                progress_cb=lambda pct: self._signals.progress.emit(int(pct), 100),
            )
            self._engine_ref = engine

            if op == "backup":
                engine.backup(project, AppConfig.VAULT_DIR / project.name)
            elif op == "restore":
                engine.restore(AppConfig.VAULT_DIR / project.name, project)
            elif op == "full_sync":
                engine.full_sync(project, AppConfig.VAULT_DIR / project.name)
            elif op == "verify":
                engine.verify(project, AppConfig.VAULT_DIR / project.name)

            success = True

        except Exception as e:
            import traceback
            self._signals.log_line.emit(f"❌ خطأ: {e}")
            self._signals.log_line.emit(traceback.format_exc())
        finally:
            # ✅ يُضمن دائماً — حتى عند أي استثناء غير متوقع
            self._signals.done.emit(success)

    def _stop_op(self):
        self.log("⏹  طلب الإيقاف...")
        if hasattr(self, '_engine_ref') and self._engine_ref:
            self._engine_ref.cancel()
        self._set_syncing(False)

    # ── Callbacks من Worker ────────────────────────────────────────
    def _append_log(self, msg: str):
        self._log_box.append(msg)
        # تمرير للأسفل تلقائياً
        sb = self._log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _update_progress(self, current: int, total: int):
        if total > 0:
            self._prog_bar.setRange(0, total)
            self._prog_bar.setValue(current)
            pct = int(current / total * 100)
            self._status_lbl.setText(f"{pct}% ({current}/{total})")

    def _update_status(self, msg: str):
        self._status_lbl.setText(msg)

    def _on_done(self, success: bool):
        self._set_syncing(False)
        self._prog_bar.setRange(0, 100)
        self._prog_bar.setValue(100 if success else 0)
        icon = "✅" if success else "❌"
        self._status_lbl.setText(f"{icon} {'اكتمل' if success else 'فشل'}")
        self.log(f"\n{icon} {'اكتملت العملية بنجاح' if success else 'فشلت العملية'}")

    # ── مساعدات ───────────────────────────────────────────────────
    def _set_syncing(self, state: bool):
        self._syncing = state
        for btn in [self._btn_backup, self._btn_restore,
                    self._btn_sync, self._btn_verify]:
            btn.setEnabled(not state)
        self._btn_stop.setEnabled(state)

    # ══════════════════════════════════════════════════════════════
    # 🧠 نافذة المزامنة الذكية
    # ══════════════════════════════════════════════════════════════
    def _open_smart_sync_dialog(self):
        """يفتح نافذة اختيار وضع المزامنة."""
        if self._syncing:
            QMessageBox.warning(self, "تحذير", Lang.t("warn_syncing"))
            return

        row = self._proj_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تحذير", Lang.t("warn_select_project"))
            return

        if not AppConfig.VAULT_DIR.exists():
            QMessageBox.warning(self, "تحذير", Lang.t("warn_vault_missing"))
            return

        project_path = Path(self._projects[row])
        if not project_path.exists():
            QMessageBox.warning(self, "خطأ", f"مجلد المشروع غير موجود:\n{project_path}")
            return

        usb_path = AppConfig.VAULT_DIR / project_path.name

        # ── بناء النافذة ──────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle(Lang.t("smart_sync_title"))
        dlg.setFixedWidth(480)
        dlg.setStyleSheet(self.styleSheet())

        ly = QVBoxLayout(dlg)
        ly.setContentsMargins(20, 20, 20, 20)
        ly.setSpacing(12)

        # عنوان
        title = QLabel(f"📁  {project_path.name}")
        title.setObjectName("SectionTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(title)

        info = QLabel(
            f"<b>جهاز:</b> {project_path}<br>"
            f"<b>فلاشة:</b> {usb_path}"
        )
        info.setObjectName("Dim")
        info.setWordWrap(True)
        ly.addWidget(info)

        # فاصل
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        ly.addWidget(sep)

        # ── الخيارات الثلاثة ──────────────────────────────────────
        self._sync_mode = [None]   # لحفظ الخيار المحدد

        def make_option(icon, title_text, desc, mode, obj_name):
            btn = QPushButton()
            btn.setObjectName(obj_name)
            btn.setMinimumHeight(64)
            btn.setText(f"{icon}  {title_text}\n{desc}")
            btn.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: 10px 14px; "
                f"font-size: 13px; border-radius: 8px; }} "
                f"QPushButton:hover {{ opacity: 0.85; }}"
            )
            btn.clicked.connect(lambda: (
                self._sync_mode.__setitem__(0, mode),
                dlg.accept()
            ))
            return btn

        ly.addWidget(make_option(
            "💻", "الجهاز هو الأصل",
            Lang.t("pc_master_desc"),
            "pc_master", "PrimaryBtn"
        ))

        ly.addWidget(make_option(
            "💾", "الفلاشة هي الأصل",
            Lang.t("usb_master_desc"),
            "usb_master", "SuccessBtn"
        ))

        ly.addWidget(make_option(
            "🔄", "مزامنة ثنائية الاتجاه",
            "ما يزيد في أي طرف يُضاف للطرف الآخر — لا حذف",
            "bidirectional", "WarnBtn"
        ))

        # إلغاء
        btn_cancel = QPushButton(Lang.t("cancel"))
        btn_cancel.clicked.connect(dlg.reject)
        ly.addWidget(btn_cancel)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if not self._sync_mode[0]:
            return

        mode = self._sync_mode[0]

        # تأكيد نهائي للأوضاع التي تحذف
        if mode in ("pc_master", "usb_master"):
            src_lbl = "الجهاز" if mode == "pc_master" else "الفلاشة"
            dst_lbl = "الفلاشة" if mode == "pc_master" else "الجهاز"
            if QMessageBox.question(
                self, "⚠️ تأكيد",
                f"سيُحذف كل ما يزيد في <b>{dst_lbl}</b> وينتقل للسلة.<br>"
                f"يمكن استرجاعه خلال {AppConfig.TRASH_KEEP_DAYS} يوم.<br><br>"
                f"هل تريد المتابعة؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes:
                return

        self._run_smart_sync(mode, project_path, usb_path)

    def _run_smart_sync(self, mode: str, project_path: Path, usb_path: Path):
        """يُشغّل المزامنة الذكية بالوضع المحدد."""
        labels = {
            "pc_master"     : Lang.t("pc_master_label"),
            "usb_master"    : Lang.t("usb_master_label"),
            "bidirectional" : Lang.t("bidir_label"),
        }
        self._set_syncing(True)
        self._prog_bar.setValue(0)
        self._prog_bar.setRange(0, 0)
        self.log(f"\n{'='*50}")
        self.log(f"▶️  {labels[mode]} — {project_path.name}")
        self.log(f"{'='*50}")

        t = threading.Thread(
            target=self._worker_smart,
            args=(mode, project_path, usb_path),
            daemon=True
        )
        t.start()

    def _worker_smart(self, mode: str, project: Path, usb: Path):
        """Worker للمزامنة الذكية — يعمل في thread خلفي."""
        success = False
        try:
            from ...sync.engine import SyncEngine
            from ...sync.copier import SafeTrash

            engine = SyncEngine(
                log_cb=lambda m: self._signals.log_line.emit(m),
                progress_cb=lambda pct: self._signals.progress.emit(int(pct), 100),
            )
            self._engine_ref = engine

            if mode == "bidirectional":
                engine.full_sync(project, usb)
            elif mode == "pc_master":
                engine.backup(project, usb)
                self._mirror_delete(src=project, dst=usb, label="USB", engine=engine)
            elif mode == "usb_master":
                engine.restore(usb, project)
                self._mirror_delete(src=usb, dst=project, label="PC", engine=engine)

            success = True

        except Exception as e:
            import traceback
            self._signals.log_line.emit(f"❌ خطأ: {e}")
            self._signals.log_line.emit(traceback.format_exc())
        finally:
            self._signals.done.emit(success)

    def _mirror_delete(self, src: Path, dst: Path,
                       label: str, engine):
        """
        ⚡ v4.0: يحذف من dst كل ملف لا يوجد في src.
        الحذف عبر SafeTrash — ينتقل للسلة لا يُمحى نهائياً.

        تحسينات v4.0:
        - os.scandir بدل rglob → أسرع 5-10x مع 200k ملف
        - يحترم EXCLUDED_DIRS + EXCLUDED_NAMES
        - path normalization: / دائماً (Windows + Linux)
        - تنظيف المجلدات الفارغة بعد الحذف
        - الملفات الفارغة (0 بايت) تُعامَل مثل أي ملف
        """
        import os
        from ...sync.copier import SafeTrash
        from ...core.app_config import AppConfig

        if not dst.exists():
            return

        excl_names = AppConfig.EXCLUDED_NAMES
        excl_dirs  = AppConfig.EXCLUDED_DIRS

        def _norm(p: Path, base: Path) -> str:
            """مسار نسبي مُوحَّد: / دائماً"""
            return str(p.relative_to(base)).replace('\\', '/')

        # ── جمع ملفات المصدر بـ scandir (سريع) ──
        src_files: set = set()

        def _collect_src(directory: Path):
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.name in excl_names:
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name in excl_dirs:
                                continue
                            _collect_src(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            src_files.add(_norm(Path(entry.path), src))
            except (OSError, PermissionError):
                pass

        _collect_src(src)

        # ── جمع ملفات الوجهة وإيجاد الزائد ──
        extra: list = []

        def _collect_dst_extra(directory: Path):
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.name in excl_names:
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name in excl_dirs:
                                continue
                            _collect_dst_extra(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            p = Path(entry.path)
                            rel = _norm(p, dst)
                            if rel not in src_files:
                                extra.append(p)
            except (OSError, PermissionError):
                pass

        _collect_dst_extra(dst)

        if not extra:
            self._signals.log_line.emit("✅ لا ملفات زائدة في الوجهة")
            return

        self._signals.log_line.emit(
            f"🗑️  نقل {len(extra)} ملف زائد للسلة ({label})..."
        )

        # ── حذف Batch عبر SafeTrash ──
        SafeTrash.begin_batch(label)
        moved = failed = 0
        for f in extra:
            if SafeTrash.move_to_trash(f, source_label=label):
                moved += 1
            else:
                failed += 1
                self._signals.log_line.emit(f"  ⚠️ فشل نقل: {f.name}")
        SafeTrash.flush_batch()

        # ── تنظيف المجلدات الفارغة بعد الحذف ──
        _cleaned_dirs = 0
        for dirpath, dirnames, filenames in os.walk(str(dst), topdown=False):
            dp = Path(dirpath)
            if dp == dst:
                continue
            try:
                if not any(dp.iterdir()):
                    dp.rmdir()
                    _cleaned_dirs += 1
            except OSError:
                pass

        self._signals.log_line.emit(
            f"✅ نُقل {moved} ملف للسلة"
            + (f" | ⚠️ {failed} فشل" if failed else "")
            + (f" | 📁 {_cleaned_dirs} مجلد فارغ حُذف" if _cleaned_dirs else "")
            + f"  ← قابل للاسترجاع {AppConfig.TRASH_KEEP_DAYS} يوماً"
        )

    # ══════════════════════════════════════════════════════════════
    # 🗑️ نافذة سلة المهملات
    # ══════════════════════════════════════════════════════════════
    def _open_trash_dialog(self):
        """⚡ v4.1: نافذة سلة محذوفات احترافية — مُجمّعة بالجلسة."""
        from ...sync.copier import SafeTrash
        from ...core.constants import fmt_size

        dlg = QDialog(self)
        dlg.setWindowTitle(Lang.t("trash_title"))
        dlg.resize(750, 520)
        dlg.setStyleSheet(self.styleSheet())

        ly = QVBoxLayout(dlg)
        ly.setContentsMargins(16, 16, 16, 16)
        ly.setSpacing(8)

        # ── Header ──
        hdr = QHBoxLayout()
        title = QLabel("🗑️")
        title.setObjectName("SectionTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        total_size_lbl = QLabel("")
        total_size_lbl.setStyleSheet("color: #666; font-size: 11px;")
        hdr.addWidget(total_size_lbl)
        btn_empty = QPushButton(Lang.t("trash_empty_btn"))
        btn_empty.setObjectName("DangerBtn")
        hdr.addWidget(btn_empty)
        ly.addLayout(hdr)

        info = QLabel(
            f"الملفات تُحفظ {AppConfig.TRASH_KEEP_DAYS} يوماً قبل الحذف النهائي التلقائي. "
            f"اختر جلسة أو ملف → استرجع."
        )
        info.setStyleSheet("color: #666; font-size: 10px;")
        info.setWordWrap(True)
        ly.addWidget(info)

        # ── Tree — مُجمّع بالجلسة ──
        from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QHeaderView
        tree = QTreeWidget()
        tree.setHeaderLabels([
            Lang.t("trash_col_file"),
            Lang.t("trash_col_source"),
            Lang.t("trash_col_size"),
            Lang.t("trash_col_date")
        ])
        tree.setRootIsDecorated(True)
        tree.setAlternatingRowColors(True)
        tree.setSortingEnabled(False)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        ly.addWidget(tree, 1)

        def _refresh():
            tree.clear()
            entries = SafeTrash.list_items()

            # تجميع بالجلسة (session = تاريخ + مصدر)
            from collections import OrderedDict
            sessions = OrderedDict()
            for e in entries:
                ts = e.get("deleted_at", "")[:19]
                src = e.get("source", "?")
                # مفتاح الجلسة = الدقيقة + المصدر
                session_key = ts[:16] + "|" + src
                if session_key not in sessions:
                    sessions[session_key] = []
                sessions[session_key].append(e)

            total_files = 0
            total_bytes = 0

            for session_key, items in sessions.items():
                ts_part, src_part = session_key.split("|", 1)
                date_str = ts_part.replace("T", " ")
                count = len(items)
                session_size = sum(e.get("size", 0) for e in items)
                total_files += count
                total_bytes += session_size

                # عقدة الجلسة
                session_node = QTreeWidgetItem([
                    f"📂 {count} ملف",
                    src_part,
                    fmt_size(session_size),
                    date_str
                ])
                session_node.setExpanded(False)
                # لون مميز للجلسة
                from PyQt6.QtGui import QColor as _QC
                for col in range(4):
                    session_node.setForeground(col, _QC("#6366f1"))
                session_node.setData(0, Qt.ItemDataRole.UserRole, items)  # كل الجلسة
                tree.addTopLevelItem(session_node)

                # الملفات داخل الجلسة
                for e in items:
                    orig = Path(e.get("original", "?"))
                    size = e.get("size", 0)
                    sz = fmt_size(size) if size > 0 else "0 B"
                    file_ts = e.get("deleted_at", "")[:19].replace("T", " ")

                    child = QTreeWidgetItem([
                        f"  {orig.name}",
                        "",
                        sz,
                        file_ts
                    ])
                    child.setToolTip(0, str(orig))
                    child.setData(0, Qt.ItemDataRole.UserRole, e)  # ملف واحد
                    session_node.addChild(child)

            title.setText(f"🗑️ سلة المحذوفات ({total_files} ملف)")
            total_size_lbl.setText(f"الحجم: {fmt_size(total_bytes)}")

            if total_files == 0:
                empty_item = QTreeWidgetItem(["السلة فارغة ✅", "", "", ""])
                tree.addTopLevelItem(empty_item)

        _refresh()

        # ── أزرار ──
        btn_row = QHBoxLayout()
        btn_restore = QPushButton(Lang.t("trash_restore_btn"))
        btn_restore.setObjectName("SuccessBtn")
        btn_row.addWidget(btn_restore)

        btn_restore_all = QPushButton("♻️ استرجاع الجلسة كاملة")
        btn_row.addWidget(btn_restore_all)
        btn_row.addStretch()
        ly.addLayout(btn_row)

        def _do_restore():
            item = tree.currentItem()
            if not item:
                QMessageBox.warning(dlg, "تحذير", "اختر ملفاً للاسترجاع!")
                return
            entry = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(entry, dict):
                ok, msg = SafeTrash.restore(entry)
                if ok:
                    QMessageBox.information(dlg, "✅", f"تم الاسترجاع:\n{Path(entry.get('original','')).name}")
                    _refresh()
                else:
                    QMessageBox.warning(dlg, "❌", f"فشل:\n{msg}")
            elif isinstance(entry, list):
                # جلسة كاملة
                _do_restore_session(entry)

        def _do_restore_session(entries=None):
            item = tree.currentItem()
            if entries is None:
                if not item:
                    QMessageBox.warning(dlg, "تحذير", "اختر جلسة!")
                    return
                entries = item.data(0, Qt.ItemDataRole.UserRole)
                if not isinstance(entries, list):
                    QMessageBox.warning(dlg, "تحذير", "اختر جلسة (📂) وليس ملف!")
                    return

            count = len(entries)
            if QMessageBox.question(
                dlg, "♻️ استرجاع جلسة",
                f"استرجاع {count} ملف؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes:
                return

            ok_count = 0
            for e in entries:
                ok, _ = SafeTrash.restore(e)
                if ok:
                    ok_count += 1
            QMessageBox.information(dlg, "✅", f"تم استرجاع {ok_count}/{count} ملف")
            _refresh()

        def _do_empty():
            entries_now = SafeTrash.list_items()
            if not entries_now:
                QMessageBox.information(dlg, "💡", "السلة فارغة بالفعل.")
                return
            if QMessageBox.question(
                dlg, "⚠️ تأكيد التفريغ",
                f"هل تريد حذف {len(entries_now)} ملف نهائياً؟\nلا يمكن التراجع!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes:
                SafeTrash.empty_trash()
                _refresh()
                QMessageBox.information(dlg, "✅", "تم تفريغ السلة.")

        btn_restore.clicked.connect(_do_restore)
        btn_restore_all.clicked.connect(lambda: _do_restore_session())
        btn_empty.clicked.connect(_do_empty)

        dlg.exec()

    def log(self, msg: str):
        """استدعاء آمن من أي thread."""
        self._signals.log_line.emit(msg)

    def _clear_log(self):
        self._log_box.clear()

    def _refresh_device_info(self):
        if DeviceProfiler._measured:
            self._device_info.setText(DeviceProfiler.get_specs_text())
        else:
            self._device_info.setText("🖥️  جاري قياس الجهاز...")
