# AyadFlowSync-v4

![Python](https://img.shields.io/badge/Python-blue?logo=python&logoColor=white) ![Files](https://img.shields.io/badge/Files-296-informational) ![Size](https://img.shields.io/badge/Size-48.7%20MB-green)

> conftest.py — إعداد pytest المركزي

---

## ✨ المميزات

- **اختبارات تلقائية** — مجموعة اختبارات شاملة
- **AppConfig** — إعدادات التطبيق المركزية.
كل إعداد له قيمة افتراضية معقولة وطريقة تحميل/حفظ.
- مكوّن **AppInfo**
- **Theme** — ألوان الواجهة — Professional Slate Dark
- **DeviceProfile** — تصنيف الجهاز — 4 مستويات
- **DeviceProfiler** — ⚡ v4.0 — قياس دقيق بالنقاط + 4 مستويات.
استدعاء measure() مرة واحدة فقط — النتيجة محفوظة.
- **HardwareMonitor** — مراقب أجهزة حي — يعمل في thread خلفي داعم (daemon).
يُحدّث كل callback مسجَّل بمعلومات CPU / RAM / USB كل UPDATE_INTERVA
- مكوّن **DatabaseManager**
- **LockManager** — ✅ FIX v4.1 — Lock مع Renewal تلقائي

المشكلة القديمة:
    stale timeout = 60 ثانية فقط.
    مزامنة مجلد كبير (>60s) تفقد
- **GitRunner** — تنفيذ أوامر Git مع:
- دعم الإلغاء (kill)
- timeout قابل للتعديل
- logging تلقائي

## 🛠 التقنيات المستخدمة

| التقنية | الغرض |
|---|---|
| `psutil` | مراقبة النظام |
| `xxhash` | تجزئة فائقة السرعة |
| `requests` | عميل HTTP |
| `PyQt6` | إطار واجهة حديث |
| `AyadFlowSync` | مكتبة أساسية |

## 📁 هيكل المشروع

```
AyadFlowSync-v4/
  AyadFlowSync/
  assets/
  dist/
  tests/
  .ayadsync_push_log.json
  .ayadsync_readme_snap
  .gitignore
  AyadFlowSync.spec
  BUILD_GUIDE.md
  README.md
  build.bat
  conftest.py
  ... +3
    core/
    data/
    db/
    github/
    lang/
    security/
    sync/
    ui/
    __init__.py
    main.py
      __init__.py
      app_config.py
      constants.py
      device_profiler.py
      hardware.py
      hash_worker.py
      logging_setup.py
      migration.py
      .flash_secret
      accumark_mode.txt
      excluded_dirs.json
      hash_cache.db
      __init__.py
      database.py
      __init__.py
      ai.py
      analyzer.py
      client.py
      manager.py
      ops.py
      readme.py
      upload_log.py
      __init__.py
      arabic.py
      lang.py
      proxy.py
```

## ⚙️ المتطلبات الأساسية

- Python 3.8+
- Git مُثبّت في PATH

## 🚀 التثبيت

```bash
# استنساخ المستودع
git clone https://github.com/Ayad-Mounir/AyadFlowSync-v4.git
cd AyadFlowSync-v4

# تثبيت المتطلبات
pip install -r requirements.txt
```

## ▶️ طريقة الاستخدام

```bash
python AyadFlowSync\main.py
```

### المكونات الرئيسية

- **AppConfig**: إعدادات التطبيق المركزية.
كل إعداد له قيمة افتراضية معقولة وطريقة تحميل/حفظ.
- **Theme**: ألوان الواجهة — Professional Slate Dark
- **DeviceProfile**: تصنيف الجهاز — 4 مستويات
- **DeviceProfiler**: ⚡ v4.0 — قياس دقيق بالنقاط + 4 مستويات.
استدعاء measure() مرة واحدة فقط — النتيجة محفوظة.
- **HardwareMonitor**: مراقب أجهزة حي — يعمل في thread خلفي داعم (daemon).
يُحدّث كل callback مسجَّل بمعلومات CPU / RAM / USB كل UPDATE_INTERVA

## 🧪 الاختبارات

```bash
pytest tests/ -v
```

## 🤝 المساهمة

1. Fork المستودع
2. أنشئ فرع الميزة: `git checkout -b feat/ميزتي`
3. سجّل التغييرات: `git commit -m "feat: إضافة ميزة رائعة"`
4. ارفع الفرع: `git push origin feat/ميزتي`
5. افتح Pull Request

## 📄 الترخيص

رخصة MIT — راجع [LICENSE](LICENSE)

## 👨‍💻 المطور

**Mounir Ayad**

[![Gmail](https://img.shields.io/badge/Gmail-contact.ayad.mounir%40gmail.com-D14836?logo=gmail&logoColor=white)](mailto:contact.ayad.mounir@gmail.com) [![GitHub](https://img.shields.io/badge/GitHub-Ayad-Mounir-181717?logo=github&logoColor=white)](https://github.com/Ayad-Mounir) [![WhatsApp](https://img.shields.io/badge/WhatsApp-%2B212653867667-25D366?logo=whatsapp&logoColor=white)](https://wa.me/212653867667) [![Telegram](https://img.shields.io/badge/Telegram-%40https://t.me/Mounir_AyadD-2CA5E0?logo=telegram&logoColor=white)](https://t.me/https://t.me/Mounir_AyadD)

---
<p align="center">صُنع بـ ❤️ بواسطة <a href="mailto:contact.ayad.mounir@gmail.com"><b>Mounir Ayad</b></a></p>
