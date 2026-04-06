#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests.test_device_profiler
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from AyadFlowSync.core.device_profiler import DeviceProfiler, DeviceProfile


class TestDeviceProfiler:

    def test_measure_returns_valid_profile(self):
        profile = DeviceProfiler.measure()
        assert profile in (DeviceProfile.WEAK, DeviceProfile.MID,
                           DeviceProfile.STRONG, DeviceProfile.ULTRA)

    def test_measure_idempotent(self):
        """استدعاء measure() عدة مرات يُعيد نفس النتيجة."""
        p1 = DeviceProfiler.measure()
        p2 = DeviceProfiler.measure()
        assert p1 == p2

    def test_get_label_not_empty(self):
        DeviceProfiler.measure()
        label = DeviceProfiler.get_label()
        assert len(label) > 0

    def test_specs_text_has_cores(self):
        DeviceProfiler.measure()
        text = DeviceProfiler.get_specs_text()
        assert "نواة" in text or "core" in text

    def test_use_process_pool_is_bool(self):
        DeviceProfiler.measure()
        result = DeviceProfiler.use_process_pool()
        assert isinstance(result, bool)

    def test_copytree_workers_positive(self):
        DeviceProfiler.measure()
        w = DeviceProfiler.get_copytree_workers()
        assert w >= 1

    def test_scan_workers_positive(self):
        DeviceProfiler.measure()
        w = DeviceProfiler.get_scan_workers()
        assert w >= 1

    def test_weak_profile_disables_process_pool(self):
        original = DeviceProfiler._profile
        DeviceProfiler._profile = DeviceProfile.WEAK
        assert DeviceProfiler.use_process_pool() is False
        DeviceProfiler._profile = original

    def test_score_in_valid_range(self):
        """⚡ v4.0: النقاط يجب أن تكون بين 0 و 100"""
        DeviceProfiler.measure()
        score = DeviceProfiler.get_score()
        assert 0 <= score <= 100

    def test_ultra_profile_settings(self):
        """⚡ v4.0: المستوى الخارق يستخدم أكثر threads"""
        original = DeviceProfiler._profile
        DeviceProfiler._profile = DeviceProfile.ULTRA
        assert DeviceProfiler.get_copytree_workers() >= 16
        assert DeviceProfiler.get_scan_workers() >= 8
        DeviceProfiler._profile = original

    def test_detailed_info_has_all_keys(self):
        """⚡ v4.0: get_detailed_info يرجع كل المعلومات"""
        DeviceProfiler.measure()
        info = DeviceProfiler.get_detailed_info()
        assert "score" in info
        assert "cpu_score" in info
        assert "ram_score" in info
        assert "hash_score" in info
        assert "color" in info
        assert info["cpu_score"] + info["ram_score"] + info["hash_score"] == info["score"]

    def test_get_color_returns_hex(self):
        """⚡ v4.0: اللون يرجع بصيغة hex"""
        DeviceProfiler.measure()
        color = DeviceProfiler.get_color()
        assert color.startswith("#")
        assert len(color) == 7
