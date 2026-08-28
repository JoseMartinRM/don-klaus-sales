import sys
import io

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

import os
import webbrowser
import uvicorn
from database import init_db
from config import config

def main():
    print("=" * 65)
    print(">>> INICIANDO INSTAFLOW SALES AI (REEMPLAZO MANYCHAT) <<<")
    print("=" * 65)
    print(f"• Servidor Web Local: http://localhost:{config.PORT}")
    print(f"• Endpoint Webhook:   http://localhost:{config.PORT}/webhook")
    print("• Base de Datos:      SQLite (instaflow.db)")
    print("=" * 65)
    
    init_db()

    # Automatically open browser
    try:
        webbrowser.open(f"http://localhost:{config.PORT}")
    except Exception:
        pass

    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)

if __name__ == "__main__":
    main()
