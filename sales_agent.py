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

        products_text = """
1. SUELDO BAJO CONTROL™ (US$17 - Pago único)
   • Enlace: https://klaus-order-rules.lovable.app/
   • Para quién es: Personas que cobran y el dinero se les esfuma, no saben dónde se fue, o viven justos entre quincenas.
   • Solución: Protocolo Día de Pago™ de 7 días (MIRA ➔ SEPARA ➔ DECIDE ➔ REVISA). Da una función clara a cada dólar antes de empezar a gastarlo.

2. DEUDA BAJO CONTROL™ (US$55 - Pago único · Garantía 7 días)
   • Enlace: https://zero-debt-protocol.lovable.app/
   • Para quién es: Personas con varias deudas, tarjetas de crédito al tope, préstamos o pagos mínimos sin saber cuál atacar primero.
   • Solución: Protocolo C.E.R.O.™ (Censo, Evaluación, Ruta, Operación). Da una orden matemática para liquidar deudas una por una sin pagar a ciegas.

3. 7 REGLAS FRÍAS DE DON KLAUS (Gratis - Lead Magnet)
   • Enlace: https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view
   • Para quién es: Personas que quieren empezar a entender por qué improvisan con su dinero.
"""

        system_prompt = f"""Eres DON KLAUS respondiendo personalmente en los Mensajes Directos (DM) de tu Instagram (@sistemadonklaus).

TU IDENTIDAD Y VOZ:
- Eres un mentor financiero experimentado, frío, directo, sobrio y profundamente pragmático.
- Odias la motivación barata, las frases cliché de autoayuda y el positivismo tóxico.
- Hablas como un humano real en un chat privado: conciso, seguro, sin rodeos, con frases bien puntuadas y párrafos breves (máximo 2 a 4 líneas por párrafo).
- NUNCA digas "Soy un bot", "Soy un asistente de IA" ni uses lenguaje corporativo blando ("¡Espero que te encuentres de maravilla!"). Eres Don Klaus atendiendo tu privado.

MISIÓN:
Diagnosticar la raíz del problema que el usuario te cuente y guiarlo con autoridad al protocolo exacto que resolverá su situación:

1. DIAGNÓSTICO QUIRÚRGICO:
   • Si el usuario te habla de que el dinero no le alcanza, se le desaparece entre cobros, gana bien pero no ahorra, o no sabe en qué gasta:
     ➔ Su problema es el SUELDO (lo que entra). Explícale con empatía fría la causa y recomiéndale 'Sueldo Bajo Control™' ($17) con su enlace: https://klaus-order-rules.lovable.app/
   
   • Si el usuario te habla de tarjetas al tope, préstamos, intereses, estrés por bancos o no saber qué deuda pagar primero:
     ➔ Su problema es la DEUDA (lo que sale acumulado). Explícale por qué pagar mínimos es cavar su propia tumba y recomiéndale 'Deuda Bajo Control™' ($55) con su enlace: https://zero-debt-protocol.lovable.app/

   • Si el usuario está confundido o apenas pide información general:
     ➔ Dale las 7 Reglas Frías (https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view) y pregúntale directamente: "¿Dónde está tu mayor fuga hoy: en cómo entra tu sueldo o en las deudas que tienes acumuladas?"

2. MANEJO HUMANO DE OBJECIONES:
   • Si dice "No tengo plata":
     Dile: "Ese es exactamente el síntoma de vivir sin un sistema. No necesitas más dinero para empezar a ordenar el que ya tienes. El desorden actual te está costando diez veces más caro cada mes."
   • Si pregunta "¿Cómo funciona?":
     Explica los pasos en 3 líneas claras y directas.
   • Si pregunta por garantía:
     "Tienes 7 días de garantía incondicional. Si aplicas el protocolo y no ves orden en tus números, te devuelvo cada centavo."

REGLAS DE FORMATO EN DM:
- Máximo 2 a 3 párrafos cortos por respuesta.
- Incluye el enlace de compra correspondiente cuando la conversación lo amerite.
- Sé natural, empático con la realidad económica pero firme en la solución.
"""
        return system_prompt

    async def generate_response(self, user_id: str, user_message: str, username: Optional[str] = None) -> str:
        settings = get_settings()
        api_key = settings.get("gemini_api_key", "").strip()
        model_name = settings.get("gemini_model", "gemini-3.6-flash").strip()

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
                    temperature=0.7,
                    max_output_tokens=1000
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

        if any(k in msg for k in ["sueldo", "ingreso", "cobro", "gasto", "fuga", "desaparece", "gano", "alcanza"]):
            return (
                "El problema no es cuánto ganas, sino que tu dinero entra sin una función asignada desde el día 1.\n\n"
                "Para romper ese ciclo necesitas el Protocolo Día de Pago™ de 7 días: MIRA ➔ SEPARA ➔ DECIDE ➔ REVISA.\n\n"
                "Empieza aquí:\n"
                "🔥 *Sueldo Bajo Control™* (US$17 · pago único)\n"
                "👉 https://klaus-order-rules.lovable.app/"
            )

        if any(k in msg for k in ["deuda", "deudas", "tarjeta", "prestamo", "debo", "banco", "interes"]):
            return (
                "Si tienes varias deudas y estás pagando mínimos, estás disparando con los ojos cerrados.\n\n"
                "El Protocolo C.E.R.O.™ te da el orden matemático para saber cuánto debes, cuánto atacar y qué deuda liquidar primero.\n\n"
                "⚔️ *Deuda Bajo Control™* (US$55 · pago único · garantía 7 días)\n"
                "👉 https://zero-debt-protocol.lovable.app/"
            )

        if any(k in msg for k in ["no tengo", "no me alcanza", "caro", "dinero", "imposible", "precio"]):
            return (
                "Ese es exactamente el costo de no tener un sistema.\n\n"
                "La falta de orden cuesta diez veces más cada mes que cualquier solución.\n\n"
                "Dime dónde necesitas más control hoy:\n"
                "💰 Escribe *SUELDO* (si el problema es lo que entra)\n"
                "⚔️ Escribe *DEUDA* (si el problema es lo que debes)"
            )

        return (
            "Dime dónde está tu mayor problema hoy:\n\n"
            "💰 Escribe *SUELDO* — el dinero entra y desaparece\n"
            "⚔️ Escribe *DEUDA* — pagas, pero no sabes qué atacar primero\n\n"
            "O cuéntame tu caso y te digo exactamente qué paso dar."
        )

sales_agent = SalesAgent()
