#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.qt.github_panel
==================
لوحة إدارة GitHub — Auth / Repos / Upload / Clone / LFS
"""

import threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QFrame, QComboBox, QTabWidget, QFileDialog, QMessageBox,
    QFormLayout, QSplitter, QCheckBox, QGroupBox,
    QDialog, QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui  import QFont, QIcon, QColor

from ...core.constants import LICENSES
from ...lang.lang      import Lang


class GithubSignals(QObject):
    log_line   = pyqtSignal(str)
    repos_ready = pyqtSignal(list)
    done       = pyqtSignal(bool, str)




# ══════════════════════════════════════════════════════════════════
# 📁 ProjectPickerDialog — منتقي المشاريع المنظّم
# ══════════════════════════════════════════════════════════════════

class ProjectPickerDialog(QDialog):
    """
    نافذة تعرض كل المشاريع المعروفة منظّمةً:
    - مشاريع الفلاشة (VAULT_DIR)
    - مشاريع الجهاز (من sync_panel)
    - آخر المشاريع المستخدمة في GitHub
    مع حالة كل مشروع (✅ 🔶 🔴 🟡)
    """
    _statuses_ready = pyqtSignal()   # signal آمن لتحديث الـ UI من thread

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_path = ""
        self.setWindowTitle("📁 اختر مشروعاً")
        self.setMinimumSize(560, 420)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._build()
        self._statuses_ready.connect(self._refresh_statuses)
        QTimer.singleShot(100, self._load_projects)

    def _build(self):
        ly = QVBoxLayout(self)
        ly.setContentsMargins(16, 16, 16, 12)
        ly.setSpacing(8)

        # عنوان + بحث
        top = QHBoxLayout()
        title = QLabel("📁 اختر مشروعاً للعمل عليه")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        top.addWidget(title)
        top.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 بحث...")
        self._search.setFixedWidth(160)
        self._search.textChanged.connect(self._filter)
        top.addWidget(self._search)
        ly.addLayout(top)

        # القائمة
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["المشروع", "المسار", "الحالة"])
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSortingEnabled(False)
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        ly.addWidget(self._tree, 1)

        # أزرار
        btn_row = QHBoxLayout()
        btn_manual = QPushButton("📂 تصفح يدوي...")
        btn_manual.setObjectName("SecondaryBtn")
        btn_manual.clicked.connect(self._browse_manual)
        btn_row.addWidget(btn_manual)
        btn_row.addStretch()

        btn_cancel = QPushButton("إلغاء")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton("✅  اختيار")
        btn_ok.setObjectName("PrimaryBtn")
        btn_ok.clicked.connect(self._accept_selected)
        btn_row.addWidget(btn_ok)
        ly.addLayout(btn_row)

    def _load_projects(self):
        """يجمع المشاريع من كل المصادر ويعرضها."""
        from AyadFlowSync.core.app_config import AppConfig
        import json

        projects = {}  # path → {name, source, icon, status, color}

        # ── 1. مشاريع الفلاشة (VAULT_DIR) ──────────────────────
        vault = AppConfig.VAULT_DIR
        if vault.exists():
            for d in sorted(vault.iterdir()):
                if d.is_dir() and not d.name.startswith('.'):
                    projects[str(d)] = {
                        'name':   d.name,
                        'path':   str(d),
                        'source': '💾 الفلاشة',
                        'icon':   '🔵', 'status': 'جاري الفحص...', 'color': '#64748b',
                    }

        # ── 2. مشاريع الجهاز (sync_panel projects) ──────────────
        # ⚡ v4.0: قراءة مشاريع هذا الحاسوب فقط
        try:
            from AyadFlowSync.db.database import DatabaseManager
            _db = DatabaseManager(AppConfig.CONFIG_FILE)
            _pc = AppConfig.PC_NAME or "default"
            _proj_list = _db.get(f"projects_{_pc}", [])
            for p in _proj_list:
                from pathlib import Path as _P
                pp = _P(p)
                if pp.exists() and str(pp) not in projects:
                    projects[str(pp)] = {
                        'name':   pp.name,
                        'path':   str(pp),
                        'source': '💻 الجهاز',
                        'icon':   '🔵', 'status': 'جاري الفحص...', 'color': '#64748b',
                    }
        except Exception:
            pass

        # ── 3. مشاريع GitHub المرفوعة سابقاً ────────────────────
        gh_file = AppConfig.DATA_DIR / "github_projects.json"
        if gh_file.exists():
            try:
                data = json.loads(gh_file.read_text(encoding='utf-8'))
                for path_str, info in data.items():
                    from pathlib import Path as _P
                    pp = _P(path_str)
                    if pp.exists() and path_str not in projects:
                        projects[path_str] = {
                            'name':   info.get('name', pp.name),
                            'path':   path_str,
                            'source': '🐙 GitHub',
                            'icon':   '🔵', 'status': 'جاري الفحص...', 'color': '#64748b',
                        }
            except Exception:
                pass

        self._all_projects = list(projects.values())
        self._render(self._all_projects)

        # فحص الحالة في الخلفية
        import threading
        threading.Thread(target=self._check_statuses, daemon=True).start()

    def _check_statuses(self):
        """يفحص حالة كل مشروع في thread خلفي."""
        from AyadFlowSync.core.app_config import AppConfig
        from pathlib import Path as _P

        for proj in self._all_projects:
            try:
                p = _P(proj['path'])
                vault_path = AppConfig.VAULT_DIR / p.name

                if vault_path.exists():
                    # فحص التغيير عبر .ayadsync_meta.json
                    meta = vault_path / '.ayadsync_meta.json'
                    import json, datetime
                    if meta.exists():
                        data = json.loads(meta.read_text(encoding='utf-8'))
                        last_sync = data.get('last_sync', '')
                        if last_sync:
                            dt   = datetime.datetime.fromisoformat(last_sync)
                            diff = datetime.datetime.now() - dt
                            sync_ts = dt.timestamp()
                            # فحص سريع للتغيير
                            changed = any(
                                f.stat().st_mtime > sync_ts
                                for f in list(p.rglob('*'))[:200]
                                if f.is_file()
                            )
                            if diff.days == 0:
                                when = f"منذ {diff.seconds//3600}س" if diff.seconds >= 3600 else f"منذ {diff.seconds//60}د"
                            elif diff.days == 1:
                                when = "أمس"
                            else:
                                when = f"منذ {diff.days} يوم"

                            if changed:
                                proj.update({'icon': '🔶', 'status': f'تغيّر ({when})', 'color': '#f59e0b'})
                            else:
                                proj.update({'icon': '✅', 'status': f'متزامن ({when})', 'color': '#22c55e'})
                        else:
                            proj.update({'icon': '🟡', 'status': 'يحتاج فحص', 'color': '#94a3b8'})
                    else:
                        proj.update({'icon': '🟡', 'status': 'لم يُزامَن', 'color': '#94a3b8'})
                else:
                    proj.update({'icon': '🔴', 'status': 'بدون باكاب', 'color': '#ef4444'})
            except Exception:
                proj.update({'icon': '🟡', 'status': '—', 'color': '#64748b'})

        # تحديث الواجهة في الـ UI thread عبر signal آمن
        self._statuses_ready.emit()

    def _refresh_statuses(self):
        """يُحدّث الألوان بعد الفحص."""
        self._render(self._all_projects)

    def _render(self, projects: list):
        """يعرض المشاريع مجمّعةً حسب المصدر."""
        self._tree.clear()
        groups = {}
        for p in projects:
            src = p['source']
            if src not in groups:
                groups[src] = []
            groups[src].append(p)

        order = ['💾 الفلاشة', '💻 الجهاز', '🐙 GitHub']
        for src in order:
            if src not in groups:
                continue
            items = groups[src]
            # عنوان القسم
            hdr = QTreeWidgetItem([f"{src}  ({len(items)})", "", ""])
            hdr.setFont(0, QFont("Segoe UI", 11, QFont.Weight.Bold))
            hdr.setForeground(0, QColor("#6366f1"))
            hdr.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._tree.addTopLevelItem(hdr)
            hdr.setExpanded(True)

            # ترتيب: 🔶 أولاً ثم ✅ ثم باقي
            order_map = {'🔶': 0, '🔴': 1, '✅': 2, '🟡': 3, '🔵': 4}
            items_sorted = sorted(items, key=lambda x: order_map.get(x['icon'], 9))

            for proj in items_sorted:
                item = QTreeWidgetItem([
                    f"  {proj['icon']}  {proj['name']}",
                    proj['path'],
                    proj['status'],
                ])
                item.setForeground(2, QColor(proj['color']))
                item.setToolTip(1, proj['path'])
                item.setData(0, Qt.ItemDataRole.UserRole, proj['path'])
                hdr.addChild(item)

        if not projects:
            empty = QTreeWidgetItem(["  — لا توجد مشاريع —", "", ""])
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._tree.addTopLevelItem(empty)

    def _filter(self, text: str):
        """فلترة فورية بالاسم."""
        filtered = [p for p in self._all_projects
                    if text.lower() in p['name'].lower() or text.lower() in p['path'].lower()]
        self._render(filtered)

    def _on_double_click(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.selected_path = path
            self.accept()

    def _accept_selected(self):
        item = self._tree.currentItem()
        if item:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                self.selected_path = path
                self.accept()
                return
        QMessageBox.warning(self, "تحذير", "اختر مشروعاً أولاً!")

    def _browse_manual(self):
        folder = QFileDialog.getExistingDirectory(self, "تصفح يدوي")
        if folder:
            self.selected_path = folder
            self.accept()

    @staticmethod
    def pick(parent=None) -> str:
        """استدعاء سريع — يُرجع المسار المختار أو فارغ."""
        dlg = ProjectPickerDialog(parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.selected_path
        return ""


class GithubPanel(QWidget):
    """
    لوحة إدارة GitHub الكاملة — تبويبات:
    ① Auth      ② المستودعات  ③ رفع جديد  ④ Clone  ⑤ Batch
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._signals  = GithubSignals()
        self._token    = ""
        self._repos    = []
        self._running  = False
        self._status_labels = {}
        self._projects_data = []

        self._signals.log_line.connect(self._append_log)
        self._signals.repos_ready.connect(self._populate_repos)
        self._signals.done.connect(self._on_done)

        self._build_ui()
        self._auto_load_token()


    def retranslateUi(self):
        """يُحدّث تبويبات ونصوص github_panel فوراً."""
        if hasattr(self, '_tabs'):
            self._tabs.setTabText(0, Lang.t("gh_tab_auth"))
            self._tabs.setTabText(1, Lang.t("gh_tab_myprojects"))
            self._tabs.setTabText(2, Lang.t("gh_tab_repos"))
            self._tabs.setTabText(3, Lang.t("gh_tab_upload"))
            self._tabs.setTabText(4, Lang.t("gh_tab_push"))
            self._tabs.setTabText(5, Lang.t("gh_tab_clone"))
            self._tabs.setTabText(6, Lang.t("gh_tab_batch"))
        if hasattr(self, '_log_title_lbl'):
            self._log_title_lbl.setText(Lang.t("gh_log_title"))

    def _auto_load_token(self):
        """تحميل Token محفوظ تلقائياً عند البدء."""
        try:
            from ...github.ops import Auth
            saved = Auth.load()
            if saved:
                self._token = saved
                if hasattr(self, '_token_input'):
                    self._token_input.setText(saved)
                if hasattr(self, '_auth_status'):
                    self._auth_status.setText("✅ Token محفوظ — مصادق")
                self.log("🔐 تم تحميل Token محفوظ تلقائياً")
        except Exception as e:
            self.log(f"⚠️ فشل تحميل Token: {e}")

    # ── بناء الواجهة ──────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self._tabs = QTabWidget()
        tabs = self._tabs
        tabs.addTab(self._build_auth_tab(),       Lang.t("gh_tab_auth"))
        tabs.addTab(self._build_myprojects_tab(), Lang.t("gh_tab_myprojects"))
        tabs.addTab(self._build_repos_tab(),      Lang.t("gh_tab_repos"))
        tabs.addTab(self._build_upload_tab(),     Lang.t("gh_tab_upload"))
        tabs.addTab(self._build_readme_tab(),     Lang.t("gh_tab_readme"))
        tabs.addTab(self._build_push_tab(),       Lang.t("gh_tab_push"))
        tabs.addTab(self._build_clone_tab(),      Lang.t("gh_tab_clone"))
        tabs.addTab(self._build_batch_tab(),      Lang.t("gh_tab_batch"))
        root.addWidget(tabs, 1)

        # ── السجل ─────────────────────────────────────────────────
        log_header = QHBoxLayout()
        self._log_title_lbl = QLabel(Lang.t("gh_log_title"))
        self._log_title_lbl.setObjectName("SectionTitle")
        log_header.addWidget(self._log_title_lbl)
        log_header.addStretch()
        btn_clear = QPushButton("🗑️")
        btn_clear.setFixedSize(28, 28)
        btn_clear.clicked.connect(self._clear_log)
        log_header.addWidget(btn_clear)
        root.addLayout(log_header)

        self._log_box = QTextEdit()
        self._log_box.setObjectName("LogBox")
        self._log_box.setReadOnly(True)
        self._log_box.setFont(QFont("Cascadia Code", 14))
        self._log_box.setMaximumHeight(160)
        root.addWidget(self._log_box)

    # ── Auth Tab ──────────────────────────────────────────────────
    def _build_auth_tab(self) -> QWidget:
        w  = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(12, 12, 12, 12)
        ly.setSpacing(10)

        lbl = QLabel(Lang.t("gh_auth_title"))
        lbl.setObjectName("SectionTitle")
        ly.addWidget(lbl)

        form = QFormLayout()
        form.setSpacing(8)

        self._token_input = QLineEdit()
        self._token_input.setPlaceholderText("ghp_xxxxxxxxxxxx...")
        self._token_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(Lang.t("gh_token_lbl"), self._token_input)

        ly.addLayout(form)

        btn_row = QHBoxLayout()
        btn_auth = QPushButton(Lang.t("gh_activate_btn"))
        btn_auth.setObjectName("PrimaryBtn")
        btn_auth.clicked.connect(self._do_auth)
        btn_row.addWidget(btn_auth)

        btn_show = QPushButton(Lang.t("gh_show_hide"))
        btn_show.clicked.connect(
            lambda: self._token_input.setEchoMode(
                QLineEdit.EchoMode.Normal
                if self._token_input.echoMode() == QLineEdit.EchoMode.Password
                else QLineEdit.EchoMode.Password
            )
        )
        btn_row.addWidget(btn_show)
        btn_row.addStretch()
        ly.addLayout(btn_row)

        self._auth_status = QLabel(Lang.t("gh_not_auth"))
        ly.addWidget(self._auth_status)
        ly.addStretch()
        return w

    # ══ تبويب مشاريعي ══════════════════════════════════════════════

    def _build_myprojects_tab(self) -> QWidget:
        """
        تبويب يعرض كل المشاريع التي رُفعت على GitHub من هذا الجهاز
        أو من الفلاشة — مع حالة كل مشروع (متزامن / تغيّر / مفقود).
        """
        w  = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(10, 10, 10, 10)
        ly.setSpacing(8)

        # ── Header ───────────────────────────────────────────────
        hdr = QHBoxLayout()
        self._myproj_title = QLabel(Lang.t("gh_myproj_title"))
        self._myproj_title.setObjectName("SectionTitle")
        hdr.addWidget(self._myproj_title)
        hdr.addStretch()

        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedSize(30, 30)
        btn_refresh.setToolTip(Lang.t("gh_myproj_refresh"))
        btn_refresh.clicked.connect(self._refresh_myprojects)
        hdr.addWidget(btn_refresh)
        ly.addLayout(hdr)

        info = QLabel(Lang.t("gh_myproj_info"))
        info.setObjectName("Dim")
        info.setWordWrap(True)
        ly.addWidget(info)

        # ⚡ v4.0: أزرار فلترة سريعة
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)
        self._myproj_filter = "all"

        for fkey, flabel, fcolor in [
            ("all", "📋 الكل", "#718096"),
            ("changed", "🔶 متغيّرة", "#f59e0b"),
            ("synced", "✅ متزامنة", "#22c55e"),
            ("missing", "🔴 مفقودة", "#ef4444"),
        ]:
            btn = QPushButton(flabel)
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                f"QPushButton {{ font-size: 12px; padding: 2px 10px; "
                f"border: 1px solid {fcolor}; border-radius: 4px; color: {fcolor}; "
                f"background: transparent; }}"
                f"QPushButton:hover {{ background: {fcolor}22; }}"
            )
            btn.clicked.connect(lambda _, k=fkey: self._filter_myprojects(k))
            filter_row.addWidget(btn)
        filter_row.addStretch()
        ly.addLayout(filter_row)

        # ── القائمة ───────────────────────────────────────────────
        self._myproj_tree = QTreeWidget()
        self._myproj_tree.setHeaderLabels([
            Lang.t("gh_myproj_col_status"),
            Lang.t("gh_myproj_col_name"),
            Lang.t("gh_myproj_col_source"),
            "💻",                                    # ⚡ v4.0: الحاسوب
            Lang.t("gh_myproj_col_path"),
            Lang.t("gh_myproj_col_last"),
            Lang.t("gh_myproj_col_pushes"),
        ])
        self._myproj_tree.setRootIsDecorated(False)
        self._myproj_tree.setAlternatingRowColors(True)
        self._myproj_tree.setSortingEnabled(True)
        self._myproj_tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._myproj_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._myproj_tree.customContextMenuRequested.connect(self._myproj_context_menu)
        ly.addWidget(self._myproj_tree, 1)

        # ── أزرار ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_open_gh = QPushButton(Lang.t("gh_myproj_open_github"))
        btn_open_gh.setObjectName("SecondaryBtn")
        btn_open_gh.clicked.connect(self._myproj_open_github)
        btn_row.addWidget(btn_open_gh)

        btn_push = QPushButton(Lang.t("gh_myproj_push_now"))
        btn_push.setObjectName("PrimaryBtn")
        btn_push.clicked.connect(self._myproj_push_now)
        btn_row.addWidget(btn_push)

        btn_row.addStretch()

        btn_remove = QPushButton(Lang.t("gh_myproj_remove"))
        btn_remove.setObjectName("DangerBtn")
        btn_remove.clicked.connect(self._myproj_remove)
        btn_row.addWidget(btn_remove)

        ly.addLayout(btn_row)

        # تحميل عند البدء
        self._refresh_myprojects()
        return w

    def _refresh_myprojects(self):
        """يُحدّث قائمة مشاريعي من السجل المحلي."""
        if not hasattr(self, '_myproj_tree'):
            return
        try:
            from ...github.upload_log import UploadLog

            projects = UploadLog.get_all()
            self._myproj_tree.clear()

            if not projects:
                item = QTreeWidgetItem(["", Lang.t("gh_myproj_empty"), "", "", "", ""])
                item.setForeground(1, QColor("#64748b"))
                self._myproj_tree.addTopLevelItem(item)
                self._myproj_title.setText(
                    f"{Lang.t('gh_myproj_title')} (0)"
                )
                return

            status_map = {
                "synced":  ("✅", "#22c55e", Lang.t("gh_myproj_status_synced")),
                "changed": ("🔶", "#f59e0b", Lang.t("gh_myproj_status_changed")),
                "missing": ("🔴", "#ef4444", Lang.t("gh_myproj_status_missing")),
                "unknown": ("🟡", "#94a3b8", Lang.t("gh_myproj_status_unknown")),
            }

            for p in projects:
                st    = p.get("status", "unknown")
                icon, color, st_txt = status_map.get(st, status_map["unknown"])

                # تنسيق آخر push
                last_push_ts = p.get("last_push_ts", 0)
                if last_push_ts:
                    from datetime import datetime
                    dt   = datetime.fromtimestamp(last_push_ts)
                    diff = datetime.now() - dt
                    if diff.days == 0:
                        if diff.seconds < 3600:
                            when = f"منذ {diff.seconds // 60} دقيقة"
                        else:
                            when = f"منذ {diff.seconds // 3600} ساعة"
                    elif diff.days == 1:
                        when = "أمس"
                    else:
                        when = f"منذ {diff.days} يوم"
                else:
                    when = "—"

                item = QTreeWidgetItem([
                    f"{icon} {st_txt}",
                    p.get("repo_name", "?"),
                    p.get("source", "?"),
                    p.get("pc_name", "—"),           # ⚡ v4.0: الحاسوب
                    p.get("local_path", "?"),
                    when,
                    str(p.get("push_count", 1)),
                ])
                item.setForeground(0, QColor(color))
                item.setToolTip(1, p.get("repo_url", ""))
                item.setToolTip(3, p.get("local_path", ""))
                item.setData(0, Qt.ItemDataRole.UserRole, p)
                self._myproj_tree.addTopLevelItem(item)

            self._myproj_title.setText(
                f"{Lang.t('gh_myproj_title')} ({len(projects)})"
            )
        except Exception as e:
            self.log(f"⚠️ خطأ في تحديث مشاريعي: {e}")

    def _myproj_open_github(self):
        item = self._myproj_tree.currentItem()
        if not item:
            return
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if p:
            url = p.get("repo_url", "")
            if url:
                import webbrowser
                webbrowser.open(url)

    def _myproj_push_now(self):
        """تحويل إلى تبويب Push مع ملء المسار تلقائياً."""
        item = self._myproj_tree.currentItem()
        if not item:
            return
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if not p:
            return
        # انتقل لتبويب Push (index 4) وملأ المسار
        if hasattr(self, '_tabs'):
            self._tabs.setCurrentIndex(4)   # Push tab
        if hasattr(self, '_push_path'):
            self._push_path.setText(p.get("local_path", ""))

    def _myproj_remove(self):
        item = self._myproj_tree.currentItem()
        if not item:
            return
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if not p:
            return
        repo = p.get("repo_name", "?")
        if QMessageBox.question(
            self, "تأكيد",
            f"حذف '{repo}' من سجل مشاريعي؟\n(لن يُحذف من GitHub)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            from ...github.upload_log import UploadLog
            UploadLog.remove(repo)
            self._refresh_myprojects()

    def _myproj_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        item = self._myproj_tree.itemAt(pos)
        if not item:
            return
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if not p:
            return
        menu = QMenu(self)
        act_gh   = menu.addAction(f"🌐  {Lang.t('gh_myproj_open_github')}")
        act_push = menu.addAction(f"🔄  {Lang.t('gh_myproj_push_now')}")
        menu.addSeparator()
        act_rm   = menu.addAction(f"🗑️  {Lang.t('gh_myproj_remove')}")
        act = menu.exec(self._myproj_tree.viewport().mapToGlobal(pos))
        if act == act_gh:   self._myproj_open_github()
        if act == act_push: self._myproj_push_now()
        if act == act_rm:   self._myproj_remove()

    def _filter_myprojects(self, status_filter: str):
        """⚡ v4.0: فلترة قائمة مشاريعي حسب الحالة."""
        self._myproj_filter = status_filter
        # إخفاء/إظهار الصفوف حسب الفلتر
        for i in range(self._myproj_tree.topLevelItemCount()):
            item = self._myproj_tree.topLevelItem(i)
            if not item:
                continue
            p = item.data(0, Qt.ItemDataRole.UserRole)
            if not p:
                item.setHidden(False)
                continue
            st = p.get("status", "unknown")
            if status_filter == "all":
                item.setHidden(False)
            else:
                item.setHidden(st != status_filter)

    # ══ repos tab ══════════════════════════════════════════════════
    def _build_repos_tab(self) -> QWidget:
        w  = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(8, 8, 8, 8)
        ly.setSpacing(6)

        btn_refresh = QPushButton(Lang.t("gh_refresh_repos"))
        btn_refresh.setObjectName("PrimaryBtn")
        btn_refresh.clicked.connect(self._fetch_repos)
        ly.addWidget(btn_refresh)

        self._repo_list = QListWidget()
        ly.addWidget(self._repo_list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        btn_open = QPushButton(Lang.t("gh_open_btn"))
        btn_open.clicked.connect(self._open_repo_browser)
        btn_row.addWidget(btn_open)

        btn_toggle = QPushButton(Lang.t("gh_toggle_btn"))
        btn_toggle.setToolTip(Lang.t("gh_toggle_btn"))
        btn_toggle.clicked.connect(self._toggle_visibility)
        btn_row.addWidget(btn_toggle)

        btn_dl = QPushButton(Lang.t("gh_download_btn"))
        btn_dl.setToolTip(Lang.t("gh_download_btn"))
        btn_dl.clicked.connect(self._download_repo)
        btn_row.addWidget(btn_dl)

        btn_readme = QPushButton(Lang.t("gh_readme_btn"))
        btn_readme.setToolTip(Lang.t("gh_readme_btn"))
        btn_readme.clicked.connect(self._generate_readme)
        btn_row.addWidget(btn_readme)

        btn_row.addStretch()

        btn_del = QPushButton(Lang.t("gh_delete_btn"))
        btn_del.setObjectName("DangerBtn")
        btn_del.clicked.connect(self._delete_repo)
        btn_row.addWidget(btn_del)
        ly.addLayout(btn_row)
        return w

    # ── Upload Tab ────────────────────────────────────────────────
    def _build_upload_tab(self) -> QWidget:
        """رفع مشروع لـ GitHub — بدون أي علاقة بالـ README."""
        w  = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(12, 12, 12, 12)
        ly.setSpacing(8)

        info = QLabel("رفع مشروع كامل لـ GitHub. الـ README يُنشأ من تبويب README AI بشكل مستقل.")
        info.setObjectName("Dim")
        info.setWordWrap(True)
        ly.addWidget(info)

        form = QFormLayout()
        form.setSpacing(8)

        # مجلد المشروع
        folder_row = QHBoxLayout()
        self._upload_path = QLineEdit()
        self._upload_path.setPlaceholderText("مجلد المشروع...")
        self._upload_path.textChanged.connect(self._on_upload_path_changed)
        folder_row.addWidget(self._upload_path)
        btn_browse = QPushButton("📂")
        btn_browse.setFixedWidth(36)
        btn_browse.clicked.connect(self._browse_upload)
        folder_row.addWidget(btn_browse)
        form.addRow(Lang.t("gh_project_lbl"), folder_row)

        # حالة المشروع
        self._upload_status_lbl = QLabel(Lang.t("gh_status_default"))
        self._upload_status_lbl.setObjectName("Dim")
        self._upload_status_lbl.setWordWrap(True)
        form.addRow(Lang.t("gh_status_lbl"), self._upload_status_lbl)

        # اسم الـ Repo
        self._repo_name = QLineEdit()
        self._repo_name.setPlaceholderText("my-project")
        form.addRow(Lang.t("gh_repo_name_lbl"), self._repo_name)

        # الوصف
        self._repo_desc = QLineEdit()
        self._repo_desc.setPlaceholderText("وصف المشروع...")
        form.addRow(Lang.t("gh_desc_lbl"), self._repo_desc)

        # الرخصة
        self._license_combo = QComboBox()
        self._license_combo.addItems(LICENSES)
        form.addRow(Lang.t("gh_license_lbl"), self._license_combo)

        # خيارات
        self._private_cb = QCheckBox(Lang.t("gh_private_cb"))
        form.addRow("", self._private_cb)

        self._lfs_cb = QCheckBox(Lang.t("gh_lfs_cb"))
        form.addRow("", self._lfs_cb)

        ly.addLayout(form)

        btn_upload = QPushButton(Lang.t("gh_upload_btn"))
        btn_upload.setObjectName("PrimaryBtn")
        btn_upload.setMinimumHeight(44)
        btn_upload.clicked.connect(self._do_upload)
        ly.addWidget(btn_upload)

        ly.addStretch()
        return w

    def _build_readme_tab(self) -> QWidget:
        """توليد README AI — مستقل تماماً عن الرفع."""
        w  = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(16, 16, 16, 16)
        ly.setSpacing(12)

        # عنوان
        title = QLabel("🤖 توليد README بالذكاء الاصطناعي")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #e2e8f0;")
        ly.addWidget(title)

        info = QLabel("يُحلّل المشروع ويُنتج README.md + README_AR.md احترافيين ويحفظهما مباشرة في مجلد المشروع.")
        info.setObjectName("Dim")
        info.setWordWrap(True)
        ly.addWidget(info)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        ly.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(10)

        # مجلد المشروع
        folder_row = QHBoxLayout()
        self._readme_path = QLineEdit()
        self._readme_path.setPlaceholderText("مجلد المشروع...")
        folder_row.addWidget(self._readme_path)
        btn_browse_readme = QPushButton("📂")
        btn_browse_readme.setFixedWidth(36)
        btn_browse_readme.clicked.connect(self._browse_readme_path)
        folder_row.addWidget(btn_browse_readme)
        form.addRow("📁 المشروع:", folder_row)

        # حالة README
        self._readme_status_lbl = QLabel("اختر مجلداً لفحص حالة README")
        self._readme_status_lbl.setObjectName("Dim")
        self._readme_status_lbl.setWordWrap(True)
        form.addRow("📊 الحالة:", self._readme_status_lbl)

        # اختيار المزود
        self._readme_provider_combo = QComboBox()
        self._readme_provider_combo.addItem("🔄 تجريب كل المزودين بالترتيب (Gemini → Claude → DeepSeek → OpenAI)")
        self._readme_provider_combo.addItem("🔵 Gemini (مجاني — موصى به)")
        self._readme_provider_combo.addItem("🟣 Claude (جودة عالية)")
        self._readme_provider_combo.addItem("🟢 DeepSeek (سريع + رخيص)")
        self._readme_provider_combo.addItem("🟡 OpenAI GPT-4o-mini")
        form.addRow("🤖 المزود:", self._readme_provider_combo)

        ly.addLayout(form)
        ly.addSpacing(8)

        # أزرار
        btn_gen = QPushButton("⚡  توليد README + حفظ في المشروع")
        btn_gen.setObjectName("PrimaryBtn")
        btn_gen.setMinimumHeight(48)
        btn_gen.clicked.connect(self._generate_readme_standalone)
        ly.addWidget(btn_gen)

        # نتيجة
        self._readme_result_lbl = QLabel("")
        self._readme_result_lbl.setWordWrap(True)
        self._readme_result_lbl.setObjectName("Dim")
        ly.addWidget(self._readme_result_lbl)

        ly.addStretch()
        return w

    # ── Clone Tab ─────────────────────────────────────────────────
    def _build_clone_tab(self) -> QWidget:
        w  = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(12, 12, 12, 12)
        ly.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)

        self._clone_url = QLineEdit()
        self._clone_url.setPlaceholderText("https://github.com/user/repo.git")
        form.addRow(Lang.t("gh_clone_url_lbl"), self._clone_url)

        dest_row = QHBoxLayout()
        self._clone_dest = QLineEdit()
        self._clone_dest.setPlaceholderText("مجلد الوجهة...")
        dest_row.addWidget(self._clone_dest)
        btn_dest = QPushButton("📂")
        btn_dest.setFixedWidth(36)
        btn_dest.clicked.connect(self._browse_clone)
        dest_row.addWidget(btn_dest)
        form.addRow(Lang.t("gh_clone_dest_lbl"), dest_row)

        ly.addLayout(form)

        btn_clone = QPushButton(Lang.t("gh_clone_btn"))
        btn_clone.setObjectName("SuccessBtn")
        btn_clone.clicked.connect(self._do_clone)
        ly.addWidget(btn_clone)
        ly.addStretch()
        return w

    # ── Batch Tab ─────────────────────────────────────────────────
    def _build_batch_tab(self) -> QWidget:
        w  = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(12, 12, 12, 12)
        ly.setSpacing(8)

        info = QLabel(
            "رفع جميع المشاريع من مجلد رئيسي واحد.\n"
            "كل مجلد فرعي = Repo مستقل على GitHub."
        )
        info.setObjectName("Dim")
        info.setWordWrap(True)
        ly.addWidget(info)

        row = QHBoxLayout()
        self._batch_path = QLineEdit()
        self._batch_path.setPlaceholderText("المجلد الرئيسي...")
        row.addWidget(self._batch_path)
        btn_b = QPushButton("📂")
        btn_b.setFixedWidth(36)
        btn_b.clicked.connect(lambda: self._batch_path.setText(
            QFileDialog.getExistingDirectory(self, "اختر المجلد الرئيسي") or self._batch_path.text()
        ))
        row.addWidget(btn_b)
        ly.addLayout(row)

        btn_batch = QPushButton(Lang.t("gh_batch_btn"))
        btn_batch.setObjectName("PrimaryBtn")
        btn_batch.clicked.connect(self._do_batch)
        ly.addWidget(btn_batch)
        ly.addStretch()
        return w

    # ── العمليات ──────────────────────────────────────────────────
    def _do_auth(self):
        token = self._token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "تحذير", Lang.t("gh_warn_token"))
            return
        self._token = token
        self._auth_status.setText("🔄 جاري التحقق...")
        threading.Thread(target=self._worker_auth, args=(token,), daemon=True).start()

    def _worker_auth(self, token: str):
        try:
            from ...github.client import GitRunner
            ok = GitRunner.verify_token(token)
            if ok:
                from ...github.ops import Auth
                Auth.save(token)
                self._signals.log_line.emit("✅ تم التحقق وحفظ الـ Token بتشفير آمن")
                self._signals.done.emit(True, "✅ مصادق بنجاح")
            else:
                self._signals.log_line.emit("❌ Token غير صالح")
                self._signals.done.emit(False, "❌ Token غير صالح")
        except Exception as e:
            self._signals.log_line.emit(f"❌ خطأ في التحقق: {e}")
            self._signals.done.emit(False, f"❌ {e}")

    def _fetch_repos(self):
        if not self._token:
            QMessageBox.warning(self, "تحذير", Lang.t("gh_warn_login"))
            return
        self.log("🔄 جاري جلب المستودعات...")
        threading.Thread(target=self._worker_fetch_repos, daemon=True).start()

    def _save_repos_cache(self, repos: list):
        """حفظ repos في cache محلي للتحميل السريع لاحقاً."""
        try:
            import json
            from ...core.app_config import AppConfig
            cache_file = AppConfig.DATA_DIR / "repos_cache.json"
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps(repos, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception:
            pass

    def _load_repos_cache(self):
        """تحميل repos من cache محلي — فوري بدون إنترنت."""
        try:
            import json
            from ...core.app_config import AppConfig
            cache_file = AppConfig.DATA_DIR / "repos_cache.json"
            if cache_file.exists():
                repos = json.loads(cache_file.read_text(encoding='utf-8'))
                if repos:
                    self._repos = repos
                    self._signals.repos_ready.emit(repos)
                    self.log(f"📦 {len(repos)} مستودع محفوظ (آخر جلب)")
        except Exception:
            pass

    def _worker_fetch_repos(self):
        try:
            from ...github.manager import RepoMgr
            mgr   = RepoMgr(self._token)
            repos = mgr.list_repos()
            self._repos = repos
            self._save_repos_cache(repos)          # ✅ حفظ تلقائي
            self._signals.repos_ready.emit(repos)
        except Exception as e:
            self._signals.log_line.emit(f"❌ {e}")

    def _populate_repos(self, repos: list):
        self._repo_list.clear()
        public  = [r for r in repos if not r.get("private")]
        private = [r for r in repos if r.get("private")]

        def _add_section(label: str, items: list):
            if not items:
                return
            # عنوان القسم
            hdr = QListWidgetItem(f"── {label} ({len(items)}) ──")
            hdr.setFlags(Qt.ItemFlag.NoItemFlags)
            hdr.setForeground(QColor("#6366f1"))
            hdr.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self._repo_list.addItem(hdr)
            for r in items:
                name  = r.get("name", "?")
                stars = r.get("stargazers_count", 0)
                lang  = r.get("language") or "—"
                priv  = "🔒" if r.get("private") else "🌐"
                stars_str = f" ⭐{stars}" if stars > 0 else ""
                item  = QListWidgetItem(f"  {priv}  {name}{stars_str}  [{lang}]")
                item.setToolTip(
                    f"🔗 {r.get('html_url','')}\n"
                    f"📝 {r.get('description','') or '—'}\n"
                    f"⏰ آخر تحديث: {r.get('updated_at','')[:10]}"
                )
                item.setData(Qt.ItemDataRole.UserRole, r)
                self._repo_list.addItem(item)

        _add_section("🌐 عام", public)
        _add_section("🔒 خاص", private)
        self.log(f"✅ {len(repos)} مستودع — {len(public)} عام | {len(private)} خاص")


    def _get_selected_repo(self) -> dict:
        """يُرجع repo dict للعنصر المحدد — يتجاهل عناوين الأقسام."""
        row = self._repo_list.currentRow()
        if row < 0:
            return {}
        item = self._repo_list.item(row)
        if not item:
            return {}
        data = item.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, dict) else {}

    def _open_repo_browser(self):
        repo = self._get_selected_repo_data()
        if repo:
            import webbrowser
            webbrowser.open(repo.get("html_url", ""))

    def _delete_repo(self):
        repo = self._get_selected_repo_data()
        if not repo:
            return
        name = repo.get("name", "?")
        if QMessageBox.question(
            self, "⚠️ تأكيد الحذف",
            f"هل أنت متأكد من حذف:\n{name}\n\nلا يمكن التراجع!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.log(f"🗑️  جاري حذف {name}...")
            threading.Thread(
                target=self._worker_delete,
                args=(repo,),
                daemon=True
            ).start()

    def _worker_delete(self, repo: dict):
        try:
            from ...github.manager import RepoMgr
            RepoMgr(self._token).delete_repo(repo["full_name"])
            self._signals.log_line.emit(f"✅ حُذف: {repo['name']}")
            self._worker_fetch_repos()
        except Exception as e:
            self._signals.log_line.emit(f"❌ {e}")

    def _browse_readme_path(self):
        folder = ProjectPickerDialog.pick(self)
        if folder:
            self._readme_path.setText(folder)
            self._check_readme_status(folder)

    def _check_readme_status(self, path: str):
        """يفحص حالة README الموجود في المجلد."""
        from pathlib import Path as _P
        p = _P(path)
        readme = p / 'README.md'
        if not readme.exists():
            self._readme_status_lbl.setText("🔴 لا يوجد README — سيُنشأ جديد")
            self._readme_status_lbl.setStyleSheet("color: #ef4444; font-weight: bold;")
        else:
            from ...github.readme import SmartReadmeGenerator
            icon, status = SmartReadmeGenerator.check_readme_status(path)
            colors = {'✅': '#22c55e', '🔶': '#f59e0b', '🟡': '#94a3b8', '🔴': '#ef4444'}
            color = colors.get(icon, '#94a3b8')
            self._readme_status_lbl.setText(f"{icon} {status}")
            self._readme_status_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _generate_readme_standalone(self):
        """توليد README مستقل — يُحفظ في مجلد المشروع فقط."""
        path = self._readme_path.text().strip()
        if not path or not Path(path).is_dir():
            if not path:
                folder = QFileDialog.getExistingDirectory(self, "اختر مجلد المشروع")
                if not folder:
                    return
                self._readme_path.setText(folder)
                path = folder
            else:
                QMessageBox.warning(self, "⚠️", f"المجلد غير موجود:\n{path}")
                return

        # تحديد المزود
        idx = self._readme_provider_combo.currentIndex()
        provider_map = {
            0: None,            # كل المزودين
            1: 'gemini',
            2: 'claude',
            3: 'deepseek',
            4: 'openai',
        }
        forced_provider = provider_map.get(idx)

        ai_keys  = SettingsPanel.get_ai_keys() if 'SettingsPanel' in dir() else {}
        dev_info = SettingsPanel.get_dev_info() if 'SettingsPanel' in dir() else {}

        # import صحيح
        try:
            from .settings_panel import SettingsPanel as _SP
            ai_keys  = _SP.get_ai_keys()
            dev_info = _SP.get_dev_info()
        except Exception:
            ai_keys  = {}
            dev_info = {}

        if not ai_keys and forced_provider:
            QMessageBox.warning(self, Lang.t("gh_no_ai_title"), Lang.t("gh_no_ai_key"))
            return

        self._readme_result_lbl.setText("⏳ جاري التوليد...")
        self._readme_result_lbl.setStyleSheet("color: #f59e0b;")

        threading.Thread(
            target=self._worker_readme_standalone,
            args=(Path(path), ai_keys, dev_info, forced_provider),
            daemon=True
        ).start()

    def _worker_readme_standalone(self, path: Path, ai_keys: dict,
                                   dev_info: dict, forced_provider):
        """Worker — يُولّد ويحفظ README في مجلد المشروع فقط."""
        try:
            from ...github.readme import SmartReadmeGenerator

            # بناء قائمة المزودين
            if forced_provider:
                multi = {forced_provider: (ai_keys or {}).get(forced_provider, '')}
                provider = forced_provider
                key = multi.get(provider, '')
            else:
                multi    = ai_keys or {}
                provider = next((p for p in ['gemini','claude','deepseek','openai']
                                 if multi.get(p)), None)
                key = multi.get(provider, '') if provider else ''

            gen = SmartReadmeGenerator(
                path=path,
                ai_provider=provider,
                ai_key=key,
                cb=lambda m: self._signals.log_line.emit(m),
                dev_info=dev_info,
                multi_keys=multi,
            )

            result    = gen.generate()
            en        = result.get('en', '') if isinstance(result, dict) else ''
            ar        = result.get('ar', '') if isinstance(result, dict) else ''
            success   = result.get('success', False) if isinstance(result, dict) else bool(en)
            prov_used = result.get('provider_used', provider or 'template') if isinstance(result, dict) else ''

            if success and en:
                gen.save(en, ar)
                msg = f"✅ README حُفظ في:\n{path / 'README.md'}  [{prov_used}]"
                self._signals.log_line.emit(f"__README_RESULT__SUCCESS__{msg}")
            else:
                err = result.get('error', 'فشل التوليد') if isinstance(result, dict) else 'فشل'
                self._signals.log_line.emit(f"__README_RESULT__FAIL__{err}")

        except Exception as e:
            import traceback
            self._signals.log_line.emit(f"__README_RESULT__FAIL__{e}\n{traceback.format_exc()}")

    def _browse_upload(self):
        folder = ProjectPickerDialog.pick(self)
        if folder:
            self._upload_path.setText(folder)
            self._repo_name.setText(Path(folder).name)

    # ══ كشف تغييرات المشروع ════════════════════════════════════════

    def _on_upload_path_changed(self, text: str):
        self._check_project_changed(text.strip(), self._upload_status_lbl)

    def _on_push_path_changed(self, text: str):
        self._check_project_changed(text.strip(), self._push_status_lbl)

    def _check_project_changed(self, path: str, label):
        """يُشغّل فحص الحالة في thread خلفي ويُحدّث اللصيقة المعطاة."""
        if not path or not Path(path).is_dir():
            label.setText(Lang.t("gh_status_default"))
            label.setStyleSheet("")
            return
        threading.Thread(
            target=self._worker_project_status,
            args=(path, label),
            daemon=True
        ).start()

    def _worker_project_status(self, path: str, label):
        """
        يفحص حالة المشروع أينما كان (جهاز أو فلاشة):
        ① إذا مجلد Git → يسأل git عن التغييرات مقارنةً بآخر commit
        ② إذا لا git    → يقارن mtime الملفات بآخر push مُسجَّل (pc_push_log.json)
        """
        try:
            icon, status, color = self._detect_project_status(Path(path))
            # أرسل النتيجة للـ UI thread عبر signal خاص
            self._signals.log_line.emit(
                f"__PROJ_STATUS__{id(label)}__{icon} {status}__COLOR__{color}"
            )
            # احفظ label reference
            self._status_labels[id(label)] = label
        except Exception:
            pass

    def _detect_project_status(self, path: Path) -> tuple:
        """
        منطق الكشف المركزي — يعمل مع أي مسار:

        حالات Git (إذا .git موجود):
          🟢  لا تغييرات — synchronized مع آخر commit
          🔶  X ملف تغيّر — لم يُعمل push بعد
          🔴  لم يُعمل commit/push قط
          🟡  لا يوجد remote (لم يُرفع لـ GitHub بعد)

        حالات بدون Git:
          ✅  لم يتغيّر منذ آخر رفع
          🔶  X ملف تغيّر منذ آخر رفع
          🔴  لم يُرفع لـ GitHub قط
        """
        from AyadFlowSync.github.client import GitRunner
        import subprocess

        is_git = GitRunner.is_git_repo(path)

        if is_git and GitRunner.has_git():
            # ── مسار Git ───────────────────────────────────────
            try:
                git = GitRunner(path)

                # هل فيه remote?
                r_remote = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=str(path), capture_output=True, text=True, timeout=5
                )
                has_remote = r_remote.returncode == 0 and r_remote.stdout.strip()

                if not has_remote:
                    return '🟡', 'لا يوجد remote — لم يُرفع لـ GitHub بعد', '#94a3b8'

                # هل فيه commits أصلاً؟
                r_log = subprocess.run(
                    ["git", "log", "--oneline", "-1"],
                    cwd=str(path), capture_output=True, text=True, timeout=5
                )
                if r_log.returncode != 0 or not r_log.stdout.strip():
                    return '🔴', 'لا يوجد commits — جاهز للرفع الأول', '#ef4444'

                # فحص الملفات المتغيّرة (staged + unstaged + untracked)
                r_status = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(path), capture_output=True, text=True, timeout=10
                )
                changed_lines = [l for l in r_status.stdout.strip().split('\n') if l.strip()]
                n_changed = len(changed_lines)

                # هل فيه commits لم تُرفع (ahead of remote)?
                r_ahead = subprocess.run(
                    ["git", "status", "--short", "--branch"],
                    cwd=str(path), capture_output=True, text=True, timeout=5
                )
                ahead_str = r_ahead.stdout.split('\n')[0] if r_ahead.stdout else ''
                is_ahead  = 'ahead' in ahead_str

                if n_changed == 0 and not is_ahead:
                    # آخر commit date
                    r_date = subprocess.run(
                        ["git", "log", "-1", "--format=%cr"],
                        cwd=str(path), capture_output=True, text=True, timeout=5
                    )
                    when = r_date.stdout.strip() or "مزامَن"
                    return '✅', f'لا تغييرات — آخر commit: {when}', '#22c55e'
                elif is_ahead and n_changed == 0:
                    r_count = subprocess.run(
                        ["git", "rev-list", "--count", "origin/HEAD..HEAD"],
                        cwd=str(path), capture_output=True, text=True, timeout=5
                    )
                    n_commits = r_count.stdout.strip() or "?"
                    return '🔶', f'{n_commits} commit جديد — لم يُرفع بعد', '#f59e0b'
                else:
                    return '🔶', f'{n_changed} ملف تغيّر — يحتاج commit + push', '#f59e0b'

            except Exception as e:
                return '🟡', 'تعذّر قراءة حالة Git', '#94a3b8'

        else:
            # ── بدون Git — نعتمد على سجل Push الداخلي ──────────
            push_log = path / '.ayadsync_push_log.json'
            try:
                import json
                if not push_log.exists():
                    return '🔴', 'لم يُرفع لـ GitHub قط — جاهز للرفع الأول', '#ef4444'

                log_data  = json.loads(push_log.read_text(encoding='utf-8'))
                last_push = log_data.get('last_push_ts', 0)

                # فحص سريع: أي ملف أحدث من آخر push؟
                changed = 0
                count   = 0
                for f in path.rglob('*'):
                    if not f.is_file():
                        continue
                    if f.name.startswith('.ayadsync'):
                        continue
                    count += 1
                    if count > 1000:
                        break
                    try:
                        if f.stat().st_mtime > last_push + 2:
                            changed += 1
                    except OSError:
                        pass

                if changed == 0:
                    import datetime
                    dt   = datetime.datetime.fromtimestamp(last_push)
                    diff = datetime.datetime.now() - dt
                    if diff.days == 0:
                        when = f"منذ {diff.seconds // 3600} ساعة" if diff.seconds >= 3600 else f"منذ {diff.seconds // 60} دقيقة"
                    elif diff.days == 1:
                        when = "أمس"
                    else:
                        when = f"منذ {diff.days} يوم"
                    return '✅', f'لا تغييرات منذ آخر رفع ({when})', '#22c55e'
                else:
                    return '🔶', f'{changed}+ ملف تغيّر منذ آخر رفع', '#f59e0b'

            except Exception:
                return '🟡', 'يحتاج فحص', '#94a3b8'

    def _do_upload(self):
        path  = self._upload_path.text().strip()
        name  = self._repo_name.text().strip()
        if not path or not name:
            QMessageBox.warning(self, "تحذير", Lang.t("gh_warn_fields"))
            return
        if not self._token:
            QMessageBox.warning(self, "تحذير", Lang.t("gh_warn_login"))
            return

        # ⚡ قراءة كل القيم من UI thread قبل بدء الخيط
        desc = self._repo_desc.text().strip()
        private = self._private_cb.isChecked()
        license_id = self._license_combo.currentText()
        use_lfs = self._lfs_cb.isChecked()
        gen_readme = False  # README منفصل تماماً — تبويب README AI
        token = self._token

        self.log(f"🚀  رفع {name}...")
        threading.Thread(
            target=self._worker_upload,
            args=(Path(path), name, desc, private, license_id, use_lfs, gen_readme, token),
            daemon=True
        ).start()

    def _worker_upload(self, path, name, desc, private, license_id, use_lfs, gen_readme, token):
        try:
            # توليد README قبل الرفع إذا مطلوب
            if gen_readme:
                self._signals.log_line.emit("🤖 توليد README...")
                try:
                    from .settings_panel import SettingsPanel
                    ai_keys = SettingsPanel.get_ai_keys()
                    dev_info = SettingsPanel.get_dev_info()
                    if ai_keys:
                        from ...github.readme import SmartReadmeGenerator
                        provider = key = None
                        for p in ['gemini', 'claude', 'openai', 'deepseek']:
                            if p in ai_keys and ai_keys[p]:
                                provider, key = p, ai_keys[p]; break
                        if provider:
                            self._signals.log_line.emit(f"🤖 استخدام {provider}...")
                            gen = SmartReadmeGenerator(
                                path=path, ai_provider=provider, ai_key=key,
                                cb=lambda m: self._signals.log_line.emit(m),
                                dev_info=dev_info, multi_keys=ai_keys,
                            )
                            result = gen.generate()
                            en = result.get('en', '') if isinstance(result, dict) else (result[0] if result else '')
                            ar = result.get('ar', '') if isinstance(result, dict) else (result[1] if result else '')
                            if not result.get('success', True) if isinstance(result, dict) else False:
                                self._signals.log_line.emit("⚠️ README: فشل التوليد — تخطي")
                            elif en or ar:
                                gen.save(en, ar)
                                self._signals.log_line.emit("✅ README جاهز")
                            else:
                                self._signals.log_line.emit("⚠️ README فارغ — تخطي")
                    else:
                        self._signals.log_line.emit("⚠️ لا يوجد مفتاح AI — اذهب للإعدادات")
                except Exception as e:
                    self._signals.log_line.emit(f"⚠️ README: {e}")

            # الرفع لـ GitHub
            self._signals.log_line.emit(f"📤 رفع {name} إلى GitHub...")
            from ...github.ops import Uploader
            up = Uploader(
                token,
                log_cb=lambda m: self._signals.log_line.emit(m),
            )
            ok = up.upload(
                path, name,
                desc=desc,
                private=private,
                license_id=license_id,
                use_lfs=use_lfs,
            )
            if ok:
                self._save_push_log(path, repo_name=name, source="PC")
                # ✅ تسجيل في UploadLog المركزي حتى يظهر في تبويب مشاريعي
                try:
                    from ...github.upload_log import UploadLog
                    from ...github.ops import Auth
                    from ...github.client import GitHubAPI
                    api = GitHubAPI(token)
                    me  = api.get("/user") or {}
                    username = me.get("login", "")
                    repo_url = f"https://github.com/{username}/{name}" if username else ""
                    UploadLog.record(str(path), "PC", name, repo_url)
                    self._refresh_myprojects()
                except Exception:
                    pass
                self._signals.done.emit(True, f"✅ رُفع {name} بنجاح")
            else:
                self._signals.done.emit(False, f"❌ فشل رفع {name}")
        except Exception as e:
            self._signals.log_line.emit(f"❌ خطأ: {e}")
            self._signals.done.emit(False, str(e))

    def _browse_clone(self):
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلد الوجهة")
        if folder:
            self._clone_dest.setText(folder)

    def _do_clone(self):
        url  = self._clone_url.text().strip()
        dest = self._clone_dest.text().strip()
        if not url or not dest:
            QMessageBox.warning(self, "تحذير", Lang.t("gh_warn_url"))
            return
        self.log(f"⬇️  Clone: {url}")
        threading.Thread(
            target=self._worker_clone,
            args=(url, Path(dest)),
            daemon=True
        ).start()

    def _worker_clone(self, url: str, dest: Path):
        try:
            from ...github.ops import Cloner
            Cloner(self._token, log_cb=lambda m: self._signals.log_line.emit(m)).clone(url, dest)
            self._signals.done.emit(True, "✅ Clone اكتمل")
        except Exception as e:
            self._signals.log_line.emit(f"❌ {e}")
            self._signals.done.emit(False, str(e))

    def _do_batch(self):
        path = self._batch_path.text().strip()
        if not path:
            QMessageBox.warning(self, "تحذير", Lang.t("gh_warn_folder"))
            return
        if not self._token:
            QMessageBox.warning(self, "تحذير", Lang.t("gh_warn_login"))
            return
        self.log(f"📦  Batch upload: {path}")
        threading.Thread(
            target=self._worker_batch,
            args=(Path(path),),
            daemon=True
        ).start()

    def _worker_batch(self, parent: Path):
        try:
            from ...github.ops import Batch
            Batch(
                self._token,
                log_cb=lambda m: self._signals.log_line.emit(m),
            ).upload_all(parent)
            self._signals.done.emit(True, "✅ Batch اكتمل")
        except Exception as e:
            self._signals.log_line.emit(f"❌ {e}")
            self._signals.done.emit(False, str(e))

    # ── Push/Update Tab ────────────────────────────────────────────
    def _build_push_tab(self) -> QWidget:
        w   = QWidget()
        ly  = QVBoxLayout(w)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # ── الجانب الأيسر: قائمة المشاريع المرفوعة ─────────────
        left = QWidget()
        left.setFixedWidth(280)
        left_ly = QVBoxLayout(left)
        left_ly.setContentsMargins(10, 10, 6, 10)
        left_ly.setSpacing(6)

        hdr = QHBoxLayout()
        self._proj_list_title = QLabel("📁 المشاريع المرفوعة")
        self._proj_list_title.setObjectName("SectionTitle")
        hdr.addWidget(self._proj_list_title)
        hdr.addStretch()
        btn_refresh_proj = QPushButton("🔄")
        btn_refresh_proj.setFixedSize(28, 28)
        btn_refresh_proj.setToolTip("تحديث الحالة")
        btn_refresh_proj.clicked.connect(self._refresh_projects_list)
        hdr.addWidget(btn_refresh_proj)
        left_ly.addLayout(hdr)

        self._projects_list = QListWidget()
        self._projects_list.setObjectName("ProjectList")
        self._projects_list.currentRowChanged.connect(self._on_project_selected)
        left_ly.addWidget(self._projects_list, 1)

        # أزرار
        btn_row = QHBoxLayout()
        btn_add_proj = QPushButton("➕ إضافة")
        btn_add_proj.clicked.connect(self._add_project_manually)
        btn_row.addWidget(btn_add_proj)
        btn_remove_proj = QPushButton("➖ إزالة")
        btn_remove_proj.clicked.connect(self._remove_project_from_list)
        btn_row.addWidget(btn_remove_proj)
        left_ly.addLayout(btn_row)

        splitter.addWidget(left)

        # ── الجانب الأيمن: تفاصيل + إجراءات ───────────────────
        right = QWidget()
        right_ly = QVBoxLayout(right)
        right_ly.setContentsMargins(8, 10, 10, 10)
        right_ly.setSpacing(8)

        # معلومات المشروع المحدد
        info_frame = QFrame()
        info_frame.setObjectName("Card")
        info_ly = QVBoxLayout(info_frame)
        info_ly.setContentsMargins(12, 10, 12, 10)
        info_ly.setSpacing(4)

        self._proj_name_lbl = QLabel("— اختر مشروعاً —")
        self._proj_name_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._proj_name_lbl.setStyleSheet("color: #e2e8f0;")
        info_ly.addWidget(self._proj_name_lbl)

        self._proj_path_lbl = QLabel("")
        self._proj_path_lbl.setObjectName("Dim")
        self._proj_path_lbl.setWordWrap(True)
        info_ly.addWidget(self._proj_path_lbl)

        self._proj_url_lbl = QLabel("")
        self._proj_url_lbl.setObjectName("Dim")
        self._proj_url_lbl.setWordWrap(True)
        info_ly.addWidget(self._proj_url_lbl)

        self._push_status_lbl = QLabel(Lang.t("gh_status_default"))
        self._push_status_lbl.setObjectName("Dim")
        self._push_status_lbl.setWordWrap(True)
        self._push_status_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        info_ly.addWidget(self._push_status_lbl)

        right_ly.addWidget(info_frame)

        # حقل مسار يدوي + commit
        form = QFormLayout()
        form.setSpacing(6)

        folder_row = QHBoxLayout()
        self._push_path = QLineEdit()
        self._push_path.setPlaceholderText("مجلد المشروع المحلي...")
        self._push_path.textChanged.connect(self._on_push_path_changed)
        folder_row.addWidget(self._push_path)
        btn_b = QPushButton("📂")
        btn_b.setFixedWidth(36)
        btn_b.clicked.connect(lambda: (
            self._push_path.setText(
                ProjectPickerDialog.pick(self) or self._push_path.text()
            )
        ))
        folder_row.addWidget(btn_b)
        form.addRow(Lang.t("gh_project_lbl"), folder_row)

        self._push_msg = QLineEdit()
        self._push_msg.setPlaceholderText("Update project files")
        self._push_msg.setText("Update via AyadFlowSync")
        form.addRow(Lang.t("gh_commit_lbl"), self._push_msg)
        right_ly.addLayout(form)

        btn_push = QPushButton(Lang.t("gh_push_btn"))
        btn_push.setObjectName("PrimaryBtn")
        btn_push.setMinimumHeight(40)
        btn_push.clicked.connect(self._do_push)
        right_ly.addWidget(btn_push)

        right_ly.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([280, 400])

        ly.addWidget(splitter, 1)

        # تحميل القائمة فوراً
        QTimer.singleShot(200, self._refresh_projects_list)
        return w

    def _refresh_projects_list(self):
        """يُحمّل ويُحدّث قائمة المشاريع المرفوعة مع حالتها."""
        threading.Thread(target=self._worker_load_projects, daemon=True).start()

    def _worker_load_projects(self):
        """يقرأ github_projects.json ويفحص حالة كل مشروع."""
        import json, time
        from AyadFlowSync.core.app_config import AppConfig
        try:
            registry_file = AppConfig.DATA_DIR / "github_projects.json"
            if not registry_file.exists():
                self._signals.log_line.emit("__PROJECTS_READY__[]")
                return

            registry = json.loads(registry_file.read_text(encoding='utf-8'))
            projects = []
            for path_str, data in registry.items():
                from pathlib import Path as _Path
                path = _Path(path_str)
                exists = path.exists()

                # فحص الحالة
                if not exists:
                    icon, status, color = "⚠️", "المجلد غير موجود", "#ef4444"
                else:
                    icon, status, color = self._detect_project_status(path)

                projects.append({
                    **data,
                    'path':   path_str,
                    'exists': exists,
                    'icon':   icon,
                    'status': status,
                    'color':  color,
                })

            # ترتيب: المتغيّرة أولاً ثم الحديثة
            order = {"🔶": 0, "🔴": 1, "✅": 2, "🟡": 3, "⚠️": 4}
            projects.sort(key=lambda p: (order.get(p['icon'], 9),
                                         -p.get('last_push_ts', 0)))

            import json as _j
            self._signals.log_line.emit(f"__PROJECTS_READY__{_j.dumps(projects, ensure_ascii=False)}")
        except Exception as e:
            self._signals.log_line.emit(f"⚠️ فشل تحميل المشاريع: {e}")

    def _on_project_selected(self, row: int):
        """عند اختيار مشروع من القائمة — يملأ الحقول تلقائياً."""
        if row < 0 or not hasattr(self, '_projects_data'):
            return
        if row >= len(self._projects_data):
            return
        proj = self._projects_data[row]
        path = proj.get('path', '')
        name = proj.get('name', '')
        url  = proj.get('repo_url', '')

        self._proj_name_lbl.setText(f"📁 {name}")
        self._proj_path_lbl.setText(f"📍 {path}")
        self._proj_url_lbl.setText(f"🔗 {url}" if url else "")

        status_text = f"{proj.get('icon','?')} {proj.get('status','')}"
        color = proj.get('color', '#94a3b8')
        self._push_status_lbl.setText(status_text)
        self._push_status_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")

        # ملء حقل المسار
        if hasattr(self, '_push_path') and path:
            self._push_path.blockSignals(True)
            self._push_path.setText(path)
            self._push_path.blockSignals(False)

        # ملء الـ commit message
        if hasattr(self, '_push_msg') and name:
            self._push_msg.setText(f"Update {name} via AyadFlowSync")

    def _add_project_manually(self):
        """إضافة مشروع يدوياً للقائمة."""
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلد المشروع")
        if not folder:
            return
        import json, time
        from pathlib import Path
        from AyadFlowSync.core.app_config import AppConfig

        path_str = str(Path(folder).resolve())
        name     = Path(folder).name
        try:
            registry_file = AppConfig.DATA_DIR / "github_projects.json"
            registry = {}
            if registry_file.exists():
                registry = json.loads(registry_file.read_text(encoding='utf-8'))
            if path_str not in registry:
                registry[path_str] = {
                    'name':          name,
                    'path':          path_str,
                    'repo_url':      '',
                    'last_push_ts':  0,
                    'last_push_str': '—',
                    'source':        'PC',
                }
                registry_file.write_text(
                    json.dumps(registry, ensure_ascii=False, indent=2),
                    encoding='utf-8'
                )
        except Exception:
            pass
        self._refresh_projects_list()

    def _remove_project_from_list(self):
        """إزالة مشروع من القائمة (لا يحذفه فعلياً)."""
        if not hasattr(self, '_projects_data'):
            return
        row = self._projects_list.currentRow()
        if row < 0 or row >= len(self._projects_data):
            return
        proj = self._projects_data[row]
        path = proj.get('path', '')
        name = proj.get('name', path)

        if QMessageBox.question(
            self, "تأكيد",
            f"إزالة من القائمة:\n{name}\n\n(لن يُحذف المجلد الفعلي)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return

        import json
        from pathlib import Path as _Path
        from AyadFlowSync.core.app_config import AppConfig
        try:
            registry_file = AppConfig.DATA_DIR / "github_projects.json"
            if registry_file.exists():
                registry = json.loads(registry_file.read_text(encoding='utf-8'))
                registry.pop(path, None)
                registry_file.write_text(
                    json.dumps(registry, ensure_ascii=False, indent=2),
                    encoding='utf-8'
                )
        except Exception:
            pass
        self._refresh_projects_list()

    @staticmethod
    def _save_push_log(path: Path, repo_name: str = "", repo_url: str = "", source: str = "PC"):
        """
        يُسجّل الرفع في مكانين:
        1. .ayadsync_push_log.json داخل مجلد المشروع (للكشف السريع)
        2. data/github_projects.json سجل مركزي لكل المشاريع المرفوعة
        """
        import json, time
        from AyadFlowSync.core.app_config import AppConfig

        now_ts   = time.time()
        path_str = str(Path(path).resolve())
        name     = repo_name or Path(path).name

        # 1. سجل المشروع الفردي
        try:
            log_file = Path(path) / '.ayadsync_push_log.json'
            log_file.write_text(
                json.dumps({'last_push_ts': now_ts, 'repo_name': name, 'repo_url': repo_url},
                           ensure_ascii=False),
                encoding='utf-8'
            )
        except Exception:
            pass

        # 2. السجل المركزي
        try:
            registry_file = AppConfig.DATA_DIR / "github_projects.json"
            registry = {}
            if registry_file.exists():
                registry = json.loads(registry_file.read_text(encoding='utf-8'))

            registry[path_str] = {
                'name':          name,
                'path':          path_str,
                'repo_url':      repo_url,
                'last_push_ts':  now_ts,
                'last_push_str': time.strftime('%Y-%m-%d %H:%M', time.localtime(now_ts)),
                'source':        source,  # PC or USB
            }
            registry_file.write_text(
                json.dumps(registry, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception:
            pass

    def _do_push(self):
        path = self._push_path.text().strip()
        if not path:
            QMessageBox.warning(self, "تحذير", "اختر مجلد المشروع!")
            return
        if not self._token:
            QMessageBox.warning(self, "تحذير", Lang.t("gh_warn_login"))
            return

        project = Path(path)
        if not project.exists():
            QMessageBox.warning(self, "⚠️", f"المجلد غير موجود:\n{path}")
            return

        # ⚡ v4.0: معاينة التغييرات + Commit ذكي
        git_dir = project / ".git"
        changed_files = []
        if git_dir.exists():
            try:
                import subprocess
                # git status --porcelain يعرض التغييرات بشكل مختصر
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(project), capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            status = line[:2].strip()
                            fname = line[3:].strip()
                            icons = {'M': '📝', 'A': '➕', 'D': '🗑️',
                                     '?': '🆕', 'R': '📛', 'C': '📋'}
                            icon = icons.get(status[0] if status else '?', '📄')
                            changed_files.append(f"{icon} {fname}")
            except Exception:
                pass

        # ⚡ v4.0: رسالة Commit ذكية
        user_msg = self._push_msg.text().strip()
        if not user_msg or user_msg == "Update via AyadFlowSync":
            if changed_files:
                n = len(changed_files)
                # استخرج أسماء أول 3 ملفات
                names = [f.split(' ', 1)[1] if ' ' in f else f for f in changed_files[:3]]
                names_str = ', '.join(Path(n).name for n in names)
                if n <= 3:
                    smart_msg = f"Update {names_str}"
                else:
                    smart_msg = f"Update {n} files: {names_str}, ..."
                from ..core.app_config import AppConfig
                pc = AppConfig.PC_NAME or "unknown"
                smart_msg += f" [{pc}]"
            else:
                smart_msg = f"Update via AyadFlowSync"
        else:
            smart_msg = user_msg

        # ⚡ v4.0: نافذة معاينة قبل الرفع
        preview_text = f"📁 المشروع: {project.name}\n"
        preview_text += f"💬 رسالة Commit: {smart_msg}\n\n"
        if changed_files:
            preview_text += f"📊 التغييرات ({len(changed_files)} ملف):\n"
            for f in changed_files[:20]:
                preview_text += f"  {f}\n"
            if len(changed_files) > 20:
                preview_text += f"  ... و {len(changed_files) - 20} ملف آخر\n"
        else:
            preview_text += "📊 لا يمكن كشف التغييرات (git غير مهيأ أو لا تغييرات)\n"
            preview_text += "سيتم رفع كل الملفات.\n"

        reply = QMessageBox.question(
            self, "📤 تأكيد الرفع",
            preview_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        token = self._token
        self.log(f"🔄  Push: {project.name}...")
        threading.Thread(
            target=self._worker_push, args=(project, smart_msg, token),
            daemon=True
        ).start()

    def _worker_push(self, path: Path, msg: str, token: str):
        try:
            self._signals.log_line.emit(f"📤 تحديث {path.name}...")
            from ...github.ops import Uploader
            up = Uploader(
                token,
                log_cb=lambda m: self._signals.log_line.emit(m),
            )
            ok = up.upload(path, path.name, update_existing=True, commit_msg=msg)
            if ok:
                self._save_push_log(path)
                # ✅ تحديث UploadLog المركزي
                try:
                    from ...github.upload_log import UploadLog
                    # نحاول نقرأ الـ repo_url من السجل المحلي
                    push_log = path / '.ayadsync_push_log.json'
                    repo_url = ""
                    repo_name = path.name
                    if push_log.exists():
                        import json as _j
                        d = _j.loads(push_log.read_text(encoding='utf-8'))
                        repo_url  = d.get("repo_url", "")
                        repo_name = d.get("repo_name", path.name)
                    UploadLog.record(str(path), "PC", repo_name, repo_url)
                    self._refresh_myprojects()
                except Exception:
                    pass
                self._signals.done.emit(True, f"✅ تم تحديث {path.name}")
            else:
                self._signals.done.emit(False, f"❌ فشل تحديث {path.name}")
        except Exception as e:
            self._signals.log_line.emit(f"❌ {e}")
            self._signals.done.emit(False, str(e))

    # ── Toggle Public↔Private ─────────────────────────────────────

    def _get_selected_repo_data(self) -> dict:
        """يُرجع repo dict من UserRole — يتجاهل عناوين الأقسام."""
        row = self._repo_list.currentRow()
        if row < 0:
            return {}
        item = self._repo_list.item(row)
        if not item:
            return {}
        data = item.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, dict) else {}

    def _toggle_visibility(self):
        repo = self._get_selected_repo_data()
        if not repo:
            QMessageBox.warning(self, "تحذير", Lang.t("gh_warn_select"))
            return
        current = "خاص" if repo.get("private") else "عام"
        new_vis = "عام" if repo.get("private") else "خاص"
        if QMessageBox.question(
            self, "تأكيد",
            f"تغيير {repo['name']} من {current} إلى {new_vis}؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            threading.Thread(
                target=self._worker_toggle, args=(repo,), daemon=True
            ).start()

    def _worker_toggle(self, repo: dict):
        try:
            from ...github.client import GitHubAPI
            api = GitHubAPI(self._token)
            new_private = not repo.get("private", False)
            api.patch(f"/repos/{repo['full_name']}", {"private": new_private})
            state = "خاص 🔒" if new_private else "عام 🌐"
            self._signals.log_line.emit(f"✅ {repo['name']} → {state}")
            self._worker_fetch_repos()
        except Exception as e:
            self._signals.log_line.emit(f"❌ {e}")

    # ── Download Repo ─────────────────────────────────────────────
    def _download_repo(self):
        repo = self._get_selected_repo_data()
        if not repo:
            return
        dest = QFileDialog.getExistingDirectory(self, "اختر مجلد التنزيل")
        if dest:
            url = repo.get("clone_url", repo.get("html_url", "") + ".git")
            self.log(f"⬇️  تنزيل {repo['name']}...")
            threading.Thread(
                target=self._worker_clone, args=(url, Path(dest) / repo["name"]), daemon=True
            ).start()

    # ── Generate README with AI ───────────────────────────────────
    def _generate_readme(self):
        """توليد README بالذكاء الاصطناعي لمشروع محلي."""
        # استخدم مسار الرفع إذا مملوء
        folder = ""
        if hasattr(self, '_upload_path') and self._upload_path.text().strip():
            folder = self._upload_path.text().strip()
        elif hasattr(self, '_push_path') and self._push_path.text().strip():
            folder = self._push_path.text().strip()
        if not folder:
            folder = QFileDialog.getExistingDirectory(self, "اختر مجلد المشروع لتوليد README")
        if not folder:
            return

        if not Path(folder).exists():
            QMessageBox.warning(self, "⚠️", f"المجلد غير موجود:\n{folder}")
            return

        # Load AI keys and dev info
        from .settings_panel import SettingsPanel
        ai_keys = SettingsPanel.get_ai_keys()
        dev_info = SettingsPanel.get_dev_info()

        if not ai_keys:
            QMessageBox.warning(
                self, "⚠️ مفتاح AI مطلوب",
                "لم تُضف أي مفتاح AI بعد.\n\n"
                "اذهب إلى: ⚙️ الإعدادات → 🤖 مفاتيح الذكاء الاصطناعي\n"
                "وأضف مفتاح Gemini أو Claude أو OpenAI أو DeepSeek."
            )
            return

        self.log(f"🤖 توليد README لـ {Path(folder).name}...")
        threading.Thread(
            target=self._worker_readme,
            args=(Path(folder), ai_keys, dev_info),
            daemon=True,
        ).start()

    def _worker_readme(self, path: Path, ai_keys: dict, dev_info: dict):
        try:
            from ...github.readme import SmartReadmeGenerator

            provider = key = None
            for p in ['gemini', 'claude', 'openai', 'deepseek']:
                if p in ai_keys and ai_keys[p]:
                    provider, key = p, ai_keys[p]
                    break

            if not provider:
                self._signals.log_line.emit("❌ لا يوجد مفتاح AI — اذهب للإعدادات")
                self._signals.done.emit(False, "لا يوجد مفتاح")
                return

            self._signals.log_line.emit(f"🤖 تحليل المشروع + توليد README بـ {provider}...")

            gen = SmartReadmeGenerator(
                path=path,
                ai_provider=provider,
                ai_key=key,
                cb=lambda m: self._signals.log_line.emit(m),
                dev_info=dev_info,
                multi_keys=ai_keys,
            )

            result = gen.generate()
            en = result.get('en', '') if isinstance(result, dict) else (result[0] if result else '')
            ar = result.get('ar', '') if isinstance(result, dict) else (result[1] if result else '')
            success = result.get('success', True) if isinstance(result, dict) else bool(en)
            provider_used = result.get('provider_used', provider) if isinstance(result, dict) else provider

            if not success:
                err = result.get('error', 'فشل التوليد') if isinstance(result, dict) else 'فشل التوليد'
                self._signals.log_line.emit(f"⚠️ التوليد فشل: {err} — جرّب مفتاح AI آخر من الإعدادات")
                self._signals.done.emit(False, "فشل التوليد")
            elif en or ar:
                gen.save(en, ar)
                self._signals.log_line.emit(f"✅ README حُفظ في: {path / 'README.md'}  [{provider_used}]")
                if ar:
                    self._signals.log_line.emit(f"✅ README_AR حُفظ في: {path / 'README_AR.md'}")
                self._signals.done.emit(True, "✅ README جاهز!")
            else:
                self._signals.log_line.emit("⚠️ التوليد فشل — جرّب مفتاح AI آخر من الإعدادات")
                self._signals.done.emit(False, "فشل التوليد")

        except Exception as e:
            import traceback
            self._signals.log_line.emit(f"❌ README خطأ: {e}")
            self._signals.log_line.emit(f"   {traceback.format_exc().splitlines()[-2]}")
            self._signals.done.emit(False, str(e))

    # ── مساعدات ───────────────────────────────────────────────────
    def log(self, msg: str):
        self._signals.log_line.emit(msg)

    def _append_log(self, msg: str):
        # ── إشارة حالة المشروع ────────────────────────────────────
        if msg.startswith("__PROJ_STATUS__"):
            try:
                rest       = msg[len("__PROJ_STATUS__"):]
                lbl_id_str, remainder = rest.split("__", 1)
                lbl_id     = int(lbl_id_str)
                parts      = remainder.split("__COLOR__")
                text       = parts[0].strip()
                color      = parts[1].strip() if len(parts) > 1 else '#94a3b8'
                label      = self._status_labels.get(lbl_id)
                if label:
                    label.setText(text)
                    label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 2px 0;")
            except Exception:
                pass
            return

        # ── نتيجة توليد README المستقل ───────────────────────────
        if msg.startswith("__README_RESULT__"):
            rest = msg[len("__README_RESULT__"):]
            if rest.startswith("SUCCESS__"):
                text = rest[len("SUCCESS__"):]
                if hasattr(self, '_readme_result_lbl'):
                    self._readme_result_lbl.setText(text)
                    self._readme_result_lbl.setStyleSheet("color: #22c55e; font-weight: bold;")
                # تحديث حالة README
                if hasattr(self, '_readme_path'):
                    self._check_readme_status(self._readme_path.text())
            else:
                text = rest[len("FAIL__"):] if rest.startswith("FAIL__") else rest
                if hasattr(self, '_readme_result_lbl'):
                    self._readme_result_lbl.setText(f"❌ {text}")
                    self._readme_result_lbl.setStyleSheet("color: #ef4444;")
            return
        if msg.startswith("__PROJECTS_READY__"):
            try:
                import json
                data = json.loads(msg[len("__PROJECTS_READY__"):])
                self._projects_data = data
                if hasattr(self, '_projects_list'):
                    self._projects_list.clear()
                    if not data:
                        item = QListWidgetItem("  — لا توجد مشاريع مرفوعة بعد —")
                        item.setFlags(Qt.ItemFlag.NoItemFlags)
                        item.setForeground(QColor("#64748b"))
                        self._projects_list.addItem(item)
                    else:
                        for proj in data:
                            icon   = proj.get('icon', '❓')
                            name   = proj.get('name', '?')
                            when   = proj.get('last_push_str', '—')
                            color  = proj.get('color', '#94a3b8')
                            item   = QListWidgetItem(f"  {icon}  {name}\n      ⏰ {when}")
                            item.setForeground(QColor(color))
                            item.setToolTip(
                                f"📍 {proj.get('path','')}\n"
                                f"🔗 {proj.get('repo_url','')}\n"
                                f"📊 {proj.get('status','')}"
                            )
                            self._projects_list.addItem(item)
                    title = f"📁 المشاريع المرفوعة ({len(data)})"
                    if hasattr(self, '_proj_list_title'):
                        self._proj_list_title.setText(title)
            except Exception as e:
                pass
            return

        # ── رسالة عادية ──────────────────────────────────────────
        self._log_box.append(msg)
        sb = self._log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_log(self):
        self._log_box.clear()

    def _on_done(self, success: bool, msg: str):
        icon = "✅" if success else "❌"
        self._append_log(f"\n{icon}  {msg}")
        if "مصادق" in msg or "Authenticated" in msg:
            self._auth_status.setText(msg)
        elif "Token" in msg and not success:
            self._auth_status.setText(msg)
        # ── بعد رفع/push ناجح → أعد فحص الحالة + تحديث القائمة ─
        if success and any(k in msg for k in ["رُفع", "تحديث", "push", "Push", "README"]):
            QTimer.singleShot(500, self._refresh_projects_list)
            for path_attr in ['_upload_path', '_push_path']:
                if hasattr(self, path_attr):
                    folder = getattr(self, path_attr).text().strip()
                    if folder and Path(folder).is_dir():
                        lbl_attr = '_upload_status_lbl' if path_attr == '_upload_path' else '_push_status_lbl'
                        if hasattr(self, lbl_attr):
                            self._check_project_changed(folder, getattr(self, lbl_attr))
