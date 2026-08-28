import sys
import io

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

import asyncio
import json
import logging
import random
import re
import time
import unicodedata
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional, Set

import uvicorn
from fastapi import FastAPI, Request, Response, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import config, BASE_DIR
from database import (
    init_db, get_settings, update_settings,
    list_campaigns, get_campaign, create_campaign, update_campaign, delete_campaign,
    list_products, create_product, update_product, delete_product,
    record_lead, list_leads, add_activity_log, list_activity_logs,
    get_stats, get_conversation_history
)
from meta_client import InstagramGraphClient
from sales_agent import sales_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("instaflow_server")

# Cache to avoid infinite loops and duplicate processing
PROCESSED_COMMENTS: Dict[str, float] = {}
PROCESSED_MESSAGES: Dict[str, float] = {}

def normalize_text(text: str) -> str:
    """
    Normaliza texto eliminando acentos, tildes y pasando a minúsculas.
    Ejemplo: 'Guía' -> 'guia', 'FRÍAS' -> 'frias', 'Información' -> 'informacion'
    """
    if not text:
        return ""
    text_norm = unicodedata.normalize('NFKD', str(text))
    text_clean = ''.join(c for c in text_norm if not unicodedata.combining(c))
    return text_clean.strip().lower()

def clean_dedup_cache():
    now = time.time()
    for cid in list(PROCESSED_COMMENTS.keys()):
        if now - PROCESSED_COMMENTS[cid] > 600:
            PROCESSED_COMMENTS.pop(cid, None)
    for mid in list(PROCESSED_MESSAGES.keys()):
        if now - PROCESSED_MESSAGES[mid] > 600:
            PROCESSED_MESSAGES.pop(mid, None)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Base de datos SQLite inicializada correctamente.")
    yield

app = FastAPI(title="InstaFlow Sales AI - ManyChat Alternative", lifespan=lifespan)

# Mount static files
static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

def get_graph_client() -> InstagramGraphClient:
    settings = get_settings()
    token = settings.get("meta_access_token", config.META_ACCESS_TOKEN)
    version = settings.get("graph_api_version", config.GRAPH_API_VERSION)
    return InstagramGraphClient(access_token=token, graph_version=version)

# ----------------- META WEBHOOKS -----------------

@app.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge")
):
    settings = get_settings()
    expected_token = settings.get("meta_verify_token", config.META_VERIFY_TOKEN)

    logger.info(f"Webhook Verification Request: mode={hub_mode}, token={hub_verify_token}")

    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("¡Verificación de Webhook de Meta exitosa!")
        add_activity_log("SYSTEM", "Webhook verificado exitosamente por Meta Graph API.")
        return Response(content=hub_challenge, media_type="text/plain", status_code=200)

    logger.warning("Fallo en verificación de Webhook: Token inválido.")
    return Response(content="Verification failed", status_code=403)


async def execute_dm_sequence(page_id: str, recipient_id: str, comment_id: Optional[str], dm_steps: List[Dict[str, Any]], username: str):
    client = get_graph_client()
    for idx, step in enumerate(dm_steps):
        text = step.get("text", "")
        delay = int(step.get("delay_seconds", 0))

        text = text.replace("@username", f"@{username}").replace("{{username}}", username)

        if delay > 0:
            await asyncio.sleep(delay)

        if idx == 0 and comment_id:
            await client.send_private_message_by_comment(page_id, comment_id, text)
        else:
            await client.send_direct_message(page_id, recipient_id, text)


def match_keyword(comment_text: str, keywords_str: str, match_mode: str) -> bool:
    if not comment_text or not keywords_str:
        return False

    # Normalizar eliminando tildes y a minúsculas
    comment_clean = normalize_text(comment_text)
    keywords = [normalize_text(k) for k in keywords_str.split(",") if k.strip()]

    if match_mode == "any" or "*" in keywords:
        return True

    if match_mode == "exact":
        return any(comment_clean == k for k in keywords)

    if match_mode == "regex":
        for k in keywords:
            try:
                if re.search(k, comment_clean):
                    return True
            except Exception:
                pass
        return False

    # Default 'contains'
    return any(k in comment_clean for k in keywords)


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        return Response(content="Invalid JSON", status_code=400)

    raw_json_str = json.dumps(body, ensure_ascii=False)
    logger.info(f"Webhook Event Received: {raw_json_str}")
    
    clean_dedup_cache()

    settings = get_settings()
    my_ig_id = settings.get("instagram_account_id", "").strip()
    my_page_id = settings.get("meta_page_id", config.META_PAGE_ID).strip()
    target_id = my_ig_id or my_page_id or "me"

    entries = body.get("entry", [])
    campaigns = list_campaigns()
    active_campaigns = [c for c in campaigns if c.get("is_active")]

    for entry in entries:
        entry_id = entry.get("id", "")

        # 1. Comentarios en Feed / Posts / Reels
        changes = entry.get("changes", [])
        for change in changes:
            field = change.get("field", "")
            value = change.get("value", {})

            if field in ["comments", "comment", "feed", "live_comments", "mentions"]:
                comment_id = value.get("id") or value.get("comment_id")
                comment_text = value.get("text") or value.get("message", "")
                
                user_info = value.get("from", {})
                if isinstance(user_info, dict):
                    username = user_info.get("username") or user_info.get("name", "amigo")
                    user_id = user_info.get("id", "")
                else:
                    username = "amigo"
                    user_id = str(user_info)

                if not comment_id or not comment_text:
                    continue

                # 🛑 ANTI-LOOP #1: Ignorar comentarios de la propia cuenta
                if normalize_text(username) in ["sistemadonklaus", "donklaus", "don klaus"] or user_id == my_ig_id:
                    logger.info(f"Ignorando comentario propio de @{username}")
                    continue

                # 🛑 ANTI-LOOP #2: Deduplicación
                if comment_id in PROCESSED_COMMENTS:
                    logger.info(f"Comentario {comment_id} ya procesado. Ignorando.")
                    continue
                PROCESSED_COMMENTS[comment_id] = time.time()

                media_info = value.get("media", {})
                post_id = media_info.get("id") if isinstance(media_info, dict) else str(value.get("post_id", ""))

                add_activity_log("COMMENT_RECEIVED", f"Comentario de @{username}: '{comment_text}'", f"Post: {post_id}")

                # Buscar campaña coincidente
                matched_campaign = None
                for camp in active_campaigns:
                    post_filter = camp.get("post_id_filter", "").strip()
                    if post_filter and post_filter not in post_id:
                        continue

                    if match_keyword(comment_text, camp.get("keywords", ""), camp.get("match_mode", "contains")):
                        matched_campaign = camp
                        break

                if matched_campaign:
                    public_replies = matched_campaign.get("public_replies", [])
                    if public_replies:
                        chosen_reply = random.choice(public_replies)
                        chosen_reply = chosen_reply.replace("@username", f"@{username}").replace("{{username}}", username)
                        background_tasks.add_task(get_graph_client().reply_to_comment, comment_id, chosen_reply)

                    dm_messages = matched_campaign.get("dm_messages", [])
                    if dm_messages:
                        background_tasks.add_task(
                            execute_dm_sequence,
                            target_id,
                            user_id,
                            comment_id,
                            dm_messages,
                            username
                        )

                    record_lead(
                        username=username,
                        user_id=user_id,
                        campaign_id=matched_campaign["id"],
                        comment_id=comment_id,
                        post_id=post_id,
                        comment_text=comment_text,
                        status="DM_SENT"
                    )

        # 2. Mensajes Directos (DMs) entrantes
        messaging_events = entry.get("messaging", [])
        for event in messaging_events:
            sender_id = event.get("sender", {}).get("id")
            recipient_id = event.get("recipient", {}).get("id")
            message = event.get("message", {})
            msg_text = message.get("text", "")
            msg_id = message.get("mid", "")
            is_echo = message.get("is_echo", False)

            if is_echo or sender_id in [my_ig_id, my_page_id, entry_id]:
                continue

            if msg_id and msg_id in PROCESSED_MESSAGES:
                continue
            if msg_id:
                PROCESSED_MESSAGES[msg_id] = time.time()

            if sender_id and msg_text:
                add_activity_log("DM_RECEIVED", f"DM recibido de {sender_id}: '{msg_text}'", f"User: {sender_id}")
                
                # Check if DM text matches specific SUELDO / DEUDA campaigns directly
                matched_dm_camp = None
                for camp in active_campaigns:
                    if match_keyword(msg_text, camp.get("keywords", ""), camp.get("match_mode", "contains")):
                        matched_dm_camp = camp
                        break

                if matched_dm_camp and matched_dm_camp.get("dm_messages"):
                    background_tasks.add_task(
                        execute_dm_sequence,
                        target_id,
                        sender_id,
                        None,
                        matched_dm_camp["dm_messages"],
                        "amigo"
                    )
                else:
                    async def handle_ai_dm(user_id: str, text: str):
                        ai_reply = await sales_agent.generate_response(user_id, text)
                        await get_graph_client().send_direct_message(target_id, user_id, ai_reply)

                    background_tasks.add_task(handle_ai_dm, sender_id, msg_text)

    return Response(content="EVENT_RECEIVED", status_code=200)

# ----------------- SIMULATOR API -----------------

class SimulatorCommentRequest(BaseModel):
    username: str = "cliente_interesado"
    comment_text: str = "quiero"
    post_id: str = "post_12345"

@app.post("/api/simulator/comment")
async def simulate_comment(payload: SimulatorCommentRequest):
    campaigns = list_campaigns()
    active_campaigns = [c for c in campaigns if c.get("is_active")]
    matched_campaign = None

    for camp in active_campaigns:
        post_filter = camp.get("post_id_filter", "").strip()
        if post_filter and post_filter not in payload.post_id:
            continue
        if match_keyword(payload.comment_text, camp.get("keywords", ""), camp.get("match_mode", "contains")):
            matched_campaign = camp
            break

    if not matched_campaign:
        return {
            "matched": False,
            "message": "No se encontró ninguna campaña activa que coincida con las palabras clave ingresadas."
        }

    public_replies = matched_campaign.get("public_replies", [])
    public_reply_chosen = random.choice(public_replies) if public_replies else "¡Te envié un DM con la información! 🚀"
    public_reply_chosen = public_reply_chosen.replace("@username", f"@{payload.username}").replace("{{username}}", payload.username)

    dm_messages = matched_campaign.get("dm_messages", [])
    processed_dms = []
    for step in dm_messages:
        text = step.get("text", "").replace("@username", f"@{payload.username}").replace("{{username}}", payload.username)
        processed_dms.append({
            "text": text,
            "delay_seconds": step.get("delay_seconds", 0)
        })

    add_activity_log("SIMULATION", f"[Simulador] Comentario '@{payload.username}': '{payload.comment_text}' -> Match con '{matched_campaign['name']}'")

    return {
        "matched": True,
        "campaign_name": matched_campaign["name"],
        "public_reply": public_reply_chosen,
        "dm_messages": processed_dms,
        "enable_ai_agent": bool(matched_campaign.get("enable_ai_agent", 1))
    }

class SimulatorChatRequest(BaseModel):
    user_id: str = "sim_user_001"
    username: str = "cliente_interesado"
    message_text: str

@app.post("/api/simulator/chat")
async def simulate_chat(payload: SimulatorChatRequest):
    reply = await sales_agent.generate_response(payload.user_id, payload.message_text, payload.username)
    return {
        "reply": reply
    }

# ----------------- DASHBOARD REST APIS -----------------

@app.get("/api/meta/status")
async def api_meta_status():
    client = get_graph_client()
    return await client.verify_connection()

@app.get("/api/stats")
async def api_stats():
    return get_stats()

@app.post("/api/stats/reset")
async def api_reset_stats():
    from database import reset_stats
    reset_stats()
    return {"status": "reset_success"}

@app.get("/api/campaigns")
async def api_list_campaigns():
    return list_campaigns()

@app.post("/api/campaigns")
async def api_create_campaign(data: Dict[str, Any]):
    camp_id = create_campaign(data)
    add_activity_log("CAMPAIGN_CREATED", f"Campaña '{data.get('name')}' creada con éxito.")
    return {"id": camp_id, "status": "created"}

@app.put("/api/campaigns/{camp_id}")
async def api_update_campaign(camp_id: int, data: Dict[str, Any]):
    update_campaign(camp_id, data)
    add_activity_log("CAMPAIGN_UPDATED", f"Campaña #{camp_id} actualizada.")
    return {"status": "updated"}

@app.delete("/api/campaigns/{camp_id}")
async def api_delete_campaign(camp_id: int):
    delete_campaign(camp_id)
    add_activity_log("CAMPAIGN_DELETED", f"Campaña #{camp_id} eliminada.")
    return {"status": "deleted"}

@app.get("/api/products")
async def api_list_products():
    return list_products()

@app.post("/api/products")
async def api_create_product(data: Dict[str, Any]):
    prod_id = create_product(data)
    add_activity_log("PRODUCT_CREATED", f"Producto '{data.get('name')}' añadido al catálogo.")
    return {"id": prod_id, "status": "created"}

@app.put("/api/products/{prod_id}")
async def api_update_product(prod_id: int, data: Dict[str, Any]):
    update_product(prod_id, data)
    return {"status": "updated"}

@app.delete("/api/products/{prod_id}")
async def api_delete_product(prod_id: int):
    delete_product(prod_id)
    return {"status": "deleted"}

@app.get("/api/leads")
async def api_list_leads():
    return list_leads(limit=50)

@app.get("/api/logs")
async def api_list_logs():
    return list_activity_logs(limit=50)

@app.get("/api/settings")
async def api_get_settings():
    return get_settings()

@app.post("/api/settings")
async def api_update_settings(updates: Dict[str, str]):
    update_settings(updates)
    add_activity_log("SETTINGS_UPDATED", "Configuración del sistema actualizada.")
    return {"status": "updated"}

# ----------------- SERVE DASHBOARD UI & LEGAL -----------------

@app.get("/privacy", response_class=HTMLResponse)
async def serve_privacy():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Política de Privacidad - InstaFlow</title>
    <style>body{font-family:sans-serif;max-width:800px;margin:40px auto;padding:20px;line-height:1.6;color:#333;}</style>
    </head>
    <body>
    <h1>Política de Privacidad</h1>
    <p>Esta aplicación procesa datos de comentarios y mensajes de Instagram únicamente para responder consultas de usuarios e interactuar de forma automatizada con nuestros clientes.</p>
    <p>No compartimos ni vendemos datos personales a terceros. Todos los datos se almacenan de forma segura.</p>
    </body>
    </html>
    """)

@app.get("/terms", response_class=HTMLResponse)
async def serve_terms():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Términos de Servicio</title>
    <style>body{font-family:sans-serif;max-width:800px;margin:40px auto;padding:20px;line-height:1.6;color:#333;}</style>
    </head>
    <body>
    <h1>Términos de Servicio</h1>
    <p>Al utilizar este servicio de mensajería automatizada, aceptas recibir respuestas informativas y comerciales sobre nuestros productos y servicios.</p>
    </body>
    </html>
    """)

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = BASE_DIR / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>InstaFlow Sales AI Backend Running</h1>")

if __name__ == "__main__":
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)
