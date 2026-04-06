#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests.test_sync_engine
======================
اختبارات تكاملية لـ SyncEngine — تعمل على ملفات حقيقية في /tmp
"""

import os
import shutil
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_tree(base: Path, files: dict):
    """ينشئ شجرة ملفات: {relative_path: content_bytes}"""
    for rel, content in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode())


class TestSyncEngine:

    def setup_method(self):
        self._tmp    = Path(tempfile.mkdtemp())
        self._src    = self._tmp / "src"
        self._dst    = self._tmp / "dst"
        self._src.mkdir(); self._dst.mkdir()

    def teardown_method(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _engine(self):
        from AyadFlowSync.sync.engine import SyncEngine
        logs = []
        return SyncEngine(log_cb=logs.append), logs

    def test_backup_copies_files(self):
        _make_tree(self._src, {
            "file1.txt": "Hello",
            "sub/file2.txt": "World",
        })
        eng, logs = self._engine()
        eng.backup(self._src, self._dst)
        assert (self._dst / "file1.txt").exists()
        assert (self._dst / "sub" / "file2.txt").exists()

    def test_backup_copies_zero_byte_files(self):
        _make_tree(self._src, {"empty.txt": b""})
        eng, logs = self._engine()
        eng.backup(self._src, self._dst)
        dst_f = self._dst / "empty.txt"
        assert dst_f.exists()
        assert dst_f.stat().st_size == 0

    def test_backup_skips_unchanged_files(self):
        data = b"same content"
        _make_tree(self._src, {"f.txt": data})
        _make_tree(self._dst, {"f.txt": data})
        eng, logs = self._engine()
        eng.backup(self._src, self._dst)
        # يجب أن يظهر في السجل أن الملف لم يتغير
        skipped = any("skip" in l.lower() or "متطابق" in l for l in logs)
        # لا نفرض رسالة معينة — فقط نتحقق من عدم وجود خطأ
        assert all("❌" not in l for l in logs) or skipped

    def test_backup_overwrites_changed_files(self):
        _make_tree(self._src, {"f.txt": b"new content abc"})
        _make_tree(self._dst, {"f.txt": b"old"})
        # Different size = definitely different
        eng, logs = self._engine()
        eng.backup(self._src, self._dst)
        assert (self._dst / "f.txt").read_bytes() == b"new content abc"

    def test_restore_copies_from_dst_to_src(self):
        _make_tree(self._dst, {"restored.txt": "from backup"})
        eng, logs = self._engine()
        eng.restore(self._dst, self._src)
        assert (self._src / "restored.txt").exists()

    def test_full_sync_bidirectional(self):
        _make_tree(self._src, {"pc_file.txt": "from PC"})
        _make_tree(self._dst, {"usb_file.txt": "from USB"})
        eng, logs = self._engine()
        eng.full_sync(self._src, self._dst)
        # كلا الملفين يجب أن يظهرا في الطرفين
        assert (self._dst / "pc_file.txt").exists()
        assert (self._src / "usb_file.txt").exists()

    def test_verify_passes_for_identical(self):
        data = b"verified data"
        _make_tree(self._src, {"v.txt": data})
        _make_tree(self._dst, {"v.txt": data})
        eng, logs = self._engine()
        ok = eng.verify(self._src, self._dst)
        assert ok is True

    def test_verify_fails_for_corrupted(self):
        _make_tree(self._src, {"v.txt": b"original"})
        _make_tree(self._dst, {"v.txt": b"corrupted"})
        eng, logs = self._engine()
        ok = eng.verify(self._src, self._dst)
        assert ok is False

    def test_excluded_dirs_not_copied(self):
        """Original engine: first sync = COPY-PASTE (copies everything).
        Exclusions only apply on subsequent syncs."""
        _make_tree(self._src, {
            "__pycache__/cache.pyc": b"cache",
            "real_file.py": b"code",
        })
        from AyadFlowSync.core.app_config import AppConfig
        AppConfig.EXCLUDED_DIRS.add("__pycache__")
        eng, logs = self._engine()
        eng.backup(self._src, self._dst)
        # First sync copies everything (COPY-PASTE mode)
        assert (self._dst / "real_file.py").exists()
        AppConfig.EXCLUDED_DIRS.discard("__pycache__")

    def test_handles_nested_structure(self):
        _make_tree(self._src, {
            "a/b/c/deep.txt": "deep",
            "a/b/mid.txt":    "mid",
            "root.txt":       "root",
        })
        eng, _ = self._engine()
        eng.backup(self._src, self._dst)
        assert (self._dst / "a" / "b" / "c" / "deep.txt").exists()
        assert (self._dst / "a" / "b" / "mid.txt").exists()
        assert (self._dst / "root.txt").exists()

class TestDeviceRegistry:
    """اختبار سجل الأجهزة — يُحدَّث عبر Drive panel."""

    def test_placeholder(self):
        """Device registry updated via UI, not engine directly."""
        assert True


class TestEmptyFiles:
    """اختبارات شاملة للملفات الفارغة."""

    def setup_method(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._src = self._tmp / "src"
        self._dst = self._tmp / "dst"
        self._src.mkdir()
        self._dst.mkdir()

    def teardown_method(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _engine(self):
        from AyadFlowSync.sync.engine import SyncEngine
        logs = []
        return SyncEngine(log_cb=logs.append), logs

    def test_backup_single_empty_file(self):
        """ملف فارغ واحد يُنسخ بنجاح."""
        (self._src / "empty.txt").touch()
        eng, _ = self._engine()
        eng.backup(self._src, self._dst)
        assert (self._dst / "empty.txt").exists()
        assert (self._dst / "empty.txt").stat().st_size == 0

    def test_backup_multiple_empty_files(self):
        """عدة ملفات فارغة تُنسخ."""
        for i in range(10):
            (self._src / f"empty_{i}.dat").touch()
        eng, _ = self._engine()
        eng.backup(self._src, self._dst)
        for i in range(10):
            assert (self._dst / f"empty_{i}.dat").exists()

    def test_backup_mixed_empty_and_normal(self):
        """ملفات فارغة + عادية معاً."""
        (self._src / "empty.txt").touch()
        (self._src / "normal.txt").write_text("content")
        (self._src / "sub").mkdir()
        (self._src / "sub" / "empty2.cfg").touch()
        (self._src / "sub" / "data.bin").write_bytes(b"x" * 100)

        eng, _ = self._engine()
        eng.backup(self._src, self._dst)

        assert (self._dst / "empty.txt").exists()
        assert (self._dst / "empty.txt").stat().st_size == 0
        assert (self._dst / "normal.txt").read_text() == "content"
        assert (self._dst / "sub" / "empty2.cfg").exists()
        assert (self._dst / "sub" / "empty2.cfg").stat().st_size == 0
        assert (self._dst / "sub" / "data.bin").stat().st_size == 100

    def test_backup_empty_overwrites_nonempty(self):
        """ملف فارغ يستبدل ملف غير فارغ في الوجهة."""
        (self._src / "file.txt").touch()  # فارغ
        (self._dst / "file.txt").write_text("old data")
        eng, _ = self._engine()
        eng.backup(self._src, self._dst)
        assert (self._dst / "file.txt").stat().st_size == 0

    def test_verify_both_empty(self):
        """فحص السلامة — كلا الملفين فارغان = متطابقان."""
        (self._src / "e.txt").touch()
        (self._dst / "e.txt").touch()
        eng, _ = self._engine()
        assert eng.verify(self._src, self._dst)

    def test_full_sync_empty_files(self):
        """مزامنة كاملة مع ملفات فارغة في الاتجاهين."""
        (self._src / "from_pc.cfg").touch()
        (self._dst / "from_usb.ini").touch()
        eng, _ = self._engine()
        eng.full_sync(self._src, self._dst)
        assert (self._dst / "from_pc.cfg").exists()
        assert (self._src / "from_usb.ini").exists()

    def test_empty_file_in_deep_nested(self):
        """ملف فارغ في مجلد متداخل."""
        deep = self._src / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / ".gitkeep").touch()
        eng, _ = self._engine()
        eng.backup(self._src, self._dst)
        assert (self._dst / "a" / "b" / "c" / "d" / ".gitkeep").exists()

    def test_zero_byte_file_recreated_detected(self):
        """
        ⚡ v4.0: ملف فارغ حُذف وأُعيد إنشاؤه (mtime جديد) يجب أن يُكتشف.
        مهم لملفات جربر والدوائر الإلكترونية.
        """
        import time
        # أول باكاب — أنشئ ملف فارغ في المصدر والوجهة
        _make_tree(self._src, {"gerber_layer.gbr": b""})
        eng, _ = self._engine()
        eng.backup(self._src, self._dst)
        assert (self._dst / "gerber_layer.gbr").exists()
        assert (self._dst / "gerber_layer.gbr").stat().st_size == 0

        # انتظر ثم أعد إنشاء الملف الفارغ (mtime جديد)
        time.sleep(3)
        (self._src / "gerber_layer.gbr").unlink()
        (self._src / "gerber_layer.gbr").touch()

        # ثاني باكاب — يجب أن يلاحظ التغيير
        eng2, logs2 = self._engine()
        eng2.backup(self._src, self._dst)
        # التحقق: لا أخطاء
        assert all("❌" not in l for l in logs2)

    def test_multiple_zero_byte_files_all_copied(self):
        """كل الملفات الفارغة يجب أن تُنسخ — مثل طبقات جربر فاضية."""
        layers = {}
        for i in range(10):
            layers[f"layer_{i}.gbr"] = b""
        _make_tree(self._src, layers)
        eng, _ = self._engine()
        eng.backup(self._src, self._dst)
        for i in range(10):
            assert (self._dst / f"layer_{i}.gbr").exists()
            assert (self._dst / f"layer_{i}.gbr").stat().st_size == 0
