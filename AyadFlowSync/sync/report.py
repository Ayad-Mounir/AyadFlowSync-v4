#!/usr/bin/env python3
"""sync.report — SyncReport, FlashLedger, ConflictResolver, CheckpointManager, SilentCorruptionDetector"""

import os
import time
import socket
import json
import shutil
import hashlib
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..core.app_config import AppConfig
from ..core.constants import APP_VERSION

_logger = logging.getLogger("AyadFlowSync.sync.report")


from ..lang.proxy import LangProxy as Lang


class SyncReport:
    """
    📋 SyncReport — يُسجّل ويحفظ تقريراً كاملاً لكل مزامنة.

    يُحفظ تلقائياً في:
        FlowSync_Data/sync_reports/YYYY-MM-DD_HH-MM-SS_نوع.txt

    يحتوي:
    - التاريخ والوقت والمدة
    - الجهاز المصدر والوجهة
    - نوع المزامنة (backup / full_sync / restore)
    - عدد الملفات: منسوخة / متخطاة / مزالة للـ Trash / فشلت
    - قائمة الملفات المنسوخة كاملة
    - قائمة الملفات المنقولة للـ Trash
    - الأخطاء إن وجدت
    - نتيجة verify لكل ملف
    """

    def __init__(self, sync_type: str, src: Path, dst: Path):
        self.sync_type   = sync_type   # "backup" | "restore" | "full_sync"
        self.src         = src
        self.dst         = dst
        self.started_at  = datetime.now()
        self.finished_at: Optional[datetime] = None

        # إحصائيات
        self.copied:  List[str] = []   # مسارات الملفات المنسوخة
        self.skipped: int       = 0
        self.trashed: List[str] = []   # مسارات المنقولة للـ Trash
        self.failed:  List[str] = []   # أخطاء
        self.verified: int      = 0    # ملفات تحقق من سلامتها بنجاح

    # ── تسجيل الأحداث ────────────────────────────────────
    def add_copied(self, rel: str):
        self.copied.append(rel)

    def add_skipped(self, count: int = 1):
        self.skipped += count

    def add_trashed(self, rel: str):
        self.trashed.append(rel)

    def add_failed(self, rel: str, reason: str):
        self.failed.append(f"{rel}: {reason}")

    def add_verified(self, count: int = 1):
        self.verified += count

    # ── الحفظ ─────────────────────────────────────────────
    def save(self) -> Optional[Path]:
        """
        يحفظ التقرير على ملف نصي — يُستدعى بعد انتهاء المزامنة.
        يرجع مسار الملف المحفوظ.
        """
        self.finished_at = datetime.now()
        duration = self.finished_at - self.started_at
        mins, secs = divmod(int(duration.total_seconds()), 60)

        ts    = self.started_at.strftime('%Y-%m-%d_%H-%M-%S')
        fname = f"{ts}_{self.sync_type}.txt"
        fpath = AppConfig.REPORTS_DIR / fname

        # تحديد النتيجة الكلية
        if not self.failed:
            result_line = "✅ ناجحة بالكامل"
        elif self.copied:
            result_line = f"⚠️ جزئية — {len(self.failed)} خطأ"
        else:
            result_line = "❌ فشلت"

        lines = [
            "═" * 65,
            f"  📋 Ayad FlowSync — تقرير المزامنة",
            f"  النسخة: {APP_VERSION}",
            "═" * 65,
            f"  النوع      : {self.sync_type}",
            f"  المصدر     : {self.src}",
            f"  الوجهة     : {self.dst}",
            f"  البدء      : {self.started_at.strftime('%Y-%m-%d  %H:%M:%S')}",
            f"  الانتهاء   : {self.finished_at.strftime('%Y-%m-%d  %H:%M:%S')}",
            f"  المدة      : {mins}د {secs}ث",
            f"  الجهاز     : {AppConfig.PC_NAME}",
            "─" * 65,
            f"  النتيجة    : {result_line}",
            "─" * 65,
            f"  منسوخة     : {len(self.copied):,} ملف",
            f"  متخطاة     : {self.skipped:,} ملف (لم تتغير)",
            f"  للـ Trash   : {len(self.trashed):,} ملف",
            f"  أخطاء      : {len(self.failed):,}",
            f"  verify ✅   : {self.verified:,} ملف",
            "═" * 65,
        ]

        if self.copied:
            lines.append(f"\n📂 الملفات المنسوخة ({len(self.copied):,}):")
            lines.append("─" * 65)
            for f in self.copied:
                lines.append(f"  ✅ {f}")

        if self.trashed:
            lines.append(f"\n🗑️  المنقولة للـ Trash ({len(self.trashed):,}):")
            lines.append("─" * 65)
            for f in self.trashed:
                lines.append(f"  🗑️  {f}")

        if self.failed:
            lines.append(f"\n❌ الأخطاء ({len(self.failed):,}):")
            lines.append("─" * 65)
            for f in self.failed:
                lines.append(f"  ❌ {f}")

        lines.append("\n" + "═" * 65)

        try:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
            _logger.info(f"SyncReport saved: {fpath.name}")
            return fpath
        except Exception as e:
            _logger.warning(f"SyncReport.save failed: {e}")
            return None

    # ── قائمة التقارير ────────────────────────────────────
    @staticmethod
    def list_reports(limit: int = 50) -> List[Path]:
        """يرجع آخر N تقرير مرتبة من الأحدث للأقدم"""
        try:
            reports = sorted(
                AppConfig.REPORTS_DIR.glob("*.txt"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            return reports[:limit]
        except Exception:
            return []

    @staticmethod
    def read_report(path: Path) -> str:
        """يقرأ محتوى تقرير"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"خطأ في قراءة التقرير: {e}"

    # ── تنظيف تلقائي ──────────────────────────────────────
    @staticmethod
    def auto_cleanup(keep_days: int = 90):
        """يحذف التقارير الأقدم من keep_days يوم"""
        cutoff = datetime.now().timestamp() - (keep_days * 86400)
        count  = 0
        try:
            for p in AppConfig.REPORTS_DIR.glob("*.txt"):
                if p.stat().st_mtime < cutoff:
                    p.unlink(missing_ok=True)
                    count += 1
        except Exception:
            pass
        if count:
            _logger.info(f"SyncReport: cleaned {count} old reports")





# ╔══════════════════════════════════════════════════════════════╗
# ║   💾 FLASH LEDGER v17 — سجل موحد على الفلاشة               ║
# ╚══════════════════════════════════════════════════════════════╝
class FlashLedger:
    """
    💾 FlashLedger — سجل يُحفظ على الفلاشة مباشرةً

    الفلاشة = مصدر الحقيقة الوحيد بين الأجهزة.
    كل مزامنة ناجحة تُسجَّل هنا: اسم الجهاز + وقت المزامنة + بصمة كل ملف.

    عند المزامنة التالية:
    ① نقارن mtime الملف على الجهاز مع آخر وقت مزامنة لهذا الجهاز
    ② إذا تغيّر الملف على جهازين مختلفين بعد آخر مزامنة = CONFLICT حقيقي
    ③ إذا تغيّر على جهاز واحد فقط = مزامنة عادية

    البنية على الفلاشة:
        {usb_folder}/.flash_ledger.json
        {
          "last_updated": "2026-02-24T10:30:00",
          "devices": {
            "جهاز-سمير": {
              "last_sync": "2026-02-24T08:00:00",    ← timestamp بعد آخر مزامنة
              "last_sync_ts": 1740384000.0            ← float للمقارنة السريعة
            },
            "ورشة-القص": {
              "last_sync": "2026-02-24T09:00:00",
              "last_sync_ts": 1740387600.0
            }
          },
          "files": {
            "موديل_001/باترن.mrk": {
              "hash": "abc123...",
              "synced_at": 1740384000.0,
              "synced_by": "جهاز-سمير"
            }
          }
        }

    السر: نستخدم last_sync_ts للجهاز الحالي كنقطة مرجعية.
    أي ملف mtime > last_sync_ts = تغيّر بعد آخر مزامنة = يحتاج رفع للفلاشة.
    """
    LEDGER_FILE = ".flash_ledger.json"
    _lock = threading.Lock()

    def __init__(self, usb_folder: Path):
        self.usb_folder  = usb_folder
        self.ledger_path = usb_folder / self.LEDGER_FILE
        self._data: Dict = {}

    # ── تحميل وحفظ ────────────────────────────────────────
    # RAM cache — لا يقرأ الفلاشة إلا مرة واحدة لكل مسار
    _cache: dict = {}

    def load(self) -> "FlashLedger":
        key = str(self.ledger_path)
        if key in FlashLedger._cache:
            self._data = FlashLedger._cache[key]
            return self
        try:
            if self.ledger_path.exists():
                self._data = json.loads(
                    self.ledger_path.read_text(encoding='utf-8')
                )
            else:
                self._data = {}
        except Exception:
            self._data = {}
        if "devices" not in self._data:
            self._data["devices"] = {}
        if "files" not in self._data:
            self._data["files"] = {}
        # حفظ في RAM cache
        FlashLedger._cache[key] = self._data
        return self

    @classmethod
    def clear_cache(cls):
        """امسح الـ RAM cache — يُستدعى بعد record_sync لضمان قراءة جديدة"""
        cls._cache.clear()

    def save(self):
        """حفظ ذري — لا تلف عند انقطاع الكهرباء
        🔴 FIX v19: Path(str+'.tmp') بدل with_suffix لدعم أي اسم ملف
        """
        try:
            self._data["last_updated"] = datetime.now().isoformat()
            # ✅ FIX: str concat بدل with_suffix (with_suffix يفشل مع أسماء معينة)
            tmp = Path(str(self.ledger_path) + '.tmp')
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            tmp.replace(self.ledger_path)
        except OSError as e:
            _logger.warning(f"FlashLedger.save: {e}")

    # ── API رئيسية ─────────────────────────────────────────
    def get_device_last_sync_ts(self, device_name: str) -> Optional[float]:
        """آخر وقت مزامنة لجهاز معين (float timestamp أو None)
        🔴 FIX v19: استخدام .get() بدل [] لتجنب KeyError عند _data فارغ
        (يحدث عند إنشاء FlashLedger بدون .load() — مثلاً عند عدم وجود USB)
        """
        dev = self._data.get("devices", {}).get(device_name)
        if dev:
            return dev.get("last_sync_ts")
        return None

    def record_sync(self, device_name: str, synced_files: Dict[str, str]):
        """
        يُسجّل مزامنة ناجحة.
        synced_files: {rel_path: sha256_hash}
        🔴 FIX v19: تهيئة "devices" و"files" إذا لم تكن موجودة (تجنب KeyError)
        """
        now_ts = time.time()
        # ✅ FIX: تأكد من وجود المفاتيح قبل الكتابة
        if "devices" not in self._data:
            self._data["devices"] = {}
        if "files" not in self._data:
            self._data["files"] = {}
        self._data["devices"][device_name] = {
            "last_sync"    : datetime.now().isoformat(),
            "last_sync_ts" : now_ts,
        }
        # تحديث بصمات الملفات المُزامَنة
        for rel, h in synced_files.items():
            self._data["files"][rel] = {
                "hash"      : h,
                "synced_at" : now_ts,
                "synced_by" : device_name,
            }
        self.save()
        # ✅ امسح الـ cache حتى تقرأ المزامنة التالية من الملف الفعلي
        FlashLedger.clear_cache()

    def detect_conflicts(
        self,
        pc_files: Dict[str, Path],
        usb_files: Dict[str, Path],
        current_device: str
    ) -> Tuple[List[Dict], List[str], List[str]]:
        """
        يحلّل الفروقات ويصنّفها:

        Returns:
            conflicts  : [{rel, pc_mtime, usb_mtime, pc_hash, usb_hash, last_sync_by}]
            pc_to_usb  : [rel]  ← تغيّر على الجهاز فقط → ينتقل للفلاشة
            usb_to_pc  : [rel]  ← تغيّر على الفلاشة من جهاز آخر → ينتقل للجهاز

        المنطق:
        1. لو الملف موجود في الطرفين وlhash مختلف:
           - احصل على last_sync_ts للجهاز الحالي
           - إذا pc_mtime > last_sync_ts AND usb_mtime > last_sync_ts = CONFLICT
           - إذا pc_mtime > last_sync_ts فقط = pc_to_usb
           - إذا usb_mtime > last_sync_ts فقط = usb_to_pc
           - إذا لا يوجد last_sync_ts (أول مزامنة) = الأحدث mtime يكسب
        """
        conflicts: List[Dict] = []
        pc_to_usb: List[str]  = []
        usb_to_pc: List[str]  = []

        my_last_sync = self.get_device_last_sync_ts(current_device)

        common = set(pc_files.keys()) & set(usb_files.keys())
        for rel in common:
            pc_f  = pc_files[rel]
            usb_f = usb_files[rel]
            try:
                pc_st  = pc_f.stat()
                usb_st = usb_f.stat()

                # حجم مختلف أو mtime مختلف = يحتاج فحصاً
                if pc_st.st_size == usb_st.st_size and \
                   abs(pc_st.st_mtime - usb_st.st_mtime) < 2:
                    continue  # متطابق عملياً

                pc_mtime  = pc_st.st_mtime
                usb_mtime = usb_st.st_mtime

                if my_last_sync is None:
                    # أول مزامنة — الأحدث يكسب
                    if pc_mtime > usb_mtime:
                        pc_to_usb.append(rel)
                    else:
                        usb_to_pc.append(rel)
                else:
                    pc_changed  = pc_mtime  > (my_last_sync + 2)   # +2s هامش
                    usb_changed = usb_mtime > (my_last_sync + 2)

                    if pc_changed and usb_changed:
                        # CONFLICT حقيقي — تغيّر على جهازين!
                        # ✅ FIX v19: .get() بدل [] لتجنب KeyError
                        ledger_entry = self._data.get("files", {}).get(rel, {})
                        conflicts.append({
                            "rel"          : rel,
                            "pc_mtime"     : pc_mtime,
                            "usb_mtime"    : usb_mtime,
                            "last_sync_ts" : my_last_sync,
                            "last_sync_by" : ledger_entry.get("synced_by", "?"),
                            "pc_size"      : pc_st.st_size,
                            "usb_size"     : usb_st.st_size,
                        })
                    elif pc_changed:
                        pc_to_usb.append(rel)
                    elif usb_changed:
                        usb_to_pc.append(rel)
                    # لم يتغير أي منهما منذ آخر مزامنة = تجاهل

            except OSError:
                continue

        return conflicts, pc_to_usb, usb_to_pc

    def get_all_devices(self) -> Dict[str, Dict]:
        """قائمة كل الأجهزة التي تزامنت مع هذه الفلاشة"""
        return self._data.get("devices", {})





# ╔══════════════════════════════════════════════════════════════╗
# ║   ⚔️  CONFLICT RESOLVER v17 — حل التعارضات يدوياً          ║
# ╚══════════════════════════════════════════════════════════════╝
class ConflictResolver:
    """
    ⚔️ ConflictResolver — نافذة حل التعارضات

    تُعرض عند اكتشاف ملفات تغيّرت على جهازين مختلفين.
    لكل ملف يختار المستخدم:
      ① 💻 خذ من الجهاز  → الجهاز يفوز، يُنسخ للفلاشة
      ② 💾 خذ من الفلاشة → الفلاشة تفوز، يُنسخ للجهاز
      ③ 📋 احفظ النسختين → يُحفظ الأصلي باسم مختلف
    """

    def __init__(self, parent, conflicts: List[Dict],
                 pc_folder: Path, usb_folder: Path):
        self.parent     = parent
        self.conflicts  = conflicts
        self.pc_folder  = pc_folder
        self.usb_folder = usb_folder
        # decisions: {rel: "pc" | "usb" | "both"}
        self.decisions: Dict[str, str] = {}
        self._decided   = False

    def show(self) -> Optional[Dict[str, str]]:
        """
        ✅ FIX v4.1 — تحويل من Tkinter إلى PyQt6
        يعرض نافذة حل التعارضات — يحجب حتى ينتهي المستخدم.
        Returns: decisions dict أو None إذا أُلغي
        """
        try:
            from PyQt6.QtWidgets import (
                QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                QScrollArea, QWidget, QFrame, QButtonGroup, QSizePolicy
            )
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QFont, QColor
        except ImportError:
            _logger.error("ConflictResolver: PyQt6 غير متاح")
            return None

        # ── الألوان ──────────────────────────────────────────────
        BG       = "#0b0d11"
        BG_CARD  = "#13161e"
        BG_ROW_A = "#13161e"
        BG_ROW_B = "#1a1e28"
        RED      = "#f87171"
        CYAN     = "#22d3ee"
        GREEN    = "#34d399"
        YELLOW   = "#fbbf24"
        DIM      = "#4a5568"
        TEXT     = "#e2e8f0"

        def _qs(widget, style: str):
            widget.setStyleSheet(style)

        # ── الحوار الرئيسي ────────────────────────────────────────
        dlg = QDialog(self.parent)
        dlg.setWindowTitle(f"⚔️  حل التعارضات — {len(self.conflicts)} ملف")
        dlg.setMinimumSize(980, 600)
        dlg.resize(1000, 650)
        dlg.setModal(True)
        _qs(dlg, f"background:{BG}; color:{TEXT}; font-family:'Segoe UI';")

        root_layout = QVBoxLayout(dlg)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Header ───────────────────────────────────────────────
        hdr = QFrame()
        _qs(hdr, f"background:#0d0f14; padding:12px 20px;")
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setSpacing(4)

        title_lbl = QLabel(Lang.t('conflict_title'))
        _qs(title_lbl, f"color:{RED}; font-size:15px; font-weight:bold;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_layout.addWidget(title_lbl)

        sub_lbl = QLabel(
            f"الجهاز الحالي: 💻 {AppConfig.PC_NAME}   |   "
            f"الفلاشة: 💾 {self.usb_folder.name}   |   "
            f"{len(self.conflicts)} تعارض يحتاج قرارك"
        )
        _qs(sub_lbl, f"color:{CYAN}; font-size:11px;")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_layout.addWidget(sub_lbl)
        root_layout.addWidget(hdr)

        # ── تلميح ─────────────────────────────────────────────────
        hint_bar = QFrame()
        _qs(hint_bar, f"background:#1a0f00; padding:6px 16px;")
        hint_lbl = QLabel(Lang.t('conflict_hint'))
        _qs(hint_lbl, f"color:{YELLOW}; font-size:10px; font-style:italic;")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        QVBoxLayout(hint_bar).addWidget(hint_lbl)
        root_layout.addWidget(hint_bar)

        # ── منطقة التمرير ─────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        _qs(scroll, f"border:none; background:{BG};")

        container = QWidget()
        _qs(container, f"background:{BG};")
        con_layout = QVBoxLayout(container)
        con_layout.setContentsMargins(8, 8, 8, 8)
        con_layout.setSpacing(2)

        # ── رأس الأعمدة ──────────────────────────────────────────
        col_hdr = QFrame()
        _qs(col_hdr, f"background:#1a1e28; border-radius:4px; padding:4px 8px;")
        col_row = QHBoxLayout(col_hdr)
        col_row.setContentsMargins(6, 0, 6, 0)
        for txt, stretch in [
            ("اسم الملف", 3), ("جهاز (mtime)", 2),
            ("فلاشة (mtime)", 2), ("الحجم", 1), ("القرار", 4)
        ]:
            lbl = QLabel(txt)
            _qs(lbl, f"color:#718096; font-size:10px; font-weight:bold;")
            col_row.addWidget(lbl, stretch)
        con_layout.addWidget(col_hdr)

        # ── helpers ───────────────────────────────────────────────
        def _fmt_time(ts: float) -> str:
            try:    return datetime.fromtimestamp(ts).strftime('%m/%d  %H:%M:%S')
            except: return "?"

        def _fmt_sz(s: int) -> str:
            if s < 1024:    return f"{s}B"
            if s < 1048576: return f"{s//1024}KB"
            return f"{s//1048576}MB"

        # decisions: {rel → "pc" | "usb" | "both"}
        # نحتفظ بقائمة أزرار لكل صف لتحديث ألوانها
        decision_state: Dict[str, list] = {}  # rel → [choice_str_holder]
        all_btn_rows: list = []               # لتطبيق الاختيار الجماعي

        for i, cf in enumerate(self.conflicts):
            rel       = cf["rel"]
            pc_mtime  = cf.get("pc_mtime",  0)
            usb_mtime = cf.get("usb_mtime", 0)
            pc_size   = cf.get("pc_size",   0)
            usb_size  = cf.get("usb_size",  0)
            last_by   = cf.get("last_sync_by", "?")
            last_ts   = cf.get("last_sync_ts",  0)

            suggested  = "pc" if pc_mtime > usb_mtime else "usb"
            choice_ref = [suggested]   # mutable holder
            decision_state[rel] = choice_ref

            row_bg = BG_ROW_A if i % 2 == 0 else BG_ROW_B
            row    = QFrame()
            _qs(row, f"background:{row_bg}; border-radius:4px; padding:3px 6px;")
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(6, 2, 6, 2)
            row_lay.setSpacing(6)

            # اسم الملف
            name_lbl = QLabel(Path(rel).name)
            _qs(name_lbl, f"color:{TEXT}; font-size:10px;")
            name_lbl.setToolTip(rel)
            row_lay.addWidget(name_lbl, 3)

            # mtime الجهاز
            pc_col  = GREEN if pc_mtime  > usb_mtime else DIM
            pc_lbl  = QLabel(_fmt_time(pc_mtime))
            _qs(pc_lbl,  f"color:{pc_col};  font-family:'Consolas'; font-size:9px;")
            row_lay.addWidget(pc_lbl,  2)

            # mtime الفلاشة
            usb_col = GREEN if usb_mtime > pc_mtime  else DIM
            usb_lbl = QLabel(_fmt_time(usb_mtime))
            _qs(usb_lbl, f"color:{usb_col}; font-family:'Consolas'; font-size:9px;")
            row_lay.addWidget(usb_lbl, 2)

            # الحجم
            sz_lbl = QLabel(f"💻{_fmt_sz(pc_size)} / 💾{_fmt_sz(usb_size)}")
            _qs(sz_lbl, f"color:{DIM}; font-size:9px;")
            row_lay.addWidget(sz_lbl, 1)

            # ── أزرار القرار ─────────────────────────────────────
            btns_widget = QWidget()
            btns_lay    = QHBoxLayout(btns_widget)
            btns_lay.setContentsMargins(0,0,0,0)
            btns_lay.setSpacing(4)

            btn_defs = [
                ("pc",   "💻 جهاز",     "#14532d", "#86efac"),
                ("usb",  "💾 فلاشة",    "#1e3a5f", "#93c5fd"),
                ("both", "📋 النسختين", "#3a1a00", "#fcd34d"),
            ]
            btn_widgets = []

            def _refresh(btn_list, choice_r, _defs=btn_defs):
                for b, (opt, lbl, bg_on, fg_on) in zip(btn_list, _defs):
                    sel = choice_r[0] == opt
                    _qs(b,
                        f"background:{bg_on if sel else '#21262d'};"
                        f"color:{fg_on if sel else '#718096'};"
                        f"font-weight:{'bold' if sel else 'normal'};"
                        f"font-size:9px; border-radius:4px; padding:3px 8px; border:none;"
                    )

            for opt, lbl, bg_on, fg_on in btn_defs:
                b = QPushButton(lbl)
                b.setCursor(Qt.CursorShape.PointingHandCursor)

                def _clicked(checked=False, _opt=opt, _cr=choice_ref, _blist=None):
                    _cr[0] = _opt
                    if _blist is not None:
                        _refresh(_blist, _cr)

                b.clicked.connect(_clicked)
                btns_lay.addWidget(b)
                btn_widgets.append(b)

            # Wire buttons with their list reference (after list is complete)
            for b, (opt, lbl, bg_on, fg_on) in zip(btn_widgets, btn_defs):
                b.clicked.disconnect()
                def _clicked(checked=False, _opt=opt, _cr=choice_ref, _blist=btn_widgets):
                    _cr[0] = _opt
                    _refresh(_blist, _cr)
                b.clicked.connect(_clicked)

            _refresh(btn_widgets, choice_ref)
            all_btn_rows.append((choice_ref, btn_widgets))
            row_lay.addWidget(btns_widget, 4)

            # آخر مزامنة
            last_str = (datetime.fromtimestamp(last_ts).strftime('%m/%d %H:%M')
                        if last_ts else "—")
            last_lbl = QLabel(f"آخر sync: {last_str} / {last_by}")
            _qs(last_lbl, f"color:{DIM}; font-size:8px;")
            btns_lay.addWidget(last_lbl)

            con_layout.addWidget(row)

        con_layout.addStretch(1)
        scroll.setWidget(container)
        root_layout.addWidget(scroll, 1)

        # ── شريط الأزرار الجماعية ────────────────────────────────
        ctrl = QFrame()
        _qs(ctrl, f"background:#0d0f14; padding:8px 16px;")
        ctrl_lay = QVBoxLayout(ctrl)
        ctrl_lay.setSpacing(6)

        bulk_row = QWidget()
        bulk_lay = QHBoxLayout(bulk_row)
        bulk_lay.setContentsMargins(0,0,0,0)
        bulk_lay.setSpacing(8)

        bulk_lbl = QLabel(Lang.t('conflict_apply_all'))
        _qs(bulk_lbl, f"color:#718096; font-size:10px;")
        bulk_lay.addWidget(bulk_lbl)

        def _apply_all(choice: str):
            for cr, blist in all_btn_rows:
                cr[0] = choice
                _refresh(blist, cr)

        for choice, lbl, style in [
            ("pc",   Lang.t('conflict_all_pc'),   f"background:#14532d;color:#86efac;"),
            ("usb",  Lang.t('conflict_all_usb'),  f"background:#1e3a5f;color:#93c5fd;"),
            ("both", Lang.t('conflict_all_both'), f"background:#3a1a00;color:#fcd34d;"),
        ]:
            b = QPushButton(lbl)
            _qs(b, style + "font-weight:bold;font-size:10px;padding:5px 14px;border-radius:5px;border:none;")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda checked=False, c=choice: _apply_all(c))
            bulk_lay.addWidget(b)

        bulk_lay.addStretch(1)
        ctrl_lay.addWidget(bulk_row)

        # ── أزرار تأكيد / إلغاء ──────────────────────────────────
        ok_row = QWidget()
        ok_lay = QHBoxLayout(ok_row)
        ok_lay.setContentsMargins(0,0,0,0)
        ok_lay.setSpacing(8)
        ok_lay.addStretch(1)

        confirmed = [False]

        confirm_btn = QPushButton(f"✅  تطبيق قراراتي ({len(self.conflicts)} ملف)")
        _qs(confirm_btn,
            "background:#166534;color:#86efac;font-weight:bold;"
            "font-size:13px;padding:8px 24px;border-radius:6px;border:none;")
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        cancel_btn = QPushButton(Lang.t('conflict_skip'))
        _qs(cancel_btn,
            "background:#21262d;color:#718096;"
            "font-size:11px;padding:8px 18px;border-radius:6px;border:none;")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def _confirm():
            confirmed[0] = True
            for rel, cr in decision_state.items():
                self.decisions[rel] = cr[0]
            self._decided = True
            dlg.accept()

        def _cancel():
            dlg.reject()

        confirm_btn.clicked.connect(_confirm)
        cancel_btn.clicked.connect(_cancel)
        ok_lay.addWidget(confirm_btn)
        ok_lay.addWidget(cancel_btn)
        ctrl_lay.addWidget(ok_row)

        root_layout.addWidget(ctrl)

        # ── تشغيل ─────────────────────────────────────────────────
        dlg.exec()
        return self.decisions if confirmed[0] else None

    def apply_decisions(
        self,
        pc_folder: Path,
        usb_folder: Path,
        log_cb=None
    ) -> Tuple[int, int, List[str]]:
        """
        يُطبّق قرارات المستخدم فعلياً.
        Returns: (copied, failed, errors)
        """
        log    = log_cb or (lambda m: None)
        copied = failed = 0
        errors: List[str] = []

        for rel, decision in self.decisions.items():
            pc_f  = pc_folder  / rel
            usb_f = usb_folder / rel

            try:
                if decision == "pc":
                    # الجهاز يفوز → انسخ للفلاشة
                    ok, msg = AtomicCopier.copy(pc_f, usb_f)
                    if ok:
                        copied += 1
                        log(f"  ✅ [جهاز→فلاشة] {Path(rel).name}")
                    else:
                        failed += 1; errors.append(f"{rel}: {msg}")
                        log(f"  ❌ {Path(rel).name}: {msg}")

                elif decision == "usb":
                    # الفلاشة تفوز → انسخ للجهاز
                    ok, msg = AtomicCopier.copy(usb_f, pc_f)
                    if ok:
                        copied += 1
                        log(f"  ✅ [فلاشة→جهاز] {Path(rel).name}")
                    else:
                        failed += 1; errors.append(f"{rel}: {msg}")
                        log(f"  ❌ {Path(rel).name}: {msg}")

                elif decision == "both":
                    # احفظ النسختين — أعطِ نسخة الفلاشة اسماً مختلفاً على الجهاز
                    ts_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
                    usb_rename = pc_f.with_stem(
                        pc_f.stem + f"_فلاشة_{ts_suffix}"
                    )
                    ok, msg = AtomicCopier.copy(usb_f, usb_rename)
                    if ok:
                        copied += 1
                        log(f"  📋 [النسختان] {Path(rel).name} → {usb_rename.name}")
                    else:
                        failed += 1; errors.append(f"{rel}: {msg}")
                        log(f"  ❌ {Path(rel).name}: {msg}")

            except Exception as e:
                failed += 1
                errors.append(f"{rel}: {e}")
                log(f"  ❌ {Path(rel).name}: {e}")

        return copied, failed, errors





# ╔═══════════════════════════════════════════╗
# ║        📌 CHECKPOINT MANAGER (FIX 3)      ║
# ╚═══════════════════════════════════════════╝
class CheckpointManager:
    """
    ✅ FIX 3 — يحفظ تقدم المزامنة ويسمح بالاستئناف من حيث توقفت.
    عند انقطاع الكهرباء أو إيقاف المزامنة يدوياً:
    في المرة القادمة يكمل من آخر ملف ناجح بدلاً من البداية.
    """
    def __init__(self, project_name: str, direction: str = "default"):
        safe = project_name.replace("/","_").replace("\\","_").replace(":","_").replace(" ","_")
        self.cp_file = AppConfig.DATA_DIR / f"checkpoint_{safe}_{direction}.json"

    def save(self, remaining: List[Tuple[Path, Path]], src: str, dst: str):
        try:
            data = {
                "src": src, "dst": dst,
                # ✅ FIX v20.1: نحفظ hostname الحقيقي للجهاز (ليس PC_NAME المحفوظ في الفلاشة)
                # يمنع جهاز B من استكمال checkpoint انقطع على جهاز A
                "hostname": socket.gethostname(),
                "remaining": [str(s) + "|" + str(d) for s, d in remaining],
                "saved_at": datetime.now().isoformat()
            }
            tmp = self.cp_file.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            tmp.replace(self.cp_file)
        except OSError: pass

    def load(self, src: str, dst: str) -> Optional[List[Tuple[Path, Path]]]:
        try:
            if not self.cp_file.exists(): return None
            data = json.loads(self.cp_file.read_text(encoding='utf-8'))
            if data.get("src") != src or data.get("dst") != dst:
                self.clear(); return None
            # ✅ FIX v20.1: تجاهل checkpoint إذا:
            #   • لا يحتوي على hostname (checkpoint قديم من قبل v20.1) → غير موثوق
            #   • محفوظ من جهاز مختلف → بيانات لا تخصّ هذا الجهاز
            saved_host = data.get("hostname", "")
            my_host    = socket.gethostname()
            if not saved_host:
                _logger.info(
                    "CheckpointManager: تجاهل checkpoint قديم (بدون hostname) "
                    "— مسح أولي كامل لضمان سلامة البيانات"
                )
                self.clear(); return None
            if saved_host != my_host:
                _logger.info(
                    f"CheckpointManager: تجاهل checkpoint من جهاز آخر "
                    f"({saved_host} ≠ {my_host}) — مسح أولي كامل"
                )
                self.clear(); return None
            pairs = []
            for line in data.get("remaining", []):
                parts = line.split("|", 1)
                if len(parts) == 2:
                    pairs.append((Path(parts[0]), Path(parts[1])))
            return pairs if pairs else None
        except Exception: return None

    def update(self, remaining: List[Tuple[Path, Path]], src: str, dst: str):
        if remaining: self.save(remaining, src, dst)
        else: self.clear()

    def clear(self):
        try: self.cp_file.unlink(missing_ok=True)
        except OSError: pass





# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  🔒 v27: SILENT CORRUPTION DETECTOR                                     ║
# ║                                                                          ║
# ║  يعمل في الخلفية عند فتح الفلاشة                                        ║
# ║  يأخذ عينة عشوائية 7% من الملفات على الفلاشة                           ║
# ║  hash الحالي ≠ hash المحفوظ → تحذير فوري + عرض استعادة                 ║
# ║  يعمل في thread خلفي — لا يوقف أي شيء                                  ║
# ║  غير موجود في أي برنامج مزامنة عادي                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝
class SilentCorruptionDetector:
    """
    🔒 v27 — فحص سري دوري للملفات على الفلاشة.

    يعمل في thread خلفي منفصل — لا يؤثر على الأداء.
    يفحص عينة عشوائية من الملفات ويقارنها بالـ hash المحفوظ.
    إذا وجد ملفاً تالفاً → ينبّه المستخدم فوراً.

    يُستدعى مرة واحدة عند فتح البرنامج أو عند اكتشاف USB.
    """

    # ── إعدادات حسب قوة الجهاز ────────────────────────────────
    _DEVICE_CONFIGS = {
        "weak":   {"sample_rate": 0.03, "max_sample": 30,  "min_size": 4096},
        "mid":    {"sample_rate": 0.07, "max_sample": 200, "min_size": 1024},
        "strong": {"sample_rate": 0.12, "max_sample": 500, "min_size": 512},
    }

    @classmethod
    def _cfg(cls) -> dict:
        p = DeviceProfiler.get() if hasattr(DeviceProfiler, '_measured') else "mid"
        return cls._DEVICE_CONFIGS.get(p, cls._DEVICE_CONFIGS["mid"])

    SAMPLE_RATE       = 0.07
    MIN_SAMPLE        = 5
    MAX_SAMPLE        = 200
    MIN_FILE_SIZE     = 1024
    # نتائج آخر فحص
    _last_result: Dict = {}
    _running: bool = False
    _lock = threading.Lock()

    @classmethod
    def check_async(cls, usb_path: Path, log_cb=None,
                    alert_cb=None, done_cb=None):
        """
        يبدأ الفحص في thread خلفي.

        log_cb:   callback للـ log (اختياري)
        alert_cb: callback يُستدعى إذا وُجد تلف → (corrupted_list)
        done_cb:  callback عند الانتهاء → (result_dict)
        """
        with cls._lock:
            if cls._running:
                return   # فحص جارٍ بالفعل
            cls._running = True

        def _run():
            try:
                result = cls._do_check(usb_path, log_cb)
                cls._last_result = result
                if result.get("corrupted") and alert_cb:
                    try: alert_cb(result["corrupted"])
                    except Exception: pass
                if done_cb:
                    try: done_cb(result)
                    except Exception: pass
            finally:
                with cls._lock:
                    cls._running = False

        t = threading.Thread(target=_run, daemon=True,
                             name="CorruptionDetector")
        t.start()

    @classmethod
    def _do_check(cls, usb_path: Path, log_cb=None) -> Dict:
        """
        الفحص الفعلي — يعمل في thread خلفي.
        يُعيد dict: {scanned, corrupted, ok, skipped, duration}
        """
        log = log_cb or (lambda m: None)
        cfg = cls._cfg()
        sample_rate  = cfg["sample_rate"]
        max_sample   = cfg["max_sample"]
        min_file_size= cfg["min_size"]
        log(f"🔒 Corruption Detector [{DeviceProfiler.get_label()}]: فحص سري بدأ في الخلفية...")

        t0 = time.monotonic()
        all_files: List[Path] = []

        # ── جمع كل الملفات على USB ────────────────────────────
        try:
            for entry in usb_path.rglob("*"):
                try:
                    if not entry.is_file():
                        continue
                    if entry.name in AppConfig.EXCLUDED_NAMES:
                        continue
                    if entry.stat().st_size < min_file_size:
                        continue
                    all_files.append(entry)
                except OSError:
                    continue
        except OSError as e:
            return {"status": "ERROR", "message": str(e)}

        if not all_files:
            return {"status": "OK", "scanned": 0, "corrupted": [], "ok": 0}

        # ── اختيار عينة عشوائية ────────────────────────────────
        import random
        n_sample = max(
            cls.MIN_SAMPLE,
            min(max_sample, int(len(all_files) * sample_rate))
        )
        sample = random.sample(all_files, min(n_sample, len(all_files)))
        log(f"🔒 Corruption Detector: فحص {len(sample)} ملف من {len(all_files)} ({sample_rate:.0%} | {DeviceProfiler.get_label()})")

        corrupted: List[Dict] = []
        ok_count  = 0
        skipped   = 0

        for f in sample:
            try:
                st = f.stat()
                # احسب hash الحالي
                current_hash = HashCache._compute_hash(f, st.st_size)
                # قارن مع hash المحفوظ في cache
                cached = HashCache._get_from_db(str(f))
                if cached is None:
                    # غير محفوظ — لا يمكن المقارنة
                    skipped += 1
                    continue

                cached_hash = cached[0] if isinstance(cached, tuple) else cached
                if current_hash and cached_hash and current_hash != cached_hash:
                    corrupted.append({
                        "path"         : str(f),
                        "name"         : f.name,
                        "size"         : st.st_size,
                        "size_str"     : Utils.format_size(st.st_size),
                        "cached_hash"  : cached_hash[:16] + "...",
                        "current_hash" : current_hash[:16] + "...",
                    })
                    log(f"  ⚠️ تلف مكتشف: {f.name} ({Utils.format_size(st.st_size)})")
                else:
                    ok_count += 1

            except OSError:
                skipped += 1
                continue

        duration = time.monotonic() - t0
        status   = "CORRUPTED" if corrupted else "OK"

        if corrupted:
            log(
                f"🚨 Corruption Detector: {len(corrupted)} ملف تالف "
                f"من {len(sample)} مفحوص في {duration:.1f}ث"
            )
        else:
            log(
                f"✅ Corruption Detector: كل الملفات سليمة "
                f"({len(sample)} مفحوص في {duration:.1f}ث)"
            )

        return {
            "status"   : status,
            "scanned"  : len(sample),
            "total"    : len(all_files),
            "corrupted": corrupted,
            "ok"       : ok_count,
            "skipped"  : skipped,
            "duration" : duration,
        }

    @classmethod
    def show_alert(cls, parent, corrupted: List[Dict], presync_dir: Path):
        """
        ✅ FIX v4.1 — تحويل من Tkinter إلى PyQt6
        يعرض نافذة تحذير مع قائمة الملفات التالفة.
        """
        if not corrupted:
            return

        try:
            from PyQt6.QtWidgets import (
                QDialog, QVBoxLayout, QHBoxLayout,
                QLabel, QPushButton, QTextEdit
            )
            from PyQt6.QtCore import Qt
        except ImportError:
            _logger.error("SilentCorruptionDetector.show_alert: PyQt6 غير متاح")
            return

        dlg = QDialog(parent)
        dlg.setWindowTitle("🚨 تحذير — ملفات تالفة مكتشفة")
        dlg.setMinimumSize(680, 460)
        dlg.setModal(True)
        dlg.setStyleSheet("background:#1a0000; color:#ffaaaa; font-family:'Segoe UI';")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        # Header
        title = QLabel("🚨 تحذير — ملفات تالفة")
        title.setStyleSheet("color:#ff4444; font-size:16px; font-weight:bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        sub = QLabel(
            f"اكتشف البرنامج {len(corrupted)} ملف تالف على الفلاشة.\n"
            "هذا يعني أن محتوى الملف تغيّر بعد آخر مزامنة — قد يكون تلفاً في الفلاشة."
        )
        sub.setStyleSheet("color:#ffaaaa; font-size:10px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub)

        # قائمة الملفات
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setStyleSheet(
            "background:#0d0000; color:#ff8888; "
            "font-family:'Consolas'; font-size:10px; border:none;"
        )
        content = ""
        for item in corrupted:
            content += (
                f"⚠️  {item['name']}  ({item['size_str']})\n"
                f"     المسار: {item['path']}\n"
                f"     Hash محفوظ:  {item['cached_hash']}\n"
                f"     Hash الحالي: {item['current_hash']}\n\n"
            )
        txt.setPlainText(content)
        lay.addWidget(txt, 1)

        # أزرار
        snaps = sorted(presync_dir.glob("*"), reverse=True) if presync_dir.exists() else []

        if snaps:
            snap_lbl = QLabel(f"✅ يوجد {len(snaps)} Snapshot للاستعادة")
            snap_lbl.setStyleSheet("color:#4ade80; font-size:10px;")
            snap_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(snap_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        if snaps:
            restore_btn = QPushButton("📸 عرض Snapshots للاستعادة")
            restore_btn.setStyleSheet(
                "background:#14532d; color:#86efac; font-weight:bold;"
                "font-size:11px; padding:7px 20px; border-radius:5px; border:none;"
            )
            restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            restore_btn.clicked.connect(dlg.accept)
            btn_row.addWidget(restore_btn)
        else:
            warn_lbl = QLabel("⚠️ لا يوجد Snapshot للاستعادة — قم بمزامنة من الجهاز")
            warn_lbl.setStyleSheet("color:#fbbf24; font-size:10px;")
            lay.addWidget(warn_lbl)

        ok_btn = QPushButton("✅ فهمت")
        ok_btn.setStyleSheet(
            "background:#21262d; color:#aaa;"
            "font-size:11px; padding:7px 20px; border-radius:5px; border:none;"
        )
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(ok_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        dlg.exec()








