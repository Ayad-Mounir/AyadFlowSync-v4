#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_github_readme — SmartReadmeGenerator
توليد README ذكي بـ AI (Gemini/Claude/DeepSeek/OpenAI) + template محلي
"""
import re
import json
import requests
import datetime
import logging as _logging_mod
from pathlib import Path

_logger = _logging_mod.getLogger("AyadFlowSync")
logger  = _logger

from .analyzer import ProjectAnalyzer
from ..core.constants import AI_PROVIDERS
from ..security.hash  import HashCache
from ..db.database    import fmt_size
class SmartReadmeGenerator:
    """توليد README احترافي بالذكاء الاصطناعي أو بقالب ذكي"""

    # ── تعليمات خاصة بنوع المشروع — تُحقن في الـ prompt ──────────────────
    # كل نوع عنده: sections إضافية + تحذيرات + نصائح خاصة به
    TYPE_HINTS = {
        'Python': {
            'en': (
                "## PYTHON-SPECIFIC REQUIREMENTS:\n"
                "- Prerequisites: Python version (detect from pyproject.toml or code syntax), pip, venv\n"
                "- Installation: always include `python -m venv venv` + activate step before pip install\n"
                "- If requirements.txt exists: show `pip install -r requirements.txt`\n"
                "- If pyproject.toml exists: show `pip install .` or `pip install -e .`\n"
                "- Add ⚠️ Warning: 'Tested on Python 3.9+. Earlier versions may not work.'\n"
                "- If Tkinter/CTk detected: add OS note (Linux may need `sudo apt install python3-tk`)\n"
                "- If .env detected: add 💡 section on configuring environment variables\n"
            ),
            'ar': (
                "## متطلبات خاصة بمشاريع Python:\n"
                "- المتطلبات: إصدار Python، pip، venv\n"
                "- التثبيت: دائماً ابدأ بـ `python -m venv venv` ثم التفعيل ثم pip install\n"
                "- إذا كان requirements.txt موجوداً: اعرض `pip install -r requirements.txt`\n"
                "- أضف ⚠️ تحذير: 'اختُبر على Python 3.9+. إصدارات أقدم قد لا تعمل.'\n"
                "- إذا اكتُشف Tkinter/CTk: أضف ملاحظة Linux (`sudo apt install python3-tk`)\n"
                "- إذا كان .env موجوداً: أضف قسم 💡 لإعداد متغيرات البيئة\n"
            ),
        },
        'Django': {
            'en': (
                "## DJANGO-SPECIFIC REQUIREMENTS:\n"
                "- Include: `python manage.py migrate` before runserver\n"
                "- Include: `python manage.py createsuperuser` for admin access\n"
                "- Add .env section: SECRET_KEY, DEBUG, DATABASE_URL, ALLOWED_HOSTS\n"
                "- Add ⚠️ Warning: 'Never run with DEBUG=True in production'\n"
                "- If static files exist: add `python manage.py collectstatic`\n"
                "- Admin panel: mention /admin/ URL\n"
                "- API endpoints: list main URL patterns if detectable from urls.py\n"
            ),
            'ar': (
                "## متطلبات خاصة بمشاريع Django:\n"
                "- اشمل: `python manage.py migrate` قبل تشغيل الخادم\n"
                "- اشمل: `python manage.py createsuperuser` للوصول للمدير\n"
                "- أضف قسم .env: SECRET_KEY، DEBUG، DATABASE_URL، ALLOWED_HOSTS\n"
                "- أضف ⚠️ تحذير: 'لا تشغّل بـ DEBUG=True في الإنتاج أبداً'\n"
                "- لوحة المدير: اذكر رابط /admin/\n"
            ),
        },
        'React': {
            'en': (
                "## REACT-SPECIFIC REQUIREMENTS:\n"
                "- Prerequisites: Node.js 18+, npm or yarn\n"
                "- Show available npm scripts from package.json (start, build, test, eject)\n"
                "- Build for production: `npm run build` → explain the build/ output folder\n"
                "- If .env.example or REACT_APP_ vars detected: add Environment Variables section\n"
                "- Add ⚠️ Warning: 'Do NOT expose API keys in REACT_APP_ vars in production — they are visible in the browser'\n"
                "- If React Router detected: briefly describe routing structure\n"
                "- Component overview: list top-level components from the file tree\n"
            ),
            'ar': (
                "## متطلبات خاصة بمشاريع React:\n"
                "- المتطلبات: Node.js 18+، npm أو yarn\n"
                "- اعرض scripts المتاحة من package.json\n"
                "- البناء للإنتاج: `npm run build` مع شرح مجلد build/\n"
                "- أضف ⚠️ تحذير: 'لا تضع مفاتيح API في متغيرات REACT_APP_ في الإنتاج — ستظهر للمتصفح'\n"
                "- نظرة عامة على المكوّنات: اذكر المكوّنات الرئيسية من شجرة الملفات\n"
            ),
        },
        'Node': {
            'en': (
                "## NODE.JS-SPECIFIC REQUIREMENTS:\n"
                "- Prerequisites: Node.js version from package.json 'engines' field, npm/yarn\n"
                "- Show all package.json scripts\n"
                "- If Express detected: list main API endpoints / routes\n"
                "- Environment: show .env variables needed (PORT, DB_URL, JWT_SECRET, etc.)\n"
                "- Add ⚠️ Warning about process.env variables in production\n"
                "- If nodemon detected: show `npm run dev` for development\n"
            ),
            'ar': (
                "## متطلبات خاصة بمشاريع Node.js:\n"
                "- المتطلبات: إصدار Node.js من حقل engines في package.json\n"
                "- اعرض كل scripts في package.json\n"
                "- إذا اكتُشف Express: اذكر المسارات الرئيسية للـ API\n"
                "- البيئة: اعرض متغيرات .env المطلوبة\n"
            ),
        },
        'Flutter': {
            'en': (
                "## FLUTTER-SPECIFIC REQUIREMENTS:\n"
                "- Prerequisites: Flutter SDK version, Dart SDK, target platforms (Android/iOS/Web/Desktop)\n"
                "- Show: `flutter pub get` then `flutter run`\n"
                "- Build commands per platform: `flutter build apk`, `flutter build ios`, `flutter build web`\n"
                "- If Android: mention minimum SDK version if detectable from android/app/build.gradle\n"
                "- State management: mention if Provider/Bloc/Riverpod/GetX detected\n"
                "- Add 💡 Tip: 'Use `flutter doctor` to verify your environment is set up correctly'\n"
            ),
            'ar': (
                "## متطلبات خاصة بمشاريع Flutter:\n"
                "- المتطلبات: Flutter SDK، Dart SDK، المنصات المستهدفة\n"
                "- اعرض: `flutter pub get` ثم `flutter run`\n"
                "- أوامر البناء لكل منصة: apk، ios، web\n"
                "- أضف 💡 نصيحة: 'استخدم `flutter doctor` للتحقق من إعداد البيئة'\n"
            ),
        },
        'Rust': {
            'en': (
                "## RUST-SPECIFIC REQUIREMENTS:\n"
                "- Prerequisites: Rust toolchain (stable), Cargo — link to rustup.rs\n"
                "- Build: `cargo build --release` for optimized binary\n"
                "- Run: `cargo run` for development, show binary path after release build\n"
                "- Test: `cargo test`\n"
                "- If Cargo.toml has features: list them with explanations\n"
                "- Add 💡 Tip: 'First build may take several minutes — subsequent builds are much faster'\n"
            ),
            'ar': (
                "## متطلبات خاصة بمشاريع Rust:\n"
                "- المتطلبات: Rust toolchain، Cargo — رابط rustup.rs\n"
                "- البناء: `cargo build --release` للنسخة المحسّنة\n"
                "- الاختبارات: `cargo test`\n"
                "- أضف 💡 نصيحة: 'أول بناء قد يأخذ دقائق — البنيات التالية أسرع بكثير'\n"
            ),
        },
        'Go': {
            'en': (
                "## GO-SPECIFIC REQUIREMENTS:\n"
                "- Prerequisites: Go version from go.mod, no external package manager needed\n"
                "- Install deps: `go mod download`\n"
                "- Build: `go build -o ./bin/appname .`\n"
                "- Run: `go run .` or the built binary\n"
                "- Test: `go test ./...`\n"
                "- If main package detected: explain entry point\n"
                "- Add 💡 Tip: 'Set GOPATH correctly if not using Go modules'\n"
            ),
            'ar': (
                "## متطلبات خاصة بمشاريع Go:\n"
                "- المتطلبات: إصدار Go من go.mod\n"
                "- تحميل التبعيات: `go mod download`\n"
                "- البناء: `go build -o ./bin/appname .`\n"
                "- الاختبارات: `go test ./...`\n"
            ),
        },
        'Java': {
            'en': (
                "## JAVA-SPECIFIC REQUIREMENTS:\n"
                "- Prerequisites: JDK version (from pom.xml or build.gradle), Maven or Gradle\n"
                "- Maven: `mvn clean install` then `mvn spring-boot:run` or `java -jar target/*.jar`\n"
                "- Gradle: `./gradlew build` then `./gradlew bootRun`\n"
                "- If Spring Boot detected: mention application.properties/yml for configuration\n"
                "- If Hibernate/JPA detected: add database setup section\n"
                "- Add ⚠️ Warning: 'Set JAVA_HOME environment variable before building'\n"
            ),
            'ar': (
                "## متطلبات خاصة بمشاريع Java:\n"
                "- المتطلبات: JDK، Maven أو Gradle\n"
                "- Maven: `mvn clean install` ثم `java -jar target/*.jar`\n"
                "- إذا اكتُشف Spring Boot: اذكر application.properties للإعداد\n"
                "- أضف ⚠️ تحذير: 'تأكد من ضبط متغير JAVA_HOME قبل البناء'\n"
            ),
        },
        'C++': {
            'en': (
                "## C++ SPECIFIC REQUIREMENTS:\n"
                "- Prerequisites: GCC/Clang/MSVC version, CMake version (if used)\n"
                "- CMake build: `mkdir build && cd build && cmake .. && cmake --build .`\n"
                "- Make build: `make` or `make -j$(nproc)` for parallel build\n"
                "- If dependencies detected (vcpkg/conan): show install commands\n"
                "- Add platform-specific notes (Windows needs MSVC or MinGW)\n"
                "- Add 💡 Tip: 'Use `cmake -DCMAKE_BUILD_TYPE=Release ..` for optimized build'\n"
            ),
            'ar': (
                "## متطلبات خاصة بمشاريع C++:\n"
                "- المتطلبات: GCC/Clang، CMake\n"
                "- بناء CMake: `mkdir build && cd build && cmake .. && cmake --build .`\n"
                "- أضف ملاحظات خاصة بكل نظام تشغيل\n"
                "- أضف 💡 نصيحة: 'استخدم `-DCMAKE_BUILD_TYPE=Release` للبناء المحسّن'\n"
            ),
        },
        'Vue': {
            'en': (
                "## VUE.JS-SPECIFIC REQUIREMENTS:\n"
                "- Prerequisites: Node.js 16+, npm or yarn\n"
                "- Show all scripts from package.json\n"
                "- Dev server: `npm run serve` (Vue CLI) or `npm run dev` (Vite)\n"
                "- Production build: `npm run build`\n"
                "- If Vuex/Pinia detected: mention state management approach\n"
                "- If Vue Router detected: describe routing structure briefly\n"
            ),
            'ar': (
                "## متطلبات خاصة بمشاريع Vue.js:\n"
                "- المتطلبات: Node.js 16+، npm أو yarn\n"
                "- خادم التطوير: `npm run serve` أو `npm run dev`\n"
                "- البناء: `npm run build`\n"
            ),
        },
        'General': {
            'en': (
                "## GENERAL PROJECT REQUIREMENTS:\n"
                "- Infer the project purpose from class/function names, file structure, and any docstrings in the data\n"
                "- If it's a desktop GUI app: describe the visual workflow (what the user sees, clicks, and gets)\n"
                "- If it's a script/tool: show exact command-line usage with all options\n"
                "- If it's a library: show import statement and a minimal usage example\n"
                "- If it's a data/ML project: describe the data pipeline and model training steps\n"
            ),
            'ar': (
                "## متطلبات المشروع العام:\n"
                "- استنتج غرض المشروع من أسماء الكلاسات والدوال وهيكل الملفات\n"
                "- إذا كان تطبيق سطح مكتب: صف سير العمل البصري\n"
                "- إذا كان سكريبت/أداة: اعرض استخدام سطر الأوامر\n"
                "- إذا كان مكتبة: اعرض مثال استخدام بسيط\n"
            ),
        },
    }

    COMMANDS = {
        'Python': ('pip install -r requirements.txt', 'python main.py'),
        'Django': ('pip install -r requirements.txt', 'python manage.py runserver'),
        'Flask': ('pip install -r requirements.txt', 'python app.py'),
        'FastAPI': ('pip install -r requirements.txt', 'uvicorn main:app --reload'),
        'Node.js': ('npm install', 'npm start'),
        'React': ('npm install', 'npm start'),
        'Vue': ('npm install', 'npm run serve'),
        'Svelte': ('npm install', 'npm run dev'),
        'Next.js': ('npm install', 'npm run dev'),
        'Nuxt': ('npm install', 'npm run dev'),
        'Angular': ('npm install', 'ng serve'),
        'Flutter': ('flutter pub get', 'flutter run'),
        'Go': ('go mod download', 'go run .'),
        'Rust': ('cargo build', 'cargo run'),
        'Java': ('mvn install', 'mvn spring-boot:run'),
        'Kotlin': ('gradle build', 'gradle run'),
        'C++': ('cmake . && make', './main'),
        'C': ('gcc -o main main.c', './main'),
        'C#': ('dotnet restore', 'dotnet run'),
        'PHP': ('composer install', 'php -S localhost:8000'),
        'Ruby': ('bundle install', 'ruby main.rb'),
        'Web (HTML/CSS/JS)': ('', 'open index.html'),
    }

    def __init__(self, path, ai_provider=None, ai_key=None, cb=None, cache=None,
                 dev_info=None, multi_keys=None):
        self.path = path
        self.provider = ai_provider
        self.key = ai_key
        self.cb = cb
        self.cache = cache
        self.dev = dev_info or {}
        # multi_keys: {'gemini': 'key...', 'claude': 'key...', ...}
        # يُستخدم للـ auto-fallback عند فشل المزود الأول
        self.multi_keys = multi_keys or {}

    # ── معلومات المطور الافتراضية — فارغة بشكل افتراضي ──
    # يملؤها المستخدم في واجهة README، لا شيء hardcoded
    _DEFAULT_DEV = {
        'name':      '',
        'email':     '',
        'whatsapp':  '',
        'github':    '',
        'website':   '',
        'twitter':   '',
        'linkedin':  '',
        'youtube':   '',
        'instagram': '',
        'telegram':  '',
        'paypal':    '',
    }

    def _merged_dev(self):
        """دمج الإعدادات الافتراضية مع ما أدخله المستخدم في الـ UI"""
        merged = dict(self._DEFAULT_DEV)
        for k, v in (self.dev or {}).items():
            if v and v.strip():
                merged[k] = v.strip()
        return merged

    def _dev_block_en(self):
        """قسم المطور بالإنجليزية — v10.7: يشمل كل حسابات التواصل الاجتماعي"""
        d = self._merged_dev()
        wa_num = d.get('whatsapp', '').replace('+', '').replace(' ', '')
        wa_link = f"https://wa.me/{wa_num}" if wa_num else ''

        lines = [
            "",
            "=== DEVELOPER / AUTHOR CONTACT (MANDATORY — include exactly as given) ===",
            f"Full Name : {d['name']}",
            f"Email     : {d['email']}",
        ]
        if wa_link:
            lines.append(f"WhatsApp  : {wa_link}  (number: +{wa_num})")
        if d.get('github'):
            lines.append(f"GitHub    : https://github.com/{d['github'].lstrip('@')}")
        if d.get('website'):
            lines.append(f"Website   : {d['website']}")
        if d.get('youtube'):
            yt = d['youtube'].strip()
            if yt.startswith('UC') or yt.startswith('http'):
                yt_link = yt if yt.startswith('http') else f"https://youtube.com/channel/{yt}"
            else:
                yt_link = f"https://youtube.com/@{yt.lstrip('@')}"
            lines.append(f"YouTube   : {yt_link}")
        if d.get('instagram'):
            ig = d['instagram'].lstrip('@')
            lines.append(f"Instagram : https://instagram.com/{ig}")
        if d.get('telegram'):
            tg = d['telegram'].lstrip('@')
            lines.append(f"Telegram  : https://t.me/{tg}")
        if d.get('twitter'):
            lines.append(f"Twitter   : https://twitter.com/{d['twitter'].lstrip('@')}")
        if d.get('linkedin'):
            lines.append(f"LinkedIn  : {d['linkedin']}")

        lines += [
            "",
            "FORMATTING INSTRUCTIONS FOR AUTHOR SECTION:",
            "- Place '## 👨\u200d💻 Author' as the LAST section before the footer.",
            "- Use a Markdown table with two columns (icon+label | value).",
            "- For Email: use a mailto: shields.io badge.",
            "- For WhatsApp: use a green shields.io badge with the wa.me link.",
            "- For YouTube: use a red shields.io badge with the channel link.",
            "- For Instagram: use a purple/gradient shields.io badge.",
            "- For Telegram: use a blue shields.io badge with the t.me link.",
            "- For GitHub: use the standard black GitHub badge.",
            "- End with a centered HTML <p> line: 'Made with ❤️ by {name}'",
        ]
        return '\n'.join(lines)

    def _dev_block_ar(self):
        """قسم المطور بالعربية — v10.7: يشمل كل حسابات التواصل الاجتماعي"""
        d = self._merged_dev()
        wa_num = d.get('whatsapp', '').replace('+', '').replace(' ', '')
        wa_link = f"https://wa.me/{wa_num}" if wa_num else ''

        lines = [
            "",
            "=== معلومات التواصل مع المطور (إلزامي — أدرجها كما هي بدقة تامة) ===",
            f"الاسم الكامل : {d['name']}",
            f"البريد الإلكتروني : {d['email']}",
        ]
        if wa_link:
            lines.append(f"واتساب : {wa_link}  (الرقم: +{wa_num})")
        if d.get('github'):
            lines.append(f"GitHub    : https://github.com/{d['github'].lstrip('@')}")
        if d.get('website'):
            lines.append(f"الموقع    : {d['website']}")
        if d.get('youtube'):
            yt = d['youtube'].strip()
            if yt.startswith('UC') or yt.startswith('http'):
                yt_link = yt if yt.startswith('http') else f"https://youtube.com/channel/{yt}"
            else:
                yt_link = f"https://youtube.com/@{yt.lstrip('@')}"
            lines.append(f"يوتيوب    : {yt_link}")
        if d.get('instagram'):
            ig = d['instagram'].lstrip('@')
            lines.append(f"انستغرام  : https://instagram.com/{ig}")
        if d.get('telegram'):
            tg = d['telegram'].lstrip('@')
            lines.append(f"تلغرام    : https://t.me/{tg}")
        if d.get('twitter'):
            lines.append(f"تويتر     : https://twitter.com/{d['twitter'].lstrip('@')}")
        if d.get('linkedin'):
            lines.append(f"LinkedIn  : {d['linkedin']}")

        lines += [
            "",
            "تعليمات التنسيق لقسم المطور:",
            "- ضع قسم '## 👨\u200d💻 المطور' كآخر قسم قبل التذييل.",
            "- استخدم جدول Markdown بعمودين (أيقونة+التسمية | القيمة).",
            "- للبريد: استخدم بادجة shields.io مع رابط mailto:.",
            "- للواتساب: استخدم بادجة خضراء shields.io مع رابط wa.me.",
            "- ليوتيوب: استخدم بادجة حمراء shields.io مع رابط القناة.",
            "- للانستغرام: استخدم بادجة بنفسجية shields.io.",
            "- للتلغرام: استخدم بادجة زرقاء shields.io مع رابط t.me.",
            "- اختم بسطر HTML مركزي: 'صُنع بـ ❤️ بواسطة {name}'",
        ]
        return '\n'.join(lines)

    def generate(self):
        """توليد README.md + README_AR.md — v10.1: auto-fallback بين كل المزودين
        الترتيب: Gemini (مجاني) ← Claude (جودة) ← DeepSeek (رخيص) ← OpenAI ← قالب"""
        self._log("🔍 جاري تحليل المشروع...", 'info')

        # ── تحليل المشروع ──────────────────────────────────
        try:
            analysis = self.cache.get(self.path) if self.cache else None
            if analysis:
                self._log("📦 استخدام التحليل المحفوظ", 'info')
            else:
                analysis = ProjectAnalyzer(self.path).analyze()
                if self.cache:
                    self.cache.put(self.path, analysis)
            self._log(
                f"✅ التحليل اكتمل: {analysis['stats']['files']} ملف | "
                f"{analysis['type']} | {len(analysis['tech_stack'])} مكتبة",
                'success'
            )
        except Exception as e:
            self._log(f"❌ فشل التحليل: {e}", 'error')
            return {'success': False, 'error': str(e)}

        # ── بناء قائمة المزودين المتاحين ──────────────────
        # v10.7: Gemini Lite أولاً (حصة مجانية أكبر) ← Gemini Flash ← Claude (Haiku أسرع) ← DeepSeek ← OpenAI
        PRIORITY = ['gemini', 'claude', 'deepseek', 'openai']

        # المفاتيح المتاحة: المزود المختار أولاً، ثم الباقين بالأولوية
        def _build_candidates():
            candidates = []

            # إذا حدد المستخدم مزوداً بمفتاح → جرّبه أولاً
            if self.key and self.provider in AI_PROVIDERS:
                candidates.append((self.provider, self.key))

            # ثم باقي المزودين من الـ multi_keys
            for prov in PRIORITY:
                if prov == self.provider:
                    continue
                k = (self.multi_keys or {}).get(prov, '')
                if k and k.strip():
                    candidates.append((prov, k.strip()))

            return candidates

        candidates = _build_candidates()

        # ── محاولة كل مزود بالترتيب ───────────────────────
        if candidates:
            for prov, key in candidates:
                if prov not in AI_PROVIDERS:
                    continue  # gemini-flash مو مزود مستقل
                pname = AI_PROVIDERS[prov]['name']
                self._log(f"🤖 جاري المحاولة مع {pname}...", 'info')
                # حفظ مؤقت للمزود الحالي
                _orig_provider = self.provider
                _orig_key      = self.key
                self.provider  = prov
                self.key       = key
                try:
                    en, ar = self._ai_both(analysis)
                    if len(en) > 300 and len(ar) > 300:
                        self._log(f"✅ {pname}: README جاهز! ({len(en)+len(ar):,} حرف)", 'success')
                        return {'success': True, 'en': en, 'ar': ar, 'analysis': analysis,
                                'provider_used': pname}
                    else:
                        self._log(f"⚠️ {pname}: الرد قصير جداً — المحاولة التالية", 'warning')
                except Exception as e:
                    err = str(e)
                    err_lower = err.lower()
                    # رسائل خطأ واضحة لكل حالة
                    if '401' in err or 'Unauthorized' in err or 'invalid_api_key' in err_lower:
                        self._log(f"❌ {pname}: مفتاح API غير صحيح", 'error')
                    elif 'RESOURCE_EXHAUSTED' in err or '429' in err or ('quota' in err_lower and 'rate' in err_lower):
                        self._log(f"⚠️ {pname}: تجاوز حد الطلبات المؤقت — المحاولة التالية", 'warning')
                    elif '402' in err or ('insufficient' in err_lower and 'quota' not in err_lower):
                        self._log(f"❌ {pname}: رصيد API غير كافٍ", 'error')
                    elif 'quota' in err_lower and 'RESOURCE_EXHAUSTED' not in err:
                        # Gemini quota warning — قد يكون rate limit أو حد يومي مجاني
                        self._log(f"⚠️ {pname}: تجاوز الحد المسموح مؤقتاً — المحاولة التالية", 'warning')
                    elif 'timeout' in err_lower:
                        self._log(f"⚠️ {pname}: انتهت مهلة الاتصال — المحاولة التالية", 'warning')
                    elif '404' in err or 'not found' in err_lower or 'invalid model' in err_lower or 'Gemini_404_model' in err:
                        self._log(f"❌ {pname}: الموديل غير متاح — جرّب مزوداً آخر", 'error')
                    else:
                        self._log(f"❌ {pname}: {err[:180]}", 'error')
                finally:
                    # استعادة المزود الأصلي
                    self.provider = _orig_provider
                    self.key      = _orig_key

            self._log("⚠️ كل المزودين فشلوا — التبديل للقالب الافتراضي", 'warning')
        else:
            self._log("ℹ️ لا يوجد مفتاح AI — استخدام القالب الافتراضي", 'info')

        # ── fallback نهائي: القالب ────────────────────────
        en = self._tpl(analysis, 'en')
        ar = self._tpl(analysis, 'ar')
        self._log("🎉 README جاهز! (قالب افتراضي)", 'success')
        return {'success': True, 'en': en, 'ar': ar, 'analysis': analysis,
                'provider_used': 'template'}

    def save(self, en, ar):
        """حفظ الملفات + تحديث HashCache + حفظ بصمة المشروع"""
        for fname, txt in [('README.md', en), ('README_AR.md', ar)]:
            p = Path(self.path) / fname
            p.write_text(txt, encoding='utf-8')
            try:
                HashCache.get_hash(p, force=True)
            except Exception:
                pass
        # ✅ احفظ بصمة المشروع لكشف التغييرات لاحقاً
        try:
            snap_file = Path(self.path) / '.ayadsync_readme_snap'
            snap_file.write_text(self._project_snapshot(), encoding='utf-8')
        except Exception:
            pass

    @staticmethod
    def check_readme_status(path) -> tuple:
        """
        فحص حالة README مقارنةً بالمشروع الحالي.
        يُستدعى تلقائياً من الواجهة عند اختيار مجلد.

        Returns: (icon, status_text)
          🔴  لا يوجد README
          🟡  README موجود لكن لم يُولَّد بالنظام (بدون بصمة)
          🔶  المشروع تغيّر منذ آخر توليد
          ✅  README حديث — المشروع لم يتغيّر
        """
        path = Path(path)
        readme   = path / 'README.md'
        snap_file = path / '.ayadsync_readme_snap'

        if not readme.exists():
            return '🔴', 'لا يوجد README'

        if not snap_file.exists():
            return '🟡', 'README موجود — يحتاج توليد بالنظام'

        try:
            saved_snap   = snap_file.read_text(encoding='utf-8').strip()
            current_snap = SmartReadmeGenerator._project_snapshot_static(path)
            if saved_snap == current_snap:
                # آخر تعديل على README
                import datetime
                mtime = readme.stat().st_mtime
                dt    = datetime.datetime.fromtimestamp(mtime)
                diff  = datetime.datetime.now() - dt
                if diff.days == 0:
                    if diff.seconds < 3600:
                        when = f"منذ {diff.seconds // 60} دقيقة"
                    else:
                        when = f"منذ {diff.seconds // 3600} ساعة"
                elif diff.days == 1:
                    when = "أمس"
                else:
                    when = f"منذ {diff.days} يوم"
                return '✅', f'README حديث ({when})'
            else:
                return '🔶', 'المشروع تغيّر — يحتاج تحديث README'
        except Exception:
            return '🟡', 'يحتاج فحص'

    def _project_snapshot(self) -> str:
        return SmartReadmeGenerator._project_snapshot_static(Path(self.path))

    @staticmethod
    def _project_snapshot_static(path: Path) -> str:
        """
        بصمة خفيفة للمشروع — سريعة ودقيقة:
        اسم الملف + حجمه + mtime لأول 500 ملف مرتبة.
        لا تقرأ محتوى الملفات — 0ms تقريباً حتى لـ 150k ملف.
        """
        import hashlib
        parts = []
        skip  = {'README.md', 'README_AR.md', '.ayadsync_readme_snap'}
        try:
            count = 0
            for f in sorted(path.rglob('*')):
                if not f.is_file():
                    continue
                if f.name in skip or f.name.startswith('.ayadsync'):
                    continue
                st = f.stat()
                parts.append(f"{f.name}:{st.st_size}:{int(st.st_mtime)}")
                count += 1
                if count >= 500:
                    break
        except Exception:
            pass
        return hashlib.md5('\n'.join(parts).encode()).hexdigest()

    # ── System prompts ────────────────────────────────────
    _SYS_EN = (
        "You are a world-class technical writer specialising in open-source documentation. "
        "Your task: write a GitHub README that reads like it was crafted by the project's "
        "own author — specific, honest, and useful. "
        "Rules: (1) Every claim must be derivable from the project data. Never invent. "
        "(2) Start with the problem the project solves, not a generic description. "
        "(3) The Usage section must be a real step-by-step guide a beginner can follow. "
        "(4) Output ONLY raw Markdown — no preamble, no explanation, no code fences around the whole file."
    )
    _SYS_AR = (
        "أنت كاتب توثيق تقني متخصص في مشاريع البرمجيات المفتوحة المصدر. "
        "مهمتك: كتابة README يبدو وكأنه كتبه صاحب المشروع بنفسه — دقيق، صادق، ومفيد. "
        "القواعد: (1) كل ادعاء يجب أن يكون مشتقاً من بيانات المشروع. لا تخترع. "
        "(2) ابدأ بالمشكلة التي يحلها المشروع، لا بوصف عام. "
        "(3) قسم الاستخدام يجب أن يكون دليلاً حقيقياً خطوة بخطوة. "
        "(4) أخرج Markdown خاماً فقط — بلا مقدمة ولا تفسير."
    )

    # ── Prompt templates ──────────────────────────────────
    _PROMPT_EN = """\
## THE PROJECT PROBLEM & PURPOSE (write this first, before anything else):
Before listing features, answer these three questions from the project data:
- **What pain does this project eliminate?** (e.g. "Managing GitHub repos across multiple devices without losing track of which version is latest")
- **Who is it for?** (e.g. "Developers who work on several machines and use a USB drive as a portable workspace")
- **Why would someone choose this over alternatives?** (e.g. "Unlike cloud-only solutions, it works offline and keeps a local backup on USB")
Write this as 3-4 sentences of flowing prose — NOT bullet points. This becomes the opening paragraph.

## README STRUCTURE (follow exactly, in this order):

### 1. Title + Badges
- Project name as `# H1`
- Relevant shields.io badges only if the data supports them (language, license, platform)

### 2. Opening Paragraph — Problem + Purpose
- Use the prose you wrote above
- End with one sentence: "**X** solves this by [key mechanism]."

### 3. ✨ Features
- Bullet list — each bullet must describe a SPECIFIC, CONCRETE capability
- Format: `- **Feature name** — what it does and why it matters`
- Bad: "Easy to use interface"  Good: "**One-click upload** — push any local project to GitHub in under 10 seconds"
- Max 8 bullets, only what exists in the code

### 4. 🛠 Tech Stack
- Table: Technology | Purpose | Version (if found)
- Only technologies actually present in the project data

### 5. 📁 Project Structure
- Use the exact tree from the data
- Add `# brief comment` after each important file/folder

### 6. ⚙️ Prerequisites
- Exact requirements with minimum versions
- OS compatibility if detectable

### 7. 🚀 Installation
- Numbered steps, each with a shell code block
- Platform-specific notes (Windows/Linux/macOS) if relevant

### 8. ▶️ Usage — Step-by-Step Guide
**This is the most important section.** Write it as a real user manual:
- "Quick Start" subsection: 3 steps or less to get running
- One subsection per major feature found in the code
- Each subsection: WHAT it does → WHEN to use it → HOW (numbered steps with exact commands)
- Add `⚠️ Warning:` for common mistakes
- Add `💡 Tip:` for best practices

### 9. 🧪 Testing — ONLY if tests were detected, otherwise omit

### 10. 🐳 Docker — ONLY if Dockerfile/compose found, otherwise omit

### 11. 🤝 Contributing
- Fork → Branch → Commit → Push → PR flow

### 12. 📄 License

## Project Data:
{ctx}
"""

    _PROMPT_AR = """\
## مشكلة المشروع والغرض منه (اكتب هذا أولاً قبل أي شيء آخر):
قبل سرد المميزات، أجب على هذه الأسئلة الثلاثة من بيانات المشروع:
- **ما الألم الذي يزيله هذا المشروع؟** (مثال: "إدارة مستودعات GitHub عبر أجهزة متعددة دون فقدان تتبع أحدث نسخة")
- **لمن هو؟** (مثال: "المطورون الذين يعملون على عدة أجهزة ويستخدمون فلاشة USB كبيئة عمل محمولة")
- **لماذا يختاره أحدهم على البدائل؟** (مثال: "بخلاف الحلول السحابية فقط، يعمل بدون إنترنت ويحتفظ بنسخة احتياطية محلية على USB")
اكتب هذا كـ 3-4 جمل متدفقة — ليس نقاطاً. هذا يصبح الفقرة الافتتاحية.

## هيكل README (اتبع بالضبط، بهذا الترتيب):

### 1. العنوان والبادجات
- اسم المشروع كـ `# H1`
- بادجات shields.io فقط إذا كانت البيانات تدعمها

### 2. الفقرة الافتتاحية — المشكلة والغرض
- استخدم النثر الذي كتبته أعلاه
- اختتم بجملة: "**X** يحل هذا عن طريق [الآلية الرئيسية]."

### 3. ✨ المميزات
- قائمة نقطية — كل نقطة تصف قدرة محددة وحقيقية
- الصيغة: `- **اسم الميزة** — ماذا تفعل ولماذا تهم`
- سيئ: "واجهة سهلة الاستخدام"  جيد: "**رفع بنقرة واحدة** — ادفع أي مشروع محلي إلى GitHub في أقل من 10 ثوانٍ"
- 8 نقاط كحد أقصى، فقط ما هو موجود في الكود

### 4. 🛠 التقنيات المستخدمة
- جدول: التقنية | الغرض | الإصدار (إن وُجد)
- فقط التقنيات الموجودة فعلاً في بيانات المشروع

### 5. 📁 هيكل المشروع
- استخدم الشجرة كما هي من البيانات
- أضف `# تعليق مختصر` بعد كل ملف/مجلد مهم

### 6. ⚙️ المتطلبات الأساسية
- المتطلبات بإصداراتها الدقيقة
- ملاحظات توافق أنظمة التشغيل إن أمكن

### 7. 🚀 التثبيت
- خطوات مرقّمة، كل خطوة مع code block
- ملاحظات خاصة بكل نظام تشغيل إن لزم

### 8. ▶️ دليل الاستخدام التفصيلي — الأهم على الإطلاق
اكتبه كدليل مستخدم حقيقي:
- قسم "البداية السريعة": 3 خطوات أو أقل للتشغيل
- قسم فرعي لكل ميزة رئيسية موجودة في الكود
- لكل ميزة: ماذا تفعل ← متى تستخدمها ← كيف (خطوات مرقمة مع أوامر دقيقة)
- `⚠️ تحذير:` للأخطاء الشائعة
- `💡 نصيحة:` لأفضل الممارسات

### 9. 🧪 الاختبارات — فقط إذا اكتُشفت اختبارات، وإلا احذف

### 10. 🐳 Docker — فقط إذا وُجد Dockerfile، وإلا احذف

### 11. 🤝 المساهمة

### 12. 📄 الترخيص

## بيانات المشروع:
{ctx}
"""

    def _ai_both(self, analysis):
        """
        v12: طلبان منفصلان — EN كاملاً أولاً، ثم AR بناءً عليه.
        كل طلب يأخذ الـ token budget كاملاً → جودة أعلى بكثير.
        + صوت المؤلف: الـ AI يكتب كأنه صاحب المشروع نفسه.
        """
        ctx      = self._ctx(analysis)
        dev_en   = self._dev_block_en()
        dev_ar   = self._dev_block_ar()

        # ── حقن تعليمات خاصة بنوع المشروع ──────────────────────
        proj_type = analysis.get('type', 'General')
        type_key  = proj_type if proj_type in self.TYPE_HINTS else 'General'
        hint_en   = self.TYPE_HINTS[type_key]['en']
        hint_ar   = self.TYPE_HINTS[type_key]['ar']
        self._log(f"🎯 نوع المشروع: {proj_type} — طلبان منفصلان EN+AR", 'info')

        # ══════════════════════════════════════════
        # طلب 1: README الإنجليزي كاملاً
        # ══════════════════════════════════════════
        sys_en = (
            "You are a senior developer documenting your own project for GitHub. "
            "Your README will be the first thing thousands of developers see. "
            "Write with the confidence of someone who built every line — specific, technical, and proud. "
            "STRICT RULES: "
            "(1) Every claim MUST come from the project data — never invent features. "
            "(2) Use exact class names, real file counts, actual library names. "
            "(3) BANNED phrases: 'easy to use', 'powerful', 'robust', 'seamless', 'intuitive', "
            "'state-of-the-art', 'cutting-edge', 'comprehensive solution'. These are filler. "
            "(4) Output ONLY raw Markdown. No preamble, no ```markdown wrapper. "
            "(5) Write for developers who will judge your project in 30 seconds."
        )

        prompt_en = f"""Write a complete, production-grade GitHub README.md.

## PROJECT TYPE: {proj_type}
{hint_en}

## QUALITY STANDARD:
This README should look like it belongs to a project with 500+ GitHub stars.
Study how top open-source projects write their READMEs: clear problem statement,
concrete features with numbers, real code examples, visual structure with badges.

## STRUCTURE (follow exactly):

### 1. Title + Badge Row
```
# ProjectName
![Python](shield) ![License](shield) ![Platform](shield)
```
- Only badges supported by the data. Use shields.io format.

### 2. One-Line Description (italic, under badges)
*One sentence that explains what this project does and why it matters.*

### 3. Opening Paragraph — Why This Exists (3-5 sentences)
Write in first person. Answer:
- What specific problem drove you to build this?
- What's your approach that makes it different?
- One concrete result (e.g. "scans 200,000 files in under 3 seconds")
End with: "**ProjectName** does this by [specific mechanism]."

### 4. ✨ Key Features (6-10 bullets)
CRITICAL: Each bullet must be SPECIFIC and CONCRETE.
Format: `- **Feature Name** — What it does (with a real number or technical detail)`

EXAMPLES of GOOD bullets:
- **xxHash-powered file detection** — identifies changed files 30× faster than MD5, comparing only files that actually differ
- **4-tier device profiling** — automatically adjusts thread count (2→16) and batch size (50→2000) based on CPU cores, RAM, and hash benchmark
- **Zero-byte file awareness** — correctly syncs empty Gerber/PCB layer files that other tools silently skip

EXAMPLES of BAD bullets (NEVER write these):
- Easy to use interface
- Powerful sync engine
- Comprehensive GitHub integration

### 5. 🖥️ Screenshots / Demo (if GUI app)
Write: `> Screenshots coming soon` or describe the UI panels if it's a desktop app.

### 6. 🛠 Tech Stack
| Technology | Purpose | Why |
|---|---|---|
Only list what's actually in the project. The "Why" column explains the technical choice.

### 7. 📁 Project Structure
Use the exact tree. Add `# comment` after important files explaining their role.

### 8. ⚙️ Prerequisites + 🚀 Installation
Numbered steps with shell blocks. Include platform-specific notes.

### 9. ▶️ Usage Guide — THE MOST IMPORTANT SECTION
Write this as if you're pair-programming with the reader:
- **Quick Start**: 3 steps to get running
- **One subsection per major feature**: title, 2-sentence explanation, then numbered steps
- Include `⚠️ Warning:` boxes for pitfalls
- Include `💡 Tip:` boxes for best practices
- If CLI tool: show real command examples with expected output
- If GUI app: describe the workflow (open → click → result)

### 10. 🏗 Architecture (optional, for complex projects)
Brief explanation of how the major modules interact. A text diagram or bullet list.

### 11. 🧪 Tests — ONLY if tests exist
### 12. 🤝 Contributing (Fork → Branch → Commit → Push → PR)
### 13. 📄 License

## Developer Section (place at the end):
{dev_en}

## Project Data (source of truth — derive ALL claims from this):
{ctx}
"""
        self._log(f"📤 طلب EN: {len(prompt_en):,} حرف", 'info')
        en_raw = self._ai_call(sys_en, prompt_en, analysis)
        en = self._clean_md(en_raw)

        if len(en) < 300:
            raise Exception("README EN قصير جداً — أقل من 300 حرف")

        self._log(f"✅ EN جاهز: {len(en):,} حرف", 'success')

        # ══════════════════════════════════════════
        # طلب 2: README العربي — ترجمة + تكيّف
        # ══════════════════════════════════════════
        sys_ar = (
            "أنت المطور الذي بنى هذا المشروع. اكتب README بالعربية الفصحى المبسطة. "
            "اكتب بثقة واعتزاز — أنت تشرح مشروعك لمطور زميل. "
            "ممنوع: 'سهل الاستخدام'، 'قوي'، 'متين'، 'سلس'، 'شامل'. هذه حشو لا قيمة له. "
            "بدلاً منها: اكتب ماذا يفعل بالضبط وبأي رقم. "
            "احتفظ بكل الأوامر التقنية والروابط وأسماء المكتبات بالإنجليزية. "
            "أخرج Markdown خاماً فقط — بلا مقدمة ولا تفسير."
        )

        prompt_ar = f"""أنتج README_AR.md عربياً احترافياً بناءً على README الإنجليزي وبيانات المشروع.

## معيار الجودة:
هذا الـ README يجب أن يبدو كأنه ينتمي لمشروع بـ 500+ نجمة على GitHub.
محدد، تقني، فيه أرقام حقيقية — لا حشو ولا عبارات عامة.

## قواعد الترجمة:
1. ترجم كل النص للعربية باستثناء: أسماء البرمجيات، أوامر Shell، روابط، أكواد
2. الفقرة الافتتاحية: أعد كتابتها لتبدو طبيعية بالعربية — لا ترجمة حرفية
3. المميزات: كل نقطة تصف ميزة محددة بأرقام حقيقية — نفس مستوى التفصيل
4. الاستخدام: الخطوات بالعربية، الأوامر بالإنجليزية
5. البادجات: كما هي بدون ترجمة
6. اكتب بضمير المتكلم كأنك صاحب المشروع

## متطلبات خاصة بالنوع ({proj_type}):
{hint_ar}

## معلومات المطور:
{dev_ar}

## README الإنجليزي (المرجع — ترجم وكيّف منه بنفس الجودة):
{en}

"""
        self._log(f"📤 طلب AR: {len(prompt_ar):,} حرف", 'info')
        ar_raw = self._ai_call(sys_ar, prompt_ar, analysis)
        ar = self._clean_md(ar_raw)

        if len(ar) < 300:
            self._log("⚠️ AR قصير — استخدام القالب كـ fallback", 'warning')
            ar = self._tpl(analysis, 'ar')

        self._log(f"✅ AR جاهز: {len(ar):,} حرف", 'success')
        return en, ar

    def _ai_call(self, system_msg, user_msg, analysis):
        """إرسال الطلب للـ API المختار وإرجاع النص الخام"""
        provider = AI_PROVIDERS[self.provider]
        headers  = {'Content-Type': 'application/json'}

        if self.provider == 'gemini' or self.provider == 'gemini-flash':
            body = {
                'contents': [{'parts': [{'text': f"{system_msg}\n\n{user_msg}"}]}],
                'generationConfig': {
                    'maxOutputTokens': 12000,
                    'temperature': 0.25,
                    'topP': 0.9,
                }
            }
            # قائمة الموديلات للمحاولة: الأساسي + fallbacks
            base_model   = provider['model']
            fallbacks    = provider.get('fallback_models', [])
            models_order = [base_model] + fallbacks

            last_err = None
            for attempt_model in models_order:
                base_url  = re.sub(r'/models/[^:]+:', f'/models/{attempt_model}:', provider['url'])
                req_url   = f"{base_url}?key={self.key}"
                try:
                    r = requests.post(req_url, headers=headers, json=body, timeout=180)
                    if r.status_code == 200:
                        data = r.json()
                        candidates = data.get('candidates', [])
                        if candidates:
                            raw = candidates[0]['content']['parts'][0]['text']
                            if attempt_model != base_model:
                                self._log(f"   ↳ نجح بـ fallback: {attempt_model}", 'info')
                            return raw.strip()
                    err_txt = r.text[:200]
                    # rate limit أو quota → جرّب الموديل التالي
                    if r.status_code in (429, 503) or 'RESOURCE_EXHAUSTED' in err_txt or 'quota' in err_txt.lower():
                        self._log(f"   ↳ {attempt_model}: حد مؤقت — جاري تجربة: ", 'info')
                        last_err = f"Gemini {r.status_code}: {err_txt}"
                        continue
                    # موديل غير موجود → جرّب التالي
                    if r.status_code == 404 or 'not found' in err_txt.lower():
                        last_err = f"Gemini_404_model: {attempt_model}"
                        continue
                    # خطأ آخر → رمي استثناء فوري
                    raise Exception(f"Gemini {r.status_code}: {err_txt}")
                except requests.exceptions.Timeout:
                    last_err = f"Gemini timeout: {attempt_model}"
                    continue
                except requests.exceptions.ConnectionError as _ce:
                    last_err = f"Gemini connection error: {attempt_model} ({_ce})"
                    continue
                except requests.exceptions.RequestException as _re:
                    last_err = f"Gemini request error: {attempt_model} ({_re})"
                    continue
                except Exception as _e:
                    if 'Gemini' in str(_e):
                        raise
                    last_err = str(_e)
                    continue
            raise Exception(last_err or "Gemini: كل الموديلات فشلت")

        elif self.provider == 'claude':
            headers['x-api-key']         = self.key
            headers['anthropic-version'] = '2023-06-01'
            # جرّب موديلات Claude بالترتيب عند فشل الأساسي
            _claude_models = [provider['model']] + provider.get('fallback_models', [])
            _last_claude_err = None
            for _cm in _claude_models:
                _body = {
                    'model':      _cm,
                    'max_tokens': 16000,
                    'system':     system_msg,
                    'messages':   [{'role': 'user', 'content': user_msg}]
                }
                try:
                    _r = requests.post(provider['url'], headers=headers, json=_body, timeout=180)
                    if _r.status_code == 200:
                        _data = _r.json()
                        return _data['content'][0]['text']
                    _err = _r.text[:200]
                    # 404 = موديل غير موجود → جرّب التالي
                    if _r.status_code == 404 or 'model_not_found' in _err.lower():
                        if _cm != _claude_models[-1]:
                            self._log(f"   ↳ Claude {_cm}: غير متاح — جاري تجربة fallback", 'info')
                            _last_claude_err = f"model_not_found: {_cm}"
                            continue
                    # ✅ FIX: 529 = overloaded → جرّب fallback
                    if _r.status_code == 529 or 'overloaded' in _err.lower():
                        if _cm != _claude_models[-1]:
                            self._log(f"   ↳ Claude {_cm}: مشغول — جاري تجربة fallback", 'info')
                            _last_claude_err = f"overloaded: {_cm}"
                            continue
                    _last_claude_err = f"Claude {_r.status_code}: {_err}"
                    raise Exception(_last_claude_err)
                except requests.exceptions.Timeout:
                    _last_claude_err = f"Claude timeout: {_cm}"
                    if _cm != _claude_models[-1]:
                        self._log(f"   ↳ Claude {_cm}: timeout — جاري تجربة fallback", 'info')
                        continue
                    raise Exception(_last_claude_err)
                except requests.exceptions.ConnectionError as _ce:
                    _last_claude_err = f"Claude connection error: {_ce}"
                    if _cm != _claude_models[-1]:
                        self._log(f"   ↳ Claude {_cm}: خطأ شبكة — جاري تجربة fallback", 'info')
                        continue
                    raise Exception(_last_claude_err)
            raise Exception(_last_claude_err or "Claude: كل الموديلات غير متاحة")

        elif self.provider == 'deepseek':
            headers['Authorization'] = f"Bearer {self.key}"
            body = {
                'model':             provider['model'],
                'max_tokens':        7500,
                'temperature':       0.3,
                'top_p':             0.9,
                'frequency_penalty': 0.1,
                'messages': [
                    {'role': 'system',    'content': system_msg},
                    {'role': 'user',      'content': user_msg},
                ]
            }
            try:
                r = requests.post(provider['url'], headers=headers, json=body, timeout=180)
            except requests.exceptions.Timeout:
                raise Exception("DeepSeek timeout — الخادم لم يستجب في 180 ثانية")
            except requests.exceptions.ConnectionError as _ce:
                raise Exception(f"DeepSeek خطأ شبكة: {_ce}")
            if r.status_code == 200:
                data = r.json()
                return data['choices'][0]['message']['content']
            raise Exception(f"DeepSeek {r.status_code}: {r.text[:300]}")

        else:  # openai
            headers['Authorization'] = f"Bearer {self.key}"
            body = {
                'model':       provider['model'],
                'max_tokens':  8000,
                'temperature': 0.3,
                'messages': [
                    {'role': 'system', 'content': system_msg},
                    {'role': 'user',   'content': user_msg}
                ]
            }
            try:
                r = requests.post(provider['url'], headers=headers, json=body, timeout=180)
            except requests.exceptions.Timeout:
                raise Exception("OpenAI timeout — الخادم لم يستجب في 180 ثانية")
            except requests.exceptions.ConnectionError as _ce:
                raise Exception(f"OpenAI خطأ شبكة: {_ce}")
            if r.status_code == 200:
                data = r.json()
                return data['choices'][0]['message']['content']
            raise Exception(f"OpenAI {r.status_code}: {r.text[:300]}")

    def _split_both(self, raw, analysis):
        """تقسيم مخرج الـ AI إلى نسختين EN و AR — v10.0
        fallback متعدد المراحل بدل التقسيم العشوائي من المنتصف"""
        name = analysis.get('name', 'Project')

        # ─── المرحلة 1: delimiter المطلوب ───
        if '===EN_README===' in raw and '===AR_README===' in raw:
            try:
                en_part = raw.split('===EN_README===')[1].split('===AR_README===')[0]
                ar_part = raw.split('===AR_README===')[1].split('===END===')[0]
                en_part = self._clean_md(en_part)
                ar_part = self._clean_md(ar_part)
                if len(en_part) > 200 and len(ar_part) > 200:
                    return en_part, ar_part
            except Exception:
                pass

        # ─── المرحلة 2: بحث عن div dir="rtl" كحد فاصل ───
        if '<div dir="rtl">' in raw:
            idx = raw.index('<div dir="rtl">')
            en_part = self._clean_md(raw[:idx])
            ar_part = self._clean_md(raw[idx:])
            if len(en_part) > 200 and len(ar_part) > 200:
                self._log("⚠️ الفاصل غير موجود — استُخدم <div dir='rtl'> كبديل", 'warning')
                return en_part, ar_part

        # ─── المرحلة 3: بحث عن H1 عربي كحد فاصل ───
        lines = raw.strip().split('\n')
        ar_indicators = ['## المميزات', '## التقنيات', '## الاستخدام', '## التثبيت', '# مشروع']
        ar_idx = None
        for i, line in enumerate(lines):
            if any(ind in line for ind in ar_indicators):
                # ابحث عن H1 قبله بـ 5 أسطر
                ar_idx = max(0, i - 5)
                break

        if ar_idx and ar_idx > 50:
            en_part = self._clean_md('\n'.join(lines[:ar_idx]))
            ar_part = self._clean_md('\n'.join(lines[ar_idx:]))
            if len(en_part) > 200 and len(ar_part) > 200:
                self._log("⚠️ استُخدم H1 العربي كفاصل بديل", 'warning')
                return en_part, ar_part

        # ─── المرحلة 4 (أخيرة): الرد كاملاً EN + قالب AR ───
        self._log("⚠️ فشل التقسيم — EN من الـ AI، AR من القالب", 'warning')
        en_part = self._clean_md(raw) if raw.strip() else self._tpl(analysis, 'en')
        ar_part = self._tpl(analysis, 'ar')
        return en_part, ar_part

    def _clean_md(self, text):
        """تنظيف الـ Markdown من أي wrappers غير مرغوبة"""
        t = text.strip()
        # إزالة code fences حول كامل الملف
        for wrapper in ('```markdown\n', '```md\n', '```\n'):
            if t.startswith(wrapper):
                t = t[len(wrapper):]
                break
        if t.endswith('\n```'):
            t = t[:-4]
        elif t.endswith('```'):
            t = t[:-3]
        return t.strip()

    def _ctx(self, a):
        """بناء سياق منظّم وغني للـ AI — v11: محسّن للملفات الكبيرة ذات الملف الواحد"""
        s = a['stats']
        ext_summary = ', '.join(
            f"{ext or 'no-ext'}×{cnt}"
            for ext, cnt in sorted(s['exts'].items(), key=lambda x: -x[1])[:8]
        )
        flags = []
        if a['has_tests']:  flags.append('has unit/integration tests')
        if a['has_docker']: flags.append('Docker support')
        if a['has_ci']:     flags.append('CI/CD pipeline')

        # ── للملفات الكبيرة ذات الملف الواحد: نقرأ 1000 سطر من الرأس ──
        main_items = list(a['main_files'].items())
        is_single_file = s['files'] <= 5 and len(main_items) >= 1
        _base_path = a.get('_path', '')
        if is_single_file and _base_path:
            for rel, _ in main_items[:1]:
                fp_candidate = os.path.join(str(_base_path), rel)
                try:
                    with open(fp_candidate, 'r', encoding='utf-8', errors='ignore') as _fh:
                        raw = _fh.read()
                    a['main_files'][rel] = '\n'.join(raw.split('\n')[:1000])
                except Exception:
                    pass

        parts = [
            "=== PROJECT SNAPSHOT ===",
            f"Name       : {a['name']}",
            f"Type       : {a['type']}",
            f"Files      : {s['files']} total  |  Size: {fmt_size(s['size'])}",
            f"Extensions : {ext_summary}",
            f"Extras     : {', '.join(flags) if flags else 'none detected'}",
        ]

        if a.get('description'):
            parts.append(f"pkg.desc   : {a['description'][:600]}")

        if a['tech_stack']:
            parts.append(
                "\n=== DEPENDENCIES / TECH STACK ===\n" +
                ', '.join(a['tech_stack'][:20])
            )

        if a.get('scripts'):
            script_lines = [f"  {k}: {v}" for k, v in list(a['scripts'].items())[:8]]
            parts.append("\n=== NPM SCRIPTS ===\n" + '\n'.join(script_lines))

        parts.append(f"\n=== DIRECTORY TREE ===\n{a['tree']}")

        if a['classes']:
            parts.append(
                "\n=== CLASSES WITH DESCRIPTIONS (shows actual features) ===\n" +
                '\n'.join(a['classes'][:30])
            )

        if a['functions']:
            parts.append(
                "\n=== KEY PUBLIC METHODS (top 40) ===\n" +
                '\n'.join(a['functions'][:40])
            )

        if a.get('sections'):
            parts.append(
                "\n=== FILE SECTIONS / MODULES (architecture overview) ===\n" +
                '\n'.join(a['sections'][:40])
            )

        for name, content_cfg in list(a['configs'].items())[:3]:
            parts.append(f"\n=== CONFIG: {name} ===\n{content_cfg[:2000]}")

        for name, txt in list(a['main_files'].items())[:1]:
            # للملفات الكبيرة: أرسل الرأس (docstring + imports + header)
            limit = 6000 if is_single_file else 2000
            parts.append(f"\n=== MAIN FILE (first {limit//100*100} chars): {name} ===\n{txt[:limit]}")

        # ── FEATURE STORIES: تحويل classes+methods لجمل وصفية ──────────────
        # هذا القسم يُترجم أسماء الكلاسات ودوالها لجمل بشرية يفهمها الـ AI
        feature_stories = []
        for entry in a['classes'][:25]:
            # مثال entry: "app.py: class SyncEngine — يزامن الملفات بـ xxHash"
            if ' — ' in entry:
                parts_e = entry.split(' — ', 1)
                cls_part = parts_e[0].split('class ')[-1].strip()
                doc_part = parts_e[1].strip()
                if len(doc_part) > 10:
                    feature_stories.append(f"• {cls_part}: {doc_part}")
            elif 'class ' in entry:
                cls_name = entry.split('class ')[-1].strip()
                feature_stories.append(f"• {cls_name}: (no description)")

        # أضف توابع مهمة كـ sub-features
        for entry in a['functions'][:40]:
            if ' — ' in entry:
                fn_parts = entry.split(' — ', 1)
                fn_name = fn_parts[0].strip().split('.')[-1].replace('()', '').strip()
                fn_doc  = fn_parts[1].strip()
                if len(fn_doc) > 15 and not fn_name.startswith('_'):
                    feature_stories.append(f"  → {fn_name}(): {fn_doc}")

        if feature_stories:
            parts.append(
                "\n=== FEATURE STORIES (CRITICAL: derive your Features bullets from these) ===\n"
                "Each story below is a REAL capability found in the code.\n"
                "Your Features section MUST reference these — not generic descriptions.\n" +
                '\n'.join(feature_stories[:40])
            )

        parts.append(
            "\n=== INSTRUCTIONS ===\n"
            "1. Your Features section must use SPECIFIC details from FEATURE STORIES above.\n"
            "2. Include real numbers: file counts, speed comparisons, thread counts.\n"
            "3. For desktop/GUI apps: describe the visual workflow (what user sees and clicks).\n"
            "4. For CLI tools: show real command examples with expected output.\n"
            "5. NEVER use generic filler words. Every sentence must contain a concrete fact.\n"
            "6. Write as if YOU built this and are showing it to a senior developer."
        )

        full = '\n'.join(parts)
        return full[:28000]

    def _tpl(self, a, lang):
        """⚡ v4.0: قالب احترافي مُحسّن — يستخرج ميزات حقيقية من التحليل"""
        from pathlib import Path as _P

        name  = a['name']
        files = a['stats']['files']
        size  = fmt_size(a['stats']['size'])
        NL    = chr(10)

        # ── نوع المشروع ──────────────────────────────────────
        pt = a['type']
        all_cls = ' '.join(a['classes'] + a['functions']).lower()
        if pt == 'General':
            if any(w in all_cls for w in ('widget', 'mainwindow', 'pyqt', 'tkinter', 'gui')):
                pt = 'Desktop Application'
            elif any(w in all_cls for w in ('flask', 'route', 'django', 'fastapi')):
                pt = 'Web Application'
            elif any(w in all_cls for w in ('bot', 'telegram', 'discord')):
                pt = 'Bot / Automation'

        # ── أوامر التثبيت والتشغيل ───────────────────────────
        inst, run = self.COMMANDS.get(a['type'], ('pip install -r requirements.txt', 'python main.py'))
        scripts = a.get('scripts', {})
        if scripts.get('dev'):     run = 'npm run dev'
        elif scripts.get('start'): run = 'npm run start'
        main_file = next((f for f in a['main_files'] if not f.startswith('_')), None)
        if main_file and main_file.endswith('.py'):
            run = f'python {main_file}'

        # ── استخراج الميزات الحقيقية من classes + functions ────
        features_en = []
        features_ar = []
        seen = set()
        for entry in a['classes'][:15]:
            if ' — ' in entry:
                parts = entry.split(' — ', 1)
                cname = parts[0].split('class ')[-1].strip() if 'class ' in parts[0] else parts[0].split(':')[-1].strip()
                desc = parts[1].strip()
                if len(desc) > 10 and cname not in seen:
                    seen.add(cname)
                    features_en.append(f"**{cname}** — {desc}")
                    features_ar.append(f"**{cname}** — {desc}")
            elif 'class ' in entry:
                cname = entry.split('class ')[-1].split(' -')[0].split('(')[0].strip()
                if cname and cname not in seen and not cname.startswith('_'):
                    seen.add(cname)
                    features_en.append(f"**{cname}** module")
                    features_ar.append(f"مكوّن **{cname}**")

        # أضف ميزات من الدوال المهمة
        for entry in a['functions'][:20]:
            if ' — ' in entry and len(features_en) < 10:
                parts = entry.split(' — ', 1)
                fname = parts[0].strip().split('.')[-1].replace('()', '').strip()
                desc = parts[1].strip()
                if len(desc) > 15 and not fname.startswith('_') and fname not in seen:
                    seen.add(fname)
                    features_en.append(f"**{fname}** — {desc}")
                    features_ar.append(f"**{fname}** — {desc}")

        # ميزات بنيوية
        if a['has_docker']:
            features_en.insert(0, '**Docker Support** — Containerized deployment ready')
            features_ar.insert(0, '**دعم Docker** — جاهز للنشر في حاويات')
        if a['has_tests']:
            features_en.insert(0, '**Automated Testing** — Comprehensive test suite included')
            features_ar.insert(0, '**اختبارات تلقائية** — مجموعة اختبارات شاملة')
        if a['has_ci']:
            features_en.insert(0, '**CI/CD Pipeline** — Automated build and deployment')
            features_ar.insert(0, '**CI/CD** — بناء ونشر تلقائي')

        if not features_en:
            features_en = [f'**{pt}** — {files} files, {size}']
            features_ar = [f'**{pt}** — {files} ملف، {size}']

        fe = NL.join(f'- {f}' for f in features_en[:10])
        fa = NL.join(f'- {f}' for f in features_ar[:10])

        # ── وصف ذكي للمشروع ──────────────────────────────────
        desc_en = a.get('description') or ''
        desc_ar = ''
        if not desc_en:
            # بناء وصف من التحليل
            mods = [_P(f).stem for f in list(a['main_files'].keys())[:3]]
            sections = a.get('sections', [])
            sec_names = [s.split(']')[-1].strip() for s in sections[:4] if ']' in s and s.split(']')[-1].strip()]

            desc_en = f"{name} is a {pt} project with {files} files ({size})."
            desc_ar = f"{name} هو مشروع {pt} يتكون من {files} ملف ({size})."
            if sec_names:
                desc_en += f" It includes: {', '.join(sec_names)}."
                desc_ar += f" يتضمن: {', '.join(sec_names)}."
            elif mods:
                desc_en += f" Core modules: {', '.join(mods)}."
                desc_ar += f" الوحدات الأساسية: {', '.join(mods)}."
        else:
            desc_ar = desc_en  # fallback

        # ── Tech Stack ────────────────────────────────────────
        stack = [lib for lib in a['tech_stack'][:12] if lib not in ('General',)]
        if not stack:
            stack = [pt.split('(')[-1].rstrip(')') if '(' in pt else pt]

        ROLES_EN = {
            'pandas':'Data manipulation & analysis','numpy':'Numerical computing',
            'requests':'HTTP client','flask':'Web framework','django':'Full-stack web',
            'fastapi':'Async API framework','pytest':'Testing framework','tkinter':'GUI toolkit',
            'PyQt6':'Modern GUI framework','PyQt5':'GUI framework','xxhash':'Ultra-fast hashing',
            'psutil':'System monitoring','cryptography':'Encryption & security',
            'sqlalchemy':'ORM / Database','pillow':'Image processing','PIL':'Image processing',
        }
        ROLES_AR = {
            'pandas':'تحليل البيانات','numpy':'حوسبة عددية',
            'requests':'عميل HTTP','flask':'إطار ويب','django':'إطار ويب متكامل',
            'fastapi':'إطار API غير متزامن','pytest':'إطار اختبارات','tkinter':'واجهة رسومية',
            'PyQt6':'إطار واجهة حديث','PyQt5':'إطار واجهة','xxhash':'تجزئة فائقة السرعة',
            'psutil':'مراقبة النظام','cryptography':'تشفير وأمان',
            'sqlalchemy':'قاعدة بيانات ORM','pillow':'معالجة صور','PIL':'معالجة صور',
        }

        te = f'| Technology | Purpose |{NL}|---|---|{NL}'
        ta = f'| التقنية | الغرض |{NL}|---|---|{NL}'
        for lib in stack:
            te += f'| `{lib}` | {ROLES_EN.get(lib, "Core dependency")} |{NL}'
            ta += f'| `{lib}` | {ROLES_AR.get(lib, "مكتبة أساسية")} |{NL}'

        # ── Badges ────────────────────────────────────────────
        lang_badge = a['type'].split('(')[0].strip().split('/')[0].strip()
        if lang_badge == 'General':
            lang_badge = 'Python' if any('.py' in str(e) for e in a.get('main_files', {})) else 'Code'

        badges = (
            f'![{lang_badge}](https://img.shields.io/badge/{lang_badge}-blue?logo=python&logoColor=white) '
            f'![Files](https://img.shields.io/badge/Files-{files}-informational) '
            f'![Size](https://img.shields.io/badge/Size-{size.replace(" ", "%20")}-green)'
        )

        # ── Usage Guide ──────────────────────────────────────
        usage_en = f'```bash{NL}{run}{NL}```'
        usage_ar = f'```bash{NL}{run}{NL}```'

        # بناء دليل استخدام حقيقي من أسماء الكلاسات
        usage_sections_en = []
        usage_sections_ar = []
        for entry in a['classes'][:6]:
            if ' — ' in entry:
                parts = entry.split(' — ', 1)
                cname = parts[0].split('class ')[-1].strip() if 'class ' in parts[0] else ''
                desc = parts[1].strip()
                if cname and len(desc) > 10 and not cname.startswith('_'):
                    usage_sections_en.append(f"**{cname}**: {desc}")
                    usage_sections_ar.append(f"**{cname}**: {desc}")

        if usage_sections_en:
            usage_en += f'{NL}{NL}### Key Components{NL}{NL}'
            usage_en += NL.join(f'- {s}' for s in usage_sections_en)
            usage_ar += f'{NL}{NL}### المكونات الرئيسية{NL}{NL}'
            usage_ar += NL.join(f'- {s}' for s in usage_sections_ar)

        # ── معلومات المطور ────────────────────────────────────
        d = self._merged_dev()
        wa = d.get('whatsapp', '').replace('+', '').replace(' ', '')
        gh = d.get('github', '').lstrip('@')
        em = d.get('email', '')
        yt = d.get('youtube', '').strip()
        ig = d.get('instagram', '').lstrip('@')
        tg = d.get('telegram', '').lstrip('@')
        tw = d.get('twitter', '').lstrip('@')

        def badge(label, color, logo, url, text):
            safe = text.replace('@', '%40').replace('+', '%2B').replace(' ', '%20')
            lbl  = label.replace(' ', '%20')
            return f'[![{label}](https://img.shields.io/badge/{lbl}-{safe}-{color}?logo={logo}&logoColor=white)]({url})'

        aen = aar = ''
        if d.get('name'):
            aen  = f'{NL}## 👨‍💻 Author{NL}{NL}'
            aar  = f'{NL}## 👨‍💻 المطور{NL}{NL}'
            contacts_en = []
            contacts_ar = []
            if em:
                b = badge('Gmail', 'D14836', 'gmail', f'mailto:{em}', em)
                contacts_en.append(b)
                contacts_ar.append(b)
            if gh:
                b = badge('GitHub', '181717', 'github', f'https://github.com/{gh}', gh)
                contacts_en.append(b)
                contacts_ar.append(b)
            if wa:
                b = badge('WhatsApp', '25D366', 'whatsapp', f'https://wa.me/{wa}', f'+{wa}')
                contacts_en.append(b)
                contacts_ar.append(b)
            if yt:
                yt_url = yt if yt.startswith('http') else f'https://youtube.com/@{yt.lstrip("@")}'
                contacts_en.append(badge('YouTube', 'FF0000', 'youtube', yt_url, 'Channel'))
                contacts_ar.append(badge('YouTube', 'FF0000', 'youtube', yt_url, 'Channel'))
            if ig:
                contacts_en.append(badge('Instagram', 'E4405F', 'instagram', f'https://instagram.com/{ig}', f'@{ig}'))
                contacts_ar.append(badge('Instagram', 'E4405F', 'instagram', f'https://instagram.com/{ig}', f'@{ig}'))
            if tg:
                contacts_en.append(badge('Telegram', '2CA5E0', 'telegram', f'https://t.me/{tg}', f'@{tg}'))
                contacts_ar.append(badge('Telegram', '2CA5E0', 'telegram', f'https://t.me/{tg}', f'@{tg}'))
            if tw:
                contacts_en.append(badge('Twitter', '1DA1F2', 'twitter', f'https://twitter.com/{tw}', f'@{tw}'))
                contacts_ar.append(badge('Twitter', '1DA1F2', 'twitter', f'https://twitter.com/{tw}', f'@{tw}'))
            pp = d.get('paypal', '').strip()
            if pp:
                contacts_en.append(badge('PayPal', '003087', 'paypal', pp, 'Donate'))
                contacts_ar.append(badge('PayPal', '003087', 'paypal', pp, 'Donate'))

            aen += f'**{d["name"]}**{NL}{NL}'
            aar += f'**{d["name"]}**{NL}{NL}'
            if contacts_en:
                aen += ' '.join(contacts_en) + NL
                aar += ' '.join(contacts_ar) + NL

            ref = f'mailto:{em}' if em else (f'https://github.com/{gh}' if gh else '#')
            aen += f'{NL}---{NL}<p align="center">Made with ❤️ by <a href="{ref}"><b>{d["name"]}</b></a></p>{NL}'
            aar += f'{NL}---{NL}<p align="center">صُنع بـ ❤️ بواسطة <a href="{ref}"><b>{d["name"]}</b></a></p>{NL}'

        # ── بناء README النهائي ──────────────────────────────
        if lang == 'en':
            return (
                f'# {name}{NL}{NL}'
                f'{badges}{NL}{NL}'
                f'> {desc_en}{NL}{NL}'
                f'---{NL}{NL}'
                f'## ✨ Features{NL}{NL}{fe}{NL}{NL}'
                f'## 🛠 Tech Stack{NL}{NL}{te}{NL}'
                f'## 📁 Project Structure{NL}{NL}```{NL}{a["tree"]}{NL}```{NL}{NL}'
                f'## ⚙️ Prerequisites{NL}{NL}'
                f'- Python 3.8+{NL}'
                f'- Git installed and in PATH{NL}{NL}'
                f'## 🚀 Installation{NL}{NL}'
                f'```bash{NL}'
                f'# Clone the repository{NL}'
                f'git clone https://github.com/{gh}/{name}.git{NL}'
                f'cd {name}{NL}{NL}'
                f'# Install dependencies{NL}'
                f'{inst}{NL}'
                f'```{NL}{NL}'
                f'## ▶️ Usage{NL}{NL}{usage_en}{NL}{NL}'
                + (f'## 🧪 Testing{NL}{NL}```bash{NL}pytest tests/ -v{NL}```{NL}{NL}' if a['has_tests'] else '')
                + f'## 🤝 Contributing{NL}{NL}'
                f'1. Fork the repository{NL}'
                f'2. Create your feature branch: `git checkout -b feat/my-feature`{NL}'
                f'3. Commit your changes: `git commit -m "feat: add amazing feature"`{NL}'
                f'4. Push to the branch: `git push origin feat/my-feature`{NL}'
                f'5. Open a Pull Request{NL}{NL}'
                f'## 📄 License{NL}{NL}MIT — see [LICENSE](LICENSE){NL}'
                f'{aen}'
            )
        else:
            return (
                f'# {name}{NL}{NL}'
                f'{badges}{NL}{NL}'
                f'> {desc_ar}{NL}{NL}'
                f'---{NL}{NL}'
                f'## ✨ المميزات{NL}{NL}{fa}{NL}{NL}'
                f'## 🛠 التقنيات المستخدمة{NL}{NL}{ta}{NL}'
                f'## 📁 هيكل المشروع{NL}{NL}```{NL}{a["tree"]}{NL}```{NL}{NL}'
                f'## ⚙️ المتطلبات الأساسية{NL}{NL}'
                f'- Python 3.8+{NL}'
                f'- Git مُثبّت في PATH{NL}{NL}'
                f'## 🚀 التثبيت{NL}{NL}'
                f'```bash{NL}'
                f'# استنساخ المستودع{NL}'
                f'git clone https://github.com/{gh}/{name}.git{NL}'
                f'cd {name}{NL}{NL}'
                f'# تثبيت المتطلبات{NL}'
                f'{inst}{NL}'
                f'```{NL}{NL}'
                f'## ▶️ طريقة الاستخدام{NL}{NL}{usage_ar}{NL}{NL}'
                + (f'## 🧪 الاختبارات{NL}{NL}```bash{NL}pytest tests/ -v{NL}```{NL}{NL}' if a['has_tests'] else '')
                + f'## 🤝 المساهمة{NL}{NL}'
                f'1. Fork المستودع{NL}'
                f'2. أنشئ فرع الميزة: `git checkout -b feat/ميزتي`{NL}'
                f'3. سجّل التغييرات: `git commit -m "feat: إضافة ميزة رائعة"`{NL}'
                f'4. ارفع الفرع: `git push origin feat/ميزتي`{NL}'
                f'5. افتح Pull Request{NL}{NL}'
                f'## 📄 الترخيص{NL}{NL}رخصة MIT — راجع [LICENSE](LICENSE){NL}'
                f'{aar}'
            )
    def _log(self, m, l='info'):
        if self.cb:
            try:
                self.cb(m, l, None)   # واجهة تقبل 3 مُعاملات (message, level, extra)
            except TypeError:
                self.cb(m)            # واجهة تقبل مُعامل واحد فقط (github_panel)





# ═════════════════════════════════════════════════════
# [18/19] REPO MANAGER
# إدارة المستودعات البعيدة
# ═════════════════════════════════════════════════════




