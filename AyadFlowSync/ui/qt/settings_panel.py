#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.qt.settings_panel
====================
لوحة الإعدادات — اسم الجهاز / مجلدات مستثناة / Cache / اللغة
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QCheckBox, QFrame, QScrollArea,
    QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ...core.app_config import AppConfig
from ...core.constants import AI_PROVIDERS
from ...core.device_profiler import DeviceProfiler
from ...lang.lang import Lang


class SettingsPanel(QWidget):
    language_changed = pyqtSignal()   # يُبثّ عند تغيير اللغة → MainWindow يبلّغ كل الـ panels

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        root    = QVBoxLayout(content)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # ── اللغة ──────────────────────────────────────────────────
        grp_lang = QGroupBox(Lang.t("set_lang_group"))
        ly_lang  = QHBoxLayout(grp_lang)
        ly_lang.setSpacing(12)


        self._btn_lang_ar = QPushButton(Lang.t("set_lang_ar"))
        self._btn_lang_ar.setCheckable(True)
        self._btn_lang_ar.setChecked(Lang.get() == "ar")
        self._btn_lang_ar.setObjectName("PrimaryBtn" if Lang.get() == "ar" else "")
        self._btn_lang_ar.clicked.connect(lambda: self._set_lang("ar"))

        self._btn_lang_en = QPushButton(Lang.t("set_lang_en"))
        self._btn_lang_en.setCheckable(True)
        self._btn_lang_en.setChecked(Lang.get() == "en")
        self._btn_lang_en.setObjectName("PrimaryBtn" if Lang.get() == "en" else "")
        self._btn_lang_en.clicked.connect(lambda: self._set_lang("en"))

        ly_lang.addWidget(self._btn_lang_ar)
        ly_lang.addWidget(self._btn_lang_en)
        ly_lang.addStretch()

        note = QLabel(Lang.t("set_lang_note"))   # "⚠️ يُطبَّق فوراً"
        note.setObjectName("Dim")
        ly_lang.addWidget(note)

        root.addWidget(grp_lang)

        # ── اسم الجهاز ────────────────────────────────────────────
        grp_pc = QGroupBox(Lang.t("set_pc_group"))
        ly_pc  = QHBoxLayout(grp_pc)
        self._pc_input = QLineEdit(AppConfig.PC_NAME or "")
        self._pc_input.setPlaceholderText(Lang.t("set_pc_placeholder"))
        btn_save_pc = QPushButton(Lang.t("set_pc_save"))
        btn_save_pc.setObjectName("PrimaryBtn")
        btn_save_pc.clicked.connect(self._save_pc_name)
        ly_pc.addWidget(self._pc_input, 1)
        ly_pc.addWidget(btn_save_pc)
        root.addWidget(grp_pc)

        # ── مجلدات مستثناة ────────────────────────────────────────
        grp_excl = QGroupBox(Lang.t("set_excl_group"))
        ly_excl  = QVBoxLayout(grp_excl)
        ly_excl.addWidget(QLabel(Lang.t("set_excl_desc")))

        self._excl_checks: dict = {}
        for name, default in AppConfig.EXCLUDED_DIRS_DEFAULTS.items():
            cb = QCheckBox(name)
            cb.setChecked(name in AppConfig.EXCLUDED_DIRS)
            self._excl_checks[name] = cb
            ly_excl.addWidget(cb)

        btn_save_excl = QPushButton(Lang.t("set_excl_save"))
        btn_save_excl.setObjectName("PrimaryBtn")
        btn_save_excl.clicked.connect(self._save_excluded)
        ly_excl.addWidget(btn_save_excl)
        root.addWidget(grp_excl)

        # ── الأداء ────────────────────────────────────────────────
        grp_perf = QGroupBox(Lang.t("set_perf_group"))
        ly_perf  = QVBoxLayout(grp_perf)
        self._specs_lbl = QLabel(DeviceProfiler.get_specs_text())
        self._specs_lbl.setObjectName("Dim")
        self._specs_lbl.setWordWrap(True)
        ly_perf.addWidget(self._specs_lbl)

        usb_spd = QLabel(DeviceProfiler.get_usb_specs_text())
        usb_spd.setObjectName("Dim")
        ly_perf.addWidget(usb_spd)
        root.addWidget(grp_perf)

        # ── AccuMark ──────────────────────────────────────────────
        grp_acc = QGroupBox(Lang.t("set_accumark_group"))
        ly_acc  = QVBoxLayout(grp_acc)
        info = QLabel(
            Lang.t("set_accumark_info")
        )
        info.setObjectName("Dim")
        info.setWordWrap(True)
        ly_acc.addWidget(info)
        self._accumark_cb = QCheckBox(Lang.t("set_accumark_cb"))
        self._accumark_cb.setChecked(AppConfig.ACCUMARK_MODE)
        self._accumark_cb.toggled.connect(AppConfig.save_accumark)
        ly_acc.addWidget(self._accumark_cb)
        root.addWidget(grp_acc)

        # ── مفاتيح الذكاء الاصطناعي ─────────────────────────────
        grp_ai = QGroupBox(Lang.t("set_ai_group"))
        ly_ai = QVBoxLayout(grp_ai)
        ly_ai.addWidget(QLabel(Lang.t("set_ai_desc")))

        self._ai_inputs = {}
        for key, info in AI_PROVIDERS.items():
            row = QHBoxLayout()
            lbl = QLabel(f"{info['name']}:")
            lbl.setFixedWidth(120)
            inp = QLineEdit()
            inp.setPlaceholderText(f"مفتاح {info['name']}...")
            inp.setEchoMode(QLineEdit.EchoMode.Password)
            self._ai_inputs[key] = inp
            row.addWidget(lbl)
            row.addWidget(inp)
            # Signup link
            btn_s = QPushButton("📝")
            btn_s.setFixedWidth(32)
            btn_s.setToolTip(f"احصل على مفتاح: {info['signup']}")
            signup_url = info['signup']
            btn_s.clicked.connect(lambda _, u=signup_url: __import__('webbrowser').open(u))
            row.addWidget(btn_s)
            ly_ai.addLayout(row)

        btn_save_ai = QPushButton(Lang.t("set_ai_save"))
        btn_save_ai.setObjectName("PrimaryBtn")
        btn_save_ai.clicked.connect(self._save_ai_keys)
        ly_ai.addWidget(btn_save_ai)
        root.addWidget(grp_ai)

        # ── معلومات المطور (للـ README) ───────────────────────────
        grp_dev = QGroupBox(Lang.t("set_dev_group"))
        ly_dev = QVBoxLayout(grp_dev)

        self._dev_inputs = {}
        dev_fields = [
            ("name", "الاسم", "Your Name"),
            ("email", "البريد", "you@email.com"),
            ("github", "GitHub", "username"),
            ("whatsapp", "WhatsApp", "+xxx..."),
            ("website", "الموقع", "https://..."),
            ("twitter", "Twitter/X", "@username"),
            ("linkedin", "LinkedIn", "linkedin.com/in/..."),
            ("youtube", "YouTube", "channel URL"),
            ("telegram", "Telegram", "@username"),
        ]
        for key, label, placeholder in dev_fields:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(80)
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            self._dev_inputs[key] = inp
            row.addWidget(lbl)
            row.addWidget(inp)
            ly_dev.addLayout(row)

        btn_save_dev = QPushButton(Lang.t("set_dev_save"))
        btn_save_dev.setObjectName("PrimaryBtn")
        btn_save_dev.clicked.connect(self._save_dev_info)
        ly_dev.addWidget(btn_save_dev)
        root.addWidget(grp_dev)

        root.addStretch()
        scroll.setWidget(content)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

        # Load saved values
        self._load_ai_keys()
        self._load_dev_info()

    def _set_lang(self, lang: str):
        Lang.set(lang)
        # حفظ الاختيار
        try:
            f = AppConfig.DATA_DIR / "ui_lang.txt"
            f.write_text(lang, encoding="utf-8")
        except Exception:
            pass
        # تحديث مظهر الأزرار
        self._btn_lang_ar.setChecked(lang == "ar")
        self._btn_lang_en.setChecked(lang == "en")
        self._btn_lang_ar.setObjectName("PrimaryBtn" if lang == "ar" else "")
        self._btn_lang_en.setObjectName("PrimaryBtn" if lang == "en" else "")
        self._btn_lang_ar.style().unpolish(self._btn_lang_ar)
        self._btn_lang_ar.style().polish(self._btn_lang_ar)
        self._btn_lang_en.style().unpolish(self._btn_lang_en)
        self._btn_lang_en.style().polish(self._btn_lang_en)
        # ✅ بثّ التغيير لكل الـ panels فوراً
        self.language_changed.emit()

    def _save_pc_name(self):
        name = self._pc_input.text().strip()
        if not name:
            QMessageBox.warning(self, "تحذير", Lang.t("set_pc_warn"))
            return
        AppConfig.PC_NAME = name
        try:
            AppConfig.PC_NAME_FILE.write_text(name, encoding='utf-8')
            AppConfig.update_cache_path()
            QMessageBox.information(self, "✅ تم", f"تم حفظ اسم الجهاز: {name}")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", str(e))

    def _save_excluded(self):
        state = {name: cb.isChecked() for name, cb in self._excl_checks.items()}
        AppConfig.save_excluded_dirs(state)
        QMessageBox.information(self, "✅ تم", Lang.t("set_excl_ok"))

    # ── AI Keys ───────────────────────────────────────────────────
    def _save_ai_keys(self):
        import json
        keys = {k: v.text().strip() for k, v in self._ai_inputs.items() if v.text().strip()}
        f = AppConfig.DATA_DIR / "ai_keys.json"
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(keys, ensure_ascii=False, indent=2), encoding='utf-8')
            QMessageBox.information(self, "✅ تم", f"تم حفظ {len(keys)} مفتاح AI")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", str(e))

    def _load_ai_keys(self):
        import json
        f = AppConfig.DATA_DIR / "ai_keys.json"
        try:
            if f.exists():
                keys = json.loads(f.read_text(encoding='utf-8'))
                for k, v in keys.items():
                    if k in self._ai_inputs:
                        self._ai_inputs[k].setText(v)
        except Exception:
            pass

    @staticmethod
    def get_ai_keys() -> dict:
        """يُستدعى من GitHub panel لجلب مفاتيح AI."""
        import json
        f = AppConfig.DATA_DIR / "ai_keys.json"
        try:
            if f.exists():
                return json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            pass
        return {}

    # ── Developer Info ────────────────────────────────────────────
    def _save_dev_info(self):
        import json
        info = {k: v.text().strip() for k, v in self._dev_inputs.items() if v.text().strip()}
        f = AppConfig.DATA_DIR / "dev_info.json"
        try:
            f.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
            QMessageBox.information(self, "✅ تم", "تم حفظ معلومات المطور")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", str(e))

    def _load_dev_info(self):
        import json
        f = AppConfig.DATA_DIR / "dev_info.json"
        try:
            if f.exists():
                info = json.loads(f.read_text(encoding='utf-8'))
                for k, v in info.items():
                    if k in self._dev_inputs:
                        self._dev_inputs[k].setText(v)
        except Exception:
            pass

    @staticmethod
    def get_dev_info() -> dict:
        """يُستدعى من GitHub panel لجلب معلومات المطور."""
        import json
        f = AppConfig.DATA_DIR / "dev_info.json"
        try:
            if f.exists():
                return json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            pass
        return {}

    def retranslateUi(self):
        """يُحدّث نصوص أزرار اللغة نفسها (تبقى ثابتة عمداً — اسم اللغة لا يتغير)."""
        pass

