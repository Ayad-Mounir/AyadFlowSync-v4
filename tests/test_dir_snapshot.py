#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests.test_dir_snapshot
=======================
اختبارات لنظام الفهرس الذكي DirSnapshot — v4.0
"""

import os
import sys
import time
import shutil
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


def _make_tree(base: Path, files: dict):
    """ينشئ شجرة ملفات: {relative_path: content}"""
    for rel, content in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding='utf-8')


class TestDirSnapshot:

    def setup_method(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._src = self._tmp / "src"
        self._dst = self._tmp / "dst"
        self._src.mkdir()
        self._dst.mkdir()
        # Override DATA_DIR for tests
        from AyadFlowSync.core.app_config import AppConfig
        self._orig_data_dir = AppConfig.DATA_DIR
        AppConfig.DATA_DIR = self._tmp / "data"
        AppConfig.DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Reset DB connection
        from AyadFlowSync.sync.dir_snapshot import DirSnapshot
        DirSnapshot._DB_FILE = AppConfig.DATA_DIR / "dir_snapshots.db"
        if hasattr(DirSnapshot._local, 'conn'):
            try:
                DirSnapshot._local.conn.close()
            except Exception:
                pass
            del DirSnapshot._local.conn

    def teardown_method(self):
        from AyadFlowSync.core.app_config import AppConfig
        AppConfig.DATA_DIR = self._orig_data_dir
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _snap(self):
        from AyadFlowSync.sync.dir_snapshot import DirSnapshot
        return DirSnapshot(self._src, self._dst)

    # ── اختبار 1: أول مزامنة — كل المجلدات "متغيرة" ──────────
    def test_first_scan_all_changed(self):
        _make_tree(self._src, {
            "a/file1.txt": "hello",
            "b/file2.txt": "world",
            "c/d/file3.txt": "deep",
        })
        snap = self._snap()
        snap.load()
        assert snap.size == 0

        changed, scanned, skipped = snap.find_changed_dirs(self._src)
        # أول مرة — كل المجلدات جديدة
        assert len(changed) > 0
        assert skipped == 0

    # ── اختبار 2: بدون تغيير — كل المجلدات تُتخطى ──────────
    def test_no_changes_all_skipped(self):
        _make_tree(self._src, {
            "a/file1.txt": "hello",
            "b/file2.txt": "world",
        })
        snap = self._snap()
        snap.load()

        # أول مسح — يبني اللقطة
        snap.find_changed_dirs(self._src)
        snap.save()

        # ثاني مسح — بدون تغيير
        snap2 = self._snap()
        snap2.load()
        changed, scanned, skipped = snap2.find_changed_dirs(self._src)

        assert len(changed) == 0
        assert skipped > 0

    # ── اختبار 3: تغيير ملف واحد — مجلد واحد يُكتشف ──────────
    def test_one_file_changed_detects_dir(self):
        _make_tree(self._src, {
            "a/file1.txt": "hello",
            "b/file2.txt": "world",
            "c/file3.txt": "stable",
        })
        snap = self._snap()
        snap.load()
        snap.find_changed_dirs(self._src)
        snap.save()

        # غيّر ملف واحد في مجلد a
        time.sleep(0.05)
        (self._src / "a" / "file1.txt").write_text("changed!", encoding='utf-8')

        snap2 = self._snap()
        snap2.load()
        changed, scanned, skipped = snap2.find_changed_dirs(self._src)

        changed_names = {d.name for d in changed}
        assert "a" in changed_names
        # b و c لم يتغيرا
        assert skipped >= 1

    # ── اختبار 4: إضافة ملف جديد — يُكتشف المجلد ──────────
    def test_new_file_detects_dir(self):
        _make_tree(self._src, {
            "a/file1.txt": "hello",
        })
        snap = self._snap()
        snap.load()
        snap.find_changed_dirs(self._src)
        snap.save()

        # أضف ملف جديد في مجلد a
        (self._src / "a" / "file_new.txt").write_text("new!", encoding='utf-8')

        snap2 = self._snap()
        snap2.load()
        changed, scanned, skipped = snap2.find_changed_dirs(self._src)

        changed_names = {d.name for d in changed}
        assert "a" in changed_names

    # ── اختبار 5: حذف ملف — يُكتشف المجلد ──────────
    def test_deleted_file_detects_dir(self):
        _make_tree(self._src, {
            "a/file1.txt": "hello",
            "a/file2.txt": "world",
        })
        snap = self._snap()
        snap.load()
        snap.find_changed_dirs(self._src)
        snap.save()

        # احذف ملف
        (self._src / "a" / "file2.txt").unlink()

        snap2 = self._snap()
        snap2.load()
        changed, scanned, skipped = snap2.find_changed_dirs(self._src)

        changed_names = {d.name for d in changed}
        assert "a" in changed_names

    # ── اختبار 6: مجلد جديد بالكامل — يُكتشف ──────────
    def test_new_directory_detected(self):
        _make_tree(self._src, {
            "a/file1.txt": "hello",
        })
        snap = self._snap()
        snap.load()
        snap.find_changed_dirs(self._src)
        snap.save()

        # أضف مجلد جديد
        _make_tree(self._src, {
            "new_dir/new_file.txt": "brand new",
        })

        snap2 = self._snap()
        snap2.load()
        changed, scanned, skipped = snap2.find_changed_dirs(self._src)

        changed_names = {d.name for d in changed}
        assert "new_dir" in changed_names

    # ── اختبار 7: clear يمسح كل شيء ──────────
    def test_clear_resets(self):
        _make_tree(self._src, {
            "a/file1.txt": "hello",
        })
        snap = self._snap()
        snap.load()
        snap.find_changed_dirs(self._src)
        snap.save()
        assert snap.size > 0

        snap.clear()
        assert snap.size == 0

        # بعد clear — كل شيء "جديد" مرة ثانية
        snap2 = self._snap()
        snap2.load()
        assert snap2.size == 0

    # ── اختبار 8: حفظ وتحميل من DB ──────────
    def test_save_load_persistence(self):
        _make_tree(self._src, {
            "a/file1.txt": "hello",
            "b/file2.txt": "world",
        })
        snap = self._snap()
        snap.load()
        snap.find_changed_dirs(self._src)
        snap.save()
        size_after_save = snap.size

        # أنشئ instance جديد — يحمّل من DB
        snap2 = self._snap()
        snap2.load()
        assert snap2.size == size_after_save

    # ── اختبار 9: مشروع كبير — أداء ──────────
    def test_performance_many_dirs(self):
        """مشروع فيه 100 مجلد × 10 ملفات = 1000 ملف"""
        files = {}
        for i in range(100):
            for j in range(10):
                files[f"dir_{i:03d}/file_{j:02d}.txt"] = f"content_{i}_{j}"
        _make_tree(self._src, files)

        snap = self._snap()
        snap.load()

        # أول مسح
        t0 = time.perf_counter()
        changed1, scanned1, skipped1 = snap.find_changed_dirs(self._src)
        t1 = time.perf_counter()
        snap.save()

        # ثاني مسح — بدون تغيير
        snap2 = self._snap()
        snap2.load()
        t2 = time.perf_counter()
        changed2, scanned2, skipped2 = snap2.find_changed_dirs(self._src)
        t3 = time.perf_counter()

        # ثاني مسح يجب أن يكون أسرع ولا يوجد متغيرات
        assert len(changed2) == 0
        assert skipped2 > 0
        # يجب أن ينتهي في أقل من ثانية
        assert (t3 - t2) < 1.0

    # ── اختبار 10: stats_msg يعمل بشكل صحيح ──────────
    def test_stats_msg(self):
        snap = self._snap()
        msg = snap.stats_msg(5, 100, 95)
        assert "100" in msg
        assert "95" in msg
        assert "5" in msg

    # ── اختبار 11: مجلد متداخل عميق ──────────
    def test_deep_nested_change(self):
        _make_tree(self._src, {
            "a/b/c/d/deep.txt": "deep content",
            "x/shallow.txt": "shallow",
        })
        snap = self._snap()
        snap.load()
        snap.find_changed_dirs(self._src)
        snap.save()

        # غيّر ملف عميق
        time.sleep(0.05)
        (self._src / "a" / "b" / "c" / "d" / "deep.txt").write_text("changed deep", encoding='utf-8')

        snap2 = self._snap()
        snap2.load()
        changed, scanned, skipped = snap2.find_changed_dirs(self._src)

        changed_paths = {str(d) for d in changed}
        # المجلد d يجب أن يُكتشف
        assert any("d" in p for p in changed_paths)
        # x لم يتغير
        assert skipped >= 1
