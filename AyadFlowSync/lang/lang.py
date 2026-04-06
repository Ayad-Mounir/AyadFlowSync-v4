#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lang.lang — نظام الترجمة النظيف
بسيط: dict + fallback، لا Proxy، لا circular imports.
"""

import logging
from typing import Dict

_logger = logging.getLogger("AyadFlowSync")

_STRINGS: Dict[str, Dict[str, str]] = {
    "app_title":          {"ar": "🛡️ Ayad FlowSync {ver}  |  💻 {pc}", "en": "🛡️ Ayad FlowSync {ver}  |  💻 {pc}"},
    "tab_sync":           {"ar": "🔄 المزامنة",        "en": "🔄 Sync"},
    "tab_github":         {"ar": "🐙 GitHub",           "en": "🐙 GitHub"},
    "tab_settings":       {"ar": "⚙️ الإعدادات",        "en": "⚙️ Settings"},
    "projects":           {"ar": "📁 المشاريع",         "en": "📁 Projects"},
    "add":                {"ar": "➕ إضافة",             "en": "➕ Add"},
    "remove":             {"ar": "➖ حذف",               "en": "➖ Remove"},
    "open":               {"ar": "📂 فتح",               "en": "📂 Open"},
    "backup":             {"ar": "💾 Backup → فلاشة",   "en": "💾 Backup → USB"},
    "restore":            {"ar": "📥 Restore ← فلاشة",  "en": "📥 Restore ← USB"},
    "full_sync":          {"ar": "🔄 مزامنة كاملة ↔",  "en": "🔄 Full Sync ↔"},
    "verify":             {"ar": "🔍 فحص السلامة",      "en": "🔍 Verify"},
    "stop":               {"ar": "⏹ إيقاف",             "en": "⏹ Stop"},
    "log_title":          {"ar": "📋 السجل",             "en": "📋 Log"},
    "ready":              {"ar": "جاهز",                 "en": "Ready"},
    "no_changes":         {"ar": "✅ لا تغييرات",        "en": "✅ No changes"},
    "done":               {"ar": "✅ اكتمل",             "en": "✅ Done"},
    "error":              {"ar": "❌ خطأ",               "en": "❌ Error"},
    "cancelled":          {"ar": "⛔ تم الإيقاف",       "en": "⛔ Cancelled"},
    "auth_token":         {"ar": "🔐 Personal Access Token", "en": "🔐 Personal Access Token"},
    "auth_ok":            {"ar": "✅ مصادق بنجاح",      "en": "✅ Authenticated"},
    "auth_fail":          {"ar": "❌ Token غير صالح",   "en": "❌ Invalid Token"},
    "repos":              {"ar": "📦 المستودعات",        "en": "📦 Repositories"},
    "upload":             {"ar": "🚀 رفع مشروع",        "en": "🚀 Upload Project"},
    "clone":              {"ar": "⬇️ Clone",             "en": "⬇️ Clone"},
    "batch":              {"ar": "📦 Batch Upload",      "en": "📦 Batch Upload"},
    "repo_name":          {"ar": "🏷️ اسم Repo",         "en": "🏷️ Repo Name"},
    "description":        {"ar": "📝 الوصف",             "en": "📝 Description"},
    "license":            {"ar": "📄 الرخصة",            "en": "📄 License"},
    "private":            {"ar": "🔒 خاص",               "en": "🔒 Private"},
    "use_lfs":            {"ar": "📦 Git LFS",           "en": "📦 Git LFS"},
    "creating_repo":      {"ar": "🔨 جاري إنشاء Repo...", "en": "🔨 Creating repo..."},
    "pushing":            {"ar": "⬆️ رفع الكود...",      "en": "⬆️ Pushing..."},
    "cloning":            {"ar": "⬇️ Clone جارٍ...",     "en": "⬇️ Cloning..."},
    "settings_title":     {"ar": "⚙️ الإعدادات",        "en": "⚙️ Settings"},
    "pc_name":            {"ar": "💻 اسم الجهاز",        "en": "💻 Device Name"},
    "save":               {"ar": "💾 حفظ",               "en": "💾 Save"},
    "vault":              {"ar": "💾 مجلد النسخ الاحتياطي", "en": "💾 Backup Folder"},
    "change":             {"ar": "📂 تغيير",             "en": "📂 Change"},
    "excluded_dirs":      {"ar": "🚫 مجلدات مستثناة",   "en": "🚫 Excluded Folders"},
    "accumark":           {"ar": "⚡ وضع AccuMark",      "en": "⚡ AccuMark Mode"},
    "cache_clear":        {"ar": "🗑️ مسح Cache",        "en": "🗑️ Clear Cache"},
    "device_weak":        {"ar": "🔴 ضعيف",              "en": "🔴 Weak"},
    "device_mid":         {"ar": "🟡 متوسط",             "en": "🟡 Mid"},
    # ── Sidebar ────────────────────────────────────────────────────
    "nav_dashboard":      {"ar": "📊  لوحة التحكم",       "en": "📊  Dashboard"},
    "nav_sync":           {"ar": "🔄  المزامنة",         "en": "🔄  Sync"},
    "nav_github":         {"ar": "🐙  GitHub",            "en": "🐙  GitHub"},
    "nav_drive":          {"ar": "💾  Drive",             "en": "💾  Drive"},
    "nav_settings":       {"ar": "⚙️  الإعدادات",         "en": "⚙️  Settings"},
    "nav_about":          {"ar": "ℹ️  حول",               "en": "ℹ️  About"},
    "sidebar_title":      {"ar": "⚡ FlowSync",           "en": "⚡ FlowSync"},
    "local_device":       {"ar": "جهاز محلي",             "en": "Local Device"},

    # ── Dashboard ──────────────────────────────────────────────────
    "dash_title":          {"ar": "📊 لوحة التحكم",           "en": "📊 Dashboard"},
    "dash_usb_title":      {"ar": "الفلاشة",                  "en": "Flash Drive"},
    "dash_pc_title":       {"ar": "الحاسوب",                  "en": "Computer"},
    "dash_projects":       {"ar": "مشروع",                    "en": "projects"},
    "dash_speed_unknown":  {"ar": "السرعة: لم تُقَس",         "en": "Speed: not measured"},
    "dash_usb_error":      {"ar": "خطأ في قراءة الفلاشة",     "en": "USB read error"},
    "dash_usb_not_found":  {"ar": "الفلاشة غير متصلة",        "en": "USB not connected"},
    "dash_attention":      {"ar": "⚡ يحتاج انتباهك",         "en": "⚡ Needs Attention"},
    "dash_go_sync":        {"ar": "→ المزامنة",               "en": "→ Sync"},
    "dash_recent":         {"ar": "📋 آخر العمليات",           "en": "📋 Recent Activity"},
    "dash_missing":        {"ar": "مجلد مفقود",               "en": "Folder missing"},
    "dash_never_synced":   {"ar": "لم يُزامَن بعد",           "en": "Never synced"},
    "dash_has_changes":    {"ar": "تغييرات جديدة",            "en": "Has changes"},
    "dash_gh_needs_push":  {"ar": "يحتاج رفع",               "en": "Needs push"},
    "dash_all_good":       {"ar": "كل شيء محدّث!",            "en": "Everything up to date!"},
    "dash_no_history":     {"ar": "لا عمليات بعد",            "en": "No activity yet"},
    "dash_repos_total":    {"ar": "مستودع",                   "en": "repositories"},
    "dash_repos_changed":  {"ar": "يحتاج تحديث",             "en": "need update"},
    "dash_repos_all_synced": {"ar": "كل المستودعات محدّثة",   "en": "All repos synced"},

    # ── Sync Panel ──────────────────────────────────────────────────
    "projects_title":     {"ar": "📁 المشاريع",           "en": "📁 Projects"},
    "add_project":        {"ar": "➕ إضافة",               "en": "➕ Add"},
    "remove_project":     {"ar": "➖ حذف",                 "en": "➖ Remove"},
    "vault_title":        {"ar": "💾 مجلد النسخ الاحتياطي","en": "💾 Backup Folder"},
    "ops_title":          {"ar": "⚡ العمليات",            "en": "⚡ Operations"},
    "btn_backup":         {"ar": "💾  Backup → فلاشة",    "en": "💾  Backup → USB"},
    "btn_restore":        {"ar": "📥  Restore ← فلاشة",   "en": "📥  Restore ← USB"},
    "btn_smart_sync":     {"ar": "🧠  مزامنة ذكية",       "en": "🧠  Smart Sync"},
    "btn_verify":         {"ar": "🔍  فحص السلامة",       "en": "🔍  Verify"},
    "btn_stop":           {"ar": "⏹  إيقاف",              "en": "⏹  Stop"},
    "btn_trash":          {"ar": "🗑️  سلة المهملات",      "en": "🗑️  Trash"},
    "log_title":          {"ar": "📋 السجل الحي",          "en": "📋 Live Log"},
    "clear_log":          {"ar": "مسح السجل",              "en": "Clear Log"},
    "status_ready":       {"ar": "جاهز",                   "en": "Ready"},
    "status_done":        {"ar": "اكتمل",                  "en": "Done"},
    "status_failed":      {"ar": "فشل",                   "en": "Failed"},
    "warn_select_project":{"ar": "اختر مشروعاً أولاً!",   "en": "Select a project first!"},
    "warn_vault_missing": {"ar": "مجلد النسخ الاحتياطي غير موجود!", "en": "Backup folder not found!"},
    "warn_syncing":       {"ar": "عملية مزامنة نشطة بالفعل!", "en": "Sync already in progress!"},
    "warn_project_missing":{"ar": "مجلد المشروع غير موجود:", "en": "Project folder not found:"},
    "confirm_remove":     {"ar": "هل تريد إزالة المشروع:\n{name}\nمن القائمة؟\n(لن يُحذف الملف الفعلي)", "en": "Remove project:\n{name}\nfrom list?\n(files will NOT be deleted)"},
    "confirm_remove_title":{"ar": "تأكيد الحذف",          "en": "Confirm Remove"},
    "not_found":          {"ar": "غير موجود",              "en": "Not found"},
    "not_synced":         {"ar": "لم يُزامَن بعد",         "en": "Never synced"},
    "needs_sync":         {"ar": "يحتاج مزامنة",           "en": "Needs sync"},
    "needs_check":        {"ar": "يحتاج فحص",              "en": "Needs check"},
    "synced_at":          {"ar": "متزامن ({when})",        "en": "Synced ({when})"},
    "new_changes":        {"ar": "تغييرات جديدة ({when})", "en": "New changes ({when})"},
    "measuring":          {"ar": "🖥️  جاري قياس الجهاز...","en": "🖥️  Measuring device..."},

    # ── Smart Sync Dialog ───────────────────────────────────────────
    "smart_sync_title":   {"ar": "🧠 اختر وضع المزامنة",  "en": "🧠 Choose Sync Mode"},
    "pc_master_btn":      {"ar": "💻 الجهاز هو الأصل",    "en": "💻 PC is Master"},
    "usb_master_btn":     {"ar": "💾 الفلاشة هي الأصل",   "en": "💾 USB is Master"},
    "bidir_btn":          {"ar": "🔄 مزامنة ثنائية الاتجاه","en": "🔄 Bidirectional Sync"},
    "pc_master_desc":     {"ar": "ما ينقص في الفلاشة يُضاف — ما يزيد في الفلاشة ينتقل للسلة", "en": "Missing on USB is added — extra on USB goes to trash"},
    "usb_master_desc":    {"ar": "ما ينقص في الجهاز يُضاف — ما يزيد في الجهاز ينتقل للسلة",  "en": "Missing on PC is added — extra on PC goes to trash"},
    "bidir_desc":         {"ar": "كل زائد في أي طرف يُضاف للآخر — لا حذف",                   "en": "Everything added in both directions — no deletion"},
    "confirm_mirror":     {"ar": "سيُحذف كل ما يزيد في <b>{dst}</b> وينتقل للسلة.\nيمكن استرجاعه خلال {days} يوم.\n\nهل تريد المتابعة؟", "en": "Everything extra in <b>{dst}</b> will move to trash.\nRecoverable for {days} days.\n\nContinue?"},
    "confirm_title":      {"ar": "⚠️ تأكيد",              "en": "⚠️ Confirm"},
    "cancel":             {"ar": "إلغاء",                  "en": "Cancel"},
    "pc_label":           {"ar": "الجهاز",                 "en": "PC"},
    "usb_label":          {"ar": "الفلاشة",                "en": "USB"},
    "pc_master_label":    {"ar": "💻 الجهاز أصل",          "en": "💻 PC Master"},
    "usb_master_label":   {"ar": "💾 الفلاشة أصل",         "en": "💾 USB Master"},
    "bidir_label":        {"ar": "🔄 ثنائي الاتجاه",       "en": "🔄 Bidirectional"},
    "no_extra_files":     {"ar": "✅ لا ملفات زائدة في الوجهة", "en": "✅ No extra files in destination"},
    "moving_to_trash":    {"ar": "🗑️  نقل {n} ملف زائد للسلة ({src})...", "en": "🗑️  Moving {n} extra files to trash ({src})..."},
    "moved_to_trash":     {"ar": "✅ نُقل {n} ملف للسلة",  "en": "✅ Moved {n} files to trash"},
    "recoverable_days":   {"ar": "← قابل للاسترجاع {days} يوماً", "en": "← Recoverable for {days} days"},

    # ── Trash Dialog ────────────────────────────────────────────────
    "trash_title":        {"ar": "🗑️ سلة المهملات",        "en": "🗑️ Trash"},
    "trash_count":        {"ar": "🗑️ الملفات المحذوفة ({n})", "en": "🗑️ Deleted Files ({n})"},
    "trash_info":         {"ar": "الملفات تُحفظ {days} يوماً قبل الحذف النهائي التلقائي.", "en": "Files are kept for {days} days before automatic permanent deletion."},
    "trash_empty_btn":    {"ar": "💥 تفريغ السلة",          "en": "💥 Empty Trash"},
    "trash_restore_btn":  {"ar": "↩️  استرجاع المحدد",      "en": "↩️  Restore Selected"},
    "trash_col_file":     {"ar": "الملف",                   "en": "File"},
    "trash_col_source":   {"ar": "المصدر",                  "en": "Source"},
    "trash_col_size":     {"ar": "الحجم",                   "en": "Size"},
    "trash_col_date":     {"ar": "تاريخ الحذف",             "en": "Date Deleted"},
    "trash_select_warn":  {"ar": "اختر ملفاً للاسترجاع!",   "en": "Select a file to restore!"},
    "trash_restore_ok":   {"ar": "تم الاسترجاع:",           "en": "Restored:"},
    "trash_restore_fail": {"ar": "فشل الاسترجاع:",          "en": "Restore failed:"},
    "trash_already_empty":{"ar": "السلة فارغة بالفعل.",     "en": "Trash is already empty."},
    "trash_confirm_empty":{"ar": "هل تريد حذف {n} ملف نهائياً؟\nلا يمكن التراجع!", "en": "Permanently delete {n} files?\nThis cannot be undone!"},
    "trash_emptied":      {"ar": "تم تفريغ السلة.",         "en": "Trash emptied."},

    # ── GitHub Panel ────────────────────────────────────────────────
    "gh_tab_auth":                {"ar": "🔐 Auth",                            "en": "🔐 Auth"},
    "gh_tab_myprojects":          {"ar": "📋 مشاريعي",                         "en": "📋 My Projects"},
    "gh_myproj_title":            {"ar": "📋 مشاريعي على GitHub",               "en": "📋 My GitHub Projects"},
    "gh_myproj_info":             {"ar": "كل المشاريع التي رفعتها من جهازك أو فلاشتك — حالتها ومتى آخر رفع.", "en": "All projects you uploaded from your PC or USB — status and last push date."},
    "gh_myproj_refresh":          {"ar": "تحديث الحالة",                         "en": "Refresh Status"},
    "gh_myproj_empty":            {"ar": "لا توجد مشاريع مرفوعة بعد",            "en": "No uploaded projects yet"},
    "gh_myproj_col_status":       {"ar": "الحالة",                               "en": "Status"},
    "gh_myproj_col_name":         {"ar": "المشروع",                              "en": "Project"},
    "gh_myproj_col_source":       {"ar": "المصدر",                               "en": "Source"},
    "gh_myproj_col_path":         {"ar": "المسار المحلي",                        "en": "Local Path"},
    "gh_myproj_col_last":         {"ar": "آخر رفع",                              "en": "Last Push"},
    "gh_myproj_col_pushes":       {"ar": "مرات الرفع",                           "en": "Push Count"},
    "gh_myproj_status_synced":    {"ar": "متزامن",                               "en": "Synced"},
    "gh_myproj_status_changed":   {"ar": "تغيّر — يحتاج push",                  "en": "Changed — needs push"},
    "gh_myproj_status_missing":   {"ar": "المجلد غير موجود",                     "en": "Folder not found"},
    "gh_myproj_status_unknown":   {"ar": "غير معروف",                            "en": "Unknown"},
    "gh_myproj_open_github":      {"ar": "🌐  فتح على GitHub",                   "en": "🌐  Open on GitHub"},
    "gh_myproj_push_now":         {"ar": "🔄  Push الآن",                        "en": "🔄  Push Now"},
    "gh_myproj_remove":           {"ar": "🗑️  حذف من السجل",                    "en": "🗑️  Remove from List"},
    "gh_tab_myprojects":  {"ar": "📋 مشاريعي",              "en": "📋 My Projects"},
    "gh_tab_repos":       {"ar": "📦 المستودعات",           "en": "📦 Repositories"},
    "gh_tab_upload":      {"ar": "⬆️ رفع جديد",            "en": "⬆️ Upload New"},
    "gh_tab_readme":      {"ar": "🤖 README AI",           "en": "🤖 README AI"},
    "gh_tab_push":        {"ar": "🔄 تحديث (Push)",        "en": "🔄 Update (Push)"},
    "gh_tab_clone":       {"ar": "⬇️ Clone",               "en": "⬇️ Clone"},
    "gh_tab_batch":       {"ar": "📦 Batch",               "en": "📦 Batch"},
    "gh_auth_title":      {"ar": "🔐 مصادقة GitHub",        "en": "🔐 GitHub Authentication"},
    "gh_token_lbl":       {"ar": "Personal Access Token:", "en": "Personal Access Token:"},
    "gh_activate_btn":    {"ar": "🔐  تفعيل Token",        "en": "🔐  Activate Token"},
    "gh_show_hide":       {"ar": "👁️  إظهار / إخفاء",      "en": "👁️  Show / Hide"},
    "gh_not_auth":        {"ar": "⬜ لم تتم المصادقة بعد", "en": "⬜ Not authenticated yet"},
    "gh_refresh_repos":   {"ar": "🔄  تحديث قائمة المستودعات","en": "🔄  Refresh Repositories"},
    "gh_open_btn":        {"ar": "🌐 فتح",                  "en": "🌐 Open"},
    "gh_toggle_btn":      {"ar": "🔄 عام↔خاص",             "en": "🔄 Public↔Private"},
    "gh_download_btn":    {"ar": "⬇️ تنزيل",               "en": "⬇️ Download"},
    "gh_readme_btn":      {"ar": "📝 README AI",           "en": "📝 README AI"},
    "gh_delete_btn":      {"ar": "🗑️ حذف",                 "en": "🗑️ Delete"},
    "gh_project_lbl":     {"ar": "📁 المشروع:",             "en": "📁 Project:"},
    "gh_repo_name_lbl":   {"ar": "🏷️ اسم Repo:",           "en": "🏷️ Repo Name:"},
    "gh_desc_lbl":        {"ar": "📝 الوصف:",               "en": "📝 Description:"},
    "gh_license_lbl":     {"ar": "📄 الرخصة:",              "en": "📄 License:"},
    "gh_private_cb":      {"ar": "🔒 خاص (Private)",       "en": "🔒 Private"},
    "gh_lfs_cb":          {"ar": "📦 تفعيل Git LFS للملفات الكبيرة", "en": "📦 Enable Git LFS for large files"},
    "gh_readme_cb":       {"ar": "🤖 توليد README بالذكاء الاصطناعي", "en": "🤖 Generate README with AI"},
    "gh_upload_btn":      {"ar": "🚀  إنشاء Repo ورفع المشروع", "en": "🚀  Create Repo & Upload"},
    "gh_readme_only_btn": {"ar": "📝  توليد README فقط",   "en": "📝  Generate README Only"},
    "gh_push_info":       {"ar": "تحديث مشروع موجود على GitHub.\nاختر المجلد المحلي — سيُرفع التغييرات فقط.", "en": "Update existing GitHub project.\nChoose local folder — only changes will be pushed."},
    "gh_commit_lbl":      {"ar": "💬 Commit:",              "en": "💬 Commit:"},
    "gh_push_btn":        {"ar": "🔄  Push التغييرات",     "en": "🔄  Push Changes"},
    "gh_clone_url_lbl":   {"ar": "🔗 URL:",                "en": "🔗 URL:"},
    "gh_clone_dest_lbl":  {"ar": "📁 الوجهة:",             "en": "📁 Destination:"},
    "gh_clone_btn":       {"ar": "⬇️  Clone",              "en": "⬇️  Clone"},
    "gh_batch_info":      {"ar": "رفع جميع المشاريع من مجلد رئيسي واحد.\nكل مجلد فرعي = Repo مستقل على GitHub.", "en": "Upload all projects from one parent folder.\nEach subfolder = separate GitHub Repo."},
    "gh_batch_folder_lbl":{"ar": "المجلد الرئيسي...",      "en": "Parent folder..."},
    "gh_batch_btn":       {"ar": "🚀  رفع الكل (Batch)",   "en": "🚀  Upload All (Batch)"},
    "gh_status_lbl":      {"ar": "📊 الحالة:",              "en": "📊 Status:"},
    "gh_status_default":  {"ar": "اختر مجلداً لفحص حالة المشروع", "en": "Select a folder to check project status"},
    "gh_log_title":       {"ar": "📋 السجل",                "en": "📋 Log"},
    "gh_warn_token":      {"ar": "أدخل الـ Token أولاً!",  "en": "Enter Token first!"},
    "gh_warn_login":      {"ar": "سجّل دخول أولاً في تبويب Auth!", "en": "Login first in the Auth tab!"},
    "gh_warn_select":     {"ar": "اختر مستودعاً!",          "en": "Select a repository!"},
    "gh_warn_fields":     {"ar": "اختر مجلد المشروع واسم Repo!", "en": "Select project folder and Repo name!"},
    "gh_warn_url":        {"ar": "أدخل الـ URL والمجلد!",  "en": "Enter URL and destination folder!"},
    "gh_warn_folder":     {"ar": "اختر المجلد الرئيسي!",   "en": "Select parent folder!"},
    "gh_confirm_delete":  {"ar": "هل أنت متأكد من حذف:\n{name}\n\nلا يمكن التراجع!", "en": "Are you sure you want to delete:\n{name}\n\nThis cannot be undone!"},
    "gh_confirm_toggle":  {"ar": "تغيير {name} من {cur} إلى {new}؟", "en": "Change {name} from {cur} to {new}?"},
    "gh_public":          {"ar": "عام",                     "en": "Public"},
    "gh_private":         {"ar": "خاص",                     "en": "Private"},
    "gh_dest_folder":     {"ar": "اختر مجلد التنزيل",       "en": "Select download folder"},
    "gh_no_ai_key":       {"ar": "لم تُضف أي مفتاح AI بعد.\n\nاذهب إلى: ⚙️ الإعدادات → 🤖 مفاتيح الذكاء الاصطناعي\nوأضف مفتاح Gemini أو Claude أو OpenAI أو DeepSeek.", "en": "No AI key added yet.\n\nGo to: ⚙️ Settings → 🤖 AI Keys\nand add a Gemini, Claude, OpenAI or DeepSeek key."},
    "gh_no_ai_title":     {"ar": "⚠️ مفتاح AI مطلوب",      "en": "⚠️ AI Key Required"},

    # ── Settings Panel ──────────────────────────────────────────────
    "set_lang_group":     {"ar": "🌍 اللغة / Language",    "en": "🌍 اللغة / Language"},
    "set_lang_ar":        {"ar": "🇸🇦  العربية",            "en": "🇸🇦  العربية"},
    "set_lang_en":        {"ar": "🇬🇧  English",            "en": "🇬🇧  English"},
    "set_lang_note":      {"ar": "⚠️ يُطبَّق فوراً",        "en": "⚠️ Applied immediately"},
    "set_pc_group":       {"ar": "💻 اسم الجهاز",           "en": "💻 Device Name"},
    "set_pc_placeholder": {"ar": "اسم هذا الجهاز...",       "en": "This device name..."},
    "set_pc_save":        {"ar": "💾  حفظ",                 "en": "💾  Save"},
    "set_pc_warn":        {"ar": "أدخل اسم الجهاز!",        "en": "Enter device name!"},
    "set_pc_ok":          {"ar": "تم حفظ اسم الجهاز: {name}", "en": "Device name saved: {name}"},
    "set_excl_group":     {"ar": "🚫 مجلدات مستثناة من المزامنة", "en": "🚫 Excluded Sync Folders"},
    "set_excl_desc":      {"ar": "المجلدات التي لن تُنسخ إلى الفلاشة:", "en": "Folders that won't be copied to USB:"},
    "set_excl_save":      {"ar": "💾  حفظ الاستثناءات",    "en": "💾  Save Exclusions"},
    "set_excl_ok":        {"ar": "تم حفظ الإعدادات.",       "en": "Settings saved."},
    "set_perf_group":     {"ar": "⚡ مواصفات الجهاز",       "en": "⚡ Device Specs"},
    "set_accumark_group": {"ar": "⚡ وضع AccuMark",          "en": "⚡ AccuMark Mode"},
    "set_accumark_info":  {"ar": "AccuMark: يعتمد على الحجم فقط بدل الـ Hash — أسرع لكن أقل دقة.", "en": "AccuMark: size-only instead of Hash — faster but less accurate."},
    "set_accumark_cb":    {"ar": "تفعيل AccuMark",          "en": "Enable AccuMark"},
    "set_ai_group":       {"ar": "🤖 مفاتيح الذكاء الاصطناعي (لتوليد README)", "en": "🤖 AI Keys (for README generation)"},
    "set_ai_desc":        {"ar": "أدخل مفتاح API لأي مزوّد — يُستخدم لتوليد README تلقائياً:", "en": "Enter API key for any provider — used for automatic README generation:"},
    "set_ai_save":        {"ar": "💾  حفظ مفاتيح AI",      "en": "💾  Save AI Keys"},
    "set_ai_ok":          {"ar": "تم حفظ {n} مفتاح AI",    "en": "Saved {n} AI keys"},
    "set_dev_group":      {"ar": "👨‍💻 معلومات المطور (تُضاف للـ README)", "en": "👨‍💻 Developer Info (added to README)"},
    "set_dev_save":       {"ar": "💾  حفظ معلومات المطور", "en": "💾  Save Developer Info"},
    "set_dev_ok":         {"ar": "تم حفظ معلومات المطور",  "en": "Developer info saved"},

    # ── Drive Panel ─────────────────────────────────────────────────
    "drv_title":          {"ar": "💾 إدارة Drive / الفلاشة","en": "💾 Drive / USB Management"},
    "drv_refresh":        {"ar": "🔄  تحديث",               "en": "🔄  Refresh"},
    "drv_change_folder":  {"ar": "📂  تغيير المجلد",        "en": "📂  Change Folder"},
    "drv_not_connected":  {"ar": "Drive غير متصل",          "en": "Drive not connected"},
    "drv_col_project":    {"ar": "المشروع",                  "en": "Project"},
    "drv_col_status":     {"ar": "الحالة",                   "en": "Status"},
    "drv_col_size":       {"ar": "الحجم",                   "en": "Size"},
    "drv_col_sync":       {"ar": "آخر مزامنة",              "en": "Last Sync"},
    "drv_col_files":      {"ar": "الملفات",                  "en": "Files"},
    "drv_upload_drive":   {"ar": "☁️  رفع لـ Drive",        "en": "☁️  Upload to Drive"},
    "drv_open_btn":       {"ar": "📂  فتح",                  "en": "📂  Open"},
    "drv_explore_btn":    {"ar": "🔍  المستكشف",             "en": "🔍  Explorer"},
    "drv_delete_btn":     {"ar": "🗑️  حذف",                 "en": "🗑️  Delete"},
    "drv_devices_title":  {"ar": "🖥️ سجل الأجهزة",          "en": "🖥️ Device History"},
    "drv_dev_col_device": {"ar": "الجهاز",                   "en": "Device"},
    "drv_dev_col_sync":   {"ar": "آخر مزامنة",              "en": "Last Sync"},
    "drv_dev_col_count":  {"ar": "المزامنات",                "en": "Syncs"},
    "drv_dev_col_proj":   {"ar": "المشاريع",                 "en": "Projects"},
    "drv_status_default": {"ar": "اضغط 🔄 تحديث لعرض المشاريع", "en": "Press 🔄 Refresh to show projects"},
    "drv_this_device":    {"ar": "(هذا الجهاز)",             "en": "(this device)"},
    "drv_no_history":     {"ar": "لا يوجد سجل بعد",         "en": "No history yet"},
    "drv_confirm_delete": {"ar": "هل تريد حذف النسخة الاحتياطية:\n\n{name}\n\nلا يمكن التراجع!", "en": "Delete backup:\n\n{name}\n\nThis cannot be undone!"},
    "drv_select_zip":     {"ar": "اختر مجلد المشروع لضغطه ورفعه", "en": "Select project folder to zip & upload"},
    "drv_select_hint":    {"ar": "اختر مشروعاً من القائمة أو اضغط لاختيار مجلد", "en": "Select a project from the list or choose a folder"},

    # ── About Panel ─────────────────────────────────────────────────
    "about_desc":         {"ar": "نظام مزامنة ذكي USB ↔ PC + إدارة GitHub كاملة", "en": "Smart USB ↔ PC sync + full GitHub management"},
    "about_features":     {"ar": "✨ الميزات الرئيسية",     "en": "✨ Key Features"},
    "about_developer":    {"ar": "👨‍💻 المطور",               "en": "👨‍💻 Developer"},
    "about_github_btn":   {"ar": "🐙  GitHub",              "en": "🐙  GitHub"},
    "about_contact_btn":  {"ar": "📧  تواصل",               "en": "📧  Contact"},
    "about_sysinfo":      {"ar": "🖥️ معلومات النظام",       "en": "🖥️ System Info"},
    "about_license":      {"ar": "📄 الرخصة",               "en": "📄 License"},
    "about_license_text": {"ar": "MIT License — مفتوح المصدر\nيمكنك استخدامه وتعديله وتوزيعه بحرية.", "en": "MIT License — Open Source\nFree to use, modify and distribute."},
    "about_sys_os":       {"ar": "النظام:",                  "en": "OS:"},
    "about_sys_python":   {"ar": "Python:",                  "en": "Python:"},
    "about_sys_device":   {"ar": "الجهاز:",                  "en": "Device:"},
    "about_sys_usb":      {"ar": "USB:",                    "en": "USB:"},
    "about_sys_data":     {"ar": "مجلد البيانات:",           "en": "Data folder:"},
    "about_sys_backup":   {"ar": "مجلد النسخ:",              "en": "Backup folder:"},
    "about_sys_name":     {"ar": "اسم الجهاز:",              "en": "Device name:"},
    "about_made_by":      {"ar": "صُنع بـ ❤️ من",           "en": "Made with ❤️ by"},
    "about_subtitle":     {"ar": "أداة مزامنة USB ↔ PC محمولة + إدارة GitHub\nتعمل بالكامل من الفلاشة — البرنامج والبيانات والإعدادات",
                           "en": "Portable USB ↔ PC sync tool + GitHub management\nRuns entirely from USB — program, data, and settings"},
    "about_stat_sync":    {"ar": "أوضاع مزامنة",            "en": "Sync modes"},
    "about_stat_perf":    {"ar": "مستويات أداء",            "en": "Perf levels"},
    "about_stat_gh":      {"ar": "تبويبات GitHub",          "en": "GitHub tabs"},
    "about_stat_lang":    {"ar": "ثنائي اللغة",             "en": "Bilingual"},
    "about_feat_title":   {"ar": "✨ المميزات الرئيسية",    "en": "✨ Key Features"},
    "about_dev_title":    {"ar": "👨‍💻 المطور",               "en": "👨‍💻 Developer"},
    "about_dev_role":     {"ar": "مطور Python · تطبيقات سطح المكتب والأتمتة", "en": "Python Developer · Desktop & Automation"},
    "about_sys_title":    {"ar": "🖥️ معلومات النظام",       "en": "🖥️ System Info"},
    "about_sys_os_lbl":   {"ar": "النظام",                  "en": "OS"},
    "about_sys_cpu_lbl":  {"ar": "المعالج",                 "en": "CPU"},
    "about_sys_ram_lbl":  {"ar": "الذاكرة",                 "en": "RAM"},
    "about_sys_dev_lbl":  {"ar": "الجهاز",                  "en": "Device"},
    "about_sys_pc_lbl":   {"ar": "اسم الجهاز",              "en": "PC Name"},
    "about_license_lbl":  {"ar": "MIT License — مفتوح المصدر", "en": "MIT License — Open Source"},
    "about_fc_sync":      {"ar": "مزامنة ذكية",             "en": "Smart Sync"},
    "about_fc_sync_d":    {"ar": "5 أوضاع — الأحدث يفوز دائماً", "en": "5 modes — newest file always wins"},
    "about_fc_snap":      {"ar": "DirSnapshot",              "en": "DirSnapshot"},
    "about_fc_snap_d":    {"ar": "فحص 2,000 مجلد بدل 200,000 ملف", "en": "Scan 2,000 dirs instead of 200,000 files"},
    "about_fc_hash":      {"ar": "xxHash",                   "en": "xxHash"},
    "about_fc_hash_d":    {"ar": "كشف التغيير 30× أسرع من MD5", "en": "Change detection 30× faster than MD5"},
    "about_fc_prof":      {"ar": "Device Profiler",          "en": "Device Profiler"},
    "about_fc_prof_d":    {"ar": "4 مستويات — يضبط الأداء تلقائياً", "en": "4 levels — auto-tunes performance"},
    "about_fc_gh":        {"ar": "GitHub كامل",              "en": "Full GitHub"},
    "about_fc_gh_d":      {"ar": "رفع + تحديث + Clone + Batch + README AI", "en": "Upload + Update + Clone + Batch + README AI"},
    "about_fc_trash":     {"ar": "حذف آمن",                 "en": "Safe Trash"},
    "about_fc_trash_d":   {"ar": "سلة محذوفات قابلة للاسترجاع 30 يوم", "en": "Recoverable trash for 30 days"},
    "about_fc_port":      {"ar": "محمول بالكامل",            "en": "Fully Portable"},
    "about_fc_port_d":    {"ar": "كل شيء على الفلاشة — انقل لأي جهاز", "en": "Everything on USB — move to any PC"},
    "about_fc_enc":       {"ar": "تشفير التوكنات",           "en": "Token Encryption"},
    "about_fc_enc_d":     {"ar": "PBKDF2 + HMAC-SHA256",     "en": "PBKDF2 + HMAC-SHA256"},
    "about_feat_1":       {"ar": "🔄  مزامنة ذكية ثنائية الاتجاه مع 4 طبقات كشف تغييرات", "en": "🔄  Smart bidirectional sync with 4-layer change detection"},
    "about_feat_2":       {"ar": "⚡  Delta Copy — نسخ الفرق فقط للملفات الكبيرة", "en": "⚡  Delta Copy — only diffs for large files"},
    "about_feat_3":       {"ar": "🔍  SyncIndex — تجاوز 95%+ من الملفات بدون إعادة حسابها", "en": "🔍  SyncIndex — skip 95%+ of files without re-checking"},
    "about_feat_4":       {"ar": "🛡️  xxHash XXH3 — أسرع 50x من SHA-256 للتحقق", "en": "🛡️  xxHash XXH3 — 50x faster than SHA-256 for verification"},
    "about_feat_5":       {"ar": "📸  Pre-sync backup تلقائي + سلة محذوفات آمنة 30 يوم", "en": "📸  Auto pre-sync backup + 30-day safe trash"},
    "about_feat_6":       {"ar": "🐙  إدارة GitHub كاملة: رفع، تحديث، Clone، Batch", "en": "🐙  Full GitHub management: upload, update, Clone, Batch"},
    "about_feat_7":       {"ar": "🤖  توليد README بالذكاء الاصطناعي (Gemini/Claude/OpenAI)", "en": "🤖  AI README generation (Gemini/Claude/OpenAI)"},
    "about_feat_8":       {"ar": "🔐  تشفير PBKDF2+HMAC لكل الأسرار", "en": "🔐  PBKDF2+HMAC encryption for all secrets"},
    "about_feat_9":       {"ar": "📊  مراقبة حية للأجهزة (CPU / RAM / USB)", "en": "📊  Live hardware monitoring (CPU / RAM / USB)"},
    "about_feat_10":      {"ar": "🌍  دعم ثنائي اللغة (عربي / إنجليزي)", "en": "🌍  Bilingual support (Arabic / English)"},
    "about_feat_11":      {"ar": "💾  وضع Portable — يشتغل من الفلاشة بدون تثبيت", "en": "💾  Portable mode — runs from USB without installation"},
    "about_dev_name":     {"ar": "الاسم: Mounir Ayad",      "en": "Name: Mounir Ayad"},
    "about_dev_email":    {"ar": "البريد: contact.ayad.mounir@gmail.com", "en": "Email: contact.ayad.mounir@gmail.com"},

    # ── Main Window ──────────────────────────────────────────────────
    "app_ready":          {"ar": "جاهز",                    "en": "Ready"},
    "now":                {"ar": "الآن",                  "en": "Just now"},
    "yesterday":          {"ar": "أمس",                   "en": "Yesterday"},
    "ago_minutes":        {"ar": "منذ {n} دقيقة",        "en": "{n}m ago"},
    "ago_hours":          {"ar": "منذ {n} ساعة",         "en": "{n}h ago"},
    "ago_days":           {"ar": "منذ {n} يوم",          "en": "{n}d ago"},
    "unknown_time":       {"ar": "—",                     "en": "—"},
    "gh_no_token":        {"ar": "أدخل الـ Token أولاً", "en": "Enter Token first"},
    "gh_repo_deleted":    {"ar": "✅ حُذف: {name}",       "en": "✅ Deleted: {name}"},
    "gh_upload_ok":       {"ar": "✅ رُفع: {name}",        "en": "✅ Uploaded: {name}"},
    "gh_clone_ok":        {"ar": "✅ Clone اكتمل",        "en": "✅ Clone done"},
    "gh_batch_ok":        {"ar": "✅ Batch اكتمل",        "en": "✅ Batch done"},
    "gh_lfs_ok":          {"ar": "✅ LFS مُفعَّل",        "en": "✅ LFS enabled"},
    "gh_rate_limit":      {"ar": "⚠️ GitHub rate limit", "en": "⚠️ GitHub rate limit"},
    "err_folder_missing": {"ar": "❌ المجلد غير موجود: {path}", "en": "❌ Folder not found: {path}"},
    "err_no_space":       {"ar": "❌ مساحة غير كافية",   "en": "❌ Not enough space"},
    "err_git_missing":    {"ar": "❌ Git غير مثبت",      "en": "❌ Git not installed"},
    "err_network":        {"ar": "❌ لا يوجد اتصال",     "en": "❌ No connection"},
    # ── Sync Engine Messages ────────────────────────────────────────
    "eng_lock_fail":     {"ar": "❌ قفل نشط — حاول لاحقاً",                 "en": "❌ Lock active — try later"},
    "eng_file_count":    {"ar": "📊 {n} ملف — {size} يحتاج تحديث",           "en": "📊 {n} files — {size} needs update"},
    "eng_need_update":   {"ar": "🔄 {n} ملف يحتاج نسخ...",                   "en": "🔄 {n} files need copying..."},
    "eng_no_changes":    {"ar": "✅ لا تغييرات — كل الملفات متطابقة",         "en": "✅ No changes — all files match"},
    "eng_presync":       {"ar": "📸 نسخة احتياطية مؤقتة: {name}",            "en": "📸 Pre-sync snapshot: {name}"},
    "eng_copied":        {"ar": "✅ {c} منسوخ | {s} متطابق | {f} خطأ",       "en": "✅ {c} copied | {s} identical | {f} failed"},
    "eng_errors_hdr":    {"ar": "❌ الأخطاء:",                                "en": "❌ Errors:"},
    "eng_retry":         {"ar": "🔄 إعادة محاولة: {name}",                   "en": "🔄 Retrying: {name}"},
    "eng_folder_missing":{"ar": "❌ المجلد غير موجود: {path}",               "en": "❌ Folder not found: {path}"},
    "eng_pc_missing":    {"ar": "❌ مجلد الجهاز غير موجود: {path}",          "en": "❌ PC folder not found: {path}"},
    "eng_scan_summary":  {"ar": "🔍 مسح: {pc} ملف PC | {usb} ملف USB",      "en": "🔍 Scan: {pc} PC files | {usb} USB files"},
    "scan_result":       {"ar": "📊 نتيجة المسح: {to_usb} PC→USB | {to_pc} USB→PC | {identical} متطابق", "en": "📊 Scan result: {to_usb} PC→USB | {to_pc} USB→PC | {identical} identical"},
    "preview_root":      {"ar": "📁 المجلد: {root}",                          "en": "📁 Folder: {root}"},
    "verify_progress":   {"ar": "🔍 فحص {n} ملف...",                         "en": "🔍 Verifying {n} files..."},

    # ── Conflict Resolution ─────────────────────────────────────────
    "conflict_title":    {"ar": "⚠️ تعارض في الملفات",                        "en": "⚠️ File Conflict"},
    "conflict_hint":     {"ar": "الملف موجود في الطرفين بإصدارات مختلفة:",   "en": "File exists on both sides with different versions:"},
    "conflict_skip":     {"ar": "تخطّي",                                      "en": "Skip"},
    "conflict_apply_all":{"ar": "تطبيق على الكل",                             "en": "Apply to all"},
    "conflict_all_pc":   {"ar": "✅ الجهاز يفوز في كل شيء",                  "en": "✅ PC wins for all"},
    "conflict_all_usb":  {"ar": "✅ الفلاشة تفوز في كل شيء",                 "en": "✅ USB wins for all"},
    "conflict_all_both": {"ar": "✅ الأحدث يفوز في كل شيء",                  "en": "✅ Newest wins for all"},
    "perf_usb_mode":      {"ar": "⚡ وضع USB (بدون fsync)", "en": "⚡ USB mode (no fsync)"},
    "perf_ssd_mode":      {"ar": "⚡ وضع SSD",            "en": "⚡ SSD mode"},
    "checking_space":     {"ar": "🔍 فحص المساحة...",    "en": "🔍 Checking space..."},
    "space_ok":           {"ar": "✅ مساحة كافية: {free} متاح", "en": "✅ Space OK: {free} free"},
}


class Lang:
    _lang:       str   = "ar"
    _font_scale: float = 1.0

    @classmethod
    def set(cls, lang: str) -> None:
        if lang in ("ar", "en"):
            cls._lang = lang

    @classmethod
    def set_lang(cls, lang: str) -> None:
        cls.set(lang)

    @classmethod
    def get(cls) -> str:
        return cls._lang

    @classmethod
    def t(cls, key: str, **kwargs) -> str:
        entry = _STRINGS.get(key)
        if entry is None:
            return key
        text = entry.get(cls._lang) or entry.get("ar") or key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    @classmethod
    def set_font_scale(cls, scale: float) -> None:
        cls._font_scale = max(0.5, min(scale, 3.0))

    @classmethod
    def scaled(cls, size: int) -> int:
        return max(8, int(size * cls._font_scale))

    @classmethod
    def add(cls, key: str, ar: str, en: str = "") -> None:
        _STRINGS[key] = {"ar": ar, "en": en or ar}


class _L:
    def t(self, key: str, **kw) -> str:
        return Lang.t(key, **kw)
    def get(self, key: str, default: str = "...") -> str:
        return Lang.t(key) if key in _STRINGS else default
    def set(self, lang: str) -> None:
        Lang.set(lang)


L = _L()
