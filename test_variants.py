import sys
import io

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

import asyncio
import httpx

async def test_variants():
    test_words = ['reglas', 'regla', 'guía', 'guia', 'pdf', 'klaus', 'sueldo', 'mi sueldo', 'deuda', 'mis deudas', 'préstamos', 'prestamos']
    async with httpx.AsyncClient() as client:
        for w in test_words:
            r = await client.post('http://localhost:8000/api/simulator/comment', json={'username': 'user_test', 'comment_text': w})
            data = r.json()
            status = f"MATCH con '{data.get('campaign_name')}'" if data.get('matched') else "NO MATCH"
            print(f"Palabra: '{w}' -> {status}")

if __name__ == '__main__':
    asyncio.run(test_variants())
