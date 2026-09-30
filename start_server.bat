@echo off
cd /d "%~dp0"
echo ========================================================
echo  Starting PDF Auto Rename Web Service
echo  Access via: http://localhost:8000
echo ========================================================
python app.py
pause
