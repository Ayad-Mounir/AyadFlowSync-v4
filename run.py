#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AyadFlowSync v3.0 — Entry point for PyInstaller EXE
"""
import sys
import os
import multiprocessing

# ── Ensure package is findable ──────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── Required for frozen multiprocessing on Windows ──────────
multiprocessing.freeze_support()

if __name__ == '__main__':
    from AyadFlowSync.main import main
    main()
