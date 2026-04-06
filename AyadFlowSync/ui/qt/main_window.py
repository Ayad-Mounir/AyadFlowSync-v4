#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.qt.main_window
=================
⚡ v4.0 — النافذة الرئيسية مع:
  - لوحة تحكم (Dashboard) كأول شاشة
  - إشعارات Toast
  - اختصارات لوحة المفاتيح
  - سحب وإفلات (Drag & Drop)
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame,
    QSizePolicy, QSplashScreen, QApplication
)
from PyQt6.QtCore    import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui     import (
    QFont, QPixmap, QColor, QPainter, QLinearGradient,
    QShortcut, QKeySequence
)

from ...core.app_config      import AppConfig
from ...core.device_profiler import DeviceProfiler, DeviceProfile
from ...core.hardware        import HardwareMonitor
from ...core.constants       import APP_NAME, APP_VERSION, Theme
from ...lang.lang            import Lang

from .hardware_widget  import HardwareWidget
from .dashboard_panel  import DashboardPanel
from .sync_panel       import SyncPanel
from .github_panel     import GithubPanel
from .settings_panel   import SettingsPanel
from .drive_panel      import DrivePanel
from .about_panel      import AboutPanel
from .toast_widget     import ToastWidget
from .styles           import MAIN_STYLESHEET


# ══════════════════════════════════════════════════════════════════
# SplashScreen
# ══════════════════════════════════════════════════════════════════

class SplashScreen(QSplashScreen):
    def __init__(self):
        px = QPixmap(520, 300)
        px.fill(QColor("#0b0d11"))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 520, 300)
        grad.setColorAt(0, QColor("#0b0d11"))
        grad.setColorAt(1, QColor("#13161e"))
        p.fillRect(0, 0, 520, 300, grad)
        p.setPen(QColor("#6366f1"))
        p.fillRect(0, 0, 520, 3, QColor("#6366f1"))
        p.setPen(QColor("#e2e8f0"))
        p.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        p.drawText(0, 0, 520, 160, Qt.AlignmentFlag.AlignCenter, "⚡ AyadFlowSync")
        p.setFont(QFont("Segoe UI", 18))
        p.setPen(QColor("#6366f1"))
        p.drawText(0, 80, 520, 60, Qt.AlignmentFlag.AlignCenter, f"v{APP_VERSION}")
        p.setFont(QFont("Segoe UI", 16))
        p.setPen(QColor("#4a5568"))
        p.drawText(0, 220, 520, 40, Qt.AlignmentFlag.AlignCenter, "by Mounir Ayad")
        p.end()
        super().__init__(px)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

    def set_status(self, msg: str, pct: int = -1):
        self.showMessage(
            f"  {msg}",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
            QColor("#718096"),
        )
        QApplication.processEvents()


# ══════════════════════════════════════════════════════════════════
# ProfilerThread
# ══════════════════════════════════════════════════════════════════

class ProfilerThread(QThread):
    done = pyqtSignal(str)

    def run(self):
        DeviceProfiler.measure()
        self.done.emit(DeviceProfiler.get_label())


# ══════════════════════════════════════════════════════════════════
# MainWindow
# ══════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    lang_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._hw_monitor: HardwareMonitor = None
        self._current_nav = 0
        self._build_ui()
        self._setup_shortcuts()
        self._setup_drag_drop()
        self._start_hardware_monitor()

    def _build_ui(self):
        self.setStyleSheet(MAIN_STYLESHEET)
        self.setWindowTitle(
            f"AyadFlowSync v{APP_VERSION}  ·  {AppConfig.PC_NAME or Lang.t('local_device')}"
            f"  ·  {DeviceProfiler.get_label()}"
        )
        self.resize(1360, 880)
        self.setMinimumSize(960, 640)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        body.addWidget(self._build_sidebar())

        self._stack = QStackedWidget()

        # ⚡ v4.0: Dashboard كأول لوحة
        self._dashboard_panel = DashboardPanel()
        self._sync_panel      = SyncPanel()
        self._github_panel    = GithubPanel()
        self._drive_panel     = DrivePanel()
        self._settings_panel  = SettingsPanel()
        self._about_panel     = AboutPanel()

        self._stack.addWidget(self._dashboard_panel)  # 0
        self._stack.addWidget(self._sync_panel)       # 1
        self._stack.addWidget(self._github_panel)     # 2
        self._stack.addWidget(self._drive_panel)      # 3
        self._stack.addWidget(self._settings_panel)   # 4
        self._stack.addWidget(self._about_panel)      # 5
        body.addWidget(self._stack, 1)

        # Dashboard → Sync navigation
        self._dashboard_panel.navigate_to.connect(self._navigate)

        # تغيير اللغة
        self.lang_changed.connect(self._dashboard_panel.retranslateUi)
        self.lang_changed.connect(self._sync_panel.retranslateUi)
        self.lang_changed.connect(self._github_panel.retranslateUi)
        self.lang_changed.connect(self._drive_panel.retranslateUi)
        self.lang_changed.connect(self._settings_panel.retranslateUi)
        self.lang_changed.connect(self._about_panel.retranslateUi)
        self.lang_changed.connect(self._retranslate_sidebar)
        self._settings_panel.language_changed.connect(self._on_lang_changed)

        self._navigate(0)
        outer.addLayout(body, 1)

        # Hardware bar
        self._hw_widget = HardwareWidget()
        hw_frame = QFrame()
        hw_frame.setFrameShape(QFrame.Shape.HLine)
        hw_ly = QVBoxLayout(hw_frame)
        hw_ly.setContentsMargins(0, 0, 0, 0)
        hw_ly.setSpacing(0)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        hw_ly.addWidget(sep)
        hw_ly.addWidget(self._hw_widget)
        outer.addWidget(hw_frame)

        # ⚡ v4.0: Toast
        self._toast = ToastWidget(central)

        self.statusBar().showMessage(
            f"{Lang.t('app_ready')}  |  {DeviceProfiler.get_specs_text()}"
        )

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        ly = QVBoxLayout(sidebar)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        self._sidebar_title = QLabel(Lang.t("sidebar_title"))
        self._sidebar_title.setObjectName("SidebarTitle")
        self._sidebar_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(self._sidebar_title)

        ver = QLabel(f"v{APP_VERSION}")
        ver.setObjectName("SidebarVersion")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(ver)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        ly.addWidget(sep)
        ly.addSpacing(8)

        nav_keys = [
            "nav_dashboard", "nav_sync", "nav_github",
            "nav_drive", "nav_settings", "nav_about"
        ]
        hints = ["Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4", "Ctrl+5", "Ctrl+6"]
        self._nav_btns = []
        self._nav_keys = nav_keys
        for i, key in enumerate(nav_keys):
            btn = QPushButton(Lang.t(key))
            btn.setObjectName("NavBtn")
            btn.setCheckable(False)
            btn.setToolTip(f"{Lang.t(key)}  ({hints[i]})")
            btn.clicked.connect(lambda _, idx=i: self._navigate(idx))
            ly.addWidget(btn)
            self._nav_btns.append(btn)

        ly.addStretch()
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        ly.addWidget(sep2)

        self._pc_lbl = QLabel(f"💻  {AppConfig.PC_NAME or '—'}")
        self._pc_lbl.setObjectName("Muted")
        self._pc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pc_lbl.setWordWrap(True)
        ly.addWidget(self._pc_lbl)

        self._dev_lbl = QLabel(DeviceProfiler.get_label())
        self._dev_lbl.setObjectName("Muted")
        self._dev_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(self._dev_lbl)
        ly.addSpacing(8)

        return sidebar

    # ── اختصارات لوحة المفاتيح ────────────────────────────────
    def _setup_shortcuts(self):
        for i in range(6):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda idx=i: self._navigate(idx))
        # Ctrl+R = تحديث Dashboard
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(
            lambda: self._dashboard_panel._refresh_data()
        )

    # ── سحب وإفلات ──────────────────────────────────────────
    def _setup_drag_drop(self):
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            from pathlib import Path
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).is_dir():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            from pathlib import Path
            for url in event.mimeData().urls():
                p = Path(url.toLocalFile())
                if p.is_dir():
                    try:
                        projects = self._sync_panel._projects
                        folder = str(p)
                        if folder not in projects:
                            projects.append(folder)
                            self._sync_panel._save_projects()
                            self._sync_panel._refresh_list()
                            self.toast(f"✅ أُضيف: {p.name}", "success")
                            self._navigate(1)
                        else:
                            self.toast(f"ℹ️ موجود مسبقاً: {p.name}", "info")
                    except Exception as e:
                        self.toast(f"❌ خطأ: {e}", "error")
                    event.acceptProposedAction()
                    return
        event.ignore()

    # ── Toast API ───────────────────────────────────────────
    def toast(self, message: str, level: str = "info"):
        if hasattr(self, '_toast'):
            self._toast.show_toast(message, level)

    def _retranslate_sidebar(self):
        self._sidebar_title.setText(Lang.t("sidebar_title"))
        for i, btn in enumerate(self._nav_btns):
            btn.setText(Lang.t(self._nav_keys[i]))
        self.statusBar().showMessage(
            f"{Lang.t('app_ready')}  |  {DeviceProfiler.get_specs_text()}"
        )

    def _on_lang_changed(self):
        self.lang_changed.emit()

    def _navigate(self, idx: int):
        self._current_nav = idx
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _start_hardware_monitor(self):
        self._hw_monitor = HardwareMonitor(usb_path_ref=lambda: AppConfig.VAULT_DIR)
        self._hw_monitor.add_callback(self._hw_widget.notify)
        data = self._hw_monitor.collect_now()
        if data:
            self._hw_widget.notify(data)
        self._hw_monitor.start()

    def closeEvent(self, event):
        if self._hw_monitor:
            self._hw_monitor.stop()
        super().closeEvent(event)
