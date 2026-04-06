#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui.qt.styles
============
QSS Stylesheet للواجهة — Professional Slate Dark.
"""

MAIN_STYLESHEET = """
/* ══════════════════════════════════════════════════════════
   AyadFlowSync — Professional Slate Dark Theme (PyQt6)
   ══════════════════════════════════════════════════════════ */

/* ── Global ──────────────────────────────────────────────── */
QWidget {
    background-color: #0b0d11;
    color: #e2e8f0;
    font-family: "Segoe UI", "Cairo", "Tahoma", sans-serif;
    font-size: 16px;
}

QMainWindow {
    background-color: #0b0d11;
}

/* ── Sidebar ─────────────────────────────────────────────── */
#Sidebar {
    background-color: #0d0f14;
    border-right: 1px solid #21262d;
    min-width: 220px;
    max-width: 220px;
}

#SidebarTitle {
    color: #818cf8;
    font-size: 18px;
    font-weight: bold;
    padding: 8px 12px 4px 12px;
    letter-spacing: 1px;
}

#SidebarVersion {
    color: #4a5568;
    font-size: 16px;
    padding: 0 12px 12px 12px;
}

/* ── Sidebar Buttons ─────────────────────────────────────── */
QPushButton#NavBtn {
    background-color: transparent;
    color: #718096;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: left;
    font-size: 16px;
    margin: 1px 8px;
}

QPushButton#NavBtn:hover {
    background-color: #13161e;
    color: #e2e8f0;
}

QPushButton#NavBtn[active="true"] {
    background-color: #1e2433;
    color: #818cf8;
    border-left: 3px solid #6366f1;
    font-weight: bold;
}

/* ── Cards ───────────────────────────────────────────────── */
QFrame#Card {
    background-color: #13161e;
    border: 1px solid #21262d;
    border-radius: 10px;
}

QFrame#CardInner {
    background-color: #1a1e28;
    border: 1px solid #21262d;
    border-radius: 8px;
}

/* ── Buttons ─────────────────────────────────────────────── */
QPushButton {
    background-color: #1e2433;
    color: #e2e8f0;
    border: 1px solid #2d3548;
    border-radius: 7px;
    padding: 7px 16px;
    font-size: 18px;
}

QPushButton:hover {
    background-color: #252c3d;
    border-color: #6366f1;
    color: #c7d2fe;
}

QPushButton:pressed {
    background-color: #1a2030;
}

QPushButton:disabled {
    background-color: #111318;
    color: #374151;
    border-color: #1a1e28;
}

QPushButton#PrimaryBtn {
    background-color: #4f46e5;
    color: #ffffff;
    border: none;
    font-weight: bold;
    padding: 8px 20px;
}

QPushButton#PrimaryBtn:hover {
    background-color: #5b52f0;
}

QPushButton#SuccessBtn {
    background-color: #059669;
    color: #ffffff;
    border: none;
    font-weight: bold;
}

QPushButton#SuccessBtn:hover {
    background-color: #10b981;
}

QPushButton#DangerBtn {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
    font-weight: bold;
}

QPushButton#DangerBtn:hover {
    background-color: #ef4444;
}

QPushButton#WarnBtn {
    background-color: #d97706;
    color: #ffffff;
    border: none;
    font-weight: bold;
}

QPushButton#WarnBtn:hover {
    background-color: #f59e0b;
}

/* ── Labels ──────────────────────────────────────────────── */
QLabel {
    color: #e2e8f0;
    background-color: transparent;
}

QLabel#SectionTitle {
    color: #818cf8;
    font-size: 17px;
    font-weight: bold;
    padding: 4px 0;
}

QLabel#Muted {
    color: #4a5568;
    font-size: 17px;
}

QLabel#Dim {
    color: #718096;
    font-size: 18px;
}

QLabel#StatusOk {
    color: #34d399;
    font-weight: bold;
}

QLabel#StatusWarn {
    color: #fbbf24;
    font-weight: bold;
}

QLabel#StatusError {
    color: #f87171;
    font-weight: bold;
}

/* ── Progress Bars ───────────────────────────────────────── */
QProgressBar {
    background-color: #1a1e28;
    border: 1px solid #21262d;
    border-radius: 5px;
    text-align: center;
    color: #718096;
    font-size: 17px;
    height: 16px;
}

QProgressBar::chunk {
    background-color: #6366f1;
    border-radius: 4px;
}

QProgressBar#CpuBar::chunk { background-color: #34d399; }
QProgressBar#RamBar::chunk { background-color: #60a5fa; }
QProgressBar#UsbBar::chunk { background-color: #a78bfa; }

/* ── TextEdit / Log ──────────────────────────────────────── */
QTextEdit, QPlainTextEdit {
    background-color: #090b0f;
    color: #9ca3af;
    border: 1px solid #21262d;
    border-radius: 8px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 18px;
    padding: 8px;
    selection-background-color: #2d3748;
}

QTextEdit#LogBox {
    font-size: 17px;
    line-height: 1.5;
}

/* ── LineEdit ────────────────────────────────────────────── */
QLineEdit {
    background-color: #13161e;
    color: #e2e8f0;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 18px;
}

QLineEdit:focus {
    border-color: #6366f1;
    background-color: #161a24;
}

/* ── ComboBox ────────────────────────────────────────────── */
QComboBox {
    background-color: #13161e;
    color: #e2e8f0;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 18px;
    min-height: 28px;
}

QComboBox:hover {
    border-color: #6366f1;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #13161e;
    color: #e2e8f0;
    border: 1px solid #21262d;
    border-radius: 6px;
    selection-background-color: #1e2433;
    outline: none;
}

/* ── ListWidget ──────────────────────────────────────────── */
QListWidget {
    background-color: #090b0f;
    color: #e2e8f0;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}

QListWidget::item {
    padding: 7px 10px;
    border-radius: 5px;
    margin: 1px 2px;
}

QListWidget::item:hover {
    background-color: #13161e;
}

QListWidget::item:selected {
    background-color: #1e2433;
    color: #818cf8;
}

/* ── TabWidget ───────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #21262d;
    border-radius: 8px;
    background-color: #0b0d11;
}

QTabBar::tab {
    background-color: #13161e;
    color: #718096;
    padding: 8px 18px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    border: 1px solid #21262d;
    font-size: 18px;
}

QTabBar::tab:selected {
    background-color: #1e2433;
    color: #818cf8;
    border-bottom: 2px solid #6366f1;
}

QTabBar::tab:hover {
    background-color: #1a1e28;
    color: #e2e8f0;
}

/* ── ScrollBar ───────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #0b0d11;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background-color: #21262d;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #374151;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #0b0d11;
    height: 8px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background-color: #21262d;
    border-radius: 4px;
    min-width: 30px;
}

/* ── Splitter ────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #21262d;
    width: 1px;
    height: 1px;
}

/* ── Separator ───────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: #21262d;
    background-color: #21262d;
    max-height: 1px;
}

/* ── CheckBox ────────────────────────────────────────────── */
QCheckBox {
    color: #e2e8f0;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #374151;
    border-radius: 4px;
    background-color: #13161e;
}

QCheckBox::indicator:checked {
    background-color: #6366f1;
    border-color: #6366f1;
    image: url(none);
}

/* ── ToolTip ─────────────────────────────────────────────── */
QToolTip {
    background-color: #13161e;
    color: #e2e8f0;
    border: 1px solid #21262d;
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 17px;
}

/* ── StatusBar ───────────────────────────────────────────── */
QStatusBar {
    background-color: #0d0f14;
    color: #718096;
    border-top: 1px solid #21262d;
    font-size: 17px;
}

QStatusBar::item {
    border: none;
}
"""
