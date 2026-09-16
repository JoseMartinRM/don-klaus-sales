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
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import config, BASE_DIR
from database import (
    init_db, get_settings, update_settings,
    list_campaigns, get_campaign, create_campaign, update_campaign, delete_campaign,
    list_products, create_product, update_product, delete_product,
    record_lead, list_leads, add_activity_log, list_activity_logs,
    get_stats, get_conversation_history,
    upsert_lead, get_lead_by_user_id, update_lead_interaction, update_lead_stage,
    set_lead_segment, record_checkout_click, record_hotmart_purchase, flag_human_escalation,
    get_pending_window_followups, update_lead_followup_sent, get_7day_inactive_leads,
    get_crm_metrics_funnel,
    # Legacy fallbacks
    register_pdf_lead, mark_lead_responded, get_pending_followup_leads, update_lead_followup_stage
)
from meta_client import InstagramGraphClient
from sales_agent import sales_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("instaflow_server")

# Cache to avoid infinite loops and duplicate processing
PROCESSED_COMMENTS: Dict[str, float] = {}
PROCESSED_MESSAGES: Dict[str, float] = {}

# Rate Limiter: Track DMs sent in last 3600 seconds (< 200 DMs/hour limit)
SENT_DM_TIMESTAMPS: List[float] = []

def record_dm_sent():
    global SENT_DM_TIMESTAMPS
    now = time.time()
    SENT_DM_TIMESTAMPS.append(now)
    # Clean timestamps older than 1 hour
    SENT_DM_TIMESTAMPS = [t for t in SENT_DM_TIMESTAMPS if now - t < 3600]

def is_rate_limited() -> bool:
    global SENT_DM_TIMESTAMPS
    now = time.time()
    SENT_DM_TIMESTAMPS = [t for t in SENT_DM_TIMESTAMPS if now - t < 3600]
    return len(SENT_DM_TIMESTAMPS) >= 195  # Safety threshold under 200 DMs/hr

def normalize_text(text: str) -> str:
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
    logger.info("Base de datos SQLite CRM inicializada correctamente con cumplimiento Meta 24h.")
    followup_task = asyncio.create_task(followup_worker_loop())
    yield
    followup_task.cancel()

app = FastAPI(title="Don Klaus Sales AI - Meta 24h Instagram Closer", lifespan=lifespan)

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


def match_keyword(comment_text: str, keywords_str: str, match_mode: str) -> bool:
    if not comment_text or not keywords_str:
        return False

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

# ----------------- CORE CONVERSATIONAL SALES FLOW -----------------

async def handle_comment_flow(target_id: str, user_id: str, comment_id: str, comment_text: str, username: str, matched_campaign: Dict[str, Any], reel_id: str = ""):
    """
    NUEVO FLUJO: Diagnóstico ANTES del PDF
    1. Publica respuesta pública (1 de 5 versiones rotativas formales).
    2. Registra el lead en CRM asignando variante A/B para DM 1 (50/50).
    3. Envía DM 1 con pregunta de diagnóstico y botones [💰 Ordenar Sueldo] / [⚔️ Liquidar Deudas] SIN ENLACES.
    """
    if is_rate_limited():
        logger.warning("[Rate Limiter] Límite de 200 DMs/hora alcanzado. Pausando respuesta.")
        return

    client = get_graph_client()

    # 1. Publicar respuesta pública formal
    public_reply = await sales_agent.generate_comment_reply(username, comment_text)
    await asyncio.sleep(random.uniform(2.5, 5.0))
    try:
        await client.reply_to_comment(comment_id, public_reply)
    except Exception as e:
        logger.warning(f"No se pudo publicar comentario público en {comment_id}: {e}")

    # 2. Prueba A/B para DM 1 (50/50)
    variant = random.choice(["A", "B"])

    # 3. Registrar Lead en CRM
    lead = upsert_lead(
        user_id=user_id,
        username=username,
        keyword=comment_text,
        reel_id=reel_id,
        variant_dm1=variant,
        campaign_id=matched_campaign.get("id"),
        comment_id=comment_id,
        comment_text=comment_text
    )

    # 4. Generar texto y botones rápidos de diagnóstico
    dm_text, quick_replies = sales_agent.generate_optin_dm_variant(username, variant)
    await asyncio.sleep(random.uniform(3.0, 6.0))

    try:
        if quick_replies:
            await client.send_quick_replies(target_id, user_id, dm_text, quick_replies)
        else:
            await client.send_private_message_by_comment(target_id, comment_id, dm_text)
        record_dm_sent()
        add_activity_log("DM_SENT", f"DM 1 Diagnóstico (Var {variant}) enviado a @{username}: '{dm_text[:60]}...'", f"User: @{username}")
    except Exception as e:
        logger.warning(f"Fallo al enviar DM 1 a {user_id}: {e}")
        try:
            await client.send_private_message_by_comment(target_id, comment_id, dm_text)
            record_dm_sent()
        except Exception:
            pass

async def handle_dm_flow(target_id: str, sender_id: str, msg_text: str):
    """
    Manejador central de DMs entrantes con cumplimiento estricto de la ventana de 24h de Meta.
    """
    if is_rate_limited():
        logger.warning("[Rate Limiter] Límite de 200 DMs/hora alcanzado.")
        return

    client = get_graph_client()
    clean_msg = normalize_text(msg_text)
    words = set(re.findall(r'\w+', clean_msg))

    # Obtener o crear lead en CRM
    lead = get_lead_by_user_id(sender_id)
    username = lead.get("instagram_username", "amigo") if lead else "amigo"
    current_segment = lead.get("segment", "sin definir") if lead else "sin definir"
    current_stage = lead.get("stage", "comento") if lead else "comento"
    reel_id = lead.get("source_reel_id", "") if lead else ""

    # Actualizar última interacción real del lead
    update_lead_interaction(sender_id, is_real_interaction=True, new_stage="respondio")

    # Detectar posibles objeciones
    detected_objection = sales_agent.detect_objection(msg_text)
    if detected_objection:
        update_lead_interaction(sender_id, is_real_interaction=True, objection=detected_objection)

    # Pausa humana aleatoria
    await asyncio.sleep(random.uniform(2.0, 4.0))

    # ----------------- INTENT CLASSIFICATION -----------------
    is_short_msg = len(clean_msg.split()) <= 4

    is_sueldo_intent = clean_msg in [
        "sueldo", "sueldos", "1", "opcion 1", "opción 1", "ordenar sueldo",
        "sueldo bajo control", "en mi sueldo", "mi sueldo", "el sueldo"
    ] or (is_short_msg and ("sueldo" in words or "sueldos" in words or "ordenar" in words))

    is_deuda_intent = clean_msg in [
        "deuda", "deudas", "2", "opcion 2", "opción 2", "liquidar deudas",
        "deuda bajo control", "en mis deudas", "mis deudas", "las deudas"
    ] or (is_short_msg and ("deuda" in words or "deudas" in words or "liquidar" in words))

    is_direct_buy_intent = any(k in clean_msg for k in ["comprar", "precio", "link", "enlace", "adquirir", "cuanto cuesta", "cuánto cuesta"])

    # 1. CASO: SEGMENTO SUELDO (Entrega de PDF + Oferta Sueldo $17 + Pregunta de compromiso Regla 1-7)
    if is_sueldo_intent:
        set_lead_segment(sender_id, "SUELDO")
        update_lead_stage(sender_id, "vio_oferta")

        # PASO A: Entrega del PDF en Tarjeta Limpia
        pdf_title = "7 Reglas Frías de Don Klaus"
        pdf_subtitle = "Guía práctica en PDF para blindar sus finanzas y frenar fugas (100% Gratis)."
        pdf_buttons = [
            {
                "type": "web_url",
                "url": "https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view",
                "title": "📥 Descargar PDF"
            }
        ]
        await client.send_generic_card(target_id, sender_id, title=pdf_title, subtitle=pdf_subtitle, buttons=pdf_buttons)
        record_dm_sent()
        await asyncio.sleep(random.uniform(2.0, 3.5))

        # PASO B: Oferta de Sueldo Bajo Control™ ($17)
        sueldo_text = (
            "Cobrar con la ilusión de avanzar y a la semana no saber a dónde se fue el dinero ocurre por entrar sin un protocolo estricto el día de cobro.\n\n"
            "Por eso creé **Sueldo Bajo Control™** con el Protocolo Día de Pago™ de 7 días (videos de 5 min y plantillas listas, cero Excels aburridos).\n\n"
            "Cuesta solo US$17 (pago único de por vida) y dispone de 7 días de garantía incondicional: si no le da orden absoluto, le devuelvo cada centavo. El riesgo es totalmente mío."
        )
        await client.send_direct_message(target_id, sender_id, sueldo_text)
        record_dm_sent()
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # Tarjeta de Compra Sueldo
        checkout_sueldo_url = f"https://klaus-order-rules.lovable.app/?src=ig_bot_sueldo_{reel_id or 'direct'}"
        sueldo_card_buttons = [
            {
                "type": "web_url",
                "url": checkout_sueldo_url,
                "title": "🔥 Adquirir ($17)"
            },
            {
                "type": "postback",
                "title": "⚔️ Tengo Deudas",
                "payload": "DEUDA"
            }
        ]
        await client.send_generic_card(
            target_id, sender_id,
            title="Sueldo Bajo Control™ ($17)",
            subtitle="Protocolo Día de Pago™ en 7 días. Garantía incondicional de 7 días.",
            buttons=sueldo_card_buttons
        )
        record_dm_sent()
        await asyncio.sleep(random.uniform(2.0, 3.5))

        # PASO C: Pregunta de compromiso que renueva la ventana de 24h
        commitment_text = (
            "Acabo de entregarle las 7 Reglas Frías arriba 👆.\n\n"
            "Léalas hoy mismo y dígame con sinceridad:\n"
            "¿Cuál de las 7 reglas siente que está rompiendo en este momento? (Dígame el número del 1 al 7) 👇"
        )
        await client.send_direct_message(target_id, sender_id, commitment_text)
        record_dm_sent()
        return

    # 2. CASO: SEGMENTO DEUDA (Entrega de PDF + Oferta Deuda $55 + Pregunta de compromiso Regla 1-7)
    if is_deuda_intent:
        set_lead_segment(sender_id, "DEUDA")
        update_lead_stage(sender_id, "vio_oferta")

        # PASO A: Entrega del PDF en Tarjeta Limpia
        pdf_title = "7 Reglas Frías de Don Klaus"
        pdf_subtitle = "Guía práctica en PDF para blindar sus finanzas y frenar fugas (100% Gratis)."
        pdf_buttons = [
            {
                "type": "web_url",
                "url": "https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view",
                "title": "📥 Descargar PDF"
            }
        ]
        await client.send_generic_card(target_id, sender_id, title=pdf_title, subtitle=pdf_subtitle, buttons=pdf_buttons)
        record_dm_sent()
        await asyncio.sleep(random.uniform(2.0, 3.5))

        # PASO B: Oferta de Deuda Bajo Control™ ($55)
        deuda_text = (
            "Pagar mínimos o abonar a ciegas es la trampa perfecta de los bancos: trabaja todo el mes para pagarles intereses sin que la deuda baje jamás.\n\n"
            "Para salir de ese ahogo necesita un mapa matemático exacto. Con el Protocolo C.E.R.O.™ de **Deuda Bajo Control™** sabe qué deuda liquidar primero y cómo frenar los intereses.\n\n"
            "Por solo US$55 (pago único de por vida y 7 días de garantía incondicional) erradica sus deudas paso a paso."
        )
        await client.send_direct_message(target_id, sender_id, deuda_text)
        record_dm_sent()
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # Tarjeta de Compra Deuda
        checkout_deuda_url = f"https://zero-debt-protocol.lovable.app/?src=ig_bot_deuda_{reel_id or 'direct'}"
        deuda_card_buttons = [
            {
                "type": "web_url",
                "url": checkout_deuda_url,
                "title": "⚔️ Adquirir ($55)"
            },
            {
                "type": "postback",
                "title": "💰 Ver Plan Sueldo",
                "payload": "SUELDO"
            }
        ]
        await client.send_generic_card(
            target_id, sender_id,
            title="Deuda Bajo Control™ ($55)",
            subtitle="Protocolo C.E.R.O.™ para liquidar deudas. Garantía incondicional de 7 días.",
            buttons=deuda_card_buttons
        )
        record_dm_sent()
        await asyncio.sleep(random.uniform(2.0, 3.5))

        # PASO C: Pregunta de compromiso que renueva la ventana de 24h
        commitment_text = (
            "Acabo de entregarle las 7 Reglas Frías arriba 👆.\n\n"
            "Revíselas hoy mismo y dígame:\n"
            "¿Cuál de las 7 reglas siente que está rompiendo hoy? (Dígame el número del 1 al 7) 👇"
        )
        await client.send_direct_message(target_id, sender_id, commitment_text)
        record_dm_sent()
        return

    # 3. CASO: COMPRADOR EXISTENTE (Upsell inteligente)
    if lead and lead.get("bought_sueldo") and not lead.get("bought_deuda"):
        upsell_text = (
            f"Hola @{username}. Ya tiene activo su acceso a Sueldo Bajo Control™.\n\n"
            "El siguiente paso estratégico para blindar sus finanzas es liquidar sus deudas con el Protocolo C.E.R.O.™ de **Deuda Bajo Control™** ($55 con 7 días de garantía total):\n"
            "👉 https://zero-debt-protocol.lovable.app/\n\n"
            "¿Desea revisar el plan de liquidación de deudas?"
        )
        await client.send_direct_message(target_id, sender_id, upsell_text)
        record_dm_sent()
        return

    # 4. CASO: USUARIO QUE PIDE PRECIO / LINK DIRECTAMENTE
    if is_direct_buy_intent:
        if current_segment == "DEUDA":
            reply = (
                "El acceso de por vida a **Deuda Bajo Control™** es de US$55 (pago único) con 7 días de garantía incondicional sin preguntas:\n\n"
                f"👉 https://zero-debt-protocol.lovable.app/?src=ig_bot_deuda_{reel_id or 'direct'}\n\n"
                "¿Desea empezar a liquidarlas hoy?"
            )
        else:
            reply = (
                "El acceso de por vida a **Sueldo Bajo Control™** es de solo US$17 (pago único) con 7 días de garantía incondicional:\n\n"
                f"👉 https://klaus-order-rules.lovable.app/?src=ig_bot_sueldo_{reel_id or 'direct'}\n\n"
                "¿Blindamos su próximo cobro?"
            )
        await client.send_direct_message(target_id, sender_id, reply)
        record_dm_sent()
        return

    # 5. CASO: RESPUESTA CONSULTIVA GENERAL IA (Gemini Don Klaus con memoria y manejo de objeciones)
    ai_reply, escalation = await sales_agent.generate_response(
        sender_id, msg_text, username=username, segment=current_segment, stage=current_stage
    )
    typing_delay = min(len(ai_reply) * 0.03, 5.0) + random.uniform(1.0, 2.0)
    await asyncio.sleep(typing_delay)

    quick_replies = [
        {"content_type": "text", "title": "💰 Sueldo ($17)", "payload": "SUELDO"},
        {"content_type": "text", "title": "⚔️ Deuda ($55)", "payload": "DEUDA"}
    ]
    await client.send_quick_replies(target_id, sender_id, ai_reply, quick_replies)
    record_dm_sent()

# ----------------- WEBHOOK EVENT DISPATCHER -----------------

@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        return Response(content="Invalid JSON", status_code=400)

    raw_json_str = json.dumps(body, ensure_ascii=False)
    logger.info(f"Webhook Event Received: {raw_json_str}")

    settings = get_settings()
    is_paused = config.AUTOMATIONS_PAUSED or settings.get("automations_paused", "false").lower() == "true"
    if is_paused:
        logger.info("🛑 [AUTOMATIONS PAUSED] Ninguna automatización será ejecutada.")
        return Response(content="AUTOMATIONS_PAUSED", status_code=200)

    my_ig_id = settings.get("instagram_account_id", "").strip()
    my_page_id = settings.get("meta_page_id", config.META_PAGE_ID).strip()
    target_id = my_ig_id or my_page_id or "me"

    entries = body.get("entry", [])
    campaigns = list_campaigns()
    active_campaigns = [c for c in campaigns if c.get("is_active")]

    for entry in entries:
        entry_id = entry.get("id", "")

        # 1. Comentarios en Publicaciones / Reels
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

                if normalize_text(username) in ["sistemadonklaus", "donklaus", "don klaus"] or user_id == my_ig_id:
                    continue

                if comment_id in PROCESSED_COMMENTS:
                    continue
                PROCESSED_COMMENTS[comment_id] = time.time()

                media_info = value.get("media", {})
                post_id = media_info.get("id") if isinstance(media_info, dict) else str(value.get("post_id", ""))

                add_activity_log("COMMENT_RECEIVED", f"Comentario de @{username}: '{comment_text}'", f"Post: {post_id}")

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
                        matched_campaign,
                        post_id
                    )

        # 2. Mensajes Directos (DMs) / Postbacks / Respuestas a Historias
        messaging_events = entry.get("messaging", [])
        for event in messaging_events:
            sender_id = event.get("sender", {}).get("id")
            recipient_id = event.get("recipient", {}).get("id")
            message = event.get("message", {})
            postback = event.get("postback", {})

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

            # Detección de Respuestas a Historias
            reply_to_story = message.get("reply_to", {}).get("story")
            if reply_to_story:
                if not msg_text:
                    msg_text = "[Reaccionó a Historia de Instagram]"
                else:
                    msg_text = f"[Respondió a Historia]: {msg_text}"

            # Detección de Menciones en Historias
            attachments = message.get("attachments", [])
            for att in attachments:
                if att.get("type") in ["story_mention", "story_share"]:
                    msg_text = "[Mención en Historia de Instagram]"
                    break

            if sender_id and msg_text:
                add_activity_log("DM_RECEIVED", f"DM recibido de {sender_id}: '{msg_text}'", f"User: {sender_id}")
                background_tasks.add_task(handle_dm_flow, target_id, sender_id, msg_text)

    return Response(content="EVENT_RECEIVED", status_code=200)

# ----------------- HOTMART & CHECKOUT TRACKING -----------------

@app.get("/r/checkout/{product_type}/{user_id}")
@app.get("/r/checkout/{product_type}/{user_id}/{reel_id}")
async def redirect_checkout(product_type: str, user_id: str, reel_id: str = "direct"):
    """
    Ruta de redirección que registra el clic en checkout en el CRM y envía al usuario a Hotmart.
    """
    prod_lower = product_type.lower()
    record_checkout_click(user_id, prod_lower, reel_id)
    add_activity_log("CHECKOUT_CLICK", f"Lead {user_id} hizo clic en checkout para {prod_lower}", f"Reel: {reel_id}")

    if "deuda" in prod_lower or "55" in prod_lower:
        target_url = f"https://zero-debt-protocol.lovable.app/?src=ig_bot_deuda_{reel_id}"
    else:
        target_url = f"https://klaus-order-rules.lovable.app/?src=ig_bot_sueldo_{reel_id}"

    return RedirectResponse(url=target_url, status_code=302)

class HotmartWebhookPayload(BaseModel):
    hottok: Optional[str] = None
    event: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

@app.post("/api/webhooks/hotmart")
async def hotmart_webhook(request: Request):
    """
    Webhook oficial para recibir compras confirmadas de Hotmart y actualizar el CRM.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "message": "Invalid JSON"}, status_code=400)

    logger.info(f"Hotmart Webhook Received: {json.dumps(body)}")

    # Extraer datos de compra
    event_type = body.get("event") or body.get("status") or "PURCHASE_COMPLETE"
    data = body.get("data") or body

    buyer = data.get("buyer") or {}
    buyer_email = buyer.get("email") or data.get("email", "")
    buyer_name = buyer.get("name") or data.get("name", "")

    purchase = data.get("purchase") or {}
    transaction_id = purchase.get("transaction") or data.get("transaction", f"tx_{int(time.time())}")
    price_paid = str(purchase.get("price", {}).get("value") or data.get("price", "17"))

    product = data.get("product") or {}
    product_name = product.get("name") or data.get("prod_name", "Sueldo Bajo Control")
    product_id = str(product.get("id") or data.get("prod", "1"))

    # Intentar obtener instagram_user_id desde src o custom params
    src = purchase.get("src") or data.get("src", "")
    user_id = None
    if "ig_bot_" in src:
        parts = src.split("_")
        if len(parts) >= 4:
            user_id = parts[-1]

    purchase_id = record_hotmart_purchase(
        transaction_id=transaction_id,
        buyer_email=buyer_email,
        buyer_name=buyer_name,
        product_id=product_id,
        product_name=product_name,
        price_paid=price_paid,
        user_id=user_id
    )

    add_activity_log("PURCHASE_VERIFIED", f"¡VENTA CONFIRMADA! {product_name} por ${price_paid} USD (Comprador: {buyer_name} / {buyer_email})", f"Tx: {transaction_id}")
    return {"status": "success", "purchase_id": purchase_id}

# ----------------- 24H META SMART FOLLOW-UP ENGINE -----------------

async def process_followups_now() -> Dict[str, Any]:
    """
    Ejecuta una ronda de seguimiento automático cumpliendo ESTRICTAMENTE con la política de 24h de Meta.
    """
    pending_leads = get_pending_window_followups()
    if not pending_leads:
        return {"processed": 0, "message": "No hay leads pendientes de seguimiento dentro de la ventana de 24h."}

    client = get_graph_client()
    settings = get_settings()
    target_id = settings.get("instagram_account_id", config.INSTAGRAM_ACCOUNT_ID)
    processed_count = 0

    for lead in pending_leads:
        if is_rate_limited():
            logger.warning("[Rate Limiter] Límite de DMs alcanzado durante follow-ups.")
            break

        user_id = lead["instagram_user_id"]
        username = lead.get("instagram_username")
        target_f = lead.get("target_followup", 1)
        segment = lead.get("segment", "SUELDO")

        # Seleccionar variante A/B para follow-up 3 (50/50)
        variant_f3 = random.choice(["A", "B"]) if target_f == 3 else "A"

        text, quick_replies = sales_agent.generate_followup_message(
            followup_num=target_f,
            username=username,
            segment=segment,
            variant_f3=variant_f3
        )
        if not text:
            continue

        try:
            if quick_replies:
                await client.send_quick_replies(target_id, user_id, text, quick_replies)
            else:
                await client.send_direct_message(target_id, user_id, text)

            record_dm_sent()
            update_lead_followup_sent(user_id, target_f, variant_f3=variant_f3 if target_f == 3 else None)
            add_activity_log("FOLLOWUP_SENT", f"Seguimiento #{target_f} (24h Window) enviado a {user_id}", f"User: @{username or user_id}")
            logger.info(f"[24h Follow-Up Engine] Seguimiento #{target_f} enviado con éxito a {user_id}")
            processed_count += 1
        except Exception as e:
            logger.warning(f"[24h Follow-Up Engine] Error enviando seguimiento a {user_id}: {e}")
            err_str = str(e).lower()
            if "outside" in err_str or "policy" in err_str or "block" in err_str:
                update_lead_stage(user_id, "perdido")

        # Pausa humana aleatoria entre envíos
        await asyncio.sleep(random.uniform(3.0, 6.0))

    return {"processed": processed_count, "total_pending": len(pending_leads)}

async def followup_worker_loop():
    """
    Loop en segundo plano que revisa cada 5 minutos la ventana de 24h de Meta.
    """
    logger.info("Iniciando Motor de Seguimiento Inteligente (Meta 24h Window Compliance)...")
    while True:
        try:
            await asyncio.sleep(300)
            await process_followups_now()
        except asyncio.CancelledError:
            logger.info("Motor de Seguimiento Inteligente detenido.")
            break
        except Exception as e:
            logger.exception(f"Error en loop de seguimiento: {e}")
            await asyncio.sleep(60)

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

    public_reply = await sales_agent.generate_comment_reply(payload.username, payload.comment_text)
    variant = random.choice(["A", "B"])
    dm_text, quick_replies = sales_agent.generate_optin_dm_variant(payload.username, variant)

    return {
        "matched": True,
        "campaign_name": matched_campaign["name"],
        "public_reply": public_reply,
        "dm_variant": variant,
        "dm_text": dm_text,
        "quick_replies": quick_replies
    }

class SimulatorChatRequest(BaseModel):
    user_id: str = "sim_user_001"
    username: str = "cliente_interesado"
    message_text: str
    segment: str = "sin definir"
    stage: str = "comento"

@app.post("/api/simulator/chat")
async def simulate_chat(payload: SimulatorChatRequest):
    reply, escalation = await sales_agent.generate_response(
        payload.user_id,
        payload.message_text,
        payload.username,
        segment=payload.segment,
        stage=payload.stage
    )
    return {
        "reply": reply,
        "escalation": escalation
    }

# ----------------- DASHBOARD & CRM REST APIS -----------------

@app.get("/api/meta/status")
async def api_meta_status():
    client = get_graph_client()
    return await client.verify_connection()

@app.get("/api/stats")
async def api_stats():
    return get_crm_metrics_funnel()

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

@app.get("/api/crm/leads")
@app.get("/api/leads")
async def api_list_leads(limit: int = 200, stage: Optional[str] = None, segment: Optional[str] = None):
    return list_leads(limit=limit, stage=stage, segment=segment)

@app.get("/api/crm/7day-leads")
async def api_get_7day_leads(limit: int = 50):
    return get_7day_inactive_leads(limit=limit)

@app.get("/api/metrics/funnel")
async def api_metrics_funnel():
    return get_crm_metrics_funnel()

@app.get("/api/followups/pending")
async def api_get_pending_followups():
    leads = get_pending_window_followups()
    return {"count": len(leads), "leads": leads}

@app.post("/api/followups/run")
async def api_run_followups():
    return await process_followups_now()

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
    <head><meta charset="UTF-8"><title>Política de Privacidad - Sistema Don Klaus</title>
    <style>body{font-family:sans-serif;max-width:800px;margin:40px auto;padding:20px;line-height:1.6;color:#333;}</style>
    </head>
    <body>
    <h1>Política de Privacidad</h1>
    <p>Esta aplicación procesa datos de comentarios y mensajes de Instagram únicamente para responder consultas de usuarios e interactuar de forma automatizada dentro del marco de políticas de mensajería de Meta (24 horas).</p>
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
    <p>Al utilizar este servicio de mensajería automatizada de Don Klaus, usted acepta recibir respuestas informativas y consultivas sobre protocolos financieros.</p>
    </body>
    </html>
    """)

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = BASE_DIR / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>Don Klaus Sales AI Backend Running</h1>")

if __name__ == "__main__":
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)
