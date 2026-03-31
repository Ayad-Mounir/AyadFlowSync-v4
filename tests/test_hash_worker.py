#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests.test_hash_worker
======================
اختبارات وحدة compute_hash.
"""

import os
import tempfile
try:
    import pytest
except ImportError:
    pytest = None
from pathlib import Path


def _write_tmp(data: bytes) -> str:
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(data); f.close()
    return f.name


# ── استيراد ──────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from AyadFlowSync.core.hash_worker import compute_hash


class TestComputeHash:

    def test_empty_file(self):
        path = _write_tmp(b"")
        result = compute_hash((path, 0, 0, False))
        os.unlink(path)
        path_r, hash_r, size, mtime, ok = result
        assert ok is True
        assert size == 0
        assert len(hash_r) > 0

    def test_small_file(self):
        data = b"Hello AyadFlowSync!"
        path = _write_tmp(data)
        stat = Path(path).stat()
        result = compute_hash((path, stat.st_size, int(stat.st_mtime_ns), False))
        os.unlink(path)
        _, hash_r, size, _, ok = result
        assert ok is True
        assert size == len(data)
        assert len(hash_r) > 0

    def test_same_content_same_hash(self):
        data = os.urandom(1024)
        p1 = _write_tmp(data)
        p2 = _write_tmp(data)
        s1 = Path(p1).stat()
        s2 = Path(p2).stat()
        r1 = compute_hash((p1, s1.st_size, int(s1.st_mtime_ns), False))
        r2 = compute_hash((p2, s2.st_size, int(s2.st_mtime_ns), False))
        os.unlink(p1); os.unlink(p2)
        assert r1[1] == r2[1], "نفس المحتوى يجب أن ينتج نفس الـ Hash"

    def test_different_content_different_hash(self):
        p1 = _write_tmp(b"content A")
        p2 = _write_tmp(b"content B")
        s1 = Path(p1).stat()
        s2 = Path(p2).stat()
        r1 = compute_hash((p1, s1.st_size, int(s1.st_mtime_ns), False))
        r2 = compute_hash((p2, s2.st_size, int(s2.st_mtime_ns), False))
        os.unlink(p1); os.unlink(p2)
        assert r1[1] != r2[1], "محتوى مختلف يجب أن ينتج Hash مختلفاً"

    def test_mmap_path_large_file(self):
        """ملف 4MB — يسلك مسار mmap."""
        data = os.urandom(4 * 1024 * 1024)
        path = _write_tmp(data)
        stat = Path(path).stat()
        result = compute_hash((path, stat.st_size, int(stat.st_mtime_ns), False))
        os.unlink(path)
        _, _, _, _, ok = result
        assert ok is True

    def test_partial_hash_flag(self):
        """ملف مع use_partial=True — يجب أن يُكمل بدون خطأ."""
        data = os.urandom(2 * 1024 * 1024)
        path = _write_tmp(data)
        stat = Path(path).stat()
        result = compute_hash((path, stat.st_size, int(stat.st_mtime_ns), True))
        os.unlink(path)
        _, _, _, _, ok = result
        assert ok is True

    def test_missing_file_returns_failure(self):
        result = compute_hash(("/nonexistent/file.bin", 100, 0, False))
        _, _, _, _, ok = result
        assert ok is False

    def test_returns_correct_path(self):
        path = _write_tmp(b"test")
        stat = Path(path).stat()
        result = compute_hash((path, stat.st_size, int(stat.st_mtime_ns), False))
        os.unlink(path)
        assert result[0] == path
