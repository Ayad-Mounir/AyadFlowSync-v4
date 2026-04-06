#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
conftest.py — إعداد pytest المركزي
"""

import sys
import tempfile
import shutil
from pathlib import Path

# إضافة جذر المشروع لـ sys.path
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest


# ── Fixtures المشتركة ────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    """مجلد مؤقت يُحذف تلقائياً بعد كل اختبار."""
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def src_dir(tmp_dir):
    """مجلد مصدر مؤقت."""
    d = tmp_dir / "src"
    d.mkdir()
    return d


@pytest.fixture
def dst_dir(tmp_dir):
    """مجلد وجهة مؤقت."""
    d = tmp_dir / "dst"
    d.mkdir()
    return d


@pytest.fixture
def sample_project(src_dir):
    """مشروع Python بسيط للاختبار."""
    (src_dir / "main.py").write_text('print("hello")\n')
    (src_dir / "utils.py").write_text('def add(a, b): return a + b\n')
    (src_dir / "README.md").write_text("# My Project\n")
    (src_dir / "requirements.txt").write_text("requests\nxxhash\n")
    sub = src_dir / "src"
    sub.mkdir()
    (sub / "module.py").write_text("# module\n")
    return src_dir


@pytest.fixture
def sync_engine():
    """SyncEngine مُعدّ للاختبار."""
    from AyadFlowSync.sync.engine import SyncEngine
    logs = []
    engine = SyncEngine(log_cb=logs.append)
    engine._test_logs = logs
    return engine


@pytest.fixture
def db(tmp_dir):
    """DatabaseManager مؤقت."""
    from AyadFlowSync.db.database import DatabaseManager
    return DatabaseManager(tmp_dir / "test.dat")


# ── pytest configuration ─────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: اختبارات بطيئة (تحتاج شبكة أو I/O كثير)"
    )
    config.addinivalue_line(
        "markers", "integration: اختبارات تكاملية"
    )
    config.addinivalue_line(
        "markers", "github: تحتاج GitHub token"
    )
