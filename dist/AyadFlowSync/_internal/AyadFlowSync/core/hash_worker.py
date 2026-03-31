#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.hash_worker
================
Worker دالة top-level لـ ProcessPoolExecutor.

يجب أن تكون على مستوى Module (لا داخل class) حتى يدعمها pickle.
"""

import struct
import mmap


def compute_hash(args: tuple) -> tuple:
    """
    ⚡ Hash Strategy ذكية حسب حجم الملف:
    • ملفات < 2MB    → chunk mode
    • ملفات 2–100MB  → mmap (hash كامل)
    • ملفات ≥ 100MB  → partial hash (أول + آخر 512KB + الحجم)

    الإرجاع: (path_str, hash_str, size, mtime_ns, success)
    """
    import hashlib

    path_str, size, mtime_ns, use_partial = args
    CHUNK = 524_288       # 512 KB
    PARTIAL_THRESHOLD = 100 * 1024 * 1024   # 100 MB
    EDGE  = 512 * 1024   # 512 KB للـ partial

    try:
        # اختر أسرع hasher متاح
        try:
            import xxhash as _xx
            h = _xx.xxh3_128()
            have_xx = True
        except ImportError:
            h = hashlib.sha256()
            have_xx = False

        # ملف فارغ
        if size == 0:
            empty = "0" * 32 if have_xx else hashlib.sha256(b"").hexdigest()
            return (path_str, empty, size, mtime_ns, True)

        with open(path_str, 'rb') as f:
            # Partial hash للملفات الضخمة
            if use_partial and size >= PARTIAL_THRESHOLD:
                first = f.read(EDGE)
                h.update(first)
                last_offset = size - EDGE
                if last_offset > EDGE:
                    f.seek(last_offset)
                    h.update(f.read())
                h.update(struct.pack('<Q', size))
                return (path_str, h.hexdigest(), size, mtime_ns, True)

            # mmap للملفات المتوسطة الكبيرة
            if size >= 2 * 1024 * 1024:
                try:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        h.update(mm)
                    return (path_str, h.hexdigest(), size, mtime_ns, True)
                except (mmap.error, OSError, ValueError):
                    f.seek(0)

            # chunk mode للملفات الصغيرة
            for chunk in iter(lambda: f.read(CHUNK), b''):
                h.update(chunk)

        return (path_str, h.hexdigest(), size, mtime_ns, True)

    except Exception:
        return (path_str, "", size, mtime_ns, False)


# alias للتوافق مع الكود القديم
_mp_compute_hash = compute_hash
