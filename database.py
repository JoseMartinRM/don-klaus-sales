import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from config import config

def get_db_connection():
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table: Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    # Table: Campaigns / Keyword Rules
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        keywords TEXT NOT NULL,
        match_mode TEXT DEFAULT 'contains',
        post_id_filter TEXT DEFAULT '',
        public_replies TEXT NOT NULL,
        dm_messages TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        enable_ai_agent INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """)

    # Table: Products (Catalog for AI Sales Agent)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price TEXT NOT NULL,
        payment_link TEXT NOT NULL,
        benefits TEXT,
        faq TEXT,
        is_available INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """)

    # Table: Leads captured (Full CRM with 24h Meta Window Tracking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instagram_user_id TEXT UNIQUE,
        instagram_username TEXT,
        first_contact_at TEXT,
        last_real_interaction_at TEXT,
        entry_keyword TEXT,
        source_reel_id TEXT,
        segment TEXT DEFAULT 'sin definir',
        stage TEXT DEFAULT 'comento',
        followups_sent INTEGER DEFAULT 0,
        last_followup_at TEXT,
        objections_detected TEXT DEFAULT '[]',
        bought_sueldo INTEGER DEFAULT 0,
        bought_deuda INTEGER DEFAULT 0,
        variant_dm1 TEXT DEFAULT 'A',
        variant_f3 TEXT DEFAULT 'A',
        needs_human_escalation INTEGER DEFAULT 0,
        escalation_reason TEXT,
        campaign_id INTEGER,
        source_comment_id TEXT,
        source_post_id TEXT,
        comment_text TEXT,
        status TEXT DEFAULT 'DM_SENT',
        created_at TEXT NOT NULL
    )
    """)

    # Check and migrate columns in 'leads' table if upgraded from older version
    cursor.execute("PRAGMA table_info(leads)")
    existing_cols = {col["name"] for col in cursor.fetchall()}
    migrations = [
        ("first_contact_at", "TEXT"),
        ("last_real_interaction_at", "TEXT"),
        ("entry_keyword", "TEXT"),
        ("source_reel_id", "TEXT"),
        ("segment", "TEXT DEFAULT 'sin definir'"),
        ("stage", "TEXT DEFAULT 'comento'"),
        ("followups_sent", "INTEGER DEFAULT 0"),
        ("last_followup_at", "TEXT"),
        ("objections_detected", "TEXT DEFAULT '[]'"),
        ("bought_sueldo", "INTEGER DEFAULT 0"),
        ("bought_deuda", "INTEGER DEFAULT 0"),
        ("variant_dm1", "TEXT DEFAULT 'A'"),
        ("variant_f3", "TEXT DEFAULT 'A'"),
        ("needs_human_escalation", "INTEGER DEFAULT 0"),
        ("escalation_reason", "TEXT"),
    ]
    for col_name, col_type in migrations:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

    # Table: Conversation Messages (Chat memory for AI Agent)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instagram_user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        message_text TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # Table: Activity Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        lead_info TEXT,
        details TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # Table: Hotmart Purchases
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT UNIQUE,
        buyer_email TEXT,
        buyer_name TEXT,
        product_name TEXT,
        product_id TEXT,
        price_paid TEXT,
        instagram_user_id TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # Table: Checkout Clicks (Tracking for Abandoned Cart recovery)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS checkout_clicks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instagram_user_id TEXT,
        product_type TEXT,
        source_reel_id TEXT,
        clicked_at TEXT NOT NULL
    )
    """)

    # Table: Legacy Followups (Maintained for backward compatibility)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS followups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instagram_user_id TEXT UNIQUE NOT NULL,
        instagram_username TEXT,
        stage INTEGER DEFAULT 0,
        pdf_sent_at TEXT NOT NULL,
        last_followup_at TEXT,
        status TEXT DEFAULT 'PENDING',
        created_at TEXT NOT NULL
    )
    """)

    # Default settings
    default_settings = {
        "company_name": "Sistema Don Klaus",
        "company_description": "Mentoría y protocolos financieros para blindar su sueldo y liquidar deudas de por vida.",
        "sales_tone": "sobrio, formal (usted), empático pero implacable contra excusas, de alto valor y cierre consultivo.",
        "meta_access_token": config.META_ACCESS_TOKEN,
        "meta_verify_token": config.META_VERIFY_TOKEN,
        "meta_page_id": config.META_PAGE_ID,
        "instagram_account_id": config.INSTAGRAM_ACCOUNT_ID,
        "gemini_api_key": config.GEMINI_API_KEY,
        "gemini_model": config.GEMINI_MODEL,
        "hotmart_webhook_token": "",
    }

    for key, val in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, str(val)))

    # Default campaign
    cursor.execute("SELECT COUNT(*) FROM campaigns")
    if cursor.fetchone()[0] == 0:
        sample_public_replies = [
            "Listo @username, le escribí por mensaje privado para que lo revise con calma. ⚔️",
            "Le dejé un mensaje directo, @username. Mírelo cuando tenga un minuto. 📩",
            "Ya le envié el mensaje al privado, @username. 📜",
            "Revise su bandeja de mensajes, @username. Le dejé lo prometido. ⚔️",
            "Le acabo de escribir al DM, @username. 📩"
        ]
        sample_dm_messages = [
            {
                "text": "Hola @username 👋 Vi su comentario en la publicación. Antes de enviarle las 7 Reglas Frías en PDF: ¿su mayor problema hoy es ordenar su Sueldo o liquidar Deudas?",
                "delay_seconds": 0
            }
        ]
        cursor.execute("""
        INSERT INTO campaigns (name, keywords, match_mode, post_id_filter, public_replies, dm_messages, is_active, enable_ai_agent, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?)
        """, (
            "Campaña Don Klaus - Diagnóstico y Conversión",
            "QUIERO, REGLAS, PDF, INFO, SUELDO, DEUDA, PRECIO, COMPRAR, LINK",
            "contains",
            "",
            json.dumps(sample_public_replies, ensure_ascii=False),
            json.dumps(sample_dm_messages, ensure_ascii=False),
            datetime.now().isoformat()
        ))

    # Default products
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO products (name, description, price, payment_link, benefits, faq, is_available, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            "Sueldo Bajo Control™",
            "Protocolo Día de Pago™ de 7 días (MIRA, SEPARA, DECIDE, REVISA). Videos cortos de 5 min al día y plantillas listas.",
            "$17 USD",
            "https://klaus-order-rules.lovable.app/",
            "• Videos de 5 min al día\n• Cero Excels complicados\n• Acceso de por vida\n• 7 días de garantía incondicional",
            "¿Tiene garantía? Sí, 7 días de garantía total sin preguntas.",
            datetime.now().isoformat()
        ))
        cursor.execute("""
        INSERT INTO products (name, description, price, payment_link, benefits, faq, is_available, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            "Deuda Bajo Control™",
            "Protocolo C.E.R.O.™ para liquidar deudas paso a paso sin regalar intereses a los bancos.",
            "$55 USD",
            "https://zero-debt-protocol.lovable.app/",
            "• Mapa de ruta matemática exacta\n• Estrategia de amortización acelerada\n• Acceso de por vida\n• 7 días de garantía incondicional",
            "¿Sirve para cualquier tipo de deuda? Sí, tarjetas, préstamos personales y créditos.",
            datetime.now().isoformat()
        ))

    conn.commit()
    conn.close()

# ----------------- DB CRUD OPERATIONS -----------------

def get_settings() -> Dict[str, str]:
    conn = get_db_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    settings_dict = {row["key"]: row["value"] for row in rows}

    if not settings_dict.get("gemini_api_key"):
        settings_dict["gemini_api_key"] = config.GEMINI_API_KEY
    if not settings_dict.get("meta_access_token"):
        settings_dict["meta_access_token"] = config.META_ACCESS_TOKEN
    if not settings_dict.get("instagram_account_id"):
        settings_dict["instagram_account_id"] = config.INSTAGRAM_ACCOUNT_ID

    return settings_dict

def update_settings(updates: Dict[str, str]):
    conn = get_db_connection()
    for k, v in updates.items():
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
    conn.commit()
    conn.close()

def list_campaigns() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        item = dict(r)
        try:
            item["public_replies"] = json.loads(item["public_replies"])
        except Exception:
            item["public_replies"] = []
        try:
            item["dm_messages"] = json.loads(item["dm_messages"])
        except Exception:
            item["dm_messages"] = []
        result.append(item)
    return result

def get_campaign(campaign_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    item["public_replies"] = json.loads(item["public_replies"])
    item["dm_messages"] = json.loads(item["dm_messages"])
    return item

def create_campaign(data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO campaigns (name, keywords, match_mode, post_id_filter, public_replies, dm_messages, is_active, enable_ai_agent, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["name"],
        data["keywords"],
        data.get("match_mode", "contains"),
        data.get("post_id_filter", ""),
        json.dumps(data.get("public_replies", []), ensure_ascii=False),
        json.dumps(data.get("dm_messages", []), ensure_ascii=False),
        1 if data.get("is_active", True) else 0,
        1 if data.get("enable_ai_agent", True) else 0,
        datetime.now().isoformat()
    ))
    campaign_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return campaign_id

def update_campaign(campaign_id: int, data: Dict[str, Any]):
    conn = get_db_connection()
    conn.execute("""
    UPDATE campaigns 
    SET name = ?, keywords = ?, match_mode = ?, post_id_filter = ?, public_replies = ?, dm_messages = ?, is_active = ?, enable_ai_agent = ?
    WHERE id = ?
    """, (
        data["name"],
        data["keywords"],
        data.get("match_mode", "contains"),
        data.get("post_id_filter", ""),
        json.dumps(data.get("public_replies", []), ensure_ascii=False),
        json.dumps(data.get("dm_messages", []), ensure_ascii=False),
        1 if data.get("is_active", True) else 0,
        1 if data.get("enable_ai_agent", True) else 0,
        campaign_id
    ))
    conn.commit()
    conn.close()

def delete_campaign(campaign_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()

def list_products() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_product(data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO products (name, description, price, payment_link, benefits, faq, is_available, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["name"],
        data.get("description", ""),
        data["price"],
        data["payment_link"],
        data.get("benefits", ""),
        data.get("faq", ""),
        1 if data.get("is_available", True) else 0,
        datetime.now().isoformat()
    ))
    prod_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return prod_id

def update_product(product_id: int, data: Dict[str, Any]):
    conn = get_db_connection()
    conn.execute("""
    UPDATE products
    SET name = ?, description = ?, price = ?, payment_link = ?, benefits = ?, faq = ?, is_available = ?
    WHERE id = ?
    """, (
        data["name"],
        data.get("description", ""),
        data["price"],
        data["payment_link"],
        data.get("benefits", ""),
        data.get("faq", ""),
        1 if data.get("is_available", True) else 0,
        product_id
    ))
    conn.commit()
    conn.close()

def delete_product(product_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

# ----------------- ADVANCED LEAD CRM OPERATIONS -----------------

def upsert_lead(
    user_id: str,
    username: str = "",
    keyword: str = "",
    reel_id: str = "",
    variant_dm1: str = "A",
    campaign_id: Optional[int] = None,
    comment_id: str = "",
    comment_text: str = ""
) -> Dict[str, Any]:
    """
    Crea o actualiza el lead en el CRM.
    Registra fecha de primer contacto y actualiza last_real_interaction_at.
    Retorna los datos del lead.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    existing = cursor.execute("SELECT * FROM leads WHERE instagram_user_id = ?", (user_id,)).fetchone()
    if existing:
        lead_dict = dict(existing)
        # Actualizar datos si es nuevo comentario
        cursor.execute("""
        UPDATE leads
        SET instagram_username = CASE WHEN ? != '' THEN ? ELSE instagram_username END,
            last_real_interaction_at = ?,
            source_reel_id = CASE WHEN ? != '' THEN ? ELSE source_reel_id END,
            entry_keyword = CASE WHEN ? != '' THEN ? ELSE entry_keyword END,
            comment_text = CASE WHEN ? != '' THEN ? ELSE comment_text END
        WHERE instagram_user_id = ?
        """, (username, username, now_iso, reel_id, reel_id, keyword, keyword, comment_text, comment_text, user_id))
        conn.commit()
        updated = cursor.execute("SELECT * FROM leads WHERE instagram_user_id = ?", (user_id,)).fetchone()
        conn.close()
        return dict(updated)
    else:
        cursor.execute("""
        INSERT INTO leads (
            instagram_user_id, instagram_username, first_contact_at, last_real_interaction_at,
            entry_keyword, source_reel_id, segment, stage, followups_sent, objections_detected,
            bought_sueldo, bought_deuda, variant_dm1, variant_f3, needs_human_escalation,
            campaign_id, source_comment_id, source_post_id, comment_text, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'sin definir', 'comento', 0, '[]', 0, 0, ?, 'A', 0, ?, ?, ?, ?, 'DM_SENT', ?)
        """, (
            user_id, username, now_iso, now_iso, keyword, reel_id, variant_dm1,
            campaign_id, comment_id, reel_id, comment_text, now_iso
        ))
        conn.commit()
        new_row = cursor.execute("SELECT * FROM leads WHERE instagram_user_id = ?", (user_id,)).fetchone()
        conn.close()
        return dict(new_row)

def get_lead_by_user_id(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM leads WHERE instagram_user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_lead_interaction(
    user_id: str,
    is_real_interaction: bool = True,
    new_stage: Optional[str] = None,
    segment: Optional[str] = None,
    objection: Optional[str] = None
):
    """
    Actualiza la última interacción REAL del usuario (mensaje escrito o clic en botón).
    IMPORTANTE: Solo actualiza last_real_interaction_at si is_real_interaction es True.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    lead = cursor.execute("SELECT * FROM leads WHERE instagram_user_id = ?", (user_id,)).fetchone()
    if not lead:
        conn.close()
        return

    now_iso = datetime.now().isoformat()
    updates = []
    params = []

    if is_real_interaction:
        updates.append("last_real_interaction_at = ?")
        params.append(now_iso)

    if new_stage:
        updates.append("stage = ?")
        params.append(new_stage)

    if segment and segment in ["SUELDO", "DEUDA"]:
        updates.append("segment = ?")
        params.append(segment)

    if objection:
        try:
            current_obs = json.loads(lead["objections_detected"] or "[]")
        except Exception:
            current_obs = []
        if objection not in current_obs:
            current_obs.append(objection)
            updates.append("objections_detected = ?")
            params.append(json.dumps(current_obs, ensure_ascii=False))

    if updates:
        sql = f"UPDATE leads SET {', '.join(updates)} WHERE instagram_user_id = ?"
        params.append(user_id)
        cursor.execute(sql, tuple(params))
        conn.commit()

    conn.close()

def update_lead_stage(user_id: str, stage: str):
    conn = get_db_connection()
    conn.execute("UPDATE leads SET stage = ? WHERE instagram_user_id = ?", (stage, user_id))
    conn.commit()
    conn.close()

def set_lead_segment(user_id: str, segment: str):
    conn = get_db_connection()
    conn.execute("UPDATE leads SET segment = ? WHERE instagram_user_id = ?", (segment, user_id))
    conn.commit()
    conn.close()

def record_checkout_click(user_id: str, product_type: str, reel_id: str = ""):
    conn = get_db_connection()
    now_iso = datetime.now().isoformat()
    conn.execute("""
    INSERT INTO checkout_clicks (instagram_user_id, product_type, source_reel_id, clicked_at)
    VALUES (?, ?, ?, ?)
    """, (user_id, product_type, reel_id, now_iso))
    # Actualizar etapa del lead a 'click_checkout' si no ha comprado
    conn.execute("""
    UPDATE leads
    SET stage = CASE WHEN stage = 'compro' THEN 'compro' ELSE 'click_checkout' END
    WHERE instagram_user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()

def record_hotmart_purchase(
    transaction_id: str,
    buyer_email: str,
    buyer_name: str,
    product_id: str,
    product_name: str,
    price_paid: str,
    user_id: Optional[str] = None
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    cursor.execute("""
    INSERT OR IGNORE INTO purchases (transaction_id, buyer_email, buyer_name, product_name, product_id, price_paid, instagram_user_id, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (transaction_id, buyer_email, buyer_name, product_name, product_id, price_paid, user_id, now_iso))
    purchase_id = cursor.lastrowid

    is_sueldo = "sueldo" in product_name.lower() or "17" in price_paid or "order-rules" in product_name.lower()
    is_deuda = "deuda" in product_name.lower() or "55" in price_paid or "zero-debt" in product_name.lower()

    if user_id:
        cursor.execute(f"""
        UPDATE leads
        SET stage = 'compro',
            bought_sueldo = CASE WHEN ? THEN 1 ELSE bought_sueldo END,
            bought_deuda = CASE WHEN ? THEN 1 ELSE bought_deuda END
        WHERE instagram_user_id = ?
        """, (1 if is_sueldo else 0, 1 if is_deuda else 0, user_id))
    elif buyer_name or buyer_email:
        # Intentar coincidencia por username
        clean_user = buyer_name.replace("@", "").strip().lower() if buyer_name else ""
        if clean_user:
            cursor.execute(f"""
            UPDATE leads
            SET stage = 'compro',
                bought_sueldo = CASE WHEN ? THEN 1 ELSE bought_sueldo END,
                bought_deuda = CASE WHEN ? THEN 1 ELSE bought_deuda END
            WHERE LOWER(instagram_username) = ?
            """, (1 if is_sueldo else 0, 1 if is_deuda else 0, clean_user))

    conn.commit()
    conn.close()
    return purchase_id

def flag_human_escalation(user_id: str, reason: str):
    conn = get_db_connection()
    conn.execute("""
    UPDATE leads
    SET needs_human_escalation = 1,
        escalation_reason = ?
    WHERE instagram_user_id = ?
    """, (reason, user_id))
    conn.commit()
    conn.close()

def list_leads(limit: int = 200, stage: Optional[str] = None, segment: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    query = "SELECT * FROM leads"
    params = []
    clauses = []
    if stage:
        clauses.append("stage = ?")
        params.append(stage)
    if segment:
        clauses.append("segment = ?")
        params.append(segment)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def record_lead(username: str, user_id: str, campaign_id: Optional[int], comment_id: str, post_id: str, comment_text: str, status: str = "DM_SENT") -> int:
    lead = upsert_lead(
        user_id=user_id,
        username=username,
        keyword="",
        reel_id=post_id,
        campaign_id=campaign_id,
        comment_id=comment_id,
        comment_text=comment_text
    )
    return lead["id"]

def add_activity_log(event_type: str, details: str, lead_info: str = ""):
    conn = get_db_connection()
    conn.execute("""
    INSERT INTO activity_logs (event_type, lead_info, details, created_at)
    VALUES (?, ?, ?, ?)
    """, (event_type, lead_info, details, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def list_activity_logs(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_conversation_message(instagram_user_id: str, role: str, message_text: str):
    conn = get_db_connection()
    conn.execute("""
    INSERT INTO conversations (instagram_user_id, role, message_text, created_at)
    VALUES (?, ?, ?, ?)
    """, (instagram_user_id, role, message_text, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_conversation_history(instagram_user_id: str, limit: int = 10) -> List[Dict[str, str]]:
    conn = get_db_connection()
    rows = conn.execute("""
    SELECT role, message_text FROM (
        SELECT id, role, message_text FROM conversations
        WHERE instagram_user_id = ?
        ORDER BY id DESC LIMIT ?
    ) ORDER BY id ASC
    """, (instagram_user_id, limit)).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["message_text"]} for r in rows]

# ----------------- 24-HOUR META WINDOW SMART FOLLOW-UP ENGINE -----------------

def get_pending_window_followups() -> List[Dict[str, Any]]:
    """
    Retorna leads pendientes de seguimiento automático cumpliendo ESTRICTAMENTE la política de 24h de Meta.
    Reglas inviolables:
    1. El tiempo transcurrido se calcula SIEMPRE desde 'last_real_interaction_at' (último mensaje o botón del usuario).
    2. Si elapsed_seconds > 84600 (23h 30m) o faltan menos de 30 minutos (1800s) para cerrar las 24h, NO ENVIAR NADA.
    3. Si el usuario ya compró (stage = 'compro') o fue escalado a humano, NO ENVIAR.
    4. Cadencia:
       - Follow-up 1 (stage 1): +2h a +6h (7200s a 21600s). Check-in curioso Regla #3 + botones.
       - Follow-up 2 (stage 2): +8h a +18h (28800s a 64800s). Prueba social / caso de estudio del segmento.
       - Follow-up 3 (stage 3): +20h a +23.5h (72000s a 84600s). Urgencia final A/B antes del cierre de ventana.
    """
    conn = get_db_connection()
    rows = conn.execute("""
    SELECT id, instagram_user_id, instagram_username, first_contact_at, last_real_interaction_at,
           segment, stage, followups_sent, last_followup_at, bought_sueldo, bought_deuda,
           variant_dm1, variant_f3, needs_human_escalation
    FROM leads
    WHERE stage NOT IN ('compro', 'perdido')
      AND needs_human_escalation = 0
      AND followups_sent < 3
      AND last_real_interaction_at IS NOT NULL
    ORDER BY id ASC
    """).fetchall()
    conn.close()

    now = datetime.now()
    pending = []

    for r in rows:
        lead = dict(r)
        last_real_str = lead["last_real_interaction_at"]
        if not last_real_str:
            continue

        try:
            last_real = datetime.fromisoformat(last_real_str)
        except Exception:
            continue

        elapsed = (now - last_real).total_seconds()
        remaining_in_window = 86400 - elapsed

        # 🛑 REGLA DE SEGURIDAD META: Si pasaron más de 23.5 horas o quedan menos de 30 min, abortar.
        if elapsed > 84600 or remaining_in_window < 1800:
            continue

        # Validar tiempo desde el último seguimiento para espaciar
        last_f_str = lead["last_followup_at"]
        last_f_elapsed = (now - datetime.fromisoformat(last_f_str)).total_seconds() if last_f_str else elapsed

        followup_count = lead.get("followups_sent", 0)

        # Seguimiento 1: +2h desde última interacción real (>= 7200s)
        if followup_count == 0 and elapsed >= 7200 and elapsed <= 25200:
            lead["target_followup"] = 1
            pending.append(lead)
        # Seguimiento 2: +8h desde última interacción real (>= 28800s) y al menos 4h desde el seguimiento 1
        elif followup_count == 1 and elapsed >= 28800 and elapsed <= 68400 and last_f_elapsed >= 14400:
            lead["target_followup"] = 2
            pending.append(lead)
        # Seguimiento 3: +20h desde última interacción real (>= 72000s) y antes de 23.5h (84600s)
        elif followup_count == 2 and elapsed >= 72000 and elapsed <= 84600 and last_f_elapsed >= 18000:
            lead["target_followup"] = 3
            pending.append(lead)

    return pending

def update_lead_followup_sent(user_id: str, followup_num: int, variant_f3: Optional[str] = None):
    conn = get_db_connection()
    now_iso = datetime.now().isoformat()
    if variant_f3:
        conn.execute("""
        UPDATE leads
        SET followups_sent = ?, last_followup_at = ?, variant_f3 = ?
        WHERE instagram_user_id = ?
        """, (followup_num, now_iso, variant_f3, user_id))
    else:
        conn.execute("""
        UPDATE leads
        SET followups_sent = ?, last_followup_at = ?
        WHERE instagram_user_id = ?
        """, (followup_num, now_iso, user_id))
    conn.commit()
    conn.close()

# ----------------- 7-DAY INACTIVE LEADS (MANUAL INBOX PANEL) -----------------

def get_7day_inactive_leads(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Retorna leads que interactuaron hace 7 o más días pero no han comprado,
    para que Don Klaus pueda enviarles un mensaje manual sugerido con 1 clic desde el Instagram Inbox.
    """
    conn = get_db_connection()
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
    rows = conn.execute("""
    SELECT id, instagram_user_id, instagram_username, first_contact_at, last_real_interaction_at,
           segment, stage, entry_keyword, source_reel_id, objections_detected
    FROM leads
    WHERE last_real_interaction_at <= ?
      AND stage NOT IN ('compro')
      AND bought_sueldo = 0
      AND bought_deuda = 0
    ORDER BY last_real_interaction_at DESC
    LIMIT ?
    """, (seven_days_ago, limit)).fetchall()
    conn.close()

    result = []
    for r in rows:
        lead = dict(r)
        segment = lead.get("segment", "SUELDO")
        username = lead.get("instagram_username") or "amigo"
        
        # Generar mensaje sugerido para copiar en 1 clic
        if segment == "DEUDA":
            suggested_msg = f"Hola @{username}. Ha pasado una semana desde que vimos el plan para tus deudas. ¿Lograste frenar los intereses de las tarjetas o necesitas que revisemos el Protocolo C.E.R.O.™?"
        else:
            suggested_msg = f"Hola @{username}. Ya pasó una semana desde que descargaste las 7 Reglas Frías. ¿Pudiste aplicar la Regla #3 en tu último cobro o el sueldo se te volvió a escapar?"

        lead["suggested_manual_message"] = suggested_msg
        result.append(lead)

    return result

# ----------------- CRM & FUNNEL METRICS -----------------

def get_crm_metrics_funnel() -> Dict[str, Any]:
    conn = get_db_connection()

    total_leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    total_dms = conn.execute("SELECT COUNT(*) FROM activity_logs WHERE event_type IN ('DM_SENT', 'CARD_SENT', 'QUICK_REPLIES_SENT')").fetchone()[0]
    total_public_replies = conn.execute("SELECT COUNT(*) FROM activity_logs WHERE event_type = 'PUBLIC_REPLY_SENT'").fetchone()[0]
    total_ai_replies = conn.execute("SELECT COUNT(*) FROM activity_logs WHERE event_type = 'AI_REPLY_SENT'").fetchone()[0]

    # Funnel Stages
    stage_counts = {
        "comento": conn.execute("SELECT COUNT(*) FROM leads WHERE stage = 'comento'").fetchone()[0],
        "respondio": conn.execute("SELECT COUNT(*) FROM leads WHERE stage = 'respondio'").fetchone()[0],
        "recibio_pdf": conn.execute("SELECT COUNT(*) FROM leads WHERE stage = 'recibio_pdf'").fetchone()[0],
        "vio_oferta": conn.execute("SELECT COUNT(*) FROM leads WHERE stage = 'vio_oferta'").fetchone()[0],
        "click_checkout": conn.execute("SELECT COUNT(*) FROM leads WHERE stage = 'click_checkout'").fetchone()[0],
        "compro": conn.execute("SELECT COUNT(*) FROM leads WHERE stage = 'compro'").fetchone()[0],
        "perdido": conn.execute("SELECT COUNT(*) FROM leads WHERE stage = 'perdido'").fetchone()[0],
    }

    # Purchases & Revenue
    bought_sueldo_count = conn.execute("SELECT COUNT(*) FROM leads WHERE bought_sueldo = 1").fetchone()[0]
    bought_deuda_count = conn.execute("SELECT COUNT(*) FROM leads WHERE bought_deuda = 1").fetchone()[0]
    total_purchases = bought_sueldo_count + bought_deuda_count
    total_revenue = (bought_sueldo_count * 17) + (bought_deuda_count * 55)

    # Segments
    sueldo_segment_count = conn.execute("SELECT COUNT(*) FROM leads WHERE segment = 'SUELDO'").fetchone()[0]
    deuda_segment_count = conn.execute("SELECT COUNT(*) FROM leads WHERE segment = 'DEUDA'").fetchone()[0]

    # A/B Tests
    # DM 1 Variant A vs B
    dm1_a = conn.execute("SELECT COUNT(*) FROM leads WHERE variant_dm1 = 'A'").fetchone()[0]
    dm1_b = conn.execute("SELECT COUNT(*) FROM leads WHERE variant_dm1 = 'B'").fetchone()[0]
    dm1_a_converted = conn.execute("SELECT COUNT(*) FROM leads WHERE variant_dm1 = 'A' AND stage IN ('recibio_pdf', 'vio_oferta', 'click_checkout', 'compro')").fetchone()[0]
    dm1_b_converted = conn.execute("SELECT COUNT(*) FROM leads WHERE variant_dm1 = 'B' AND stage IN ('recibio_pdf', 'vio_oferta', 'click_checkout', 'compro')").fetchone()[0]

    # Followup 3 Variant A vs B
    f3_a = conn.execute("SELECT COUNT(*) FROM leads WHERE variant_f3 = 'A' AND followups_sent >= 3").fetchone()[0]
    f3_b = conn.execute("SELECT COUNT(*) FROM leads WHERE variant_f3 = 'B' AND followups_sent >= 3").fetchone()[0]
    f3_a_sales = conn.execute("SELECT COUNT(*) FROM leads WHERE variant_f3 = 'A' AND stage = 'compro'").fetchone()[0]
    f3_b_sales = conn.execute("SELECT COUNT(*) FROM leads WHERE variant_f3 = 'B' AND stage = 'compro'").fetchone()[0]

    # Objections breakdown
    objections_rows = conn.execute("SELECT objections_detected FROM leads WHERE objections_detected != '[]'").fetchall()
    objections_count = {}
    for r in objections_rows:
        try:
            obs = json.loads(r["objections_detected"])
            for ob in obs:
                objections_count[ob] = objections_count.get(ob, 0) + 1
        except Exception:
            pass

    # Top Reels
    reels_rows = conn.execute("""
    SELECT source_reel_id, COUNT(*) as lead_count, SUM(bought_sueldo + bought_deuda) as sales_count
    FROM leads
    WHERE source_reel_id != ''
    GROUP BY source_reel_id
    ORDER BY lead_count DESC
    LIMIT 5
    """).fetchall()
    top_reels = [dict(r) for r in reels_rows]

    conn.close()

    return {
        "total_leads_captured": total_leads,
        "total_dms_sent": total_dms,
        "total_public_replies": total_public_replies,
        "total_ai_replies": total_ai_replies,
        "total_purchases": total_purchases,
        "total_revenue_usd": total_revenue,
        "stage_counts": stage_counts,
        "segments": {
            "sueldo": sueldo_segment_count,
            "deuda": deuda_segment_count,
            "sin_definir": total_leads - sueldo_segment_count - deuda_segment_count
        },
        "ab_tests": {
            "dm1": {
                "variant_a": {"sent": dm1_a, "engaged": dm1_a_converted, "rate": round(dm1_a_converted / max(dm1_a, 1) * 100, 1)},
                "variant_b": {"sent": dm1_b, "engaged": dm1_b_converted, "rate": round(dm1_b_converted / max(dm1_b, 1) * 100, 1)}
            },
            "followup3": {
                "variant_a": {"sent": f3_a, "sales": f3_a_sales, "rate": round(f3_a_sales / max(f3_a, 1) * 100, 1)},
                "variant_b": {"sent": f3_b, "sales": f3_b_sales, "rate": round(f3_b_sales / max(f3_b, 1) * 100, 1)}
            }
        },
        "objections": objections_count,
        "top_reels": top_reels
    }

def get_stats() -> Dict[str, Any]:
    return get_crm_metrics_funnel()

def reset_stats():
    conn = get_db_connection()
    conn.execute("DELETE FROM leads")
    conn.execute("DELETE FROM activity_logs")
    conn.execute("DELETE FROM conversations")
    conn.execute("DELETE FROM followups")
    conn.execute("DELETE FROM purchases")
    conn.execute("DELETE FROM checkout_clicks")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('leads', 'activity_logs', 'conversations', 'followups', 'purchases', 'checkout_clicks')")
    conn.commit()
    conn.close()

# Legacy functions maintained for backward compatibility
def register_pdf_lead(instagram_user_id: str, username: Optional[str] = None):
    upsert_lead(user_id=instagram_user_id, username=username or "")
    update_lead_interaction(user_id=instagram_user_id, is_real_interaction=True, new_stage="recibio_pdf")

def mark_lead_responded(instagram_user_id: str):
    update_lead_interaction(user_id=instagram_user_id, is_real_interaction=True, new_stage="respondio")

def get_pending_followup_leads() -> List[Dict[str, Any]]:
    return get_pending_window_followups()

def update_lead_followup_stage(instagram_user_id: str, new_stage: int, status: str = 'PENDING'):
    update_lead_followup_sent(instagram_user_id, new_stage)


