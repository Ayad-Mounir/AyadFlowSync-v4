# 🔨 كيفية بناء AyadFlowSync كملف تنفيذي

## الطريقة السريعة (Windows)

```
1. ثبّت Python 3.9+ من python.org
2. افتح CMD في مجلد المشروع
3. شغّل: build.bat
4. انتظر 2-5 دقائق
5. الملف التنفيذي في: dist\AyadFlowSync\AyadFlowSync.exe
```

## إضافة الأيقونة

```
1. ضع ملف icon.ico في مجلد assets\
2. أعد تشغيل build.bat
```

## للعمل من الفلاشة (Portable)

```
1. ابنِ المشروع بـ build.bat
2. انسخ مجلد dist\AyadFlowSync\ بالكامل إلى الفلاشة
3. شغّل AyadFlowSync.exe من الفلاشة مباشرة
```

ملف `.portable` يُخبر البرنامج أنه يعمل بوضع محمول:
- البيانات تُحفظ في `data\` بجانب الـ EXE (ليس في المستخدم)
- يعمل على أي جهاز بدون تثبيت
- الإعدادات والـ Tokens تنتقل مع الفلاشة

## البنية النهائية على الفلاشة

```
USB:\
├── AyadFlowSync.exe          ← البرنامج
├── .portable                 ← علامة الوضع المحمول
├── data\                     ← الإعدادات (يُنشأ تلقائياً)
│   ├── logs\
│   ├── .gh_token_v3          ← Token مشفر
│   ├── hash_cache.db         ← cache الـ Hash
│   └── sync_index.db         ← حالة المزامنة
├── FlowSync_Backup\          ← مجلد النسخ الاحتياطي
│   ├── Project_A\
│   └── Project_B\
├── _internal\                ← مكتبات PyQt6 (لا تحذفها)
└── README.md
```

## البناء يدوياً (بدون build.bat)

```bash
pip install pyinstaller PyQt6 xxhash psutil requests cryptography GitPython packaging
pyinstaller AyadFlowSync.spec --noconfirm
```

## استكشاف الأخطاء

| المشكلة | الحل |
|---------|------|
| `ModuleNotFoundError` | شغّل `pip install <module>` ثم أعد البناء |
| EXE لا يفتح | شغّل من CMD لرؤية الأخطاء: `AyadFlowSync.exe` |
| حجم كبير جداً | طبيعي — PyQt6 وحدها ~50MB |
| الأيقونة لا تظهر | تأكد أن `assets\icon.ico` موجود ثم أعد البناء |
