@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Lab de Cortes

where python >nul 2>nul || (echo [!] Python nao encontrado. Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH". & pause & exit /b 1)
where ffmpeg >nul 2>nul || (
  echo [!] FFmpeg nao encontrado. Tentando instalar com o winget...
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  echo.
  echo Feche esta janela e abra o iniciar.bat de novo para o FFmpeg ser reconhecido.
  pause & exit /b 1
)

where deno >nul 2>nul || (
  echo Instalando o Deno - o yt-dlp precisa dele para baixar do YouTube...
  winget install --id DenoLand.Deno -e --accept-source-agreements --accept-package-agreements >nul 2>nul
)

if not exist .venv (
  echo Criando ambiente Python - so na primeira vez...
  python -m venv .venv || (pause & exit /b 1)
)
call .venv\Scripts\activate.bat
echo Verificando dependencias...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
python -m pip install -q -U "yt-dlp[default,curl-cffi]"
python app.py
pause
