# AyadFlowSync-v4

![Python](https://img.shields.io/badge/Python-3.9%2B-3776ab?style=flat-square&logo=python) ![License](https://img.shields.io/badge/License-MIT-green?style=flat-square) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-blue?style=flat-square)

*مزامنة ملفات USB ↔ الحاسوب مع تكامل GitHub، وضبط الأداء حسب الأجهزة، وتخزين آمن مشفّر — كل ذلك في واجهة PyQt6.*

---

## 📖 السبب وراء هذا المشروع

مزامنة الملفات بين محركات USB والحواسيب بطيئة وغير موثوقة. معظم الأدوات تتجاهل قدرات الأجهزة الفعلية — تستخدم نفس عدد الخيوط وأحجام المخزن المؤقت على حاسوب بسيط كما على محطة عمل احترافية. بنيت AyadFlowSync لتحليل CPU و RAM وسرعة USB على أول تشغيل، ثم تضبط عدد الخيوط (2→16)، أحجام الدفعات (50→2000)، وخوارزميات الـ Hash تلقائياً. النتيجة: مسح 200,000 ملف في أقل من 3 ثوانٍ باستخدام xxhash XXH3_128 بدلاً من MD5.

بعيداً عن المزامنة، يمكنك فحص المشاريع المحلية، رفع مستودعات كاملة إلى GitHub جماعياً، استنساخ مستودعات بعيدة، وتوليد ملفات README احترافية. كل البيانات السرية تُخزّن مشفّرة بـ AES-256-GCM — لا توكنات نصية واضحة على محرك USB.

**AyadFlowSync** يحقق ذلك بدمج تحليل أجهزة 4-طبقات، كشف التغييرات المدعوم بـ xxhash، مراقبة الأجهزة الحية، وواجهة PyQt6 تعرض التقدم الفوري مع 110 وحدة Python موزعة على 297 ملف.

---

## ✨ المميزات الأساسية

- **محلل أجهزة 4-طبقات** — يقيس أنوية CPU و RAM وعرض نطاق USB مرة واحدة عند البدء؛ يختار تلقائياً عدد الخيوط (2/4/8/16) وحجم الطابور (50/500/2000) بناءً على فئة الجهاز (ميزانية/معياري/أداء/خادم)

- **كشف الملفات بـ xxhash XXH3_128** — يحدد الملفات المتغيرة بسرعة 30× أسرع من MD5؛ يتخطى الملفات دون تغيير عبر ذاكرة mtime مع SQLite WAL وتسريع mmap

- **مراقب الأجهزة الحي** — خيط daemon يفحص حالة CPU/RAM/USB كل 500 ميلي ثانية؛ يحدّث callbacks مسجّلة في الوقت الفعلي دون حجب الواجهة

- **تجديد الأقفال التلقائي** — أقفال قاعدة البيانات تتضمن تجديداً تلقائياً لمنع انتهاء الصلاحية؛ يحل مشكلة v3 حيث فقدت المزامنة قفل في المجلدات الكبيرة (>60 ثانية)

- **رفع GitHub جماعي** — يمسح مجلداً أب ويتعامل مع كل مجلد فرعي كمستودع Git مستقل، يرفع الكل في عملية واحدة مع تخطي المجلدات بـ `.git/config` موجود

- **فاحص المشاريع** — تحليل بمسح واحد أسرع 3× من الماسحات المنفصلة؛ يكتشف نوع المشروع والتبعيات واللغة وعدد الملفات في مسح واحد

- **تخزين مشفّر بـ AES-256-GCM** — كل البيانات السرية (توكنات GitHub، مفاتيح API) تستخدم تشفير مُصادّق؛ حماية اختيارية برمز PIN قائمة على PBKDF2+HMAC لمحركات USB

- **توليد README ذكي** — ينشئ توثيق مشروع احترافي مع بديل AI أو بناء على قالب

- **Git مع دعم الإلغاء** — GitRunner ينفذ أوامر Git مع انتظار قابل للتكوين، وقتل تلقائي عند الإلغاء، وتسجيل منظم

- **رفع متوافق FAT32** — يتعامل مع قيود FAT32 بنقل مجلد `.git` مؤقتاً أثناء عمليات الدفع على محركات USB

---

## 🖥️ لقطات الشاشة / العرض التوضيحي

> لوحات الواجهة قريباً. سير العمل الحالي: تشغيل التطبيق → يعمل محلل الأجهزة تلقائياً → اختر مجلدات المصدر والوجهة → انقر "مزامنة" → راقب شريط التقدم الحي مع مقاييس CPU/RAM/USB → فحص المشاريع المرفوعة في تبويب GitHub.

---

## 🛠 مكدس التكنولوجيا

| التكنولوجيا | الغرض | السبب |
|---|---|---|
| **PyQt6** | إطار عمل الواجهة الرسومية | عناصر واجهة محلية، signals/slots آمنة للخيوط لتحديثات الأجهزة الحية |
| **xxhash** | تجزئة الملفات | XXH3_128 أسرع 30× من MD5 في كشف التغييرات |
| **psutil** | مراقبة الأجهزة | قياسات CPU/RAM/USB عبر الأنظمة دون استدعاءات النظام |
| **cryptography** | تخزين البيانات السرية | AES-256-GCM توفر تشفيراً مصادقاً لتوكنات GitHub |
| **GitPython** | أتمتة Git | غلاف Python حول أوامر Git مع دعم الانتظار والإيقاف |
| **requests** | GitHub REST API | عميل HTTP خفيف لعمليات المستودع (القائمة/الإنشاء/الحذف) |
| **SQLite** | ذاكرة التجزئة + الأقفال | وضع WAL يفعّل القراءات المتزامنة أثناء المزامنة النشطة |

---

## 📁 هيكل المشروع

```
AyadFlowSync-v4/
├── AyadFlowSync/                    # الحزمة الرئيسية (110 ملف .py)
│   ├── main.py                      # نقطة الدخول: إعداد multiprocess، تطبيق PyQt6
│   ├── core/                        # طبقة الأجهزة والإعدادات
│   │   ├── app_config.py            # AppConfig: إعدادات مركزية، تهيئة الدليل، معايرة USB
│   │   ├── constants.py             # AppInfo، Theme (Professional Slate Dark)، التنسيق
│   │   ├── device_profiler.py       # DeviceProfiler: تسجيل 4-طبقات CPU/RAM/USB + ذاكرة
│   │   ├── hardware.py              # HardwareMonitor: خيط daemon، فحص CPU/RAM/USB الحي
│   │   └── hash_worker.py           # معالج خط أنابيب التجزئة
│   ├── db/                          # استمرارية البيانات
│   │   └── database.py              # DatabaseManager + LockManager (مع التجديد التلقائي)
│   ├── github/                      # عمليات GitHub
│   │   ├── client.py                # GitRunner (تنفيذ + انتظار)، GitHubAPI (REST v3)
│   │   ├── manager.py               # RepoMgr: قائمة/إنشاء/حذف مستودعات
│   │   ├── ops.py                   # Uploader، Cloner، Batch، LFS، ProjectInspector، Auth
│   │   ├── analyzer.py              # ProjectAnalyzer: فحص كود عميق
│   │   ├── readme.py                # SmartReadmeGenerator
│   │   └── upload_log.py            # UploadLog: سجل مشاريع قابل للعمل بلا اتصال
│   ├── security/                    # التشفير والبيانات السرية
│   │   ├── secure_store.py          # SecureStore: تشفير مفتاح-قيمة AES-256-GCM
│   │   ├── hash.py                  # HashCache: xxhash + SQLite WAL + mmap
│   │   └── security.py              # MultiKeyStore، AppSettings، History، AnalysisCache
│   ├── lang/                        # التدويل
│   │   ├── lang.py                  # Lang: محمل الترجمات
│   │   └── proxy.py                 # LangProxy: التحميل الكسول للتبعيات الدائرية
│   ├── ui/                          # واجهة PyQt6 الرسومية
│   ├── sync/                        # محرك المزامنة (غير مفصّل في اللقطة)
│   ├── logs/                        # دليل السجلات في وقت التشغيل
│   ├── data/                        # الإعدادات والذاكرة والبيانات
│   │   ├── hash_cache.db            # SQLite WAL: تجزئة الملفات + mtime_ns
│   │   ├── .ai_keys_enc             # مفاتيح API مشفّرة (MultiKeyStore)
│   │   ├── excluded_dirs.json       # مجلدات للتخطي أثناء المزامنة
│   │   ├── accumark_mode.txt        # إعداد وضع التراكم
│   │   └── .flash_secret            # رمز PIN/سر للوسائط القابلة للإزالة
│   ├── presync_snapshots/           # لقطات حالة ما قبل المزامنة
│   ├── sync_reports/                # سجلات عمليات المزامنة
│   ├── trash/                       # تجميع الملفات المحذوفة
│   └── __init__.py
├── tests/                           # مجموعة الاختبارات (pytest)
│   └── conftest.py                  # Fixtures: tmp_dir، src_dir، dst_dir، sample_project، sync_engine، db
├── assets/                          # موارد الواجهة (96 ملف .qm ترجمة)
├── dist/                            # مخرجات البناء (EXE مجمد + DLLs)
├── BUILD_GUIDE.md                   # تعليمات بناء PyInstaller
├── README.md                        # هذا الملف (English)
├── pyproject.toml                   # إعداد Poetry/setuptools، التبعيات، البرامج
├── conftest.py                      # إعداد pytest المركزي
├── icon.ico                         # أيقونة التطبيق
├── AyadFlowSync.spec                # ملف PyInstaller spec
└── build.bat                        # نص بناء Windows
```

---

## ⚙️ المتطلبات الأساسية

- **Python 3.9 أو أعلى** (مختبر على 3.9+؛ الإصدارات الأقدم قد لا تعمل)
- **pip** (يأتي مع Python 3.9+)
- **دعم البيئة الافتراضية** (venv)
- **Git** (لعمليات GitHub، يُكتشف تلقائياً في وقت التشغيل)

### ملاحظات خاصة بنظام Linux:
إذا كنت تستخدم Tkinter أو عناصر واجهة مخصصة، فبعض توزيعات Linux تتطلب:
```bash
sudo apt install python3-tk
```

⚠️ **تحذير:** تم الاختبار على Python 3.9+. الإصدارات الأقدم قد لا تعمل.

---

## 🚀 التثبيت

### 1. استنساخ المستودع
```bash
git clone https://github.com/Ayad-Mounir/AyadFlowSync-v4.git
cd AyadFlowSync-v4
```

### 2. إنشاء بيئة افتراضية
```bash
python -m venv venv
```

### 3. تفعيل البيئة الافتراضية

**على Windows:**
```bash
venv\Scripts\activate
```

**على macOS/Linux:**
```bash
source venv/bin/activate
```

### 4. تثبيت التبعيات
```bash
pip install .
```

أو للتطوير مع أدوات الاختبار:
```bash
pip install ".[dev]"
```

### 5. تشغيل التطبيق
```bash
python -m AyadFlowSync.main
```

أو استخدم الأمر المثبت:
```bash
ayad-flowsync
```

---

## ▶️ دليل الاستخدام

### البداية السريعة

1. **شغّل التطبيق:**
   ```bash
   python -m AyadFlowSync.main
   ```
   محلل الأجهزة يعمل تلقائياً على أول تشغيل. يقيس أجهزتك ويخزن النتيجة في `data/hash_cache.db`.

2. **اختر مجلدات المصدر والوجهة** في الواجهة وانقر **مزامنة**.

3. **راقب التقدم** — يحدّث مراقب الأجهزة مقاييس CPU/RAM/USB كل 500 ميلي ثانية أثناء نقل الملفات.

---

### مزامنة الملفات بين USB والحاسوب

**ما يحدث:**
- xxhash يمسح الملفات في 3 ثوانٍ (مقابل 90 ثانية مع MD5)
- يُكتشف التغيير عبر mtime_ns + تجزئة مخزنة
- خيوط العامل تتسع تلقائياً: خيطان على الأجهزة البسيطة، حتى 16 على معالجات عالية

---

### رفع المشاريع المحلية إلى GitHub

**محمل الدفعات** يمسح مجلداً أب ويرفع كل مجلد فرعي كمستودع Git مستقل.

**مثال على هيكل المجلد:**
```
~/MyProjects/
  ├── web-app/          → ينشئ مستودع "web-app"
  ├── cli-tool/         → ينشئ مستودع "cli-tool"
  └── data-viz/         → ينشئ مستودع "data-viz"
```

**الخطوات:**
1. اذهب إلى تبويب **GitHub** → **رفع جماعي**
2. اختر المجلد الأب (مثل `~/MyProjects`)
3. الصق توكن GitHub (يُخزن مشفراً في `data/.ai_keys_enc`)
4. انقر **رفع الكل** → يتخطى المجلدات بـ `.git/config` موجود

**ما يفعله المحمل (لكل مشروع):**
1. ينشئ مستودع GitHub
2. يهيئ Git محلياً (إن لم يكن موجوداً)
3. يضيف GitHub remote
4. يدفع جميع الـ commits
5. يتعامل مع FAT32 بنقل `.git` مؤقتاً

**سجل الإخراج** (`.ayadsync_push_log.json`):
```json
{
  "web-app": {
    "status": "success",
    "repo": "https://github.com/user/web-app",
    "files_pushed": 156,
    "size_mb": 42.3
  }
}
```

💡 **نصيحة:** استخدم **فاحص المشاريع** أولاً للكشف عن نوع المشروع والتبعيات واللغة — ينشئ بيانات وصفية لتوليد README.

---

### تحليل مشروع

**فاحص المشاريع** يمسح مجلداً بمسح واحد ويكتشف:
- نوع المشروع (Python، JavaScript، Java، إلخ)
- التبعيات (من `requirements.txt`، `package.json`، إلخ)
- لغة البرمجة
- عدد الملفات حسب الامتداد

**أسرع 3× من الماسح المنفصل** لأنه يقطع شجرة الدليل مرة واحدة.

**الخطوات:**
1. اذهب إلى تبويب **GitHub** → **فحص المشروع**
2. اختر مجلد المشروع
3. انتظر 2-5 ثوانٍ → شاهد النتائج (النوع والتبعيات واللغة وعدد الملفات)

---

### توليد README احترافي

**منشئ README الذكي** ينشئ README بـ:
- وصف المشروع (AI-مولد أو على أساس قالب)
- تعليمات التثبيت
- أمثلة الاستخدام
- إرشادات المساهمة

**الخطوات:**
1. فحص المشروع (أعلاه)
2. انقر **توليد README**
3. اختر: **مدعوم AI** (يستخدم مفاتيح API مخزنة) أو **قائم على قالب**
4. راجع واحفظ في `README.md`

⚠️ **تحذير:** وضع AI يتطلب مفتاح API معد مسبقاً (OpenAI، Claude، أو Anthropic). خزنه عبر **الإعدادات** → **مفاتيح API**.

---

### إدارة توكنات GitHub بأمان

التوكنات مشفّرة بـ **AES-256-GCM** وتُخزن في `data/.ai_keys_enc`. حماية اختيارية برمز PIN تستخدم PBKDF2+HMAC.

**الخطوات:**
1. اذهب إلى **الإعدادات** → **توكن GitHub**
2. الصق توكنك
3. (اختياري) فعّل حماية PIN → اختر رمز PIN 4-6 أرقام
4. انقر **حفظ** → التوكن مشفر تلقائياً

**على محرك USB برمز PIN:**
```
data/
├── .ai_keys_enc          # توكن مشفر (يتطلب PIN للفك)
└── .flash_secret         # hash رمز PIN
```

💡 **نصيحة:** بدون رمز PIN، يُخزن التوكن بشكل معادل للنص الواضح في ذاكرة التطبيق لكن مشفر على القرص. يضيف رمز PIN التحقق HMAC.

---

### فحص سجل المزامنة

وحدة **السجل** تسجل كل عملية مزامنة مع الطوابع الزمنية وعدد الملفات والأخطاء.

**الملف:** `data/history.json` (كتابات معلقة كل ثانيتين)

**مثال على إدخال:**
```json
{
  "timestamp": "2024-01-15T14:32:45",
  "operation": "sync",
  "source": "/media/usb",
  "destination": "/home/user/backup",
  "files_changed": 12340,
  "size_mb": 28.1,
  "duration_seconds": 24,
  "status": "success"
}
```

---

### مراقبة الأجهزة في الوقت الفعلي

**مراقب الأجهزة** يعمل كخيط daemon ويحدث كل 500 ميلي ثانية. مرئي في شريط حالة الواجهة.

**المقاييس:**
- استخدام CPU (%)
- استخدام RAM (%)
- سرعة USB (MB/s، مقاسة أثناء المزامنة)

**يُدرج عبر:**
```python
from AyadFlowSync.core.hardware import HardwareMonitor

monitor = HardwareMonitor()
monitor.register_callback(lambda cpu, ram, usb: print(f"CPU: {cpu}%"))
monitor.start()
```

---

## 🏗 العمارة

**AyadFlowSync** يستخدم هندسة متعددة الطبقات:

```
┌─────────────────────────────────────┐
│  طبقة الواجهة (PyQt6)              │
│  ├─ MainWindow                      │
│  ├─ SyncTab, GitHubTab, SettingsTab │
│  └─ مقاييس الأجهزة الحية           │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  طبقة العمليات                     │
│  ├─ Uploader (رفع جماعي إلى GitHub)│
│  ├─ ProjectInspector (تحليل)       │
│  ├─ SyncEngine (مزامنة الملفات)    │
│  └─ SmartReadmeGenerator            │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  الطبقة الأساسية                   │
│  ├─ DeviceProfiler (تسجيل 4-طبقات) │
│  ├─ HardwareMonitor (فحص daemon)   │
│  ├─ AppConfig (إعدادات)            │
│  └─ DatabaseManager (أقفال + ذاكرة) │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  طبقة الأمان                       │
│  ├─ SecureStore (AES-256-GCM)       │
│  ├─ HashCache (xxhash + SQLite WAL) │
│  └─ Auth (تشفير التوكن)            │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  الخدمات الخارجية                  │
│  ├─ GitHub REST API (عبر requests)  │
│  ├─ Git CLI (عبر GitPython)        │
│  └─ نظام الملفات المحلي (psutil)   │
└─────────────────────────────────────┘
```

**التفاعلات الأساسية:**
- DeviceProfiler → HardwareMonitor: فئة الأجهزة تحدد عدد الخيوط
- SyncEngine → HashCache: قراءة/كتابة تجزئة الملفات المخزنة
- Uploader → Auth + SecureStore: استرجاع توكن GitHub المشفر
- واجهة → DatabaseManager: اكتساب قفل قبل المزامنة
- ProjectInspector → ProjectAnalyzer: فحص الكود العميق

---

## 🧪 الاختبارات

الاختبارات موجودة في `tests/` وتستخدم **pytest** مع fixtures للاختبار المعزول.

**تشغيل جميع الاختبارات:**
```bash
pytest tests/ -v
```

**التشغيل مع التغطية:**
```bash
pytest tests/ --cov=AyadFlowSync --cov-report=html
```

**Fixtures متاحة** (في `conftest.py`):
- `tmp_dir()` — دليل مؤقت، تنظيف تلقائي بعد كل اختبار
- `src_dir()` — مجلد المصدر للاختبار
- `dst_dir()` — مجلد الوجهة للاختبار
- `sample_project()` — مشروع Python بملفات، لاختبارات المحلل
- `sync_engine()` — SyncEngine معد مسبقاً
- `db()` — DatabaseManager مؤقت

**مثال اختبار:**
```python
def test_sync_basic(src_dir, dst_dir, sync_engine):
    # إنشاء 10 ملفات اختبار في src_dir
    (src_dir / "file1.txt").write_text("hello")
    
    # المزامنة
    sync_engine.sync(src_dir, dst_dir)
    
    # التحقق
    assert (dst_dir / "file1.txt").read_text() == "hello"
```

---

## 🤝 المساهمة

1. **اعمل نسخة (Fork) من المستودع** على GitHub
2. **استنسخ نسختك** محلياً:
   ```bash
   git clone https://github.com/YOUR-USERNAME/AyadFlowSync-v4.git
   cd AyadFlowSync-v4
   ```
3. **أنشئ فرع ميزة:**
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **أجر تغييراتك** وشغّل الاختبارات:
   ```bash
   pytest tests/ -v
   ```
5. **التزم برسائل واضحة:**
   ```bash
   git commit -m "feat: إضافة دعم xxhash XXH4 للمسح أسرع"
   ```
6. **ادفع إلى نسختك:**
   ```bash
   git push origin feature/your-feature-name
   ```
7. **افتح طلب دمج (Pull Request)** على المستودع الرئيسي بوصف التغييرات

**أسلوب الكود:** يستخدم **ruff** (طول السطر 100، Python 3.9+) و **mypy** للتحقق من النوع. شغّل قبل الإرسال:
```bash
ruff check AyadFlowSync/
mypy AyadFlowSync/ --ignore-missing-imports
```

---

## 📄 الترخيص

هذا المشروع مرخص تحت **MIT License** — انظر ملف LICENSE للتفاصيل.

---

## 👨‍💻 المطور

| | |
|---|---|
| **البريد الإلكتروني** | [![Email](https://img.shields.io/badge/Email-contact.ayad.mounir%40gmail.com-blue?style=flat-square&logo=gmail)](mailto:contact.ayad.mounir@gmail.com) |
| **واتساب** | [![WhatsApp](https://img.shields.io/badge/WhatsApp-%2B212653867667-25D366?style=flat-square&logo=whatsapp)](https://wa.me/212653867667) |
| **تلغرام** | [![Telegram](https://img.shields.io/badge/Telegram-Mounir_AyadD-0088cc?style=flat-square&logo=telegram)](https://t.me/Mounir_AyadD) |
| **GitHub** | [![GitHub](https://img.shields.io/badge/GitHub-Ayad--Mounir-black?style=flat-square&logo=github)](https://github.com/Ayad-Mounir) |

<p align="center">صُنع بـ ❤️ بواسطة Mounir Ayad</p>