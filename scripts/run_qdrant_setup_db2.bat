@echo off
echo =====================================================
echo QDRANT DB2 SETUP - Creating Collections
echo =====================================================
echo.

cd /d "%~dp0.."

set PYTHONHOME=
set PYTHONPATH=

echo Running Qdrant DB2 setup...
python scripts\qdrant_setup_db2.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Setup completed successfully!
) else (
    echo.
    echo Setup failed with error code: %ERRORLEVEL%
)

pause
