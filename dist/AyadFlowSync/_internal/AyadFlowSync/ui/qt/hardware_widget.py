#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.qt.hardware_widget
=====================
HardwareWidget — شريط مراقبة الأجهزة الحي.
يستقبل بيانات من HardwareMonitor عبر Qt Signals.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QProgressBar, QFrame
)
from PyQt6.QtCore    import Qt, pyqtSignal, QObject
from PyQt6.QtGui     import QColor


class HardwareSignals(QObject):
    """Signals للتواصل بين thread الـ monitor والـ UI thread."""
    updated = pyqtSignal(dict)


class HardwareWidget(QWidget):
    """
    شريط مراقبة CPU / RAM / USB — يُحدَّث كل ثانية.
    يُستخدم في أسفل الواجهة الرئيسية.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = HardwareSignals()
        self.signals.updated.connect(self._on_update)
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("HardwareBar")
        self.setFixedHeight(56)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 6, 12, 6)
        root.setSpacing(16)

        # ── CPU ──────────────────────────────────────────────────────
        self._cpu_lbl, self._cpu_bar = self._make_meter("🖥️ CPU", "#CpuBar")
        cpu_box = self._box(self._cpu_lbl, self._cpu_bar)
        root.addWidget(cpu_box)

        self._sep(root)

        # ── RAM ──────────────────────────────────────────────────────
        self._ram_lbl, self._ram_bar = self._make_meter("🧠 RAM", "#RamBar")
        ram_box = self._box(self._ram_lbl, self._ram_bar)
        root.addWidget(ram_box)

        self._sep(root)

        # ── USB ──────────────────────────────────────────────────────
        self._usb_lbl, self._usb_bar = self._make_meter("💾 USB", "#UsbBar")
        usb_box = self._box(self._usb_lbl, self._usb_bar)
        root.addWidget(usb_box)

        self._sep(root)

        # ── Device Profile ───────────────────────────────────────────
        self._device_lbl = QLabel("🖥️  —")
        self._device_lbl.setObjectName("Dim")
        self._device_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self._device_lbl)

        root.addStretch()

        # ── USB Speed ────────────────────────────────────────────────
        self._speed_lbl = QLabel("⚡ —")
        self._speed_lbl.setObjectName("Dim")
        self._speed_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        root.addWidget(self._speed_lbl)

    # ── مساعدات البناء ────────────────────────────────────────────
    def _make_meter(self, title: str, bar_id: str):
        lbl = QLabel(f"{title}  0%")
        lbl.setObjectName("Dim")
        lbl.setFixedWidth(100)

        bar = QProgressBar()
        bar.setObjectName(bar_id.lstrip("#"))
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        bar.setFixedWidth(100)

        return lbl, bar

    def _box(self, lbl: QLabel, bar: QProgressBar) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        v.addWidget(lbl)
        v.addWidget(bar)
        return w

    def _sep(self, layout: QHBoxLayout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        layout.addWidget(sep)

    # ── تحديث البيانات ────────────────────────────────────────────
    def notify(self, data: dict):
        """يُستدعى من thread خلفي — يرسل signal للـ UI thread."""
        self.signals.updated.emit(data)

    def _on_update(self, data: dict):
        """يُنفَّذ في UI thread فقط."""
        cpu  = data.get("cpu_pct",  0.0)
        ram  = data.get("ram_pct",  0.0)
        ram_used  = data.get("ram_used_gb",  0.0)
        ram_total = data.get("ram_total_gb", 0.0)
        usb  = data.get("usb_used_pct", 0.0)
        usb_free  = data.get("usb_free_gb", -1.0)
        spd  = data.get("usb_speed", 0.0)
        dev  = data.get("device_label", "—")

        # CPU
        self._cpu_lbl.setText(f"🖥️ CPU  {cpu:.0f}%")
        self._cpu_bar.setValue(int(cpu))
        self._set_bar_color(self._cpu_bar, cpu, "#34d399", "#fbbf24", "#f87171")

        # RAM
        ram_txt = f"{ram_used:.1f}/{ram_total:.0f} GB" if ram_total > 0 else f"{ram:.0f}%"
        self._ram_lbl.setText(f"🧠 RAM  {ram_txt}")
        self._ram_bar.setValue(int(ram))
        self._set_bar_color(self._ram_bar, ram, "#60a5fa", "#fbbf24", "#f87171")

        # USB
        if usb_free >= 0:
            self._usb_lbl.setText(f"💾 USB  {usb_free:.1f}GB free")
            self._usb_bar.setValue(int(usb))
            self._set_bar_color(self._usb_bar, usb, "#a78bfa", "#fbbf24", "#f87171")
        else:
            self._usb_lbl.setText("💾 USB  غير متصل")
            self._usb_bar.setValue(0)

        # Device + Speed
        self._device_lbl.setText(f"🖥️  {dev}")
        if spd > 0:
            icon = "🟢" if spd >= 100 else ("🟡" if spd >= 30 else "🔴")
            self._speed_lbl.setText(f"⚡ {icon} {spd:.0f} MB/s")
        else:
            self._speed_lbl.setText("⚡ —")

    @staticmethod
    def _set_bar_color(bar: QProgressBar, pct: float, ok: str, warn: str, bad: str):
        color = ok if pct < 50 else (warn if pct < 80 else bad)
        bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}"
        )
