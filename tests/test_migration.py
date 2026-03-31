#!/usr/bin/env python3
"""Tests for v2→v3 migration system."""

import sys
import json
import shutil
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMigration:
    def setup_method(self):
        self._tmp = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_schema_version_default(self):
        from AyadFlowSync.core.migration import get_schema_version
        assert get_schema_version() >= 1

    def test_set_and_get_version(self):
        from AyadFlowSync.core.migration import set_schema_version, get_schema_version, VERSION_FILE
        old = VERSION_FILE
        # Test with temp file
        import AyadFlowSync.core.migration as m
        m.VERSION_FILE = self._tmp / ".schema_version"
        set_schema_version(5)
        assert get_schema_version() == 5
        m.VERSION_FILE = old

    def test_needs_migration_fresh(self):
        from AyadFlowSync.core.migration import CURRENT_VERSION
        assert CURRENT_VERSION == 3

    def test_plaintext_token_migration(self):
        from AyadFlowSync.core.app_config import AppConfig
        from AyadFlowSync.core.migration import _migrate_v2_to_v3

        # Simulate old plaintext token
        old_token = AppConfig.DATA_DIR / ".gh_token"
        old_token.write_text("ghp_test_token_12345", encoding='utf-8')

        msgs = _migrate_v2_to_v3()

        # Old file should be gone
        assert not old_token.exists(), "Plaintext token should be deleted"

        # New encrypted file should exist
        new_token = AppConfig.DATA_DIR / ".gh_token_v3"
        assert new_token.exists(), "Encrypted token should exist"

        # Should be readable
        from AyadFlowSync.security.secure_store import SecureStore
        loaded = SecureStore.load(new_token)
        assert loaded == "ghp_test_token_12345"

        # Verify migration message
        assert any("encrypted" in m.lower() for m in msgs)

        # Cleanup
        new_token.unlink(missing_ok=True)

    def test_temp_file_cleanup(self):
        from AyadFlowSync.core.app_config import AppConfig
        from AyadFlowSync.core.migration import _migrate_v2_to_v3

        # Create fake temp files
        tmp1 = AppConfig.DATA_DIR / "test.__tmp__"
        tmp2 = AppConfig.DATA_DIR / "test.tmpsync"
        tmp1.write_text("garbage")
        tmp2.write_text("garbage")

        msgs = _migrate_v2_to_v3()

        assert not tmp1.exists()
        assert not tmp2.exists()
        assert any("temp" in m.lower() for m in msgs)
