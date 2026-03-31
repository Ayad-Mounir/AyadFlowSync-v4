#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests.test_hardware_monitor
"""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from AyadFlowSync.core.hardware import HardwareMonitor


class TestHardwareMonitor:

    def _make_monitor(self):
        return HardwareMonitor(usb_path_ref=lambda: None)

    def test_collect_now_returns_dict(self):
        mon  = self._make_monitor()
        data = mon.collect_now()
        assert isinstance(data, dict)

    def test_collect_has_required_keys(self):
        mon  = self._make_monitor()
        data = mon.collect_now()
        for key in ("cpu_pct", "ram_pct", "cpu_cores", "usb_free_gb"):
            assert key in data, f"Missing key: {key}"

    def test_cpu_pct_range(self):
        mon  = self._make_monitor()
        data = mon.collect_now()
        assert 0.0 <= data["cpu_pct"] <= 100.0

    def test_ram_pct_range(self):
        mon  = self._make_monitor()
        data = mon.collect_now()
        assert 0.0 <= data["ram_pct"] <= 100.0

    def test_usb_free_negative_when_no_usb(self):
        mon  = self._make_monitor()
        data = mon.collect_now()
        assert data["usb_free_gb"] == -1.0   # لا فلاشة متصلة

    def test_start_stop(self):
        mon = self._make_monitor()
        mon.start()
        assert mon._running is True
        time.sleep(0.1)
        mon.stop()
        assert mon._running is False

    def test_callback_receives_data(self):
        received = []
        mon = self._make_monitor()
        mon.add_callback(received.append)
        mon.start()
        time.sleep(1.5)
        mon.stop()
        assert len(received) >= 1
        assert "cpu_pct" in received[0]

    def test_remove_callback(self):
        mon = self._make_monitor()
        cb  = lambda d: None
        mon.add_callback(cb)
        assert cb in mon._callbacks
        mon.remove_callback(cb)
        assert cb not in mon._callbacks

    def test_format_bar(self):
        bar = HardwareMonitor.format_bar(50.0, width=8)
        assert len(bar) == 8
        assert bar == "████░░░░"

    def test_cpu_color_thresholds(self):
        assert HardwareMonitor.cpu_color(30)  == "#00ff41"
        assert HardwareMonitor.cpu_color(65)  == "#fbbf24"
        assert HardwareMonitor.cpu_color(90)  == "#ff4444"

    def test_ram_color_thresholds(self):
        assert HardwareMonitor.ram_color(50)  == "#00d4ff"
        assert HardwareMonitor.ram_color(75)  == "#fbbf24"
        assert HardwareMonitor.ram_color(95)  == "#ff4444"

    def test_get_last_after_collect(self):
        mon  = self._make_monitor()
        data = mon.collect_now()
        last = mon.get_last()
        assert last == data
