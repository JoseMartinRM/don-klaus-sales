import sys
import io

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

import logging
from typing import List, Dict, Any, Optional
from database import get_settings, list_products, get_conversation_history, save_conversation_message, add_activity_log

logger = logging.getLogger("sales_agent")

class SalesAgent:
    def __init__(self):
        pass

    def build_system_prompt(self) -> str:
        settings = get_settings()
        products = list_products()

        products_text = ""
        for idx, p in enumerate(products, 1):
            if p.get("is_available"):
                products_text += f"\n--- PRODUCTO #{idx}: {p['name']} ---\n"
                products_text += f"• Precio: {p['price']}\n"
                products_text += f"• Descripción: {p.get('description', 'N/A')}\n"
                products_text += f"• Beneficios: {p.get('benefits', 'N/A')}\n"
                products_text += f"• Enlace de Compra: {p['payment_link']}\n"

        system_prompt = f"""Eres DON KLAUS.
Tu identidad: Eres un mentor financiero frío, implacable con las excusas, directo y quirúrgico. Desprecias la motivación vacía y los consejos cliché de ahorro.

MISIÓN:
Diagnosticar a los usuarios en Instagram y guiarlos al protocolo exacto:
1. Si su problema es que el dinero entra y desaparece ➔ Su problema es el SUELDO ➔ Ofrecer 'Sueldo Bajo Control™' (US$17).
2. Si su problema es que tienen deudas y no saben cuál atacar primero ➔ Su problema es la DEUDA ➔ Ofrecer 'Deuda Bajo Control™' con el Plan C.E.R.O. (US$55).

CATÁLOGO OFICIAL:
{products_text}

ESTILO Y TONO DE DON KLAUS:
- Mensajes persuasivos, profundos pero sin rodeos. Que hagan decir al lector 'esto me pasa exactamente a mí'.
- Enlace de compra oficial: https://zero-debt-protocol.lovable.app/
"""
        return system_prompt

    async def generate_response(self, user_id: str, user_message: str, username: Optional[str] = None) -> str:
        settings = get_settings()
        api_key = settings.get("gemini_api_key", "").strip()
        model_name = settings.get("gemini_model", "gemini-2.5-flash").strip()

        save_conversation_message(user_id, "user", user_message)

        if not api_key:
            fallback_reply = self._generate_rule_based_fallback(user_message)
            save_conversation_message(user_id, "assistant", fallback_reply)
            add_activity_log("AI_REPLY_SENT", f"[Don Klaus Rules] Respondido a {user_id}: '{fallback_reply[:60]}...'", f"User: {username or user_id}")
            return fallback_reply

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            system_instruction = self.build_system_prompt()

            history = get_conversation_history(user_id, limit=8)
            contents = []

            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                ))

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.6,
                    max_output_tokens=400
                )
            )

            reply_text = response.text.strip()
            save_conversation_message(user_id, "assistant", reply_text)
            add_activity_log("AI_REPLY_SENT", f"Don Klaus IA respondió a {user_id}: '{reply_text}'", f"User: {username or user_id}")
            return reply_text

        except Exception as e:
            logger.exception(f"Error en Gemini: {e}")
            fallback_reply = self._generate_rule_based_fallback(user_message)
            save_conversation_message(user_id, "assistant", fallback_reply)
            return fallback_reply

    def _generate_rule_based_fallback(self, message: str) -> str:
        msg = message.lower().strip()

        if any(k in msg for k in ["sueldo", "ingreso", "cobro", "gasto", "fuga", "desaparece"]):
            return (
                "Si cada vez que cobras sientes que el dinero dura menos de lo que debería, el problema no es cuánto ganas. Empieza en que tu sueldo entra sin una orden clara.\n\n"
                "Para eso está *Sueldo Bajo Control™* (US$17 · pago único).\n"
                "Protocolo Día de Pago™ de 7 días: MIRA ➔ SEPARA ➔ DECIDE ➔ REVISA.\n\n"
                "👉 [ QUIERO PONER MI SUELDO BAJO CONTROL → ]\nhttps://klaus-order-rules.lovable.app/"
            )

        if any(k in msg for k in ["deuda", "deudas", "tarjeta", "prestamo", "debo", "banco"]):
            return (
                "Si hoy aparecieran $300 extra para tus deudas… ¿sabrías exactamente cuál atacar primero y por qué?\n\n"
                "Si no lo sabes, estás pagando a ciegas. *Deuda Bajo Control™* organiza eso con el Protocolo C.E.R.O.™ (Censo, Evaluación, Ruta, Operación).\n\n"
                "⚔️ US$55 · pago único · garantía 7 días\n\n"
                "👉 [ QUIERO MI PLAN C.E.R.O.™ → ]\nhttps://zero-debt-protocol.lovable.app/"
            )

        if any(k in msg for k in ["no tengo", "no me alcanza", "caro", "dinero", "imposible"]):
            return (
                "Ese es exactamente el síntoma de improvisar con el dinero.\n\n"
                "La falta de orden cuesta diez veces más que cualquier sistema.\n\n"
                "Decide dónde necesitas más control hoy:\n\n"
                "💰 Escribe *SUELDO* — el dinero entra y desaparece\n"
                "⚔️ Escribe *DEUDA* — pagas, pero no sabes qué atacar primero"
            )

        return (
            "Dime dónde necesitas más control hoy:\n\n"
            "💰 Escribe *SUELDO* — el dinero entra y desaparece\n"
            "⚔️ Escribe *DEUDA* — pagas, pero no sabes qué atacar primero"
        )

sales_agent = SalesAgent()
