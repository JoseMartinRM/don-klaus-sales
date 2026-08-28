import sys
import io

# Set UTF-8 for console output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import asyncio
import httpx
from database import init_db, list_campaigns, list_products, get_stats

def test_database():
    print("-> Verificando Base de Datos SQLite...")
    init_db()
    camps = list_campaigns()
    prods = list_products()
    stats = get_stats()
    
    assert len(camps) > 0, "Debería haber al menos una campaña por defecto"
    assert len(prods) > 0, "Debería haber al menos un producto por defecto"
    print(f"   [OK] {len(camps)} campañas encontradas.")
    print(f"   [OK] {len(prods)} productos encontrados.")
    print(f"   [OK] Estadísticas iniciales: {stats}")

async def test_fastapi_endpoints():
    print("\n-> Verificando Endpoints de FastAPI...")
    from main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Test Index
        r_index = await ac.get("/")
        assert r_index.status_code == 200, f"Index failed: {r_index.status_code}"
        print("   [OK] GET / (Dashboard UI) -> 200 OK")

        # 2. Test Stats
        r_stats = await ac.get("/api/stats")
        assert r_stats.status_code == 200
        print("   [OK] GET /api/stats -> 200 OK")

        # 3. Test Webhook Verification
        r_wh_valid = await ac.get("/webhook?hub.mode=subscribe&hub.verify_token=instaflow_verify_token_secure_2026&hub.challenge=998877")
        assert r_wh_valid.status_code == 200 and r_wh_valid.text == "998877", f"Webhook verify failed: {r_wh_valid.text}"
        print("   [OK] GET /webhook (Meta Hub Verification) -> 200 OK con Challenge validado")

        # 4. Test Simulator Comment Match
        r_sim = await ac.post("/api/simulator/comment", json={
            "username": "usuario_test",
            "comment_text": "QUIERO el curso por favor",
            "post_id": "test_post_1"
        })
        sim_data = r_sim.json()
        assert sim_data.get("matched") is True, f"Simulator match failed: {sim_data}"
        assert len(sim_data.get("dm_messages", [])) > 0
        print(f"   [OK] POST /api/simulator/comment -> Match con '{sim_data['campaign_name']}' ({len(sim_data['dm_messages'])} pasos de DM)")

        # 5. Test Simulator Chat
        r_chat = await ac.post("/api/simulator/chat", json={
            "user_id": "test_user_001",
            "username": "usuario_test",
            "message_text": "¿Cuál es el precio y cómo puedo comprarlo?"
        })
        chat_data = r_chat.json()
        assert "reply" in chat_data and len(chat_data["reply"]) > 5
        print(f"   [OK] POST /api/simulator/chat -> Respuesta IA generada: '{chat_data['reply'][:60]}...'")

        # 6. Test Webhook POST Event
        mock_meta_comment_event = {
            "object": "instagram",
            "entry": [{
                "id": "ig_page_123",
                "time": 1700000000,
                "changes": [{
                    "field": "comments",
                    "value": {
                        "id": "comment_999",
                        "text": "PRECIO",
                        "post_id": "post_777",
                        "from": {
                            "id": "user_456",
                            "username": "comprador_real"
                        }
                    }
                }]
            }]
        }
        r_wh_post = await ac.post("/webhook", json=mock_meta_comment_event)
        assert r_wh_post.status_code == 200
        print("   [OK] POST /webhook (Meta Comment Event Ingestion) -> 200 OK")

if __name__ == "__main__":
    test_database()
    asyncio.run(test_fastapi_endpoints())
    print("\n" + "="*50)
    print("✅ TODAS LAS PRUEBAS PASARON CON ÉXITO")
    print("="*50)
