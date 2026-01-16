@echo off
cd /d "%~dp0"

echo.
echo ========================================
echo   AutoCoder - Autonomous Coding Agent
echo ========================================
echo.

REM Load .env file if it exists
if exist .env (
    for /f "tokens=1,2 delims==" %%a in ('type .env ^| findstr /v "^#" ^| findstr /v "^$"') do (
        set %%a=%%b
    )
)

REM Verify autocoder CLI exists before running
where autocoder >nul 2>nul
if %errorlevel% neq 0 (
  echo.
  echo [ERROR] autocoder command not found
  echo.
  echo Please install the package first:
  echo   pip install -e '.[dev]'
  echo.
  pause
  exit /b 1
)

REM Run autocoder CLI
autocoder
set EXIT_CODE=%errorlevel%
if %EXIT_CODE% neq 0 (
  echo.
  echo [ERROR] autocoder exited with code %EXIT_CODE%
  echo.
  pause
  exit /b %EXIT_CODE%
)
