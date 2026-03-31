#!/usr/bin/env python3
"""Tests for SecureStore encryption."""

import sys
import tempfile
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSecureStore:
    def setup_method(self):
        self._tmp = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_save_and_load(self):
        from AyadFlowSync.security.secure_store import SecureStore
        f = self._tmp / "test.enc"
        SecureStore.save(f, "my_secret_token_12345")
        result = SecureStore.load(f)
        assert result == "my_secret_token_12345"

    def test_tampered_file_fails(self):
        from AyadFlowSync.security.secure_store import SecureStore
        import json
        f = self._tmp / "test.enc"
        SecureStore.save(f, "secret")
        # Tamper with ciphertext
        doc = json.loads(f.read_text())
        doc["ct"] = "00" * 10
        f.write_text(json.dumps(doc))
        result = SecureStore.load(f)
        assert result is None  # HMAC mismatch

    def test_nonexistent_returns_none(self):
        from AyadFlowSync.security.secure_store import SecureStore
        result = SecureStore.load(self._tmp / "nope.enc")
        assert result is None

    def test_delete(self):
        from AyadFlowSync.security.secure_store import SecureStore
        f = self._tmp / "test.enc"
        SecureStore.save(f, "token")
        assert f.exists()
        SecureStore.delete(f)
        assert not f.exists()

    def test_unicode_content(self):
        from AyadFlowSync.security.secure_store import SecureStore
        f = self._tmp / "unicode.enc"
        text = "مرحباً بالعالم 🌍 こんにちは"
        SecureStore.save(f, text)
        assert SecureStore.load(f) == text

    def test_with_pin(self):
        from AyadFlowSync.security.secure_store import SecureStore
        f = self._tmp / "pinned.enc"
        SecureStore.set_master_pin("1234")
        SecureStore.save(f, "secret_with_pin")
        result = SecureStore.load(f)
        assert result == "secret_with_pin"
        # Wrong PIN
        SecureStore.set_master_pin("9999")
        result = SecureStore.load(f)
        assert result is None  # HMAC mismatch with wrong PIN
        SecureStore.clear_master_pin()
