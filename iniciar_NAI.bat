@echo off
chcp 65001 >nul
cd /d "%~dp0"
call :acharVenv
if not exist "%VENV%\Scripts\python.exe" goto :semInstalar
title NAI - Mundo SENAI  (F = fechar a NAI)
"%VENV%\Scripts\python.exe" nai_maos.py %*
if errorlevel 1 pause
exit /b

:semInstalar
echo Rode primeiro o arquivo instalar.bat
pause
exit /b 1

:acharVenv
rem a biblioteca de maos (mediapipe) nao funciona em pasta com acento: o ambiente fica fora da pasta da NAI
set "VENV=%LOCALAPPDATA%\NAI-venv"
powershell -NoProfile -Command "if ($env:LOCALAPPDATA -match '[^\x00-\x7F]') { exit 1 }" >nul 2>&1
if errorlevel 1 set "VENV=C:\NAI-venv"
goto :eof
