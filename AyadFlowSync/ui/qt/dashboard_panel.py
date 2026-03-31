#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.qt.dashboard_panel
=====================
⚡ v4.0 — لوحة تحكم احترافية — أنمشن صحيح + تصميم نظيف.
"""

import os
import json
import shutil
import threading
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, pyqtProperty, QRect,
    QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup
)
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QLinearGradient, QBrush

from ...core.app_config import AppConfig
from ...core.constants import APP_VERSION, Theme, fmt_size
from ...core.device_profiler import DeviceProfiler
from ...lang.lang import Lang


# ══════════════════════════════════════════════════════════════════
# ScoreArc — مقياس دائري متحرك
# ══════════════════════════════════════════════════════════════════

class ScoreArc(QWidget):
    """قوس نقاط متحرك — يستخدم pyqtProperty للأنمشن."""

    def __init__(self, score=0, max_score=35, label="", color="#6366f1", parent=None):
        super().__init__(parent)
        self._score = score
        self._max = max_score
        self._label = label
        self._color = QColor(color)
        self._pct = 0.0          # 0.0 → 1.0 — يتحرك بالأنمشن
        self.setFixedSize(88, 98)

    # ── pyqtProperty — هذا اللي يخلي الأنمشن يشتغل ──
    def _get_pct(self):
        return self._pct

    def _set_pct(self, v):
        self._pct = v
        self.update()

    pct = pyqtProperty(float, _get_pct, _set_pct)

    def animate(self):
        target = self._score / max(self._max, 1)
        anim = QPropertyAnimation(self, b"pct", self)
        anim.setDuration(1000)
        anim.setStartValue(0.0)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim_ref = anim   # احفظ المرجع

    def set_score(self, score):
        self._score = score
        self.animate()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy, r = 44, 40, 32
        arc_rect = QRect(cx - r, cy - r, r * 2, r * 2)

        # خلفية القوس
        p.setPen(QPen(QColor(Theme.BORDER), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc_rect, 225 * 16, -270 * 16)

        # القوس الملون
        if self._pct > 0.001:
            p.setPen(QPen(self._color, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            span = int(-270 * 16 * self._pct)
            p.drawArc(arc_rect, 225 * 16, span)

        # الرقم
        shown = int(self._score * min(self._pct / max(self._score / max(self._max, 1), 0.01), 1.0)) if self._pct > 0 else 0
        if self._pct >= (self._score / max(self._max, 1)) - 0.01:
            shown = self._score
        p.setPen(self._color)
        p.setFont(QFont(Theme.FONT_MONO, 15, QFont.Weight.Bold))
        p.drawText(QRect(cx - 18, cy - 12, 36, 20), Qt.AlignmentFlag.AlignCenter, str(shown))

        # /max
        p.setPen(QColor(Theme.TEXT_MUTED))
        p.setFont(QFont(Theme.FONT_UI, 8))
        p.drawText(QRect(cx - 14, cy + 7, 28, 12), Qt.AlignmentFlag.AlignCenter, f"/{self._max}")

        # Label
        p.setPen(QColor(Theme.TEXT_DIM))
        p.setFont(QFont(Theme.FONT_UI, 10))
        p.drawText(QRect(0, 80, 88, 16), Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()


# ══════════════════════════════════════════════════════════════════
# ProgressStrip — شريط أداء صغير
# ══════════════════════════════════════════════════════════════════

class ProgressStrip(QWidget):
    """شريط تقدم مع label ورقم."""

    def __init__(self, value=0, max_val=16, label="", color="#6366f1", parent=None):
        super().__init__(parent)
        self._val = value
        self._max = max_val
        self._label = label
        self._color = QColor(color)
        self.setFixedHeight(16)

    def set_value(self, v):
        self._val = v
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()

        # label
        p.setPen(QColor(Theme.TEXT_DIM))
        p.setFont(QFont(Theme.FONT_UI, 9))
        p.drawText(QRect(0, 0, 54, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._label)

        # bar
        bx, bw, bh, by = 60, w - 100, 4, 6
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(Theme.BORDER))
        p.drawRoundedRect(bx, by, bw, bh, 2, 2)

        pct = min(self._val / max(self._max, 1), 1.0)
        fw = int(bw * pct)
        if fw > 0:
            g = QLinearGradient(bx, 0, bx + fw, 0)
            g.setColorAt(0, QColor(self._color.red(), self._color.green(), self._color.blue(), 90))
            g.setColorAt(1, self._color)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(bx, by, fw, bh, 2, 2)

        # value
        p.setPen(self._color)
        p.setFont(QFont(Theme.FONT_MONO, 9))
        p.drawText(QRect(w - 38, 0, 38, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(self._val))
        p.end()


# ══════════════════════════════════════════════════════════════════
# DashboardPanel
# ══════════════════════════════════════════════════════════════════

class DashboardPanel(QWidget):
    navigate_to = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._arcs = []
        self._build_ui()
        QTimer.singleShot(300, self._refresh_data)
        QTimer.singleShot(500, self._animate_arcs)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_data)
        self._timer.start(30_000)

    # ── بناء الواجهة ────────────────────────────────────────────
    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        t = QLabel(f"⚡ {Lang.t('dash_title')}")
        t.setFont(QFont(Theme.FONT_UI, 19, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {Theme.ACCENT2};")
        hdr.addWidget(t)
        hdr.addStretch()
        self._clock = QLabel()
        self._clock.setFont(QFont(Theme.FONT_MONO, 10))
        self._clock.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        hdr.addWidget(self._clock)
        root.addLayout(hdr)

        # ── 3 بطاقات علوية ──────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self._mk_usb_card(), 10)
        top.addWidget(self._mk_pc_card(), 14)
        top.addWidget(self._mk_gh_card(), 10)
        root.addLayout(top)

        # ── صف سفلي ──────────────────────────────────────────────
        bot = QHBoxLayout()
        bot.setSpacing(10)
        bot.addWidget(self._mk_attn_card(), 12)
        bot.addWidget(self._mk_hist_card(), 10)
        root.addLayout(bot)

        root.addStretch()
        scroll.setWidget(content)
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.addWidget(scroll)

    # ── مساعدات بناء ─────────────────────────────────────────────
    def _card(self, accent="") -> QFrame:
        f = QFrame()
        f.setObjectName("Card")
        if accent:
            f.setStyleSheet(
                f"QFrame#Card {{ background: {Theme.BG_CARD}; "
                f"border: 1px solid {Theme.BORDER}; border-radius: 12px; "
                f"border-top: 2px solid {accent}40; }}")
        return f

    def _h(self, text, color=Theme.TEXT, size=12, bold=False, mono=False):
        l = QLabel(text)
        fam = Theme.FONT_MONO if mono else Theme.FONT_UI
        w = QFont.Weight.Bold if bold else QFont.Weight.Normal
        l.setFont(QFont(fam, size, w))
        l.setStyleSheet(f"color: {color};")
        return l

    def _badge(self, text, color):
        l = QLabel(text)
        l.setStyleSheet(
            f"color:{color}; background:{color}18; font-size:10px; "
            f"font-weight:600; padding:2px 8px; border-radius:4px;")
        return l

    # ══ USB Card ═════════════════════════════════════════════════
    def _mk_usb_card(self):
        c = self._card(Theme.CYAN)
        ly = QVBoxLayout(c)
        ly.setContentsMargins(14, 12, 14, 12)
        ly.setSpacing(6)

        r = QHBoxLayout()
        r.addWidget(self._h("💾", size=18))
        r.addWidget(self._h("الفلاشة", Theme.CYAN, 12, True))
        r.addStretch()
        self._usb_badge = self._badge("—", Theme.TEXT_MUTED)
        r.addWidget(self._usb_badge)
        ly.addLayout(r)

        r2 = QHBoxLayout()
        self._usb_used = self._h("—", Theme.TEXT, 20, True, True)
        r2.addWidget(self._usb_used)
        self._usb_total = self._h("", Theme.TEXT_DIM, 10)
        r2.addWidget(self._usb_total)
        r2.addStretch()
        ly.addLayout(r2)

        # شريط المساحة
        self._usb_bar_bg = QFrame()
        self._usb_bar_bg.setFixedHeight(5)
        self._usb_bar_bg.setStyleSheet(f"background:{Theme.BORDER}; border-radius:2px;")
        ly.addWidget(self._usb_bar_bg)
        self._usb_fill = QFrame(self._usb_bar_bg)
        self._usb_fill.setFixedHeight(5)
        self._usb_fill.setGeometry(0, 0, 0, 5)

        r3 = QHBoxLayout()
        self._usb_proj = self._h("—", Theme.TEXT_DIM, 10)
        r3.addWidget(self._usb_proj)
        r3.addStretch()
        self._usb_spd = self._h("", Theme.TEXT_DIM, 10)
        r3.addWidget(self._usb_spd)
        ly.addLayout(r3)
        return c

    # ══ PC Card ══════════════════════════════════════════════════
    def _mk_pc_card(self):
        c = self._card(Theme.ACCENT)
        ly = QVBoxLayout(c)
        ly.setContentsMargins(14, 12, 14, 10)
        ly.setSpacing(4)

        # Header
        r = QHBoxLayout()
        r.addWidget(self._h("💻", size=18))
        self._pc_name = self._h("—", Theme.TEXT, 13, True)
        r.addWidget(self._pc_name)
        self._pc_lvl = self._h("", Theme.TEXT_DIM, 10)
        r.addWidget(self._pc_lvl)
        r.addStretch()
        # Score box
        self._score_frame = QFrame()
        self._score_frame.setFixedSize(50, 42)
        sf_ly = QVBoxLayout(self._score_frame)
        sf_ly.setContentsMargins(0, 3, 0, 1)
        sf_ly.setSpacing(0)
        self._score_num = self._h("—", Theme.ACCENT, 17, True, True)
        self._score_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sf_ly.addWidget(self._score_num)
        s100 = self._h("/100", Theme.TEXT_MUTED, 8)
        s100.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sf_ly.addWidget(s100)
        r.addWidget(self._score_frame)
        ly.addLayout(r)

        # Specs
        self._pc_specs = self._h("", Theme.TEXT_MUTED, 10)
        ly.addWidget(self._pc_specs)

        # Arcs
        arc_row = QHBoxLayout()
        arc_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arc_row.setSpacing(10)
        self._arc_cpu = ScoreArc(0, 35, "CPU", Theme.ACCENT2)
        self._arc_ram = ScoreArc(0, 35, "RAM", Theme.SUCCESS)
        self._arc_hash = ScoreArc(0, 30, "Hash", Theme.CYAN)
        self._arcs = [self._arc_cpu, self._arc_ram, self._arc_hash]
        for a in self._arcs:
            arc_row.addWidget(a)
        ly.addLayout(arc_row)

        # Bars
        self._bar_thr = ProgressStrip(0, 16, "Threads", Theme.ACCENT2)
        self._bar_bat = ProgressStrip(0, 2000, "Batch", Theme.SUCCESS)
        ly.addWidget(self._bar_thr)
        ly.addWidget(self._bar_bat)
        return c

    # ══ GitHub Card ══════════════════════════════════════════════
    def _mk_gh_card(self):
        c = self._card(Theme.SUCCESS)
        ly = QVBoxLayout(c)
        ly.setContentsMargins(14, 12, 14, 12)
        ly.setSpacing(6)

        r = QHBoxLayout()
        r.addWidget(self._h("🐙", size=18))
        r.addWidget(self._h("GitHub", Theme.SUCCESS, 12, True))
        r.addStretch()
        self._gh_auth = self._h("—", Theme.TEXT_DIM, 10)
        r.addWidget(self._gh_auth)
        ly.addLayout(r)

        grid = QGridLayout()
        grid.setSpacing(5)
        self._gh_nums = {}
        for i, (k, lbl, clr) in enumerate([
            ("total", "مستودع", Theme.TEXT),
            ("changed", "يحتاج رفع", Theme.WARNING),
            ("synced", "متزامن", Theme.SUCCESS),
            ("missing", "مفقود", Theme.ERROR),
        ]):
            box = QFrame()
            box.setStyleSheet(f"background:{clr}08; border:1px solid {clr}12; border-radius:7px;")
            b = QVBoxLayout(box)
            b.setContentsMargins(2, 5, 2, 5)
            b.setSpacing(1)
            n = self._h("0", clr, 16, True, True)
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b.addWidget(n)
            lb = self._h(lbl, Theme.TEXT_DIM, 9)
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b.addWidget(lb)
            grid.addWidget(box, i // 2, i % 2)
            self._gh_nums[k] = n
        ly.addLayout(grid)
        return c

    # ══ Attention Card ═══════════════════════════════════════════
    def _mk_attn_card(self):
        c = self._card()
        ly = QVBoxLayout(c)
        ly.setContentsMargins(14, 12, 14, 12)
        ly.setSpacing(6)

        r = QHBoxLayout()
        r.addWidget(self._h("⚡", size=14))
        r.addWidget(self._h(Lang.t("dash_attention"), Theme.WARNING, 12, True))
        r.addStretch()
        self._attn_cnt = self._badge("0", Theme.WARNING)
        r.addWidget(self._attn_cnt)
        btn = QPushButton(f"→ {Lang.t('dash_go_sync')}")
        btn.setObjectName("PrimaryBtn")
        btn.setFixedHeight(26)
        btn.setFixedWidth(90)
        btn.clicked.connect(lambda: self.navigate_to.emit(1))
        r.addWidget(btn)
        ly.addLayout(r)

        self._attn_box = QVBoxLayout()
        self._attn_box.setSpacing(4)
        ly.addLayout(self._attn_box)
        return c

    # ══ History Card ═════════════════════════════════════════════
    def _mk_hist_card(self):
        c = self._card()
        ly = QVBoxLayout(c)
        ly.setContentsMargins(14, 12, 14, 12)
        ly.setSpacing(4)

        r = QHBoxLayout()
        r.addWidget(self._h("📋", size=14))
        r.addWidget(self._h(Lang.t("dash_recent"), Theme.ACCENT2, 12, True))
        r.addStretch()
        ly.addLayout(r)

        self._hist_box = QVBoxLayout()
        self._hist_box.setSpacing(0)
        ly.addLayout(self._hist_box)
        return c

    # ── أنمشن ────────────────────────────────────────────────────
    def _animate_arcs(self):
        for a in self._arcs:
            a.animate()

    # ══ تحديث البيانات ═══════════════════════════════════════════
    def _refresh_data(self):
        try:
            self._clock.setText(datetime.now().strftime("%H:%M  ·  %Y-%m-%d"))
            self._upd_usb()
            self._upd_pc()
            self._upd_gh()
            self._upd_attn()
            self._upd_hist()
        except Exception:
            pass

    def _upd_usb(self):
        v = AppConfig.VAULT_DIR
        if v.exists():
            try:
                u = shutil.disk_usage(v)
                gb = u.used / (1024**3)
                tot = u.total / (1024**3)
                pct = int(u.used / u.total * 100)
                self._usb_used.setText(f"{gb:.1f}")
                self._usb_total.setText(f"/ {tot:.0f} GB")
                self._usb_badge.setText("متصلة")
                self._usb_badge.setStyleSheet(
                    f"color:{Theme.SUCCESS}; background:{Theme.SUCCESS}18; "
                    f"font-size:10px; font-weight:600; padding:2px 8px; border-radius:4px;")
                clr = Theme.SUCCESS if pct < 70 else (Theme.WARNING if pct < 90 else Theme.ERROR)
                bw = max(self._usb_bar_bg.width() - 1, 10)
                fw = int(bw * pct / 100)
                self._usb_fill.setFixedWidth(fw)
                self._usb_fill.setStyleSheet(
                    f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                    f"stop:0 {clr}88, stop:1 {clr}); border-radius:2px;")
                prj = [d for d in v.iterdir() if d.is_dir() and not d.name.startswith('.')]
                self._usb_proj.setText(f"{len(prj)} مشروع")
                s = AppConfig.USB_SPEED_MBS
                self._usb_spd.setText(f"⚡ {s:.0f} MB/s" if s > 0 else "⚡ —")
            except OSError:
                pass
        else:
            self._usb_used.setText("—")
            self._usb_total.setText("")
            self._usb_badge.setText("غير متصلة")
            self._usb_badge.setStyleSheet(
                f"color:{Theme.ERROR}; background:{Theme.ERROR}18; "
                f"font-size:10px; padding:2px 8px; border-radius:4px;")

    def _upd_pc(self):
        info = DeviceProfiler.get_detailed_info()
        self._pc_name.setText(AppConfig.PC_NAME or "—")
        self._pc_name.setStyleSheet(f"color:{info['color']}; font-size:13px; font-weight:bold;")
        self._pc_lvl.setText(f"  {info['label']}")
        self._pc_lvl.setStyleSheet(f"color:{info['color']}; font-size:10px;")
        self._pc_specs.setText(
            f"{info['cores']} نواة  ·  {info['ram_total']:.0f} GB RAM  ·  "
            f"{info['hash_speed']:.0f} MB/s")
        self._score_num.setText(str(info['score']))
        self._score_num.setStyleSheet(f"color:{info['color']};")
        self._score_frame.setStyleSheet(
            f"background:{info['color']}12; border:1px solid {info['color']}28; border-radius:8px;")
        self._arc_cpu.set_score(info['cpu_score'])
        self._arc_ram.set_score(info['ram_score'])
        self._arc_hash.set_score(info['hash_score'])
        self._bar_thr.set_value(info['threads_small'])
        self._bar_bat.set_value(info['batch_size'])

    def _upd_gh(self):
        try:
            from ...github.upload_log import UploadLog
            ps = UploadLog.get_all()
            ch = sum(1 for p in ps if p.get("status") == "changed")
            sy = sum(1 for p in ps if p.get("status") == "synced")
            mi = sum(1 for p in ps if p.get("status") == "missing")
            self._gh_nums["total"].setText(str(len(ps)))
            self._gh_nums["changed"].setText(str(ch))
            self._gh_nums["synced"].setText(str(sy))
            self._gh_nums["missing"].setText(str(mi))
            from ...github.ops import Auth
            self._gh_auth.setText("✓ مصادق" if Auth.load() else "✗ غير مصادق")
        except Exception:
            pass

    # ── Attention — فحص عميق في thread ────────────────────────
    def _upd_attn(self):
        self._clear_layout(self._attn_box)
        self._attn_box.addWidget(self._h("  🔍 جاري الفحص...", Theme.TEXT_DIM, 11))
        threading.Thread(target=self._deep_scan, daemon=True).start()

    def _deep_scan(self):
        items = []
        try:
            from ...db.database import DatabaseManager
            db = DatabaseManager(AppConfig.CONFIG_FILE)
            en = AppConfig.EXCLUDED_NAMES
            ed = AppConfig.EXCLUDED_DIRS
            pc = AppConfig.PC_NAME or "default"
            project_list = db.get(f"projects_{pc}", [])
            for p in project_list:
                pp = Path(p)
                if not pp.exists():
                    items.append(("⚠️", f"{pp.name} — مجلد مفقود", Theme.ERROR, ""))
                    continue
                bk = AppConfig.VAULT_DIR / pp.name
                if not bk.exists():
                    fc = self._cnt(pp, en, ed)
                    items.append(("🔴", f"{pp.name} — لم يُزامَن ({fc:,} ملف)", Theme.ERROR, "مزامنة"))
                    continue
                meta = bk / ".ayadsync_meta.json"
                if not meta.exists():
                    items.append(("🟡", f"{pp.name} — يحتاج مزامنة", Theme.WARNING, "مزامنة"))
                    continue
                try:
                    d = json.loads(meta.read_text(encoding='utf-8'))
                    ls = d.get("last_sync", "")
                    if not ls:
                        items.append(("🟡", f"{pp.name} — يحتاج فحص", Theme.WARNING, "مزامنة"))
                        continue
                    ts = datetime.fromisoformat(ls).timestamp()
                    nw, md, dl = self._cmp(pp, bk, ts, en, ed)
                    tot = nw + md + dl
                    if tot == 0:
                        continue
                    parts = []
                    if nw: parts.append(f"➕{nw}")
                    if md: parts.append(f"📝{md}")
                    if dl: parts.append(f"🗑️{dl}")
                    diff = datetime.now() - datetime.fromisoformat(ls)
                    when = f"منذ {diff.days} يوم" if diff.days > 1 else ("أمس" if diff.days == 1 else f"منذ {max(diff.seconds//3600,1)} ساعة")
                    items.append(("🔶", f"{pp.name} — {' · '.join(parts)} ({when})", Theme.WARNING, "مزامنة"))
                except Exception:
                    items.append(("🟡", f"{pp.name} — يحتاج فحص", Theme.WARNING, "مزامنة"))
        except Exception:
            pass
        try:
            from ...github.upload_log import UploadLog
            for p in UploadLog.get_all():
                if p.get("status") == "changed":
                    items.append(("🐙", f"{p.get('repo_name','')} — يحتاج رفع", Theme.CYAN, "رفع"))
        except Exception:
            pass
        self._pending = items
        QTimer.singleShot(0, self._apply_attn)

    def _apply_attn(self):
        items = getattr(self, '_pending', [])
        self._clear_layout(self._attn_box)
        self._attn_cnt.setText(str(len(items)))
        if not items:
            row = QFrame()
            row.setStyleSheet(f"background:{Theme.SUCCESS}08; border:1px solid {Theme.SUCCESS}15; border-radius:6px;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 7, 10, 7)
            rl.addWidget(self._h(f"✅  {Lang.t('dash_all_good')}", Theme.SUCCESS, 12))
            self._attn_box.addWidget(row)
        else:
            for icon, text, color, action in items[:8]:
                row = QFrame()
                row.setStyleSheet(
                    f"QFrame{{background:{color}08; border:1px solid {color}15; border-radius:6px;}}"
                    f"QFrame:hover{{background:{color}12; border-color:{color}28;}}")
                rl = QHBoxLayout(row)
                rl.setContentsMargins(10, 6, 10, 6)
                rl.setSpacing(8)
                rl.addWidget(self._h(icon, size=13))
                t = self._h(text, Theme.TEXT, 11)
                t.setWordWrap(True)
                rl.addWidget(t, 1)
                if action:
                    a = self._h(f"{action} →", color, 10, True)
                    a.setCursor(Qt.CursorShape.PointingHandCursor)
                    rl.addWidget(a)
                self._attn_box.addWidget(row)

    # ── History ──────────────────────────────────────────────────
    def _upd_hist(self):
        self._clear_layout(self._hist_box)
        rd = AppConfig.REPORTS_DIR
        entries = []
        if rd.exists():
            try:
                for f in sorted(rd.iterdir(), reverse=True)[:6]:
                    if f.is_file() and f.suffix == '.txt':
                        parts = f.stem.split("_", 3)
                        if len(parts) >= 3:
                            date = parts[0]
                            time = parts[1].replace("-", ":")[:5]
                            op = parts[2]
                            name = parts[3] if len(parts) > 3 else ""
                            icons = {"backup": "💾", "restore": "📥", "full": "🔄", "sync": "🔄"}
                            entries.append((icons.get(op, "📋"), date, time, op, name))
            except OSError:
                pass

        if not entries:
            self._hist_box.addWidget(self._h(f"  {Lang.t('dash_no_history')}", Theme.TEXT_MUTED, 11))
            return

        for icon, date, time, op, name in entries:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.setContentsMargins(0, 3, 0, 3)
            row.addWidget(self._h(icon, size=12))
            tl = self._h(time, Theme.TEXT_MUTED, 10, mono=True)
            tl.setFixedWidth(42)
            row.addWidget(tl)
            row.addWidget(self._h(f"{op}", Theme.TEXT_DIM, 10))
            if name:
                row.addWidget(self._h(f"— {name}", Theme.TEXT_DIM, 10))
            row.addStretch()
            dl = self._h(date, Theme.TEXT_MUTED, 9)
            row.addWidget(dl)

            wrapper = QWidget()
            wrapper.setLayout(row)
            wrapper.setStyleSheet(f"border-bottom: 1px solid {Theme.BORDER}30;")
            self._hist_box.addWidget(wrapper)

    # ── مساعدات ──────────────────────────────────────────────────
    def _clear_layout(self, ly):
        while ly.count():
            item = ly.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _cnt(self, folder, en, ed):
        c = 0
        stk = [str(folder)]
        while stk and c < 5000:
            d = stk.pop()
            try:
                with os.scandir(d) as es:
                    for e in es:
                        if e.name in en: continue
                        if e.is_dir(follow_symlinks=False):
                            if e.name not in ed: stk.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            c += 1
            except OSError:
                pass
        return c

    def _cmp(self, src, dst, sync_ts, en, ed):
        nw = md = dl = 0
        ck = 0
        MX = 2000
        sf = set()
        stk = [str(src)]
        while stk and ck < MX:
            d = stk.pop()
            try:
                with os.scandir(d) as es:
                    for e in es:
                        if e.name in en: continue
                        if e.is_dir(follow_symlinks=False):
                            if e.name not in ed: stk.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            ck += 1
                            rel = os.path.relpath(e.path, src)
                            sf.add(rel)
                            df = dst / rel
                            if not df.exists():
                                nw += 1
                            else:
                                try:
                                    ss = e.stat()
                                    ds = df.stat()
                                    if ss.st_size != ds.st_size:
                                        md += 1
                                    elif ss.st_mtime > sync_ts + 2:
                                        md += 1
                                except OSError:
                                    pass
            except OSError:
                pass
        if ck < MX:
            stk2 = [str(dst)]
            while stk2 and ck < MX:
                d = stk2.pop()
                try:
                    with os.scandir(d) as es:
                        for e in es:
                            if e.name in en or e.name == ".ayadsync_meta.json": continue
                            if e.is_dir(follow_symlinks=False):
                                if e.name not in ed: stk2.append(e.path)
                            elif e.is_file(follow_symlinks=False):
                                ck += 1
                                rel = os.path.relpath(e.path, dst)
                                if rel not in sf:
                                    dl += 1
                except OSError:
                    pass
        return nw, md, dl

    def retranslateUi(self):
        ly = self.layout()
        if ly:
            it = ly.itemAt(0)
            if it and it.widget():
                old = it.widget()
                ly.removeWidget(old)
                old.deleteLater()
        self._arcs = []
        self._build_ui()
        self._refresh_data()
        QTimer.singleShot(400, self._animate_arcs)
