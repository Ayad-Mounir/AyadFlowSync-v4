#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.qt.toast_widget
==================
⚡ v4.0 — إشعارات Toast احترافية
تنزلق من الأعلى وتختفي لوحدها — بدل النوافذ المنبثقة المزعجة.
"""

from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QPushButton, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QFont

from ...core.constants import Theme


class ToastWidget(QWidget):
    """
    إشعار Toast — ينزلق من الأعلى ويختفي لوحده.

    الاستخدام:
        toast = ToastWidget(parent)
        toast.show_toast("✅ تمت المزامنة بنجاح", "success")
        toast.show_toast("⚠️ تنبيه: مساحة منخفضة", "warning")
        toast.show_toast("❌ فشلت العملية", "error")
    """

    _COLORS = {
        "success": {"bg": "#065f46", "border": "#34d399", "text": "#d1fae5"},
        "warning": {"bg": "#78350f", "border": "#fbbf24", "text": "#fef3c7"},
        "error":   {"bg": "#7f1d1d", "border": "#f87171", "text": "#fecaca"},
        "info":    {"bg": "#1e3a5f", "border": "#60a5fa", "text": "#dbeafe"},
    }
    _DURATION = 4000   # 4 ثواني ثم يختفي

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedHeight(48)

        self._queue = []
        self._showing = False

        ly = QHBoxLayout(self)
        ly.setContentsMargins(16, 6, 12, 6)
        ly.setSpacing(8)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFont(QFont("Segoe UI", 16))
        ly.addWidget(self._icon_lbl)

        self._msg_lbl = QLabel()
        self._msg_lbl.setFont(QFont("Segoe UI", 13))
        ly.addWidget(self._msg_lbl, 1)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #94a3b8; "
            "border: none; font-size: 14px; } "
            "QPushButton:hover { color: #e2e8f0; }"
        )
        self._close_btn.clicked.connect(self._dismiss)
        ly.addWidget(self._close_btn)

        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0.0)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

    def show_toast(self, message: str, level: str = "info", duration: int = None):
        """
        يعرض إشعار Toast.
        level: "success" / "warning" / "error" / "info"
        """
        if self._showing:
            self._queue.append((message, level, duration))
            return

        self._showing = True
        colors = self._COLORS.get(level, self._COLORS["info"])

        # أيقونة حسب النوع
        icons = {"success": "✅", "warning": "⚠️", "error": "❌", "info": "ℹ️"}
        self._icon_lbl.setText(icons.get(level, "ℹ️"))
        self._msg_lbl.setText(message)
        self._msg_lbl.setStyleSheet(f"color: {colors['text']};")

        self.setStyleSheet(
            f"ToastWidget {{ "
            f"  background-color: {colors['bg']}; "
            f"  border: 1px solid {colors['border']}; "
            f"  border-radius: 8px; "
            f"}}"
        )

        # حساب الموقع: أعلى منتصف النافذة الأب
        if self.parent():
            pw = self.parent().width()
            w = min(pw - 40, 600)
            self.setFixedWidth(w)
            x = (pw - w) // 2
            self.move(x, 8)

        self.show()
        self.raise_()

        # أنمشن الظهور
        self._opacity.setOpacity(0.0)
        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setDuration(250)
        anim.setStartValue(0.0)
        anim.setEndValue(0.95)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim = anim  # حافظ على المرجع

        # مؤقت الاختفاء
        dur = duration or self._DURATION
        if level == "error":
            dur = max(dur, 6000)  # الأخطاء تبقى أطول
        self._timer.start(dur)

    def _fade_out(self):
        anim = QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setDuration(400)
        anim.setStartValue(0.95)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self._on_hidden)
        anim.start()
        self._anim = anim

    def _dismiss(self):
        self._timer.stop()
        self._fade_out()

    def _on_hidden(self):
        self.hide()
        self._showing = False
        # عرض الإشعار التالي في الصف
        if self._queue:
            msg, lvl, dur = self._queue.pop(0)
            QTimer.singleShot(200, lambda: self.show_toast(msg, lvl, dur))
