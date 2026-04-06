@echo off
chcp 65001 >nul 2>&1
title AyadFlowSync v3.0 - Build

echo.
echo  ===================================================
echo   AyadFlowSync v3.0 - Portable EXE Builder
echo  ===================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found! Install from python.org
    pause & exit /b 1
)
echo  [OK] Python found:
python --version

:: Check Python 3.9+
python -c "import sys; exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python 3.9 or higher required!
    pause & exit /b 1
)

:: Install dependencies
echo.
echo  [..] Installing dependencies...
pip install PyQt6 xxhash psutil requests cryptography GitPython packaging --quiet
if errorlevel 1 (
    echo  ERROR: Failed to install dependencies!
    pause & exit /b 1
)
pip install pyinstaller --quiet
if errorlevel 1 (
    echo  ERROR: Failed to install PyInstaller!
    pause & exit /b 1
)
echo  [OK] Dependencies installed

:: Check run.py
if not exist "run.py" (
    echo  ERROR: run.py not found! Extract the full archive.
    pause & exit /b 1
)
echo  [OK] Entry point: run.py

:: Check icon
if exist "assets\icon.ico" (
    echo  [OK] Icon: assets\icon.ico
) else (
    echo  [..] No icon found - building without icon
)

:: Clean previous build
echo.
echo  [..] Cleaning previous build...
if exist "build" rmdir /s /q "build"
if exist "dist\AyadFlowSync" rmdir /s /q "dist\AyadFlowSync"

:: Build EXE
echo.
echo  [..] Building EXE... (3-8 minutes)
echo.
pyinstaller AyadFlowSync.spec --noconfirm --clean

if errorlevel 1 (
    echo.
    echo  ERROR: Build FAILED!
    echo  Tips:
    echo    - Run as Administrator
    echo    - Disable antivirus temporarily
    echo    - Try: pip install pyinstaller --upgrade
    pause & exit /b 1
)

:: Verify EXE exists
if not exist "dist\AyadFlowSync\AyadFlowSync.exe" (
    echo  ERROR: EXE not found after build!
    pause & exit /b 1
)

:: Portable setup
echo.
echo  [..] Setting up portable structure...
echo. > "dist\AyadFlowSync\.portable"
if not exist "dist\AyadFlowSync\data" mkdir "dist\AyadFlowSync\data"
if not exist "dist\AyadFlowSync\data\logs" mkdir "dist\AyadFlowSync\data\logs"
if not exist "dist\AyadFlowSync\FlowSync_Backup" mkdir "dist\AyadFlowSync\FlowSync_Backup"
if exist "README.md"    copy "README.md"    "dist\AyadFlowSync\" >nul
if exist "README_AR.md" copy "README_AR.md" "dist\AyadFlowSync\" >nul
if exist "assets\icon.ico" copy "assets\icon.ico" "dist\AyadFlowSync\" >nul

echo.
echo  ===================================================
echo   BUILD COMPLETE!
echo  ===================================================
echo.
echo   Output : dist\AyadFlowSync\
echo   EXE    : dist\AyadFlowSync\AyadFlowSync.exe
echo.
echo   To use as portable:
echo   Copy the ENTIRE dist\AyadFlowSync\ folder to USB
echo   Run AyadFlowSync.exe from there
echo.

explorer "dist\AyadFlowSync"
pause
