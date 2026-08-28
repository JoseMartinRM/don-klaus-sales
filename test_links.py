import asyncio
import httpx

async def test_links():
    async with httpx.AsyncClient() as client:
        # Test 1: Sueldo Trigger
        r1 = await client.post('http://localhost:8000/api/simulator/comment', json={'username': 'prospecto_sueldo', 'comment_text': 'sueldo'})
        dms_sueldo = r1.json()['dm_messages']
        print("[SUELDO] Link en Mensaje 2:", "https://klaus-order-rules.lovable.app/" in dms_sueldo[1]['text'])
        print(dms_sueldo[1]['text'][-60:])

        # Test 2: Deuda Trigger
        r2 = await client.post('http://localhost:8000/api/simulator/comment', json={'username': 'prospecto_deuda', 'comment_text': 'deuda'})
        dms_deuda = r2.json()['dm_messages']
        print("\n[DEUDA] Link en Mensaje 2:", "https://zero-debt-protocol.lovable.app/" in dms_deuda[1]['text'])
        print(dms_deuda[1]['text'][-60:])

if __name__ == '__main__':
    asyncio.run(test_links())
