@echo off
chcp 65001 > nul
title InstaFlow Sales AI - Modo Online con Tunel Gratuito
echo ===================================================================
echo               INSTAFLOW ONLINE - CONEXION CON INSTAGRAM
echo ===================================================================
echo 1. Iniciando Servidor Local en http://localhost:8000 ...
start "" python run.py

timeout /t 3 /nobreak > nul

echo.
echo 2. Generando enlace publico seguro con Cloudflare Tunnel (100%% Gratis)...
echo Copia la URL que termine en ".trycloudflare.com" para pegarla en Meta Developers.
echo ===================================================================
echo.
npx -y cloudflared tunnel --url http://localhost:8000
pause
