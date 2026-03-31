# -*- mode: python ; coding: utf-8 -*-
"""
AyadFlowSync v4.0 — PyInstaller Spec
Compatible with PyInstaller 5.x and 6.x
"""

import sys
import os
from pathlib import Path

ROOT = os.path.dirname(os.path.abspath(SPEC))

# ── الأيقونة — محاولة مسارات متعددة ──────────────────────
_icon_candidates = [
    os.path.join(ROOT, 'assets', 'icon.ico'),
    os.path.join(ROOT, 'icon.ico'),
    os.path.join(os.getcwd(), 'assets', 'icon.ico'),
    os.path.join(os.getcwd(), 'icon.ico'),
]
ICON_FILE = None
for _c in _icon_candidates:
    if os.path.exists(_c):
        ICON_FILE = _c
        print(f"[icon] Found: {_c}")
        break
if not ICON_FILE:
    print(f"[icon] Not found — checked: {_icon_candidates}")
else:
    print(f"[icon] Using: {ICON_FILE}")

# ── ملفات البيانات ─────────────────────────────────────────
datas = [
    (os.path.join(ROOT, 'AyadFlowSync', 'lang'), os.path.join('AyadFlowSync', 'lang')),
    (os.path.join(ROOT, 'AyadFlowSync'), 'AyadFlowSync'),
]

# ── Hidden imports ─────────────────────────────────────────
hidden_imports = [
    # Qt
    'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.sip',
    'PyQt6.QtNetwork',
    # Third party
    'xxhash', 'psutil', 'requests', 'requests.adapters', 'requests.auth',
    'cryptography', 'cryptography.fernet',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.kdf.pbkdf2',
    'cryptography.hazmat.primitives.hashes',
    'cryptography.hazmat.primitives.ciphers',
    'cryptography.hazmat.backends',
    'cryptography.hazmat.backends.openssl',
    'git', 'git.repo', 'git.exc',
    'packaging', 'packaging.version', 'packaging.requirements',
    # stdlib
    'sqlite3', 'mmap', 'json', 'hashlib', 'hmac', 'socket',
    'multiprocessing', 'multiprocessing.pool',
    'concurrent.futures', 'concurrent.futures.thread',
    'email', 'email.mime', 'email.mime.text',
    'urllib', 'urllib.parse', 'urllib.request', 'urllib.error',
    'http', 'http.client', 'http.cookiejar',
    'ssl', 'certifi',
    # AyadFlowSync
    'AyadFlowSync',
    'AyadFlowSync.core',
    'AyadFlowSync.core.constants',
    'AyadFlowSync.core.app_config',
    'AyadFlowSync.core.device_profiler',
    'AyadFlowSync.core.hardware',
    'AyadFlowSync.core.hash_worker',
    'AyadFlowSync.core.logging_setup',
    'AyadFlowSync.core.migration',
    'AyadFlowSync.sync',
    'AyadFlowSync.sync.engine',
    'AyadFlowSync.sync.copier',
    'AyadFlowSync.sync.report',
    'AyadFlowSync.sync.pipeline',
    'AyadFlowSync.sync.index',
    'AyadFlowSync.github',
    'AyadFlowSync.github.client',
    'AyadFlowSync.github.manager',
    'AyadFlowSync.github.ops',
    'AyadFlowSync.github.analyzer',
    'AyadFlowSync.github.readme',
    'AyadFlowSync.github.ai',
    'AyadFlowSync.db',
    'AyadFlowSync.db.database',
    'AyadFlowSync.lang',
    'AyadFlowSync.lang.lang',
    'AyadFlowSync.lang.proxy',
    'AyadFlowSync.lang.arabic',
    'AyadFlowSync.security',
    'AyadFlowSync.security.secure_store',
    'AyadFlowSync.security.security',
    'AyadFlowSync.security.hash',
    'AyadFlowSync.ui',
    'AyadFlowSync.ui.qt',
    'AyadFlowSync.ui.qt.main_window',
    'AyadFlowSync.ui.qt.sync_panel',
    'AyadFlowSync.ui.qt.github_panel',
    'AyadFlowSync.ui.qt.drive_panel',
    'AyadFlowSync.ui.qt.about_panel',
    'AyadFlowSync.ui.qt.settings_panel',
    'AyadFlowSync.ui.qt.hardware_widget',
    'AyadFlowSync.ui.qt.styles',
]

# ── Analysis ───────────────────────────────────────────────
a = Analysis(
    [os.path.join(ROOT, 'run.py')],   # ← نقطة الدخول الصحيحة
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter', 'matplotlib', 'numpy', 'scipy',
        'pandas', 'PIL', 'Pillow', 'cv2', 'tensorflow', 'torch',
        'notebook', 'jupyter', 'IPython',
        'test', 'tests', 'unittest',
    ],
    noarchive=False,
)

# ── تصغير الحجم — حذف Qt modules غير مستخدمة ──────────────
REMOVE_PATTERNS = [
    'Qt6Web', 'Qt6Quick', 'Qt6Qml', 'Qt6Designer',
    'Qt6Pdf', 'Qt6Multimedia', 'Qt6Bluetooth',
    'Qt6Location', 'Qt6Positioning', 'Qt6RemoteObjects',
    'Qt6Sensors', 'Qt6SerialPort', 'Qt6Sql', 'Qt6Test',
    'Qt6VirtualKeyboard', 'Qt6Charts', 'Qt63D',
]
a.binaries = [
    (name, path, typ)
    for name, path, typ in a.binaries
    if not any(pat in name for pat in REMOVE_PATTERNS)
]

# ── Build ──────────────────────────────────────────────────
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AyadFlowSync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AyadFlowSync',
)
