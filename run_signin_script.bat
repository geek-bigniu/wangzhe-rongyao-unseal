@echo off
chcp 65001 >nul
set PYTHONPATH=O:\.pyenv\pyenv-win\versions\3.9.10
set SCRIPT_PATH=K:\pythonProject\王者荣耀解封\营地自动签到.py
set LOG_FILE=K:\pythonProject\王者荣耀解封\signin_log.txt
set DIR_PATH=K:\pythonProject\王者荣耀解封

:: 记录开始时间
echo %DATE% %TIME% - Starting script execution >> %LOG_FILE%

:: 检查 K 盘是否存在
if not exist K:\ (
    echo %DATE% %TIME% - Error: K drive not found >> %LOG_FILE%
    exit /b 1
)

:: 检查目录是否存在
if not exist "%DIR_PATH%" (
    echo %DATE% %TIME% - Error: Directory %DIR_PATH% not found >> %LOG_FILE%
    exit /b 1
)

:: 检查 Python 可执行文件
if not exist "%PYTHONPATH%\python.exe" (
    echo %DATE% %TIME% - Error: Python not found at %PYTHONPATH%\python.exe >> %LOG_FILE%
    exit /b 1
)

:: 检查脚本文件
if not exist "%SCRIPT_PATH%" (
    echo %DATE% %TIME% - Error: Script file not found at %SCRIPT_PATH% >> %LOG_FILE%
    exit /b 1
)

:: 运行脚本
echo %DATE% %TIME% - Attempting to run script %SCRIPT_PATH% >> %LOG_FILE%
"%PYTHONPATH%\python.exe" "%SCRIPT_PATH%" >> %LOG_FILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %DATE% %TIME% - Script execution failed with error code %ERRORLEVEL% >> %LOG_FILE%
) else (
    echo %DATE% %TIME% - Script executed successfully >> %LOG_FILE%
)