import sqlite3
import json
from datetime import datetime
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

    # Table: Leads captured
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instagram_username TEXT,
        instagram_user_id TEXT,
        campaign_id INTEGER,
        source_comment_id TEXT,
        source_post_id TEXT,
        comment_text TEXT,
        status TEXT DEFAULT 'DM_SENT',
        created_at TEXT NOT NULL
    )
    """)

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

    # Insert default settings if empty
    default_settings = {
        "company_name": "Mi Negocio / Tienda",
        "company_description": "Venta de productos y servicios digitales y físicos con atención personalizada.",
        "sales_tone": "amable, persuasivo, profesional, claro y enfocado en cerrar la venta con el link de compra.",
        "meta_access_token": config.META_ACCESS_TOKEN,
        "meta_verify_token": config.META_VERIFY_TOKEN,
        "meta_page_id": config.META_PAGE_ID,
        "instagram_account_id": config.INSTAGRAM_ACCOUNT_ID,
        "gemini_api_key": config.GEMINI_API_KEY,
        "gemini_model": config.GEMINI_MODEL,
    }

    for key, val in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, str(val)))

    # Insert a sample ready-to-use campaign if empty
    cursor.execute("SELECT COUNT(*) FROM campaigns")
    if cursor.fetchone()[0] == 0:
        sample_public_replies = [
            "¡Listo! Te acabo de enviar toda la información por mensaje privado 📩✨",
            "¡Revisa tu bandeja de entrada! Te envié el link y los detalles 🚀",
            "¡Te escribí por DM con la info exclusiva y el acceso! 😉🎁"
        ]
        sample_dm_messages = [
            {
                "text": "¡Hola @username! 👋 Gracias por tu comentario. Aquí tienes los detalles del producto que viste en nuestra publicación 🎁",
                "delay_seconds": 0
            },
            {
                "text": "🔥 *Beneficios clave*:\n• Acceso inmediato y garantía de satisfacción.\n• Soporte personalizado.\n\nPuedes adquirirlo o ver más detalles directamente aquí:\n👉 https://mitienda.com/producto",
                "delay_seconds": 2
            },
            {
                "text": "¿Tienes alguna duda sobre métodos de pago o entrega? Escríbeme aquí mismo y te ayudo de inmediato. 😊",
                "delay_seconds": 3
            }
        ]
        cursor.execute("""
        INSERT INTO campaigns (name, keywords, match_mode, post_id_filter, public_replies, dm_messages, is_active, enable_ai_agent, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?)
        """, (
            "Campaña Principal - Palabras Clave de Venta",
            "QUIERO, PRECIO, LINK, INFO, COMPRAR, DETALLES, CATALOGO",
            "contains",
            "",
            json.dumps(sample_public_replies, ensure_ascii=False),
            json.dumps(sample_dm_messages, ensure_ascii=False),
            datetime.now().isoformat()
        ))

    # Insert sample product if empty
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO products (name, description, price, payment_link, benefits, faq, is_available, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            "Producto / Servicio Estrella",
            "Nuestro producto más vendido con entrega inmediata y garantía.",
            "$29.99 USD",
            "https://mitienda.com/checkout/oferta-especial",
            "• Entrega inmediata\n• Garantía de 30 días\n• Bonos exclusivos incluidos",
            "¿Qué métodos de pago aceptan? Aceptamos Tarjeta de Crédito/Débito, PayPal y Transferencias.",
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

    # Fallback permanente a Variables de Entorno de Render / config
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

def record_lead(username: str, user_id: str, campaign_id: Optional[int], comment_id: str, post_id: str, comment_text: str, status: str = "DM_SENT") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO leads (instagram_username, instagram_user_id, campaign_id, source_comment_id, source_post_id, comment_text, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (username, user_id, campaign_id, comment_id, post_id, comment_text, status, datetime.now().isoformat()))
    lead_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return lead_id

def list_leads(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

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
    SELECT role, message_text FROM conversations
    WHERE instagram_user_id = ?
    ORDER BY id ASC LIMIT ?
    """, (instagram_user_id, limit)).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["message_text"]} for r in rows]

def get_stats() -> Dict[str, Any]:
    conn = get_db_connection()
    total_campaigns = conn.execute("SELECT COUNT(*) FROM campaigns WHERE is_active = 1").fetchone()[0]
    total_leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    total_dms = conn.execute("SELECT COUNT(*) FROM activity_logs WHERE event_type = 'DM_SENT'").fetchone()[0]
    total_public_replies = conn.execute("SELECT COUNT(*) FROM activity_logs WHERE event_type = 'PUBLIC_REPLY_SENT'").fetchone()[0]
    total_ai_replies = conn.execute("SELECT COUNT(*) FROM activity_logs WHERE event_type = 'AI_REPLY_SENT'").fetchone()[0]
    conn.close()
    return {
        "active_campaigns": total_campaigns,
        "total_leads_captured": total_leads,
        "total_dms_sent": total_dms,
        "total_public_replies": total_public_replies,
        "total_ai_replies": total_ai_replies
    }

def reset_stats():
    conn = get_db_connection()
    conn.execute("DELETE FROM leads")
    conn.execute("DELETE FROM activity_logs")
    conn.execute("DELETE FROM conversations")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('leads', 'activity_logs', 'conversations')")
    conn.commit()
    conn.close()
