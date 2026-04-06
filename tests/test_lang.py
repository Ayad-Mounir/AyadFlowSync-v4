
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from AyadFlowSync.lang.lang import Lang, L

class TestLang:
    def setup_method(self): Lang.set("ar")

    def test_basic_translation(self):
        assert Lang.t("backup") == "💾 Backup → فلاشة"

    def test_english_translation(self):
        Lang.set("en")
        assert Lang.t("backup") == "💾 Backup → USB"

    def test_format_args(self):
        Lang.set("ar")
        result = Lang.t("ago_hours", n=3)
        assert "3" in result

    def test_missing_key_returns_key(self):
        assert Lang.t("nonexistent_key_xyz") == "nonexistent_key_xyz"

    def test_set_invalid_lang(self):
        Lang.set("fr")
        assert Lang.get() == "ar"  # unchanged

    def test_font_scale(self):
        Lang.set_font_scale(2.0)
        assert Lang.scaled(14) == 28
        Lang.set_font_scale(1.0)

    def test_add_custom_key(self):
        Lang.add("test_custom", ar="مخصص", en="custom")
        assert Lang.t("test_custom") == "مخصص"
        Lang.set("en")
        assert Lang.t("test_custom") == "custom"
        Lang.set("ar")

    def test_L_shorthand(self):
        assert L.t("done") == Lang.t("done")

    def test_all_keys_have_ar(self):
        from AyadFlowSync.lang.lang import _STRINGS
        for key, val in _STRINGS.items():
            assert "ar" in val, f"Missing Arabic for key: {key}"
