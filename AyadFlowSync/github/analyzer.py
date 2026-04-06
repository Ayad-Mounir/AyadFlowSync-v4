#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_github_analyzer — ProjectAnalyzer
تحليل المشاريع: Python/JS/Java/Go/Rust/C++/C#/Dart/PHP/Ruby/HTML
"""
import os
import re
import json
import fnmatch
import logging as _logging_mod
from pathlib import Path

_logger = _logging_mod.getLogger("AyadFlowSync")
logger  = _logger

from .ops import Auth, ProjectInspector, LFS, Uploader, Cloner, Batch
from ..core.constants import IGNORED_DIRS
class ProjectAnalyzer:
    """تحليل عميق للمشروع: النوع، المكتبات، الكلاسات، الدوال"""

    CONFIG_FILES = [
        'package.json', 'requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile',
        'Cargo.toml', 'go.mod', 'pubspec.yaml', 'composer.json', 'Gemfile',
        'pom.xml', 'build.gradle', 'build.gradle.kts', 'CMakeLists.txt', 'Makefile',
        'Dockerfile', 'docker-compose.yml', '*.csproj', '*.sln',
        # v10.7: إضافات
        'tsconfig.json', 'vite.config.js', 'vite.config.ts',
        'next.config.js', 'next.config.ts', 'nuxt.config.js', 'nuxt.config.ts',
        'webpack.config.js', 'rollup.config.js', 'angular.json',
        '.env.example', 'config.yaml', 'config.yml',
        'Procfile', 'vercel.json', 'netlify.toml',
    ]
    MAIN_FILES = [
        'main.py', 'app.py', 'index.py', 'manage.py', 'wsgi.py', 'asgi.py',
        'main.js', 'index.js', 'app.js', 'server.js', 'main.ts', 'index.ts', 'app.ts',
        'App.jsx', 'App.tsx', 'App.vue', 'App.svelte',
        'main.go', 'main.rs', 'lib.rs', 'main.dart', 'Main.java', 'main.cpp', 'main.c',
        'Program.cs', 'Startup.cs',
        # v10.7: إضافات
        'index.html', 'index.php', 'routes.rb', 'app.rb',
        'main.kt', 'Application.kt', 'Main.kt',
    ]

    def __init__(self, path):
        self.path = path
        self.name = Path(path).name

    def analyze(self):
        result = {
            'name': self.name, 'tree': self._tree(), 'type': 'Unknown',
            'configs': {}, 'main_files': {}, 'functions': [], 'classes': [],
            'stats': {'files': 0, 'size': 0, 'exts': {}}, 'tech_stack': [],
            'has_tests': False, 'has_docker': False, 'has_ci': False,
            'description': '', 'scripts': {},
            '_path': self.path,  # مطلوب لـ _ctx لقراءة الملفات الكبيرة
        }

        # v10.7: تتبع أكبر ملف كود لاكتشافه كـ main file إذا لم يُعثر على ملف قياسي
        _largest_code = {'path': None, 'rel': None, 'size': 0}
        _CODE_EXTS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java', '.cpp', '.c', '.cs', '.dart'}

        for root, dirs, files in os.walk(self.path):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and d != '.git']
            for f in files:
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, self.path)
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    continue
                result['stats']['files'] += 1
                result['stats']['size'] += sz
                ext = os.path.splitext(f)[1].lower()
                result['stats']['exts'][ext] = result['stats']['exts'].get(ext, 0) + 1

                # v10.7: تتبع أكبر ملف كود
                if ext in _CODE_EXTS and sz > _largest_code['size']:
                    _largest_code = {'path': fp, 'rel': rel, 'size': sz}

                for pat in self.CONFIG_FILES:
                    if fnmatch.fnmatch(f, pat):
                        try:
                            result['configs'][rel] = Path(fp).read_text('utf-8', errors='ignore')[:3000]
                        except Exception:
                            pass
                        break
                if f in self.MAIN_FILES:
                    try:
                        lines = Path(fp).read_text('utf-8', errors='ignore').split('\n')[:200]
                        result['main_files'][rel] = '\n'.join(lines)
                    except Exception:
                        pass
                if ext == '.py' and sz < 500000:
                    self._py(fp, rel, result)
                if ext in ('.js', '.ts', '.jsx', '.tsx') and sz < 500000:
                    self._js(fp, rel, result)
                # v10.7: محللات لغات إضافية
                if ext in ('.java', '.kt', '.kts') and sz < 500000:
                    self._java(fp, rel, result)
                if ext == '.go' and sz < 500000:
                    self._go(fp, rel, result)
                if ext == '.rs' and sz < 500000:
                    self._rust(fp, rel, result)
                if ext in ('.c', '.cpp', '.cc', '.cxx', '.h', '.hpp') and sz < 500000:
                    self._c_cpp(fp, rel, result)
                if ext == '.cs' and sz < 500000:
                    self._csharp(fp, rel, result)
                if ext == '.dart' and sz < 500000:
                    self._dart(fp, rel, result)
                if ext == '.php' and sz < 500000:
                    self._php(fp, rel, result)
                if ext == '.rb' and sz < 500000:
                    self._ruby(fp, rel, result)
                if ext in ('.html', '.htm') and sz < 200000:
                    self._html(fp, rel, result)
                if 'test' in rel.lower() or 'spec' in rel.lower():
                    result['has_tests'] = True
                if f in ('Dockerfile', 'docker-compose.yml'):
                    result['has_docker'] = True
                if rel.startswith('.github/') or f in ('.gitlab-ci.yml', 'Jenkinsfile'):
                    result['has_ci'] = True

        # v10.7: إذا لم يُعثر على main file قياسي، استخدم أكبر ملف كود
        if not result['main_files'] and _largest_code['path']:
            try:
                lines = Path(_largest_code['path']).read_text('utf-8', errors='ignore').split('\n')[:200]
                result['main_files'][_largest_code['rel']] = '\n'.join(lines)
            except Exception:
                pass

        if 'package.json' in result['configs']:
            try:
                pkg = json.loads(result['configs']['package.json'])
                result['description'] = pkg.get('description', '')
                result['scripts'] = pkg.get('scripts', {})
                result['tech_stack'].extend(list(pkg.get('dependencies', {}).keys())[:15])
            except Exception:
                pass
        if 'requirements.txt' in result['configs']:
            for line in result['configs']['requirements.txt'].split('\n')[:20]:
                pkg = line.split('==')[0].split('>=')[0].strip()
                if pkg and not pkg.startswith('#'):
                    result['tech_stack'].append(pkg)

        # v10.7: استخراج المكتبات من أنظمة بيئات إضافية
        # Go modules
        if 'go.mod' in result['configs']:
            for line in result['configs']['go.mod'].split('\n'):
                s = line.strip()
                if s and not s.startswith('//') and not s.startswith('module') \
                   and not s.startswith('go ') and not s.startswith(')') and s != '(':
                    if s.startswith('require'):
                        s = s.replace('require', '').strip().strip('(')
                    pkg = s.split()[0] if s.split() else ''
                    if '/' in pkg:
                        result['tech_stack'].append(pkg.split('/')[-1])

        # Rust Cargo.toml
        if 'Cargo.toml' in result['configs']:
            in_deps = False
            for line in result['configs']['Cargo.toml'].split('\n'):
                s = line.strip()
                if s.startswith('[') and 'dependencies' in s.lower():
                    in_deps = True
                    continue
                elif s.startswith('['):
                    in_deps = False
                if in_deps and '=' in s and not s.startswith('#'):
                    pkg = s.split('=')[0].strip()
                    if pkg:
                        result['tech_stack'].append(pkg)
                # Package description
                if s.startswith('description') and not result.get('description'):
                    m = re.search(r'"(.*?)"', s)
                    if m:
                        result['description'] = m.group(1)

        # Flutter/Dart pubspec.yaml
        if 'pubspec.yaml' in result['configs']:
            in_deps = False
            for line in result['configs']['pubspec.yaml'].split('\n'):
                if line.strip().startswith('dependencies:') or line.strip().startswith('dev_dependencies:'):
                    in_deps = True
                    continue
                elif line and not line.startswith(' ') and not line.startswith('\t'):
                    in_deps = False
                if in_deps and ':' in line and line.startswith('  '):
                    pkg = line.strip().split(':')[0].strip()
                    if pkg and not pkg.startswith('#') and pkg != 'flutter':
                        result['tech_stack'].append(pkg)
                # Description
                if line.strip().startswith('description:') and not result.get('description'):
                    desc = line.split(':', 1)[1].strip().strip('"').strip("'")
                    if desc:
                        result['description'] = desc

        # PHP composer.json
        if 'composer.json' in result['configs']:
            try:
                pkg = json.loads(result['configs']['composer.json'])
                if not result.get('description'):
                    result['description'] = pkg.get('description', '')
                for dep in list(pkg.get('require', {}).keys())[:15]:
                    if dep != 'php' and not dep.startswith('ext-'):
                        result['tech_stack'].append(dep.split('/')[-1])
            except Exception:
                pass

        # Ruby Gemfile
        if 'Gemfile' in result['configs']:
            for line in result['configs']['Gemfile'].split('\n'):
                m = re.match(r"^\s*gem\s+['\"](\w[\w-]*)['\"]", line)
                if m:
                    result['tech_stack'].append(m.group(1))

        # C# .csproj
        for cfg_name, cfg_content in result['configs'].items():
            if cfg_name.endswith('.csproj'):
                for m in re.finditer(r'<PackageReference\s+Include="([\w.]+)"', cfg_content):
                    result['tech_stack'].append(m.group(1))

        result['type'] = self._detect(result)
        result['tech_stack'] = list(set(result['tech_stack']))[:20]

        # استخراج الـ docstring من الملف الرئيسي كوصف للمشروع
        if not result['description']:
            for rel, txt in result['main_files'].items():
                lines = txt.split('\n')
                # ابحث عن أول docstring بين ''' أو """
                in_doc = False
                doc_lines = []
                for line in lines[:50]:
                    stripped = line.strip()
                    if not in_doc and stripped.startswith(('"""', "'''")):
                        in_doc = True
                        inner = stripped[3:]
                        if inner:
                            doc_lines.append(inner)
                        if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                            in_doc = False
                            break
                    elif in_doc:
                        if '"""' in stripped or "'''" in stripped:
                            inner = stripped.replace('"""','').replace("'''","").strip()
                            if inner:
                                doc_lines.append(inner)
                            break
                        doc_lines.append(stripped)
                if doc_lines:
                    result['description'] = ' '.join(doc_lines[:5])[:400]
                    break

        # استخراج أقسام الملف الكبير (السطور التي تبدأ بـ # ═══)
        result['sections'] = []
        for rel, txt in result['main_files'].items():
            for line in txt.split('\n'):
                if '═' in line or ('# [' in line and '/' in line):
                    clean = line.strip().lstrip('#').strip()
                    if clean and len(clean) > 4:
                        result['sections'].append(clean[:80])

        # ══════════════════════════════════════════════════════
        # استخراج المكتبات من كل ملفات .py — مسح عميق لأول 300 سطر
        # ══════════════════════════════════════════════════════
        _PY_STDLIB = {
            'os','sys','re','json','time','threading','pathlib','datetime','logging',
            'subprocess','hashlib','base64','shutil','fnmatch','signal','typing','abc',
            'io','collections','copy','__future__','tkinter','ttk','math','random',
            'string','struct','socket','ssl','http','urllib','email','html','xml',
            'csv','sqlite3','pickle','shelve','tempfile','glob','stat','errno',
            'platform','ctypes','multiprocessing','concurrent','asyncio','queue',
            'heapq','bisect','array','weakref','gc','inspect','ast','dis','code',
            'traceback','warnings','contextlib','functools','itertools','operator',
            'dataclasses','enum','decimal','fractions','statistics','textwrap',
            'unicodedata','codecs','locale','gettext','argparse','configparser',
            'secrets','hmac','zlib','gzip','bz2','lzma','zipfile','tarfile',
            'mmap','msvcrt','winreg','winsound','nt','posix','calendar','sched',
            'atexit','builtins','site','sysconfig','importlib','pkgutil','runpy',
            'token','tokenize','keyword','pyclbr','py_compile','compileall',
            'ftplib','poplib','imaplib','smtplib','telnetlib','xmlrpc','ipaddress',
            'binascii','quopri','uu','encodings','mimetypes','webbrowser','uuid',
            'pprint','reprlib','numbers','cmath','colorsys','wave','audioop',
            'tkinter','ttk','filedialog','messagebox','scrolledtext','simpledialog',
            'customtkinter','ctk',
        }

        _KNOWN_THIRD_PARTY = {
            'requests','flask','django','fastapi','sqlalchemy','pandas','numpy',
            'matplotlib','seaborn','pillow','PIL','cv2','sklearn','tensorflow','torch',
            'keras','scipy','sympy','pytest','celery','redis','pymongo','psycopg2',
            'aiohttp','httpx','pydantic','alembic','boto3','stripe','twilio',
            'cryptography','paramiko','fabric','click','rich','typer','loguru',
            'dotenv','yaml','toml','lxml','bs4','scrapy','selenium','playwright',
            'pyautogui','pynput','pyperclip','pygetwindow','keyboard','mouse',
            'watchdog','schedule','apscheduler','freezegun','faker','factory_boy',
            'xxhash','psutil','tqdm','colorama','tabulate','prettytable',
            'openpyxl','xlrd','xlwt','reportlab','fpdf','pypdf2','pdfplumber',
            'pytesseract','easyocr','pyqt5','pyqt6','wx','kivy','pyglet','pygame',
            'customtkinter','flet','nicegui','gradio','streamlit','dash','plotly',
            'bokeh','altair','folium','geopandas','shapely','pyproj',
        }

        # مسح كل ملفات .py في المشروع
        for _root, _dirs, _files in os.walk(self.path):
            _dirs[:] = [d for d in _dirs if d not in IGNORED_DIRS and d != '.git']
            for _f in _files:
                if not _f.endswith('.py'):
                    continue
                _fp = os.path.join(_root, _f)
                _lines = []
                try:
                    with open(_fp, 'r', encoding='utf-8', errors='ignore') as _fh:
                        _lines = [next(_fh) for _ in range(300)]
                except StopIteration:
                    pass  # ملف أقل من 300 سطر — تمّ قراءته كاملاً
                except Exception:
                    continue
                for _line in _lines:
                    _s = _line.strip()
                    if not (_s.startswith('import ') or _s.startswith('from ')):
                        continue
                    try:
                        _parts = _s.split()
                        if _s.startswith('import '):
                            # import x, y, z  |  import x as y
                            for _part in _parts[1:]:
                                _pkg = _part.split('.')[0].rstrip(',')
                                if _pkg and _pkg.isidentifier():
                                    result['tech_stack'].append(_pkg)
                                    break  # خذ فقط الأول لكل import
                        else:  # from x import y
                            _pkg = _parts[1].split('.')[0]
                            if _pkg and _pkg.isidentifier():
                                result['tech_stack'].append(_pkg)
                    except Exception:
                        pass

        # ── تصفية وترتيب المكتبات ──
        _raw_stack = result['tech_stack']
        _filtered  = []
        _seen      = set()
        # أولاً: المكتبات المعروفة third-party
        for _p in _raw_stack:
            if _p in _KNOWN_THIRD_PARTY and _p not in _seen:
                _filtered.append(_p)
                _seen.add(_p)
        # ثانياً: أي شيء ليس stdlib وليس مكتبة مدمجة
        for _p in _raw_stack:
            if _p not in _PY_STDLIB and _p not in _seen and not _p.startswith('_') and len(_p) > 1:
                _filtered.append(_p)
                _seen.add(_p)
        result['tech_stack'] = list(dict.fromkeys(_filtered))[:25]

        return result

    def _tree(self, depth=3):
        lines = [f"{self.name}/"]
        for root, dirs, files in os.walk(self.path):
            dirs[:] = sorted([d for d in dirs if d not in IGNORED_DIRS and d != '.git'])
            d = root.replace(str(self.path), '').count(os.sep)
            if d >= depth:
                dirs.clear()
                continue
            indent = "  " * (d + 1)
            for di in dirs:
                lines.append(f"{indent}{di}/")
            for f in sorted(files)[:8]:
                lines.append(f"{indent}{f}")
            if len(files) > 8:
                lines.append(f"{indent}... +{len(files) - 8}")
        return '\n'.join(lines[:50])

    def _py(self, fp, rel, result):
        """تحليل Python — AST للملفات المعقولة، regex للملفات الضخمة جداً"""
        try:
            import ast as _ast
            _MAX_AST_BYTES = 1_500_000  # 1.5 MB
            _MAX_AST_LINES = 15_000     # 15,000 سطر

            stat = os.stat(fp)
            if stat.st_size > _MAX_AST_BYTES:
                self._py_regex(fp, rel, result)
                return

            with open(fp, 'r', encoding='utf-8', errors='ignore') as _f:
                src = _f.read()
            if src.count('\n') > _MAX_AST_LINES:
                self._py_regex_from_src(src, fp, rel, result)
                return

            tree = _ast.parse(src)

            mod_doc = _ast.get_docstring(tree) or ''
            if mod_doc and not result.get('description'):
                result['description'] = mod_doc[:500]

            for n in _ast.walk(tree):
                if isinstance(n, _ast.ClassDef):
                    doc = _ast.get_docstring(n) or ''
                    entry = f"{rel}: class {n.name}"
                    if doc:
                        entry += f" — {doc[:120]}"
                    result['classes'].append(entry)
                    for child in _ast.walk(n):
                        if isinstance(child, _ast.FunctionDef) and not child.name.startswith('_'):
                            fdoc = _ast.get_docstring(child) or ''
                            fentry = f"  {n.name}.{child.name}()"
                            if fdoc:
                                fentry += f" — {fdoc[:80]}"
                            result['functions'].append(fentry)
                elif isinstance(n, _ast.FunctionDef) and not n.name.startswith('_'):
                    doc = _ast.get_docstring(n) or ''
                    entry = f"{rel}: def {n.name}()"
                    if doc:
                        entry += f" — {doc[:80]}"
                    result['functions'].append(entry)

            for line in src.split('\n'):
                s = line.strip()
                if ('═' in s or '─' in s) and s.startswith('#') and len(s) > 6:
                    clean = s.lstrip('#').strip().strip('═─ ')
                    if clean and len(clean) > 3:
                        result.setdefault('sections', []).append(clean[:80])
        except SyntaxError:
            pass  # ملف Python بصيغة خاطئة — تجاهل
        except Exception:
            pass

    def _py_regex(self, fp, rel, result):
        """تحليل سريع بـ regex للملفات الكبيرة — يمسح الملف كله"""
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                full_src = f.read()
            self._py_regex_from_src(full_src, fp, rel, result)
        except Exception:
            pass

    @staticmethod
    def _py_regex_from_src(src, fp, rel, result):
        # ── الكلاسات مع docstrings ──
        for m in re.finditer(
            r'''(?m)^class\s+(\w+)[^:]*:\s*\n\s+["\\']{3}(.*?)["\\']{3}''',
            src, re.DOTALL
        ):
            doc = m.group(2).strip().split('\n')[0][:120]
            result['classes'].append(f"{rel}: class {m.group(1)} — {doc}")
        if not result['classes']:
            for m in re.finditer(r'(?m)^class\s+(\w+)', src):
                result['classes'].append(f"{rel}: class {m.group(1)}")

        # ── الدوال العامة مع docstrings ──
        for m in re.finditer(
            r'''(?m)^    def\s+([^_]\w*)\s*\([^)]*\)[^:]*:\s*\n\s+["\\']{3}(.*?)["\\']{3}''',
            src, re.DOTALL
        ):
            doc = m.group(2).strip().split('\n')[0][:100]
            result['functions'].append(f"{rel}: def {m.group(1)}() — {doc}")
        if not result['functions']:
            for m in re.finditer(r'(?m)^    def\s+([^_]\w*)\s*\(', src):
                result['functions'].append(f"{rel}: def {m.group(1)}()")

        # ── الـ docstring الأولى ──
        head = src[:5000]
        dm = re.search('"""(.*?)"""', head, re.DOTALL) or re.search("'''(.*?)'''", head, re.DOTALL)
        if dm and not result.get('description'):
            result['description'] = dm.group(1).strip()[:500]

        # ── أقسام الملف ──
        for line in src.split('\n'):
            s = line.strip()
            if s.startswith('#') and ('═' in s or '─' in s or ('[' in s and '/' in s and ']' in s)):
                clean = re.sub(r'[═─#\s]+', ' ', s).strip()
                if clean and len(clean) > 4:
                    result.setdefault('sections', []).append(clean[:80])

    def _js(self, fp, rel, result):
        """تحليل JS/TS — v10.7: محسّن لاكتشاف arrow functions و React components و JSDoc"""
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as _f:
                src = _f.read()
            lines = src.split('\n')
            prev_comment = ''
            for i, line in enumerate(lines):
                s = line.strip()

                # التقاط JSDoc comments
                if s.startswith('/**') or s.startswith('//'):
                    comment = s.lstrip('/*/ ').rstrip('*/ ')
                    if len(comment) > 5:
                        prev_comment = comment[:100]
                    continue

                # Classes
                if re.match(r'^(export\s+)?(default\s+)?class\s+\w+', s):
                    name = re.match(r'^(?:export\s+)?(?:default\s+)?class\s+(\w+)', s)
                    if name:
                        entry = f"{rel}: class {name.group(1)}"
                        if prev_comment:
                            entry += f" — {prev_comment}"
                        result['classes'].append(entry)
                        prev_comment = ''
                        continue

                # Standard functions
                if re.match(r'^(export\s+)?(default\s+)?(async\s+)?function\s+\w+', s):
                    name = re.match(r'^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)', s)
                    if name:
                        entry = f"{rel}: function {name.group(1)}()"
                        if prev_comment:
                            entry += f" — {prev_comment}"
                        result['functions'].append(entry)
                        prev_comment = ''
                        continue

                # Arrow functions: export const name = (...) => | const name = (...) =>
                m = re.match(r'^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(', s)
                if m and ('=>' in s or '=>' in (lines[i+1].strip() if i+1 < len(lines) else '')):
                    entry = f"{rel}: const {m.group(1)}()"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['functions'].append(entry)
                    prev_comment = ''
                    continue

                # React components: const Name = () =>
                m = re.match(r'^(?:export\s+)?(?:const|function)\s+([A-Z]\w+)', s)
                if m:
                    entry = f"{rel}: component {m.group(1)}"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['classes'].append(entry)
                    prev_comment = ''
                    continue

                # imports for tech stack
                m = re.match(r'^import\s+.*from\s+[\'"]([^\.\/][^\'"]*)[\'"]', s)
                if m:
                    pkg = m.group(1).split('/')[0]
                    if pkg and not pkg.startswith('@types'):
                        result['tech_stack'].append(pkg.lstrip('@'))

                if not s.startswith('//') and not s.startswith('*'):
                    prev_comment = ''
        except Exception:
            pass

    def _java(self, fp, rel, result):
        """تحليل Java/Kotlin — v10.7: classes + methods + annotations + imports"""
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as _f:
                src = _f.read()
            prev_comment = ''

            for line in src.split('\n'):
                s = line.strip()

                # Javadoc
                if s.startswith('/**') or (s.startswith('*') and not s.startswith('*/')):
                    comment = s.lstrip('/* ').rstrip('*/ ')
                    if len(comment) > 3 and not comment.startswith('@'):
                        prev_comment = comment[:120]
                    continue

                # Classes / Interfaces / Enums
                m = re.match(
                    r'^(?:public\s+|private\s+|protected\s+)?'
                    r'(?:abstract\s+|static\s+|final\s+)*'
                    r'(class|interface|enum|record)\s+(\w+)', s)
                if m:
                    entry = f"{rel}: {m.group(1)} {m.group(2)}"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['classes'].append(entry)
                    prev_comment = ''
                    continue

                # Public methods
                m = re.match(
                    r'^(?:public\s+|protected\s+)'
                    r'(?:static\s+)?(?:final\s+)?'
                    r'(?:synchronized\s+)?'
                    r'(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\(', s)
                if m and m.group(1) not in ('if', 'for', 'while', 'switch', 'catch'):
                    entry = f"{rel}: {m.group(1)}()"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['functions'].append(entry)
                    prev_comment = ''
                    continue

                # Imports for tech stack
                m = re.match(r'^import\s+(?:static\s+)?(\w+\.\w+)', s)
                if m:
                    pkg = m.group(1)
                    if not pkg.startswith('java.') and not pkg.startswith('javax.'):
                        result['tech_stack'].append(pkg.split('.')[0])

                if s and not s.startswith('//') and not s.startswith('*'):
                    prev_comment = ''
        except Exception:
            pass

    def _go(self, fp, rel, result):
        """تحليل Go — v10.7: structs + functions + interfaces + imports"""
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as _f:
                src = _f.read()
            prev_comment = ''

            for line in src.split('\n'):
                s = line.strip()

                # Comments
                if s.startswith('//'):
                    comment = s.lstrip('/ ').strip()
                    if len(comment) > 3:
                        prev_comment = comment[:120]
                    continue

                # Structs and interfaces
                m = re.match(r'^type\s+(\w+)\s+(struct|interface)\s*\{', s)
                if m:
                    entry = f"{rel}: {m.group(2)} {m.group(1)}"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['classes'].append(entry)
                    prev_comment = ''
                    continue

                # Functions (exported = starts with uppercase)
                m = re.match(r'^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(', s)
                if m:
                    name = m.group(1)
                    entry = f"{rel}: func {name}()"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    if name[0].isupper():
                        result['functions'].append(entry)
                    prev_comment = ''
                    continue

                if s and not s.startswith('//'):
                    prev_comment = ''
        except Exception:
            pass

    def _rust(self, fp, rel, result):
        """تحليل Rust — v10.7: structs + impl + pub fn + traits"""
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as _f:
                src = _f.read()
            prev_comment = ''

            for line in src.split('\n'):
                s = line.strip()

                # Doc comments
                if s.startswith('///') or s.startswith('//!'):
                    comment = s.lstrip('/! ').strip()
                    if len(comment) > 3:
                        prev_comment = comment[:120]
                    continue

                # Structs / Enums / Traits
                m = re.match(r'^(?:pub\s+)?(struct|enum|trait)\s+(\w+)', s)
                if m:
                    entry = f"{rel}: {m.group(1)} {m.group(2)}"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['classes'].append(entry)
                    prev_comment = ''
                    continue

                # Public functions
                m = re.match(r'^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)', s)
                if m and not m.group(1).startswith('_'):
                    entry = f"{rel}: fn {m.group(1)}()"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['functions'].append(entry)
                    prev_comment = ''
                    continue

                # use statements for tech stack
                m = re.match(r'^use\s+(\w+)', s)
                if m and m.group(1) not in ('std', 'core', 'alloc', 'self', 'super', 'crate'):
                    result['tech_stack'].append(m.group(1))

                if s and not s.startswith('//'):
                    prev_comment = ''
        except Exception:
            pass

    def _c_cpp(self, fp, rel, result):
        """تحليل C/C++ — v10.7: classes + functions + structs"""
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as _f:
                src = _f.read()
            prev_comment = ''

            for line in src.split('\n'):
                s = line.strip()

                # Comments
                if s.startswith('//') or s.startswith('/*'):
                    comment = s.lstrip('/*/ ').rstrip('*/ ')
                    if len(comment) > 3:
                        prev_comment = comment[:120]
                    continue

                # C++ classes
                m = re.match(r'^(?:class|struct)\s+(\w+)(?:\s*:\s*(?:public|private|protected))?', s)
                if m:
                    entry = f"{rel}: class {m.group(1)}"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['classes'].append(entry)
                    prev_comment = ''
                    continue

                # Functions (not indented = top-level)
                if not line.startswith((' ', '\t')):
                    m = re.match(
                        r'^(?:(?:static|inline|virtual|extern|const)\s+)*'
                        r'(?:\w+[\*&\s]+)(\w+)\s*\([^;]*\)\s*\{?$', s)
                    if m and m.group(1) not in ('if', 'for', 'while', 'switch', 'return', 'main'):
                        entry = f"{rel}: {m.group(1)}()"
                        if prev_comment:
                            entry += f" — {prev_comment}"
                        result['functions'].append(entry)
                        prev_comment = ''
                        continue

                # #include for tech stack
                m = re.match(r'#include\s*[<"](\w+)', s)
                if m and m.group(1) not in ('stdio', 'stdlib', 'string', 'iostream',
                                             'vector', 'map', 'set', 'algorithm', 'cmath',
                                             'fstream', 'sstream', 'cstring', 'memory'):
                    result['tech_stack'].append(m.group(1))

                if s and not s.startswith('//') and not s.startswith('*'):
                    prev_comment = ''
        except Exception:
            pass

    def _csharp(self, fp, rel, result):
        """تحليل C# — v10.7: classes + methods + properties"""
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as _f:
                src = _f.read()
            prev_comment = ''

            for line in src.split('\n'):
                s = line.strip()

                # XML doc comments
                if s.startswith('///'):
                    m2 = re.search(r'<summary>(.*?)</summary>', s)
                    if m2:
                        prev_comment = m2.group(1).strip()[:120]
                    else:
                        comment = s.lstrip('/ ').strip()
                        if len(comment) > 3 and not comment.startswith('<'):
                            prev_comment = comment[:120]
                    continue

                # Classes / Interfaces / Records
                m = re.match(
                    r'^(?:public\s+|private\s+|protected\s+|internal\s+)?'
                    r'(?:abstract\s+|static\s+|sealed\s+|partial\s+)*'
                    r'(class|interface|record|struct|enum)\s+(\w+)', s)
                if m:
                    entry = f"{rel}: {m.group(1)} {m.group(2)}"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['classes'].append(entry)
                    prev_comment = ''
                    continue

                # Public methods
                m = re.match(
                    r'^(?:public\s+|protected\s+)'
                    r'(?:static\s+)?(?:async\s+)?(?:virtual\s+)?(?:override\s+)?'
                    r'(?:\w+(?:<[^>]+>)?[\[\]]*)\s+(\w+)\s*\(', s)
                if m and m.group(1) not in ('if', 'for', 'while', 'switch'):
                    entry = f"{rel}: {m.group(1)}()"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['functions'].append(entry)
                    prev_comment = ''
                    continue

                # using for tech stack
                m = re.match(r'^using\s+(?:static\s+)?(\w+(?:\.\w+)*)', s)
                if m:
                    pkg = m.group(1).split('.')[0]
                    if pkg not in ('System', 'Microsoft'):
                        result['tech_stack'].append(pkg)

                if s and not s.startswith('//'):
                    prev_comment = ''
        except Exception:
            pass

    def _dart(self, fp, rel, result):
        """تحليل Dart/Flutter — v10.7: classes + methods + widgets"""
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as _f:
                src = _f.read()
            prev_comment = ''

            for line in src.split('\n'):
                s = line.strip()

                # Doc comments
                if s.startswith('///'):
                    comment = s.lstrip('/ ').strip()
                    if len(comment) > 3:
                        prev_comment = comment[:120]
                    continue

                # Classes (including widgets)
                m = re.match(r'^(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?', s)
                if m:
                    widget_type = ''
                    parent = m.group(2) or ''
                    if parent in ('StatefulWidget', 'StatelessWidget'):
                        widget_type = ' (Widget)'
                    entry = f"{rel}: class {m.group(1)}{widget_type}"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['classes'].append(entry)
                    prev_comment = ''
                    continue

                # Functions
                m = re.match(
                    r'^(?:static\s+)?(?:Future<[^>]+>|void|int|String|bool|double|List|Map|\w+)'
                    r'\s+(\w+)\s*\(', s)
                if m and not m.group(1).startswith('_'):
                    entry = f"{rel}: {m.group(1)}()"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['functions'].append(entry)
                    prev_comment = ''
                    continue

                # imports for tech stack
                m = re.match(r"^import\s+'package:(\w+)/", s)
                if m and m.group(1) != 'flutter':
                    result['tech_stack'].append(m.group(1))

                if s and not s.startswith('//'):
                    prev_comment = ''
        except Exception:
            pass

    def _php(self, fp, rel, result):
        """تحليل PHP — v10.7: classes + functions + traits"""
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as _f:
                src = _f.read()
            prev_comment = ''

            for line in src.split('\n'):
                s = line.strip()

                # PHPDoc
                if s.startswith('/**') or (s.startswith('*') and not s.startswith('*/')):
                    comment = s.lstrip('/* ').rstrip('*/ ')
                    if len(comment) > 3 and not comment.startswith('@'):
                        prev_comment = comment[:120]
                    continue

                # Classes / Interfaces / Traits
                m = re.match(
                    r'^(?:abstract\s+|final\s+)?'
                    r'(class|interface|trait|enum)\s+(\w+)', s)
                if m:
                    entry = f"{rel}: {m.group(1)} {m.group(2)}"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['classes'].append(entry)
                    prev_comment = ''
                    continue

                # Functions
                m = re.match(
                    r'^(?:public\s+|protected\s+|private\s+)?'
                    r'(?:static\s+)?function\s+(\w+)\s*\(', s)
                if m and not m.group(1).startswith('_'):
                    entry = f"{rel}: function {m.group(1)}()"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['functions'].append(entry)
                    prev_comment = ''
                    continue

                # use for tech stack
                m = re.match(r'^use\s+(\w+(?:\\\w+)*)', s)
                if m:
                    result['tech_stack'].append(m.group(1).split('\\')[0])

                if s and not s.startswith('//') and not s.startswith('*'):
                    prev_comment = ''
        except Exception:
            pass

    def _ruby(self, fp, rel, result):
        """تحليل Ruby — v10.7: classes + modules + methods"""
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as _f:
                src = _f.read()
            prev_comment = ''

            for line in src.split('\n'):
                s = line.strip()

                # Comments
                if s.startswith('#'):
                    comment = s.lstrip('# ').strip()
                    if len(comment) > 3:
                        prev_comment = comment[:120]
                    continue

                # Classes / Modules
                m = re.match(r'^(class|module)\s+(\w+(?:::\w+)*)', s)
                if m:
                    entry = f"{rel}: {m.group(1)} {m.group(2)}"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['classes'].append(entry)
                    prev_comment = ''
                    continue

                # Methods
                m = re.match(r'^(?:def\s+)(?:self\.)?(\w+)', s)
                if m and not m.group(1).startswith('_'):
                    entry = f"{rel}: def {m.group(1)}"
                    if prev_comment:
                        entry += f" — {prev_comment}"
                    result['functions'].append(entry)
                    prev_comment = ''
                    continue

                # require for tech stack
                m = re.match(r"^require\s+['\"](\w+)", s)
                if m:
                    result['tech_stack'].append(m.group(1))

                if s and not s.startswith('#'):
                    prev_comment = ''
        except Exception:
            pass

    def _html(self, fp, rel, result):
        """تحليل HTML — v10.7: اكتشاف الإطارات والمكتبات من script/link tags"""
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as _f:
                src = _f.read(50000)

            # Meta description
            m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', src, re.I)
            if m and not result.get('description'):
                result['description'] = m.group(1)[:300]

            # Title
            m = re.search(r'<title>(.*?)</title>', src, re.I)
            if m:
                title = m.group(1).strip()
                if title and not result.get('description'):
                    result['description'] = title

            # CDN libraries (Bootstrap, jQuery, Vue, React, etc.)
            for m in re.finditer(r'(?:src|href)=["\'].*?(?:cdn[^"\']*?|unpkg[^"\']*?)/([\w.-]+?)(?:@|/)', src):
                lib = m.group(1).lower()
                if lib not in ('css', 'js', 'min'):
                    result['tech_stack'].append(lib)

            # Known frameworks
            frameworks = {
                'bootstrap': 'Bootstrap', 'tailwind': 'Tailwind CSS',
                'jquery': 'jQuery', 'vue': 'Vue.js', 'react': 'React',
                'angular': 'Angular', 'alpine': 'Alpine.js',
            }
            src_lower = src.lower()
            for key, name in frameworks.items():
                if key in src_lower:
                    result['tech_stack'].append(name)
        except Exception:
            pass

    def _detect(self, r):
        """v10.7: اكتشاف محسّن لأنواع أكثر من المشاريع"""
        configs = set(r['configs'].keys())
        exts = r['stats'].get('exts', {})

        # Python frameworks
        if 'manage.py' in r['main_files']:
            return 'Django'
        if any('flask' in c.lower() for c in r.get('tech_stack', [])):
            return 'Flask'
        if any('fastapi' in c.lower() for c in r.get('tech_stack', [])):
            return 'FastAPI'

        # Mobile
        if 'pubspec.yaml' in configs:
            return 'Flutter'

        # JS Frameworks
        if any(f in r['main_files'] for f in ['App.jsx', 'App.tsx', 'src/App.jsx', 'src/App.tsx']):
            return 'React'
        if any(f in r['main_files'] for f in ['App.vue', 'src/App.vue']):
            return 'Vue'
        if any(f in r['main_files'] for f in ['App.svelte', 'src/App.svelte']):
            return 'Svelte'
        if any(c in configs for c in ['next.config.js', 'next.config.ts']):
            return 'Next.js'
        if any(c in configs for c in ['nuxt.config.js', 'nuxt.config.ts']):
            return 'Nuxt'
        if 'angular.json' in configs:
            return 'Angular'

        # Compiled languages
        if 'Cargo.toml' in configs:
            return 'Rust'
        if 'go.mod' in configs:
            return 'Go'
        if 'CMakeLists.txt' in configs or exts.get('.cpp', 0) + exts.get('.c', 0) > 0:
            if exts.get('.cpp', 0) > 0 or exts.get('.hpp', 0) > 0:
                return 'C++'
            return 'C'
        if any(c in configs for c in ['pom.xml', 'build.gradle', 'build.gradle.kts']):
            if exts.get('.kt', 0) > exts.get('.java', 0):
                return 'Kotlin'
            return 'Java'

        # .NET
        if any(fnmatch.fnmatch(c, '*.csproj') or fnmatch.fnmatch(c, '*.sln') for c in configs):
            return 'C#'

        # Scripting
        if 'composer.json' in configs:
            return 'PHP'
        if 'Gemfile' in configs:
            return 'Ruby'
        if 'package.json' in configs:
            return 'Node.js'
        if any(c in configs for c in ['requirements.txt', 'setup.py', 'pyproject.toml']):
            return 'Python'

        # Python بدون requirements.txt (single-file أو مشروع بسيط)
        if exts.get('.py', 0) > 0:
            classes = [c for c in r.get('classes', [])]
            funcs   = [f for f in r.get('functions', [])]
            stack   = [s.lower() for s in r.get('tech_stack', [])]
            # Desktop app بـ tkinter أو customtkinter
            if any(x in stack for x in ('tkinter', 'customtkinter', 'ctk', 'pyqt5', 'pyqt6', 'wx', 'kivy')):
                return 'Python Desktop App'
            # Web scraping / automation
            if any(x in stack for x in ('selenium', 'playwright', 'scrapy', 'bs4', 'requests')):
                return 'Python Automation'
            # Data / ML
            if any(x in stack for x in ('pandas', 'numpy', 'sklearn', 'tensorflow', 'torch', 'matplotlib')):
                return 'Python Data/ML'
            # CLI tool
            if any(x in stack for x in ('click', 'typer', 'argparse', 'rich')):
                return 'Python CLI'
            # عام
            if exts.get('.py', 0) > 3:
                return 'Python'
            return 'Python Script'

        # Web
        if exts.get('.html', 0) > 0:
            if exts.get('.css', 0) > 0 or exts.get('.js', 0) > 0:
                return 'Web (HTML/CSS/JS)'
            return 'HTML'

        return 'General'





