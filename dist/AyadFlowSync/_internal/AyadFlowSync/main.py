#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AyadFlowSync v3.0 — نقطة الدخول (PyQt6)
"""

import sys
import os
import multiprocessing
import traceback

# ── sys.path ────────────────────────────────────────────────────
_HERE   = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)


def _check_pyqt6():
    """تحقق من وجود PyQt6 وثبّته تلقائياً إذا لزم."""
    try:
        from PyQt6.QtWidgets import QApplication
        return True
    except ImportError:
        # Skip auto-install when running as frozen EXE
        if getattr(sys, 'frozen', False):
            print("❌ PyQt6 missing in frozen build!")
            return False
        print("📦 Installing PyQt6...")
        import subprocess
        for flag in ['--user', '--break-system-packages']:
            r = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', 'PyQt6', flag, '--quiet'],
                capture_output=True, timeout=180
            )
            if r.returncode == 0:
                try:
                    from PyQt6.QtWidgets import QApplication
                    return True
                except ImportError:
                    continue
        return False


def main():
    multiprocessing.freeze_support()

    # ── Logging ──────────────────────────────────────────────────
    import logging
    try:
        from AyadFlowSync.core.logging_setup import setup_logging
        from AyadFlowSync.core.app_config    import AppConfig
        setup_logging(AppConfig.DATA_DIR / 'logs')
        
        # ⚡ تنظيف إعدادات قديمة تمنع النسخ الكامل
        _fix_old = AppConfig.DATA_DIR / "excluded_dirs.json"
        if _fix_old.exists():
            try:
                import json as _j
                _old_data = _j.loads(_fix_old.read_text(encoding='utf-8'))
                # إذا فيه أي مجلد مفعّل من الإعدادات القديمة → احذف الملف
                if any(v for v in _old_data.values()):
                    _fix_old.unlink()
                    logging.getLogger('AyadFlowSync').info("Cleared old exclusion config — all dirs will be copied")
            except Exception:
                try: _fix_old.unlink()
                except: pass
        logging.getLogger('AyadFlowSync').info("=" * 50)
        logging.getLogger('AyadFlowSync').info("AyadFlowSync v4.0 starting (PyQt6)...")
    except Exception as e:
        logging.basicConfig(level=logging.DEBUG)
        logging.warning(f"setup_logging failed: {e}")

    # ── PyQt6 check ──────────────────────────────────────────────
    if not _check_pyqt6():
        print("❌ فشل تثبيت PyQt6. شغّل يدوياً: pip install PyQt6")
        sys.exit(1)

    # ✅ Windows: AppUserModelID يجب أن يُسجَّل قبل QApplication
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "AyadMounir.AyadFlowSync.4.0"
            )
        except Exception:
            pass

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QLinearGradient
    from PyQt6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setApplicationName("AyadFlowSync")
    app.setOrganizationName("Ayad Mounir")

    # ⚡ v4.0: أيقونة — تحميل .ico أو توليد برمجي
    _icon_found = False
    _icon_dirs = [
        os.path.join(_HERE, 'assets', 'icon.ico'),
        os.path.join(_HERE, '..', 'assets', 'icon.ico'),
        os.path.join(_PARENT, 'assets', 'icon.ico'),
        os.path.join(os.getcwd(), 'assets', 'icon.ico'),
        os.path.join(_HERE, 'icon.ico'),
        os.path.join(_PARENT, 'icon.ico'),
    ]
    for _icon_path in _icon_dirs:
        if os.path.isfile(_icon_path):
            app.setWindowIcon(QIcon(_icon_path))
            _icon_found = True
            break

    if not _icon_found:
        # توليد أيقونة برمجياً — تظهر في taskbar + title bar
        _icon = QIcon()
        for _sz in [16, 24, 32, 48, 64, 128, 256]:
            _px = QPixmap(_sz, _sz)
            _px.fill(QColor(0, 0, 0, 0))
            _p = QPainter(_px)
            _p.setRenderHint(QPainter.RenderHint.Antialiasing)
            _g = QLinearGradient(0, 0, _sz, _sz)
            _g.setColorAt(0, QColor("#4f46e5"))
            _g.setColorAt(1, QColor("#818cf8"))
            _p.setBrush(_g)
            _p.setPen(Qt.PenStyle.NoPen)
            _m = max(_sz // 16, 1)
            _p.drawRoundedRect(_m, _m, _sz - _m*2, _sz - _m*2, _sz//4, _sz//4)
            _p.setPen(QColor("#ffffff"))
            _fs = max(_sz * 55 // 100, 8)
            _p.setFont(QFont("Segoe UI", _fs, QFont.Weight.Bold))
            _p.drawText(_px.rect(), Qt.AlignmentFlag.AlignCenter, "⚡")
            _p.end()
            _icon.addPixmap(_px)
        app.setWindowIcon(_icon)

    # ── Splash Screen ─────────────────────────────────────────────
    try:
        from AyadFlowSync.ui.qt.main_window import SplashScreen, ProfilerThread
        splash = SplashScreen()
        splash.show()
        app.processEvents()

        # ── قياس الجهاز ──────────────────────────────────────────
        splash.set_status("قياس أداء الجهاز...", 15)

        profiler = ProfilerThread()
        profiler.start()

        # انتظر قياس الجهاز
        while not profiler.isFinished():
            app.processEvents()

        splash.set_status("تهيئة قاعدة بيانات الـ Hash...", 40)
        try:
            from AyadFlowSync.security.hash import HashCache
            HashCache.load()
        except Exception as e:
            import logging
            logging.getLogger('AyadFlowSync').warning(f"HashCache.load: {e}")

        # ── Migration v2 → v3 ────────────────────────────────────
        splash.set_status("فحص الترقية...", 55)
        try:
            from AyadFlowSync.core.migration import needs_migration, run_all_migrations
            if needs_migration():
                splash.set_status("ترقية البيانات...", 60)
                msgs = run_all_migrations()
                for m in msgs:
                    logging.getLogger('AyadFlowSync').info(f"Migration: {m}")
        except Exception as e:
            logging.getLogger('AyadFlowSync').warning(f"Migration: {e}")

        splash.set_status("تحميل الواجهة...", 75)

        # ── اسم الجهاز (أول تشغيل = نافذة إدخال) ──────────────
        from AyadFlowSync.core.app_config import AppConfig
        try:
            if AppConfig.PC_NAME_FILE.exists():
                AppConfig.PC_NAME = AppConfig.PC_NAME_FILE.read_text(encoding='utf-8').strip()

            if not AppConfig.PC_NAME:
                # أول تشغيل — اطلب اسم الجهاز
                splash.hide()
                from PyQt6.QtWidgets import QInputDialog
                import socket
                default_name = socket.gethostname()
                name, ok = QInputDialog.getText(
                    None,
                    "⚡ AyadFlowSync — إعداد أولي",
                    "مرحباً! هذا أول تشغيل.\n\n"
                    "أدخل اسماً لهذا الجهاز:\n"
                    "(يُستخدم لتتبع المزامنة بين أجهزة متعددة)\n",
                    text=default_name,
                )
                if ok and name.strip():
                    AppConfig.PC_NAME = name.strip()
                else:
                    AppConfig.PC_NAME = default_name

                # حفظ الاسم بشكل دائم
                AppConfig.PC_NAME_FILE.parent.mkdir(parents=True, exist_ok=True)
                AppConfig.PC_NAME_FILE.write_text(AppConfig.PC_NAME, encoding='utf-8')
                logging.getLogger('AyadFlowSync').info(f"First run: device name = {AppConfig.PC_NAME}")
                splash.show()
                app.processEvents()

            AppConfig.update_cache_path()

        except Exception:
            pass

        # ── تحميل اللغة المحفوظة ─────────────────────────────────
        try:
            lang_file = AppConfig.DATA_DIR / "ui_lang.txt"
            if lang_file.exists():
                from AyadFlowSync.lang.lang import Lang
                saved_lang = lang_file.read_text(encoding="utf-8").strip()
                if saved_lang in ("ar", "en"):
                    Lang.set(saved_lang)
        except Exception:
            pass

        splash.set_status("جاهز!", 100)

        # ── النافذة الرئيسية ─────────────────────────────────────
        from AyadFlowSync.ui.qt.main_window import MainWindow
        window = MainWindow()
        splash.finish(window)
        window.show()

    except Exception as e:
        import logging
        logging.critical(f"فشل تحميل الواجهة: {e}\n{traceback.format_exc()}")
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "خطأ فادح", f"فشل تحميل الواجهة:\n{e}")
        except Exception:
            print(f"خطأ فادح: {e}")
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
