@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title NAI - instalacao dos pre-requisitos
echo ==========================================================
echo   NAI - Mundo SENAI : instalacao dos pre-requisitos
echo   (so precisa rodar 1 vez, com internet)
echo ==========================================================
echo.

set "PYVER=3.12.10"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe"
set "VCURL=https://aka.ms/vs/17/release/vc_redist.x64.exe"

if /i not "%PROCESSOR_ARCHITECTURE%"=="AMD64" if /i not "%PROCESSOR_ARCHITEW6432%"=="AMD64" goto :erroArq

rem ---------- 1. Python 3.12 ----------
echo [1/4] Verificando o Python 3.12...
call :acharPython
if defined PY goto :temPython
echo       Nao encontrado. Baixando o Python %PYVER%...
set "INST=%TEMP%\python-%PYVER%-amd64.exe"
call :baixar "%PYURL%" "%INST%"
if not exist "%INST%" goto :erroDownload
echo       Instalando o Python (pode levar 1 a 2 minutos)...
start "" /wait "%INST%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0 Include_doc=0
call :acharPython
if not defined PY goto :erroPython
:temPython
echo       OK: %PY%
echo.

rem ---------- 2. Visual C++ (necessario para o reconhecimento de maos) ----------
echo [2/4] Verificando o Microsoft Visual C++ Redistributable...
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if not errorlevel 1 goto :temVC
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if not errorlevel 1 goto :temVC
echo       Nao encontrado. Baixando...
set "VCINST=%TEMP%\vc_redist.x64.exe"
call :baixar "%VCURL%" "%VCINST%"
if not exist "%VCINST%" goto :avisoVC
echo       Instalando - se o Windows pedir permissao, clique em SIM.
start "" /wait "%VCINST%" /install /quiet /norestart
:temVC
echo       OK
echo.

rem ---------- 3. Ambiente e bibliotecas ----------
call :acharVenv
echo [3/4] Instalando as bibliotecas (mediapipe, opencv, websockets) em %VENV% ...
if exist "%VENV%\Scripts\python.exe" goto :temVenv
"%PY%" -m venv "%VENV%"
if not exist "%VENV%\Scripts\python.exe" goto :erroVenv
:temVenv
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip --disable-pip-version-check -q
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 goto :erroPip
echo.

rem ---------- 4. Teste final ----------
echo [4/4] Testando...
"%VENV%\Scripts\python.exe" -c "import cv2, websockets, mediapipe as mp; mp.solutions.hands.Hands().close(); print('      OK: mediapipe', mp.__version__, '| opencv', cv2.__version__, '| websockets', websockets.__version__)"
if errorlevel 1 goto :erroTeste

powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\NAI Mundo SENAI.lnk'); $s.TargetPath='%~dp0iniciar_NAI.bat'; $s.WorkingDirectory='%~dp0'; $s.Save()" >nul 2>&1
echo.
echo ==========================================================
echo   TUDO PRONTO!
echo   - Atalho "NAI Mundo SENAI" criado na Area de Trabalho
echo   - Para conferir a camera e as maos: testar_maos.bat
echo   - Para o evento: iniciar_NAI.bat (ou o atalho)
echo ==========================================================
pause
exit /b 0

rem ================= funcoes =================
:acharVenv
rem a biblioteca de maos (mediapipe) nao funciona em pasta com acento: o ambiente fica fora da pasta da NAI
set "VENV=%LOCALAPPDATA%\NAI-venv"
powershell -NoProfile -Command "if ($env:LOCALAPPDATA -match '[^\x00-\x7F]') { exit 1 }" >nul 2>&1
if errorlevel 1 set "VENV=C:\NAI-venv"
goto :eof

:acharPython
set "PY="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if defined PY goto :eof
if exist "%ProgramFiles%\Python312\python.exe" set "PY=%ProgramFiles%\Python312\python.exe"
if defined PY goto :eof
for /f "delims=" %%i in ('py -3.12 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
goto :eof

:baixar
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; $ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing -Uri '%~1' -OutFile '%~2' } catch { exit 1 }"
if errorlevel 1 if exist "%~2" del "%~2"
goto :eof

rem ================= erros =================
:erroArq
echo [ERRO] Este computador nao e 64 bits (x64). O reconhecimento de maos precisa de Windows 64 bits.
goto :fimErro
:erroDownload
echo [ERRO] Nao consegui baixar o Python. Verifique a internet e rode de novo.
echo        Ou instale manualmente: %PYURL%
echo        (marque "Add python.exe to PATH") e rode este arquivo de novo.
goto :fimErro
:erroPython
echo [ERRO] A instalacao do Python nao terminou. Rode este arquivo de novo,
echo        ou instale manualmente: %PYURL%
goto :fimErro
:avisoVC
echo [AVISO] Nao consegui baixar o Visual C++. Continuando mesmo assim...
goto :temVC
:erroVenv
echo [ERRO] Nao consegui criar o ambiente Python em %VENV%.
echo        Verifique se o antivirus bloqueou e rode de novo.
goto :fimErro
:erroPip
echo [ERRO] Falha ao instalar as bibliotecas. Verifique a internet e rode de novo.
goto :fimErro
:erroTeste
echo [ERRO] As bibliotecas instalaram, mas o teste falhou (veja a mensagem acima).
echo        Reinicie o computador e rode este arquivo de novo.
goto :fimErro
:fimErro
echo.
pause
exit /b 1
