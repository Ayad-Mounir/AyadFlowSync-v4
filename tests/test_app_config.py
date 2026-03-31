#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests.test_app_config
"""

import json
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from AyadFlowSync.core.app_config import AppConfig


class TestAppConfig:

    def test_data_dir_exists(self):
        assert AppConfig.DATA_DIR.exists()

    def test_init_dirs_creates_all(self):
        AppConfig.init_dirs()
        for d in [AppConfig.LOG_DIR, AppConfig.LOCK_DIR,
                  AppConfig.PRESYNC_DIR, AppConfig.TRASH_DIR]:
            assert d.exists()

    def test_load_excluded_dirs_default(self):
        AppConfig.load_excluded_dirs()
        # الافتراضي: لا شيء مستثنى — نسخ مطابق 100%
        assert isinstance(AppConfig.EXCLUDED_DIRS, set)

    def test_save_and_load_excluded_dirs(self):
        state = {'__pycache__': True, 'venv': False, '.git': True}
        AppConfig.save_excluded_dirs(state)
        AppConfig.load_excluded_dirs()
        assert '__pycache__' in AppConfig.EXCLUDED_DIRS
        assert 'venv' not in AppConfig.EXCLUDED_DIRS

    def test_accumark_save_load(self):
        AppConfig.save_accumark(True)
        AppConfig.load_accumark()
        assert AppConfig.ACCUMARK_MODE is True

        AppConfig.save_accumark(False)
        AppConfig.load_accumark()
        assert AppConfig.ACCUMARK_MODE is False

    def test_apply_speed_profile_slow_usb(self):
        AppConfig._apply_speed_profile(10.0)
        assert AppConfig.THREADS_SMALL == 2
        assert AppConfig.THREADS_LARGE == 1
        assert AppConfig.BATCH_SIZE == 50

    def test_apply_speed_profile_fast_usb(self):
        AppConfig._apply_speed_profile(120.0)
        assert AppConfig.THREADS_SMALL == 8
        assert AppConfig.THREADS_LARGE == 4
        assert AppConfig.BATCH_SIZE == 500

    def test_update_cache_path_uses_pc_name(self):
        AppConfig.PC_NAME = "TestPC"
        AppConfig.update_cache_path()
        assert "TestPC" in str(AppConfig.HASH_CACHE_FILE)

    def test_is_removable_non_windows(self):
        import platform
        if platform.system() != "Windows":
            result = AppConfig.is_removable(Path("/tmp"))
            assert result is False
