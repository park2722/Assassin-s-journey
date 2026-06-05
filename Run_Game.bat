@echo off
chcp 65001 > nul
title AR Assesin's Journey

echo ===================================================
echo     AR Assesin's Journey 서버 시작 준비 중...
echo ===================================================

REM 1. 파이썬 설치 여부 확인
python --version >nul 2>&1
if errorlevel 1 goto NOPYTHON

REM 2. 가상환경 존재 여부 확인
if exist "venv\Scripts\activate.bat" goto RUN_GAME

REM 3. 가상환경이 없으면 새로 설치
echo.
echo [시스템] 🛠️ 최초 실행 감지: 가상 환경을 생성하고 필수 라이브러리를 설치합니다.
echo (인터넷 속도에 따라 1~3분 정도 소요될 수 있습니다. 창을 닫지 마세요...)
echo.

python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ✅ 설치가 모두 완료되었습니다!

:RUN_GAME
call venv\Scripts\activate
echo ===================================================
echo     서버가 구동 중입니다. 창을 닫으면 종료됩니다.
echo ===================================================
python main.py
pause
exit

:NOPYTHON
echo 🚨 오류: 파이썬이 설치되어 있지 않거나 환경변수(PATH)에 등록되지 않았습니다!
echo 파이썬(Python 3.8 이상)을 먼저 설치해 주시기 바랍니다.
pause
exit