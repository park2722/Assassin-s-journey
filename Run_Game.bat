@echo off
:: 1. 한글 깨짐 방지 (UTF-8 인코딩 강제 적용)
chcp 65001 > nul

title AR Encounter and Capture Creature
echo ===================================================
echo     AR Creature Game 서버를 시작합니다...
echo     (게임을 종료하려면 이 창을 닫아주세요)
echo ===================================================

:: 2. 유저님의 가상 환경(venv)을 먼저 켜고 파이썬을 실행합니다!
call venv\Scripts\activate
python main.py

pause