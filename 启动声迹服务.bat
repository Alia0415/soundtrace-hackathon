@echo off
chcp 65001 >nul
cd /d %~dp0
echo SoundTrace MVP 服务启动中... 浏览器打开 http://127.0.0.1:8090
"%~dp0..\hackathon-env\Scripts\python.exe" soundtrace_gpu.py
pause
