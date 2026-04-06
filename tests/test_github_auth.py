#!/usr/bin/env python3
"""Tests for GitHub Auth (encrypted token storage)."""

import sys
import shutil
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestGitHubAuth:
    def setup_method(self):
        self._tmp = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_save_and_load_token(self):
        from AyadFlowSync.github.ops import Auth
        from AyadFlowSync.core.app_config import AppConfig

        # Override token path for test
        original = Auth._TOKEN_FILE
        Auth._TOKEN_FILE = self._tmp / ".gh_token_test"

        try:
            Auth.save("ghp_test_12345abcdef")
            loaded = Auth.load()
            assert loaded == "ghp_test_12345abcdef"
        finally:
            Auth._TOKEN_FILE = original

    def test_clear_token(self):
        from AyadFlowSync.github.ops import Auth

        original = Auth._TOKEN_FILE
        Auth._TOKEN_FILE = self._tmp / ".gh_token_test"

        try:
            Auth.save("ghp_test_token")
            assert Auth.load() == "ghp_test_token"
            Auth.clear()
            assert Auth.load() == ""
        finally:
            Auth._TOKEN_FILE = original

    def test_token_saved_plaintext_by_default(self):
        """بدون PIN → الـ Token يُحفظ بشكل عادي."""
        from AyadFlowSync.github.ops import Auth

        original = Auth._TOKEN_FILE
        Auth._TOKEN_FILE = self._tmp / ".gh_token_test"

        try:
            Auth.save("ghp_secret_token_xyz")
            raw = Auth._TOKEN_FILE.read_text(encoding='utf-8').strip()
            assert raw == "ghp_secret_token_xyz"
        finally:
            Auth._TOKEN_FILE = original

    def test_token_encrypted_with_pin(self):
        """مع PIN مفعّل → الـ Token يُشفَّر."""
        from AyadFlowSync.github.ops import Auth
        from AyadFlowSync.security.secure_store import SecureStore
        import json

        original = Auth._TOKEN_FILE
        Auth._TOKEN_FILE = self._tmp / ".gh_token_pin"

        try:
            SecureStore.set_master_pin("1234")
            Auth.save("ghp_encrypted_token")
            raw = Auth._TOKEN_FILE.read_text(encoding='utf-8')
            doc = json.loads(raw)
            assert "ct" in doc
            assert "ghp_encrypted_token" not in raw
            # Should load back correctly
            assert Auth.load() == "ghp_encrypted_token"
        finally:
            SecureStore.clear_master_pin()
            Auth._TOKEN_FILE = original

    def test_load_nonexistent(self):
        from AyadFlowSync.github.ops import Auth

        original = Auth._TOKEN_FILE
        Auth._TOKEN_FILE = self._tmp / "nonexistent_token"

        try:
            assert Auth.load() == ""
        finally:
            Auth._TOKEN_FILE = original

    def test_plain_token_loads_correctly(self):
        """Token محفوظ كنص عادي يُقرأ بشكل صحيح."""
        from AyadFlowSync.github.ops import Auth

        original = Auth._TOKEN_FILE
        Auth._TOKEN_FILE = self._tmp / ".gh_token_test"

        try:
            # Write plain token directly
            Auth._TOKEN_FILE.write_text("ghp_plain_token_123", encoding='utf-8')
            loaded = Auth.load()
            assert loaded == "ghp_plain_token_123"
        finally:
            Auth._TOKEN_FILE = original
