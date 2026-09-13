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


def resolve_spintax(text: str) -> str:
    """
    Convierte sintaxis de variación tipo {opcion1|opcion2|opcion3}
    en una opción seleccionada aleatoriamente para evitar huellas hash repetitivas de spam.
    """
    if not text:
        return ""
    pattern = re.compile(r'\{([^{}]+)\}')
    while pattern.search(text):
        text = pattern.sub(lambda m: random.choice(m.group(1).split('|')), text)
    return text

async def execute_dm_sequence(page_id: str, recipient_id: str, comment_id: Optional[str], dm_steps: List[Dict[str, Any]], username: str):
    client = get_graph_client()
    for idx, step in enumerate(dm_steps):
        raw_text = step.get("text", "")
        delay = int(step.get("delay_seconds", 0))

        # 1. Resolver spintax dinámico y nombres
        text = resolve_spintax(raw_text)
        text = text.replace("@username", f"@{username}").replace("{{username}}", username)

        # 2. Human Jitter (Retardo con variación humana aleatoria)
        if delay > 0:
            jitter = random.uniform(0.8, 3.5)
            await asyncio.sleep(delay + jitter)
        elif idx == 0:
            # Pausa natural antes del primer contacto (3 a 8 seg)
            await asyncio.sleep(random.uniform(3.0, 8.0))

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



async def handle_comment_flow(target_id: str, user_id: str, comment_id: str, comment_text: str, username: str, matched_campaign: Dict[str, Any]):
    # 1. Generar respuesta pública personalizada con IA Don Klaus
    public_reply = await sales_agent.generate_comment_reply(username, comment_text)
    await asyncio.sleep(random.uniform(3.0, 7.5))
    try:
        await get_graph_client().reply_to_comment(comment_id, public_reply)
    except Exception as e:
        logger.warning(f"No se pudo publicar comentario público en {comment_id}: {e}")

    # 2. Generar Opt-In DM ultra-humano y SIN ENLACES con IA
    optin_dm = await sales_agent.generate_optin_dm(username, comment_text)
    await asyncio.sleep(random.uniform(4.0, 9.0))
    try:
        await get_graph_client().send_private_message_by_comment(target_id, comment_id, optin_dm)
    except Exception as e:
        logger.warning(f"No se pudo enviar private message by comment en {comment_id}: {e}")

async def handle_dm_flow(target_id: str, sender_id: str, msg_text: str):
    # Simular pausa de lectura y pensamiento humano (2.0 a 3.5 seg)
    await asyncio.sleep(random.uniform(2.0, 3.5))
    
    clean_msg = normalize_text(msg_text)
    words = set(re.findall(r'\w+', clean_msg))
    client = get_graph_client()

    is_short_message = len(clean_msg.split()) <= 4
    
    # Detección de Sueldo y Deuda
    is_sueldo_intent = clean_msg in ["sueldo", "sueldos", "1", "opcion 1", "opción 1", "ordenar sueldo", "sueldo bajo control", "mi sueldo no rinde"] or (is_short_message and ("sueldo" in words or "sueldos" in words))
    is_deuda_intent = clean_msg in ["deuda", "deudas", "2", "opcion 2", "opción 2", "liquidar deudas", "deuda bajo control", "mis deudas ahogan"] or (is_short_message and ("deuda" in words or "deudas" in words))

    # 1. Caso: El usuario pide la guía / confirma el Opt-In (QUIERO, SI, SI QUIERO, FRASES, PDF, REGLAS, LOGO, etc.)
    gift_phrases = [
        "si quiero", "si por favor", "si porfa", "si claro", "si me interesa", "si enviamelo",
        "si pasamelo", "si mandalo", "quiero ver", "quiero el pdf", "quiero las frases",
        "quiero las reglas", "las frases", "el pdf", "la guia", "las 7 reglas", "7 reglas",
        "me interesa", "mandame el link", "pasame el link", "donde lo descargo", "descargar pdf",
        "pdf gratis", "guia gratis", "libro gratis", "reglas frias", "frases de don klaus"
    ]
    gift_words = {
        "si", "quiero", "klaus", "logo", "dale", "pasamelo", "pasame", "envialo", "enviame",
        "claro", "porfa", "mandalo", "mandame", "donde", "reglas", "regla", "pdf", "guia",
        "frase", "frases", "libro", "regalo", "gratis", "enlace", "link", "acceso",
        "info", "informacion", "interesa", "interesado", "interesada", "verlo", "descargar"
    }
    
    has_gift_phrase = any(gp in clean_msg for gp in gift_phrases)
    has_gift_word = clean_msg in gift_words or bool(words & gift_words)
    is_pure_optin = not is_sueldo_intent and not is_deuda_intent and (has_gift_phrase or (has_gift_word and len(words) <= 8))

    if is_pure_optin:
        # PASO A: Entrega 100% limpia del Regalo sin venta prematura (Generic Card)
        title = "7 Reglas Frías de Don Klaus"
        subtitle = "Guía práctica en PDF para ordenar tu dinero y frenar fugas (100% Gratis)."
        buttons = [
            {
                "type": "web_url",
                "url": "https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view",
                "title": "📥 Descargar PDF"
            }
        ]
        await client.send_generic_card(target_id, sender_id, title=title, subtitle=subtitle, buttons=buttons)
        
        # PASO B: Mensaje conversacional de transición diagnóstica con botones rápidos (ManyChat style)
        await asyncio.sleep(random.uniform(2.0, 3.5))
        transition_text = (
            "Léelo pensando en esto: La mayoría cree que necesita ganar más, pero el 90% de las fugas ocurren por no tener un protocolo el día de pago.\n\n"
            "Cuando le eches un ojo, dime con sinceridad:\n"
            "¿Dónde sientes que se te escapa más dinero hoy? 👇"
        )
        quick_replies = [
            {"content_type": "text", "title": "💰 Mi Sueldo no rinde", "payload": "SUELDO"},
            {"content_type": "text", "title": "⚔️ Mis Deudas ahogan", "payload": "DEUDA"}
        ]
        await client.send_quick_replies(target_id, sender_id, transition_text, quick_replies)
        return

    # 2. Caso: El usuario elige SUELDO (vía botón postback, quick reply o palabra directa)
    if is_sueldo_intent:
        msg_part1 = "Te entiendo perfectamente. Cobras el sueldo y a los pocos días no sabes en qué se fue todo."
        await client.send_direct_message(target_id, sender_id, msg_part1)
        await asyncio.sleep(random.uniform(1.2, 2.0))
        
        msg_part2 = (
            "Más de 1,400 personas aplicaron el Protocolo Día de Pago™ de 7 días y rescataron entre $150 y $300 en fugas desde su primera quincena.\n\n"
            "Por solo US$17 (pago único de por vida y 7 días de garantía total) tienes el método exacto en video y plantillas listas."
        )
        await client.send_direct_message(target_id, sender_id, msg_part2)
        await asyncio.sleep(random.uniform(1.2, 2.0))
        
        title = "Sueldo Bajo Control™ ($17)"
        subtitle = "Protocolo Día de Pago™ en 7 días para blindar tu dinero. Garantía 7 días."
        buttons = [
            {
                "type": "web_url",
                "url": "https://klaus-order-rules.lovable.app/",
                "title": "🔥 Adquirir ($17)"
            },
            {
                "type": "postback",
                "title": "⚔️ Tengo Deudas",
                "payload": "DEUDA"
            }
        ]
        await client.send_generic_card(target_id, sender_id, title=title, subtitle=subtitle, buttons=buttons)
        return

    # 3. Caso: El usuario elige DEUDA (vía botón postback, quick reply o palabra directa)
    if is_deuda_intent:
        msg_part1 = "Pagar mínimos o abonar a ciegas es trabajar para regalarle intereses al banco. Los bancos apuestan a que no tengas un plan."
        await client.send_direct_message(target_id, sender_id, msg_part1)
        await asyncio.sleep(random.uniform(1.2, 2.0))

        msg_part2 = (
            "Con el Protocolo C.E.R.O.™ tienes el mapa matemático exacto para saber qué deuda liquidar primero paso a paso.\n\n"
            "Por US$55 (pago único y 7 días de garantía incondicional) frenas el acoso bancario y recuperas tu tranquilidad."
        )
        await client.send_direct_message(target_id, sender_id, msg_part2)
        await asyncio.sleep(random.uniform(1.2, 2.0))

        title = "Deuda Bajo Control™ ($55)"
        subtitle = "Protocolo C.E.R.O.™ para liquidar deudas sin pagar a ciegas. Garantía 7 días."
        buttons = [
            {
                "type": "web_url",
                "url": "https://zero-debt-protocol.lovable.app/",
                "title": "⚔️ Adquirir ($55)"
            },
            {
                "type": "postback",
                "title": "💰 Ver Plan Sueldo",
                "payload": "SUELDO"
            }
        ]
        await client.send_generic_card(target_id, sender_id, title=title, subtitle=subtitle, buttons=buttons)
        return

    # 4. Caso: Pregunta abierta o caso particular -> Gemini AI Don Klaus
    ai_reply = await sales_agent.generate_response(sender_id, msg_text)
    typing_delay = min(len(ai_reply) * 0.035, 6.0) + random.uniform(1.0, 2.0)
    await asyncio.sleep(typing_delay)
    
    # Enviar respuesta con botones rápidos (Quick Replies)
    quick_replies = [
        {"content_type": "text", "title": "💰 Sueldo ($17)", "payload": "SUELDO"},
        {"content_type": "text", "title": "⚔️ Deuda ($55)", "payload": "DEUDA"},
        {"content_type": "text", "title": "📥 Descargar Reglas", "payload": "QUIERO"}
    ]
    await client.send_quick_replies(target_id, sender_id, ai_reply, quick_replies)

@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        return Response(content="Invalid JSON", status_code=400)

    raw_json_str = json.dumps(body, ensure_ascii=False)
    logger.info(f"Webhook Event Received: {raw_json_str}")
    
    # 🛑 HARD STOP TOTAL (48h-72h Cooldown Anti-Shadowban):
    settings = get_settings()
    is_paused = config.AUTOMATIONS_PAUSED or settings.get("automations_paused", "false").lower() == "true"
    if is_paused:
        logger.info("🛑 [HARD STOP ACTIVO] Todas las automatizaciones están 100% DETENIDAS. Ningún mensaje o comentario será enviado.")
        return Response(content="AUTOMATIONS_PAUSED", status_code=200)

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
                    background_tasks.add_task(
                        handle_comment_flow,
                        target_id,
                        user_id,
                        comment_id,
                        comment_text,
                        username,
                        matched_campaign
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

        # 2. Mensajes Directos (DMs) entrantes (incluye Respuestas a Historias y Menciones)
        messaging_events = entry.get("messaging", [])
        for event in messaging_events:
            sender_id = event.get("sender", {}).get("id")
            recipient_id = event.get("recipient", {}).get("id")
            message = event.get("message", {})
            postback = event.get("postback", {})

            # 1. Obtener texto del mensaje (soporta texto regular, botones rápidos y tarjetas)
            msg_text = ""
            if message:
                msg_text = message.get("quick_reply", {}).get("payload") or message.get("text", "")
            elif postback:
                msg_text = postback.get("payload") or postback.get("title", "")

            msg_id = message.get("mid", "") or postback.get("mid", "")
            is_echo = message.get("is_echo", False)

            if is_echo or sender_id in [my_ig_id, my_page_id, entry_id]:
                continue

            if msg_id and msg_id in PROCESSED_MESSAGES:
                continue
            if msg_id:
                PROCESSED_MESSAGES[msg_id] = time.time()

            # 📸 Detección de Respuestas a Historias (Story Reply)
            reply_to_story = message.get("reply_to", {}).get("story")
            if reply_to_story:
                if not msg_text:
                    msg_text = "[Reaccionó a tu Historia de Instagram]"
                else:
                    msg_text = f"[Respondió a tu Historia]: {msg_text}"

            # 📸 Detección de Menciones en Historias (Story Mention)
            attachments = message.get("attachments", [])
            for att in attachments:
                if att.get("type") in ["story_mention", "story_share"]:
                    msg_text = "[Te mencionó en su Historia de Instagram]"
                    break

            if sender_id and msg_text:
                add_activity_log("DM_RECEIVED", f"DM recibido de {sender_id}: '{msg_text}'", f"User: {sender_id}")
                background_tasks.add_task(handle_dm_flow, target_id, sender_id, msg_text)

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
async def api_list_leads(limit: int = 200):
    return list_leads(limit=limit)

@app.post("/api/leads/batch")
async def api_batch_leads(leads_data: List[Dict[str, Any]]):
    for ld in leads_data:
        record_lead(
            username=ld.get("username", "usuario"),
            user_id=ld.get("user_id", ""),
            campaign_id=ld.get("campaign_id", 1),
            comment_id=ld.get("comment_id", ""),
            post_id=ld.get("post_id", ""),
            comment_text=ld.get("comment_text", ""),
            status="DM_SENT"
        )
        add_activity_log("DM_SENT", f"DM entregado a @{ld.get('username')}: '{ld.get('comment_text')}'", f"Lead: @{ld.get('username')}")
    return {"status": "synced", "count": len(leads_data)}

@app.get("/api/logs")
async def api_list_logs(limit: int = 200):
    return list_activity_logs(limit=limit)

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
