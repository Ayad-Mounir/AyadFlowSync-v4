#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.qt.about_panel — صفحة "حول" احترافية مع دعم كامل لتغيير اللغة
"""

import sys
import platform
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QDesktopServices, QLinearGradient
from PyQt6.QtCore import QUrl

from ...core.constants import APP_NAME, APP_VERSION, APP_AUTHOR, Theme
from ...core.app_config import AppConfig
from ...core.device_profiler import DeviceProfiler
from ...lang.lang import Lang


class AboutPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        # ══ Header ═══════════════════════════════════════════
        hdr = QFrame()
        hdr.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {Theme.ACCENT}12, stop:1 {Theme.BG_CARD});"
            f"border: 1px solid {Theme.ACCENT}20; border-radius: 14px;")
        hly = QVBoxLayout(hdr)
        hly.setContentsMargins(24, 28, 24, 24)
        hly.setSpacing(6)

        hly.addWidget(self._centered("⚡", Theme.TEXT, 36))
        hly.addWidget(self._centered("AyadFlowSync", Theme.ACCENT2, 26, bold=True))

        ver = QLabel(f"v{APP_VERSION}")
        ver.setFont(QFont(Theme.FONT_MONO, 13))
        ver.setStyleSheet(
            f"color:{Theme.ACCENT}; background:{Theme.ACCENT}15; "
            f"padding:3px 14px; border-radius:10px;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setFixedWidth(80)
        vr = QHBoxLayout()
        vr.addStretch(); vr.addWidget(ver); vr.addStretch()
        hly.addLayout(vr)
        hly.addSpacing(8)
        hly.addWidget(self._centered(Lang.t("about_subtitle"), Theme.TEXT_DIM, 12, wrap=True))
        root.addWidget(hdr)

        # ══ Stats Row ════════════════════════════════════════
        sr = QHBoxLayout()
        sr.setSpacing(8)
        for val, key, color in [
            ("5", "about_stat_sync", Theme.CYAN),
            ("4", "about_stat_perf", Theme.SUCCESS),
            ("8", "about_stat_gh", Theme.ACCENT2),
            ("AR/EN", "about_stat_lang", Theme.WARNING),
        ]:
            sr.addWidget(self._stat_box(val, Lang.t(key), color), 1)
        root.addLayout(sr)

        # ══ Features ═════════════════════════════════════════
        root.addWidget(self._section(Lang.t("about_feat_title")))
        fg = QGridLayout()
        fg.setSpacing(8)
        features = [
            ("🔄", "about_fc_sync", "about_fc_sync_d", Theme.CYAN),
            ("⚡", "about_fc_snap", "about_fc_snap_d", Theme.ACCENT2),
            ("🛡️", "about_fc_hash", "about_fc_hash_d", Theme.SUCCESS),
            ("📊", "about_fc_prof", "about_fc_prof_d", Theme.WARNING),
            ("🐙", "about_fc_gh", "about_fc_gh_d", Theme.SUCCESS),
            ("🗑️", "about_fc_trash", "about_fc_trash_d", Theme.ERROR),
            ("💾", "about_fc_port", "about_fc_port_d", Theme.CYAN),
            ("🔐", "about_fc_enc", "about_fc_enc_d", Theme.ACCENT2),
        ]
        for i, (icon, tk, dk, color) in enumerate(features):
            fg.addWidget(self._feat(icon, Lang.t(tk), Lang.t(dk), color), i // 2, i % 2)
        root.addLayout(fg)

        # ══ Developer ════════════════════════════════════════
        root.addWidget(self._section(Lang.t("about_dev_title")))
        dev = QFrame()
        dev.setObjectName("Card")
        dly = QHBoxLayout(dev)
        dly.setContentsMargins(20, 16, 20, 16)
        dly.setSpacing(16)

        avatar = QLabel("M")
        avatar.setFixedSize(52, 52)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont(Theme.FONT_UI, 22, QFont.Weight.Bold))
        avatar.setStyleSheet(f"color:white; background:{Theme.ACCENT}; border-radius:26px;")
        dly.addWidget(avatar)

        di = QVBoxLayout()
        di.setSpacing(3)
        dn = QLabel(APP_AUTHOR)
        dn.setFont(QFont(Theme.FONT_UI, 15, QFont.Weight.Bold))
        dn.setStyleSheet(f"color:{Theme.TEXT};")
        di.addWidget(dn)
        dr = QLabel(Lang.t("about_dev_role"))
        dr.setFont(QFont(Theme.FONT_UI, 10))
        dr.setStyleSheet(f"color:{Theme.TEXT_DIM};")
        di.addWidget(dr)
        de = QLabel("contact.ayad.mounir@gmail.com")
        de.setFont(QFont(Theme.FONT_MONO, 9))
        de.setStyleSheet(f"color:{Theme.TEXT_MUTED};")
        di.addWidget(de)
        dly.addLayout(di, 1)

        db = QVBoxLayout()
        db.setSpacing(6)
        bg = QPushButton("🐙  GitHub")
        bg.setObjectName("PrimaryBtn")
        bg.setFixedWidth(120)
        bg.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/Ayad-Mounir")))
        db.addWidget(bg)
        be = QPushButton("📧  Email")
        be.setFixedWidth(120)
        be.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("mailto:contact.ayad.mounir@gmail.com")))
        db.addWidget(be)
        dly.addLayout(db)
        root.addWidget(dev)

        # ══ System Info ══════════════════════════════════════
        root.addWidget(self._section(Lang.t("about_sys_title")))
        sf = QFrame()
        sf.setObjectName("Card")
        sg = QGridLayout(sf)
        sg.setContentsMargins(16, 12, 16, 12)
        sg.setSpacing(4)

        info = DeviceProfiler.get_detailed_info()
        rows = [
            (Lang.t("about_sys_os_lbl"), f"{platform.system()} {platform.release()}", Theme.TEXT),
            ("Python", sys.version.split()[0], Theme.TEXT),
            (Lang.t("about_sys_dev_lbl"), f"{info['label']} ({info['score']}/100)", info['color']),
            (Lang.t("about_sys_cpu_lbl"), f"{info['cores']} {'نواة' if Lang._lang == 'ar' else 'cores'}", Theme.TEXT),
            (Lang.t("about_sys_ram_lbl"), f"{info['ram_avail']:.1f} / {info['ram_total']:.0f} GB", Theme.TEXT),
            ("Hash", f"{info['hash_speed']:.0f} MB/s", Theme.TEXT),
            ("USB", DeviceProfiler.get_usb_specs_text().replace("💾  ", ""), Theme.TEXT),
            (Lang.t("about_sys_pc_lbl"), AppConfig.PC_NAME or "—", Theme.ACCENT),
        ]
        for i, (label, value, color) in enumerate(rows):
            l = QLabel(label)
            l.setFont(QFont(Theme.FONT_UI, 10))
            l.setStyleSheet(f"color:{Theme.TEXT_MUTED};")
            sg.addWidget(l, i, 0)
            v = QLabel(value)
            v.setFont(QFont(Theme.FONT_MONO, 10))
            v.setStyleSheet(f"color:{color};")
            sg.addWidget(v, i, 1)
        root.addWidget(sf)

        # ══ Footer ═══════════════════════════════════════════
        root.addWidget(self._centered(
            f"{Lang.t('about_made_by')} {APP_AUTHOR}  ·  {Lang.t('about_license_lbl')}",
            Theme.TEXT_MUTED, 10
        ))

        root.addStretch()
        scroll.setWidget(content)
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.addWidget(scroll)

    # ── helpers ──────────────────────────────────────────────
    def _centered(self, text, color, size, bold=False, wrap=False):
        l = QLabel(text)
        w = QFont.Weight.Bold if bold else QFont.Weight.Normal
        l.setFont(QFont(Theme.FONT_UI, size, w))
        l.setStyleSheet(f"color:{color};")
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if wrap:
            l.setWordWrap(True)
        return l

    def _section(self, text):
        l = QLabel(text)
        l.setFont(QFont(Theme.FONT_UI, 14, QFont.Weight.Bold))
        l.setStyleSheet(f"color:{Theme.ACCENT2};")
        return l

    def _stat_box(self, value, label, color):
        f = QFrame()
        f.setStyleSheet(f"background:{color}0A; border:1px solid {color}18; border-radius:10px;")
        ly = QVBoxLayout(f)
        ly.setContentsMargins(8, 10, 8, 10)
        ly.setSpacing(2)
        v = QLabel(value)
        v.setFont(QFont(Theme.FONT_MONO, 18, QFont.Weight.Bold))
        v.setStyleSheet(f"color:{color};")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(v)
        l = QLabel(label)
        l.setFont(QFont(Theme.FONT_UI, 9))
        l.setStyleSheet(f"color:{Theme.TEXT_DIM};")
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(l)
        return f

    def _feat(self, icon, title, desc, color):
        f = QFrame()
        f.setStyleSheet(
            f"QFrame{{background:{Theme.BG_CARD}; border:1px solid {Theme.BORDER}; "
            f"border-radius:10px; border-left:3px solid {color};}}")
        ly = QHBoxLayout(f)
        ly.setContentsMargins(12, 10, 12, 10)
        ly.setSpacing(10)
        ic = QLabel(icon)
        ic.setFont(QFont(Theme.FONT_UI, 18))
        ic.setFixedWidth(28)
        ly.addWidget(ic)
        tl = QVBoxLayout()
        tl.setSpacing(1)
        t = QLabel(title)
        t.setFont(QFont(Theme.FONT_UI, 11, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{Theme.TEXT}; border:none;")
        tl.addWidget(t)
        d = QLabel(desc)
        d.setFont(QFont(Theme.FONT_UI, 9))
        d.setStyleSheet(f"color:{Theme.TEXT_DIM}; border:none;")
        d.setWordWrap(True)
        tl.addWidget(d)
        ly.addLayout(tl, 1)
        return f

    def retranslateUi(self):
        ly = self.layout()
        if ly:
            it = ly.itemAt(0)
            if it and it.widget():
                old = it.widget()
                ly.removeWidget(old)
                old.deleteLater()
        self._build_ui()
