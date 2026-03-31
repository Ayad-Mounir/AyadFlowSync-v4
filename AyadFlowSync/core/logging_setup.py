#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.logging_setup
==================
إعداد نظام Logging الاحترافي مع تدوير الملفات.
"""

import sys
import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_dir: Path = None) -> None:
    """
    إعداد نظام Logging مع:
    - RotatingFileHandler لكل وحدة
    - Console handler للتطوير (خارج EXE فقط)
    يُستدعى مرة واحدة من main().
    """
    if log_dir is None:
        from .app_config import AppConfig
        log_dir = AppConfig.DATA_DIR / 'logs'

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt_full  = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fmt_short = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )

    configs = [
        ('AyadFlowSync',        log_dir / 'system.log',  logging.DEBUG,  fmt_full),
        ('AyadFlowSync.sync',   log_dir / 'sync.log',    logging.INFO,   fmt_short),
        ('AyadFlowSync.github', log_dir / 'github.log',  logging.INFO,   fmt_short),
    ]

    for name, path, level, fmt in configs:
        logger = logging.getLogger(name)
        if logger.handlers:
            continue
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
        )
        handler.setFormatter(fmt)
        handler.setLevel(level)
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False

    # Console handler — التطوير فقط
    if not getattr(sys, 'frozen', False):
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(fmt_short)
        console.setLevel(logging.WARNING)
        root = logging.getLogger('AyadFlowSync')
        if not any(isinstance(h, logging.StreamHandler) and h.stream == sys.stdout
                   for h in root.handlers):
            root.addHandler(console)
