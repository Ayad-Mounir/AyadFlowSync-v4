#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.constants
==============
جميع ثوابت التطبيق في مكان واحد.
لا يستورد من أي وحدة داخلية — صفر circular imports.
"""

import sys
from pathlib import Path

# ── معلومات التطبيق ────────────────────────────────────────────
APP_NAME    = "Ayad FlowSync"
APP_VERSION = "4.0.0"
APP_AUTHOR  = "Mounir Ayad"
NL          = "\n"


def fmt_size(n: int) -> str:
    """تنسيق حجم الملف — دالة موحّدة تُستخدم في كل النظام."""
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != 'B' else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


class AppInfo:
    VERSION = APP_VERSION
    NAME    = APP_NAME
    AUTHOR  = APP_AUTHOR


# ── مسارات أساسية ─────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    # تشغيل من EXE (PyInstaller)
    SCRIPT_DIR = Path(sys.executable).parent.resolve()
else:
    # AyadFlowSync/core/constants.py → parent.parent = AyadFlowSync/
    SCRIPT_DIR = Path(__file__).parent.parent.resolve()

PORTABLE_MARKER   = SCRIPT_DIR / '.portable'
_FIRST_RUN_MARKER = SCRIPT_DIR / '.first_run_done'


# ── امتدادات الملفات الثنائية ───────────────────────────────────
BINARY_EXTENSIONS: frozenset = frozenset({
    '.exe', '.dll', '.msi', '.bat', '.com',
    '.so', '.dylib', '.out', '.elf', '.bin', '.run', '.appimage',
    '.apk', '.ipa', '.aab',
    '.zip', '.tar', '.gz', '.7z', '.rar',
    '.db', '.sqlite', '.sqlite3',
    '.mp4', '.mp3', '.wav', '.png', '.jpg', '.jpeg', '.gif', '.webp',
    '.pdf', '.ico', '.icns',
})

# ── حد حجم Git Push ────────────────────────────────────────────
MAX_FILE_SIZE_MB = 90

# ── أنماط الملفات الحساسة ───────────────────────────────────────
SENSITIVE_PATTERNS = [
    ".env", "*.key", "*.pem", "*.p12", "*.pfx",
    "*.secret", "secrets.*", "credentials.*",
    "config/database.yml", "*.sqlite", "*.db",
]

# ── مجلدات يجب تجاهلها دائماً ──────────────────────────────────
IGNORED_DIRS: frozenset = frozenset({
    'node_modules', '__pycache__', '.git', '.svn', '.hg',
    'venv', 'env', '.env', '.venv', 'build',
    '.idea', '.vscode', 'target', 'bin', 'obj',
    '.dart_tool', '.flutter-plugins', 'Pods',
    '.gradle', '.cache', 'coverage', '.nyc_output',
    '.ayad_build_venv', '.ayadsync_tmp',
})

# ── تراخيص GitHub ──────────────────────────────────────────────
LICENSES = [
    'None', 'MIT', 'Apache-2.0', 'GPL-3.0', 'BSD-3-Clause',
    'ISC', 'LGPL-3.0', 'MPL-2.0', 'AGPL-3.0', 'Unlicense',
]

# ── مزودو الذكاء الاصطناعي ──────────────────────────────────────
AI_PROVIDERS: dict = {
    'gemini': {
        'name': 'Gemini 2.0 Flash',
        'model': 'gemini-2.0-flash',
        'url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
        'signup': 'https://aistudio.google.com/',
        'fallback_models': ['gemini-2.0-flash-lite', 'gemini-1.5-flash'],
    },
    'claude': {
        'name': 'Claude Haiku',
        'model': 'claude-haiku-4-5-20251001',
        'url': 'https://api.anthropic.com/v1/messages',
        'signup': 'https://console.anthropic.com/',
        'fallback_models': ['claude-haiku-3-5-20241022'],
    },
    'deepseek': {
        'name': 'DeepSeek',
        'model': 'deepseek-chat',
        'url': 'https://api.deepseek.com/chat/completions',
        'signup': 'https://platform.deepseek.com/',
        'fallback_models': [],
    },
    'openai': {
        'name': 'OpenAI GPT-4o',
        'model': 'gpt-4o-mini',
        'url': 'https://api.openai.com/v1/chat/completions',
        'signup': 'https://platform.openai.com/',
        'fallback_models': ['gpt-4o', 'gpt-3.5-turbo'],
    },
}


# ── ثيمات الألوان ───────────────────────────────────────────────
class Theme:
    """ألوان الواجهة — Professional Slate Dark"""
    # خلفيات
    BG        = "#0b0d11"
    BG_CARD   = "#13161e"
    BG_CARD2  = "#1a1e28"
    BORDER    = "#21262d"
    SIDEBAR   = "#0d0f14"

    # نصوص
    TEXT      = "#e2e8f0"
    TEXT_DIM  = "#718096"
    TEXT_MUTED= "#4a5568"

    # ألوان التمييز
    ACCENT    = "#6366f1"   # Indigo
    ACCENT2   = "#818cf8"
    CYAN      = "#22d3ee"
    SUCCESS   = "#34d399"
    ERROR     = "#f87171"
    WARNING   = "#fbbf24"
    INFO      = "#60a5fa"
    PURPLE    = "#a78bfa"

    # أحجام الخطوط
    F_TITLE   = 24
    F_HEAD    = 16
    F_BTN     = 14
    F_STATUS  = 12

    # خطوط
    FONT_UI   = "Segoe UI"
    FONT_MONO = "Cascadia Code"
    FONT_MONO_FB = "Consolas"
