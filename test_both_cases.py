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

async def test_both_cases():
    test_words = [
        # MAYÚSCULAS
        'REGLAS', 'SUELDO', 'DEUDA', 'GUÍA', 'PDF', 'QUIERO',
        # minúsculas
        'reglas', 'sueldo', 'deuda', 'guia', 'pdf', 'quiero',
        # Mixtas / Capitalizadas
        'Reglas', 'Sueldo', 'Deuda', 'Guía', 'Pdf', 'Quiero'
    ]
    async with httpx.AsyncClient() as client:
        for w in test_words:
            r = await client.post('http://localhost:8000/api/simulator/comment', json={'username': 'user_test', 'comment_text': w})
            data = r.json()
            status = f"✅ MATCH con '{data.get('campaign_name')}'" if data.get('matched') else "❌ NO MATCH"
            print(f"[{w:8}] -> {status}")

if __name__ == '__main__':
    asyncio.run(test_both_cases())
