@echo off
chcp 65001 > nul
title InstaFlow Sales AI - Automatizacion de Instagram
echo ===================================================================
echo               INSTAFLOW SALES AI - REEMPLAZO MANYCHAT
echo ===================================================================
echo Iniciando servidor en http://localhost:8000 ...
start http://localhost:8000
python run.py
pause
