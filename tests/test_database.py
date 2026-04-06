#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests.test_database"""

import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDatabaseManager:

    def _db(self):
        from AyadFlowSync.db.database import DatabaseManager
        tmp = Path(tempfile.mktemp(suffix=".dat"))
        return DatabaseManager(tmp), tmp

    def test_get_default(self):
        db, tmp = self._db()
        assert db.get("missing", "default") == "default"

    def test_set_and_get(self):
        db, tmp = self._db()
        db.set("key", "value")
        assert db.get("key") == "value"

    def test_save_and_reload(self):
        db, tmp = self._db()
        db.set("name", "Mounir")
        db.save()
        from AyadFlowSync.db.database import DatabaseManager
        db2 = DatabaseManager(tmp)
        assert db2.get("name") == "Mounir"
        tmp.unlink(missing_ok=True)

    def test_save_is_atomic(self):
        """الحفظ عبر ملف مؤقت — إذا فشل لا يُفسد الأصلي."""
        db, tmp = self._db()
        db.set("safe", True)
        db.save()
        from AyadFlowSync.db.database import DatabaseManager
        db2 = DatabaseManager(tmp)
        assert db2.get("safe") is True
        tmp.unlink(missing_ok=True)

    def test_overwrites_existing(self):
        db, tmp = self._db()
        db.set("x", 1)
        db.set("x", 99)
        assert db.get("x") == 99

    def test_stores_list(self):
        db, tmp = self._db()
        db.set("projects", ["/a", "/b", "/c"])
        assert db.get("projects") == ["/a", "/b", "/c"]

    def test_stores_nested_dict(self):
        db, tmp = self._db()
        db.set("config", {"lang": "ar", "scale": 1.2})
        assert db.get("config")["lang"] == "ar"
