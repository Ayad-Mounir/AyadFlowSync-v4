#!/usr/bin/env python3
"""
security.security — SecureStore (redirected), MultiKeyStore, 
AppSettings, History, AnalysisCache, TokenScopeChecker
"""

import os
import sys
import json
import time
import hashlib
import hmac
import threading
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.app_config import AppConfig
from ..core.constants import APP_NAME

_logger = logging.getLogger("AyadFlowSync.security")

DATA_DIR = AppConfig.DATA_DIR


class SecureStore:
    """⚠️ REDIRECTED → security.secure_store.SecureStore (PBKDF2 + HMAC).
    This wrapper ensures old code calling security.security.SecureStore
    automatically uses the new encrypted version."""
    
    _REDIRECTED = True
    
    @staticmethod
    def _new():
        from .secure_store import SecureStore as _New
        return _New
    
    # ── حفظ وتحميل (redirect) ────────────────────────────
    @classmethod
    def save_token(cls, filepath, token, **kw):
        return cls._new().save(filepath, token, extra=kw)
    
    @classmethod
    def load_token(cls, filepath):
        return cls._new().load(filepath)
    
    @classmethod
    def save(cls, filepath, plaintext, **kw):
        return cls._new().save(filepath, plaintext, extra=kw)
    
    @classmethod
    def load(cls, filepath):
        return cls._new().load(filepath)
    
    @classmethod
    def delete(cls, filepath):
        return cls._new().delete(filepath)
    
    # ── PIN support (redirect) ────────────────────────────
    @staticmethod
    def set_master_pin(pin):
        from .secure_store import SecureStore as _New
        _New.set_master_pin(pin)
    
    @staticmethod
    def clear_master_pin():
        from .secure_store import SecureStore as _New
        _New.clear_master_pin()
    
    # ── Legacy methods (backward compat) ──────────────────
    @classmethod
    def encrypt(cls, data: str, filepath=None) -> str:
        """Legacy: encrypt string. If filepath given, also saves."""
        if filepath:
            cls._new().save(filepath, data)
        return data  # Return original for in-memory use
    
    @classmethod
    def decrypt(cls, filepath) -> str:
        """Legacy: decrypt from file."""
        result = cls._new().load(filepath)
        return result or ""





class MultiKeyStore:
    """تخزين مفاتيح كل مزودي الذكاء الاصطناعي في ملف واحد مشفر — v10.1
    مفتاح لكل مزود، محفوظ في data/.ai_keys_enc على الفلاشة"""

    def __init__(self):
        self._store = SecureStore(AI_KEYS_FILE, "multi_ai_keys")
        self._keys = self._load()

    def _load(self):
        raw, _ = self._store.load()
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return {}

    def _flush(self):
        self._store.save(json.dumps(self._keys))

    def set(self, provider, key):
        """حفظ مفتاح مزود معين"""
        if key and key.strip():
            self._keys[provider] = key.strip()
        else:
            self._keys.pop(provider, None)
        self._flush()

    def get(self, provider):
        """جلب مفتاح مزود معين"""
        return self._keys.get(provider, '')

    def all(self):
        """كل المفاتيح المحفوظة"""
        return dict(self._keys)

    def has(self, provider):
        return bool(self._keys.get(provider, ''))

    def providers_available(self):
        """قائمة المزودين المتاحين"""
        PRIORITY = ['gemini', 'claude', 'deepseek', 'openai']
        return [p for p in PRIORITY if self._keys.get(p)]


_NET_CACHE: dict = {'result': None, 'at': 0.0, 'bool': False}
_NET_TTL = 30.0   # FIX 10: كاش 30 ثانية — حالة الشبكة لا تتغير كل ثانية

def check_net(timeout=5):
    """فحص الاتصال بالإنترنت — cached 30s"""
    now = time.monotonic()
    if _NET_CACHE['result'] is not None and (now - _NET_CACHE['at']) < _NET_TTL:
        return _NET_CACHE['bool']
    ok = False
    for host, port in [('1.1.1.1', 53), ('8.8.8.8', 53)]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout); s.connect((host, port)); s.close()
            ok = True; break
        except OSError: continue
    if not ok:
        try:
            r = requests.head('https://www.google.com', timeout=timeout)
            ok = r.status_code < 500
        except: pass
    _NET_CACHE['result'] = ok; _NET_CACHE['at'] = time.monotonic(); _NET_CACHE['bool'] = ok
    return ok




# ═════════════════════════════════════════════════════
# [6/19] APP SETTINGS & HISTORY
# إعدادات البرنامج وسجل العمليات
# ═════════════════════════════════════════════════════

class AppSettings:
    """إعدادات البرنامج المستمرة — تشمل إعدادات UI وإعدادات المشروع المتقدمة"""

    DEFAULTS = {
        'ui_mode': 'advanced',
        'theme': 'dark',
        'lang': 'ar',
        'git_protocol': 'https',
        'pin_enabled': False,
        'notify_sync': True,
        # v8.5: إعدادات متقدمة محفوظة (كانت تضيع عند الإغلاق)
        'last_description': '',
        'last_topics': '',
        'last_commit_msg': '',
        'last_license': 'MIT',
        'last_lfs': True,
        'last_issues': True,
        'last_wiki': False,
        'last_pages': False,
        'last_conflict': 'merge',
        'last_organization': None,
        'preferred_ai_provider': 'auto',
        'dev_info': {
            'name':      'Ayad Mounir',
            'github':    'Ayad-Mounir',
            'email':     'contact.ayad.mounir@gmail.com',
            'whatsapp':  '+212653867667',
            'telegram':  'Mounir_AyadD',
            'paypal':    'https://paypal.me/MounirAyaad?locale.x=ar_EG&country.x=MA',
            'website':   '',
            'youtube':   '',
            'instagram': '',
            'twitter':   '',
        },
    }

    # الاعدادات المحلية - خاصة بهذا الجهاز فقط
    LOCAL_DEFAULTS = {
        'window_geometry': None,
        'last_project':    None,
        'parent_folder':   None,    # قديم — يُهاجَر تلقائياً إلى parent_folders
        'parent_folders':  [],      # قائمة المجلدات الأم: [{path, name, collapsed}]
    }

    def __init__(self):
        self._lock = threading.Lock()
        self.data = {**self.DEFAULTS}
        self._local = {**self.LOCAL_DEFAULTS}
        self._load()
        self._load_local()

    def _load(self):
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, 'r') as f:
                    saved = json.load(f)
                    self.data.update(saved)
        except Exception as e:
            logger.error(f"AppSettings load: {e}")

    def _load_local(self):
        try:
            lf = DATA_DIR / 'local_prefs.json'   # ✅ على الفلاشة — ينتقل مع الجهاز
            if lf.exists():
                with open(lf) as f:
                    self._local.update(json.load(f))
        except Exception:
            pass
        # ── هجرة تلقائية: parent_folder (قديم) → parent_folders (جديد) ──
        old = self._local.get('parent_folder')
        existing = self._local.get('parent_folders', [])
        if old and isinstance(old, str) and not any(p['path'] == old for p in existing):
            existing.append({
                'path':      old,
                'name':      Path(old).name,
                'collapsed': False,
            })
            self._local['parent_folders'] = existing
            self._local['parent_folder']  = None   # امسح القديم

    def save_local(self, key, val):
        """حفظ تفضيل على الفلاشة — ينتقل مع الفلاشة لأي جهاز"""
        self._local[key] = val
        try:
            lf = DATA_DIR / 'local_prefs.json'   # ✅ على الفلاشة
            with open(lf, 'w') as f:
                json.dump(self._local, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_local(self, key):
        return self._local.get(key, self.LOCAL_DEFAULTS.get(key))

    def save(self):
        """حفظ الاعدادات على الفلاشة - thread-safe"""
        with self._lock:
            try:
                with open(SETTINGS_FILE, 'w') as f:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"AppSettings save: {e}")

    def get(self, key, default=None):
        result = self.data.get(key, self.DEFAULTS.get(key))
        if result is None:
            return default
        return result

    def set(self, key, val):
        self.data[key] = val
        self.save()

    def set_many(self, updates):
        """تحديث عدة إعدادات دفعة واحدة (أفضل أداء)"""
        self.data.update(updates)
        self.save()

    def export_all(self, filepath):
        """تصدير كل الإعدادات + الملفات الشخصية لملف واحد"""
        try:
            bundle = {'settings': self.data, 'profiles': {}, 'autosync': {}}
            if PROFILES_FILE.exists():
                with open(PROFILES_FILE, 'r') as f:
                    bundle['profiles'] = json.load(f)
            if AUTOSYNC_FILE.exists():
                with open(AUTOSYNC_FILE, 'r') as f:
                    bundle['autosync'] = json.load(f)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(bundle, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False

    def import_all(self, filepath):
        """استيراد الإعدادات من ملف"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                bundle = json.load(f)
            if 'settings' in bundle:
                self.data.update(bundle['settings'])
                self.save()
            if 'profiles' in bundle:
                with open(PROFILES_FILE, 'w') as f:
                    json.dump(bundle['profiles'], f, indent=2)
            if 'autosync' in bundle:
                with open(AUTOSYNC_FILE, 'w') as f:
                    json.dump(bundle['autosync'], f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return False





class History:
    """سجل العمليات الدائم — v13: Debounced write لتقليل I/O على الفلاشة.
    كتابة واحدة بعد 2 ثانية من آخر تعديل بدل كتابة على كل عملية."""

    MAX_RECORDS = 500
    _WRITE_DELAY = 2.0   # ثانيتان debounce

    def __init__(self):
        self._lock = threading.Lock()
        self._dirty = False
        self._timer = None
        self.records = self._load()

    def _load(self):
        try:
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
        except Exception as e:
            logger.error(f"History load: {e}")
        return []

    def _schedule_save(self):
        """جدوِل كتابة واحدة بعد WRITE_DELAY — ألغِ أي كتابة سابقة"""
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self._WRITE_DELAY, self._flush)
        self._timer.daemon = True
        self._timer.start()

    def _flush(self):
        """كتابة فعلية للقرص — مرة واحدة بعد هدوء العمليات"""
        with self._lock:
            if not self._dirty:
                return
            try:
                self.records = self.records[-self.MAX_RECORDS:]
                with open(HISTORY_FILE, 'w') as f:
                    json.dump(self.records, f, indent=2)
                self._dirty = False
            except Exception as e:
                logger.error(f"History flush: {e}")

    def _save(self):
        """للتوافق مع الكود القديم — يُجدول كتابة مؤجلة"""
        self._schedule_save()

    def add(self, op_type, name, success, details=""):
        """إضافة سجل عملية"""
        with self._lock:
            self.records.append({
                'time': datetime.now().isoformat(),
                'type': op_type,
                'name': name,
                'success': success,
                'details': str(details)[:200],
            })
            self._dirty = True
        self._schedule_save()

    def get_all(self):
        return list(reversed(self.records))

    def clear(self):
        with self._lock:
            self.records = []
            self._dirty = True
        self._flush()

    def search(self, query):
        q = query.lower()
        return [
            r for r in reversed(self.records)
            if q in r.get('name', '').lower() or q in r.get('type', '').lower()
        ]

    def close(self):
        """استدعِه عند إغلاق البرنامج لضمان كتابة آخر التغييرات"""
        if self._timer:
            self._timer.cancel()
        self._flush()





class AnalysisCache:
    """كاش تحليل المشاريع — v13: بصمة سريعة بـ iterdir() بدل فحص كل الملفات"""

    MAX_ENTRIES = 20

    def __init__(self):
        self._lock = threading.Lock()
        self.cache = self._load()

    def _load(self):
        try:
            if CACHE_FILE.exists():
                with open(CACHE_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Cache load: {e}")
        return {}

    def _save(self):
        with self._lock:
            try:
                keys = list(self.cache.keys())
                if len(keys) > self.MAX_ENTRIES:
                    for k in keys[:-self.MAX_ENTRIES]:
                        del self.cache[k]
                with open(CACHE_FILE, 'w') as f:
                    json.dump(self.cache, f)
            except Exception as e:
                logger.error(f"Cache save: {e}")

    def get(self, project_path):
        """جلب التحليل المحفوظ إذا لم يتغير المشروع"""
        key = str(project_path)
        if key not in self.cache:
            return None
        cached = self.cache[key]
        try:
            sig = self._fast_sig(project_path)
            if sig != cached.get('sig'):
                return None
            return cached.get('analysis')
        except Exception:
            return None

    def put(self, project_path, analysis):
        """حفظ التحليل في الكاش"""
        key = str(project_path)
        self.cache[key] = {
            'sig':      self._fast_sig(project_path),
            'analysis': analysis,
            'cached_at': datetime.now().isoformat(),
        }
        self._save()

    @staticmethod
    def _fast_sig(path):
        """
        FIX 6: بصمة سريعة — iterdir() على الجذر فقط بدل فحص كل الملفات.
        أسرع 100x: ~0.5ms بدل ~50ms على الفلاشة.
        دقيقة كافية: أي تغيير في الجذر يُكتشف، وتغيير المجلدات
        يُغيّر mtime الجذر على NTFS/ext4 تلقائياً.
        """
        try:
            p = Path(path)
            entries = list(p.iterdir())
            root_mtime = p.stat().st_mtime
            count = len(entries)
            max_child = max(
                (e.stat().st_mtime for e in entries if e.is_file()),
                default=0.0
            )
            return f"{root_mtime:.2f}_{count}_{max_child:.2f}"
        except Exception:
            return str(time.time())





# ═════════════════════════════════════════════════════
# [7/19] TOKEN SCOPE CHECKER
# فحص صلاحيات التوكن
# ═════════════════════════════════════════════════════

class TokenScopeChecker:
    """فحص صلاحيات التوكن بالتفصيل وإرجاع تقرير"""

    REQUIRED = {'repo': 'Create/push repos', 'delete_repo': 'Delete repos'}
    OPTIONAL = {'admin:org': 'Manage orgs', 'read:org': 'Read orgs', 'workflow': 'GitHub Actions'}

    @staticmethod
    def check(token):
        try:
            r = requests.get(
                'https://api.github.com/user',
                headers={'Authorization': f'Bearer {token}'},
                timeout=10
            )
            if r.status_code != 200:
                return {'valid': False, 'error': f'HTTP {r.status_code}'}
            scopes = [s.strip() for s in r.headers.get('X-OAuth-Scopes', '').split(',') if s.strip()]
            report = {
                'valid': True, 'scopes': scopes, 'user': r.json(),
                'required_ok': {}, 'required_missing': {},
                'optional_ok': {}, 'optional_missing': {}
            }
            for s, d in TokenScopeChecker.REQUIRED.items():
                target = report['required_ok'] if s in scopes else report['required_missing']
                target[s] = d
            for s, d in TokenScopeChecker.OPTIONAL.items():
                target = report['optional_ok'] if s in scopes else report['optional_missing']
                target[s] = d
            report['all_required'] = len(report['required_missing']) == 0
            return report
        except Exception as e:
            logger.error(f"TokenCheck: {e}")
            return {'valid': False, 'error': str(e)}

    @staticmethod
    def get_create_url():
        scopes = ','.join(list(TokenScopeChecker.REQUIRED) + list(TokenScopeChecker.OPTIONAL))
        return f'https://github.com/settings/tokens/new?scopes={scopes}&description=Ayad FlowSync'





# ═════════════════════════════════════════════════════
# [8/19] GIT RUNNER (SHARED)
# تنفيذ أوامر Git — كلاس مشترك بدل التكرار
# ═════════════════════════════════════════════════════

