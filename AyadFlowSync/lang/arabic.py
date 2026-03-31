#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_arabic — معالج النص العربي لـ Tkinter/CustomTkinter
يحل مشكلة عرض النص العربي المقلوب بدون أي مكتبات خارجية
"""
import unicodedata, re

_EMOJI_RANGES = [
    (0x1F300, 0x1FFFF), (0x2600, 0x27BF),
    (0x00A9, 0x00A9), (0x00AE, 0x00AE), (0x2122, 0x2122),
]

def _is_emoji(ch):
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)

def _is_arabic_char(ch):
    try:
        return unicodedata.bidirectional(ch) in ('R', 'AL', 'NSM')
    except Exception:
        return False

def _is_ltr_char(ch):
    if _is_emoji(ch): return False
    if _is_arabic_char(ch): return False
    try:
        return unicodedata.bidirectional(ch) in ('L', 'EN', 'ES', 'ET', 'AN')
    except Exception:
        return True


def fix_arabic(text: str) -> str:
    """
    تُصلح النص العربي للعرض الصحيح في Tkinter (بيئة LTR)

    الخوارزمية:
    1. قسّم النص إلى tokens (كلمات + مسافات + رموز)
    2. احدد نوع كل token (ar / ltr / neutral)
    3. عكس ترتيب الـ tokens للعرض RTL في LTR widget

    الفرق بين "قبل" و"بعد":
    - "قبل"  = كيف يُخزَّن في الذاكرة (منطقي)
    - "بعد"  = كيف يجب أن يُعرض في Tkinter (بصري RTL)
    """
    if not text: return text
    if '\n' in text:
        return '\n'.join(fix_arabic(line) for line in text.split('\n'))
    if not any(_is_arabic_char(c) for c in text): return text

    # تقسيم إلى tokens مع الحفاظ على المسافات
    tokens = re.split(r'(\s+)', text)

    result_tokens = []
    for token in tokens:
        if not token: continue
        if token.isspace():
            result_tokens.append((' ', token))
        elif any(_is_arabic_char(c) for c in token):
            result_tokens.append(('ar', token))
        else:
            result_tokens.append(('ltr', token))

    # عكس ترتيب كل شيء
    result_tokens.reverse()

    return ''.join(t for _, t in result_tokens).strip()


fix_multiline = fix_arabic


if __name__ == '__main__':
    print("═"*62)
    print("  اختبار fix_arabic — عرض مرئي صحيح في Tkinter LTR")
    print("═"*62)
    tests = [
        "مرحباً بك في النظام",
        "Ayad FlowSync — نظام مزامنة ذكي",
        "✅ اكتملت المزامنة — 42 ملف",
        "عياد منير",
        "📱 واتساب: +212653867667",
        "© 2026 عياد منير — جميع الحقوق محفوظة",
        "📧 للتواصل والدعم الفني:",
        "contact.ayad.mounir@gmail.com",
        "مطوّر برمجيات — متخصص في أدوات الإنتاجية",
        "GitHub Sync Pro",
    ]
    for t in tests:
        r = fix_arabic(t)
        print(f"  ◀ {t}")
        print(f"  ▶ {r}")
        print()
