import sys
import io

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

import logging
import random
import re
from typing import List, Dict, Any, Optional
from database import get_settings, list_products, get_conversation_history, save_conversation_message, add_activity_log

logger = logging.getLogger("sales_agent")

FALLBACK_MODELS = [
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-3.7-flash",
    "gemini-3.8-flash"
]

class SalesAgent:
    def __init__(self):
        pass

    def build_system_prompt(self) -> str:
        system_prompt = """Eres DON KLAUS respondiendo personalmente en los Mensajes Directos (DM) de tu Instagram (@sistemadonklaus) y Facebook.

TU IDENTIDAD Y VOZ:
- Eres un mentor financiero experimentado, frío, sobrio, directo y profundamente pragmático.
- Odias la motivación barata, las frases cliché de autoayuda y el positivismo tóxico.
- Hablas como un humano real en un chat privado: conciso, seguro, sin rodeos, con frases bien puntuadas y párrafos breves (máximo 2 a 4 líneas por párrafo).
- NUNCA digas "Soy un bot", "Soy un asistente de IA" ni uses lenguaje corporativo blando ("¡Espero que te encuentres de maravilla!"). Eres Don Klaus atendiendo tu privado.

PRODUCTOS Y PROTOCOLOS:
1. SUELDO BAJO CONTROL™ (US$17 - Pago único)
   • Enlace: https://klaus-order-rules.lovable.app/
   • Para quién es: Personas que cobran y el dinero se les esfuma, no saben dónde se fue, o viven justos entre quincenas.
   • Solución: Protocolo Día de Pago™ de 7 días (MIRA ➔ SEPARA ➔ DECIDE ➔ REVISA).

2. DEUDA BAJO CONTROL™ (US$55 - Pago único · Garantía 7 días)
   • Enlace: https://zero-debt-protocol.lovable.app/
   • Para quién es: Personas con varias deudas, tarjetas de crédito al tope, préstamos o pagos mínimos sin saber cuál atacar primero.
   • Solución: Protocolo C.E.R.O.™ (Censo, Evaluación, Ruta, Operación).

3. 7 REGLAS FRÍAS DE DON KLAUS (Gratis - Lead Magnet)
   • Enlace: https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view
   • Para quién es: Personas que quieren empezar a entender por qué improvisan con su dinero.

MISIÓN Y ESTRATEGIA EN DM:
1. DIAGNÓSTICO QUIRÚRGICO:
   • Si el usuario dice que el dinero no le alcanza, se le desaparece o no sabe en qué gasta:
     ➔ Explícale con empatía fría la causa y recomiéndale 'Sueldo Bajo Control™' ($17): https://klaus-order-rules.lovable.app/
   
   • Si el usuario habla de tarjetas al tope, préstamos, intereses o deudas acumuladas:
     ➔ Explícale por qué pagar mínimos es cavar su propia tumba y recomiéndale 'Deuda Bajo Control™' ($55): https://zero-debt-protocol.lovable.app/

   • Si el usuario está pidiendo las reglas o apenas saluda:
     ➔ Dale el PDF de las 7 Reglas (https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view) y pregúntale directamente: "¿Dónde está tu mayor fuga hoy: en cómo entra tu sueldo o en las deudas que tienes acumuladas?"

2. MANEJO HUMANO DE OBJECIONES:
   • "No tengo plata": "Ese es exactamente el síntoma de vivir sin un sistema. No necesitas más dinero para empezar a ordenar el que ya tienes. El desorden actual te está costando diez veces más caro cada mes."
   • "¿Cómo funciona?": Explica los pasos en 3 líneas claras y directas.
   • "Garantía": "Tienes 7 días de garantía incondicional. Si aplicas el protocolo y no ves orden en tus números, te devuelvo cada centavo."

REGLAS DE FORMATO:
- Máximo 2 a 3 párrafos cortos por respuesta.
- Sé natural, empático con la realidad económica pero firme en la solución.
"""
        return system_prompt

    def _call_gemini_with_fallback(self, client, contents, system_instruction=None, max_tokens=800, temperature=0.7) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_tokens
        ) if system_instruction else types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        )

        for model in FALLBACK_MODELS:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"Fallo en modelo {model}: {e}. Intentando siguiente modelo...")
                continue
        raise RuntimeError("Todos los modelos de Gemini fallaron.")

    async def generate_comment_reply(self, username: str, comment_text: str) -> str:
        """
        Genera una respuesta pública al comentario de Instagram/Facebook 100% personalizada y humana.
        """
        settings = get_settings()
        api_key = settings.get("gemini_api_key", "").strip()

        fallback_options = [
            f"Listo @{username}, te escribí por privado para que lo revises con calma. ⚔️",
            f"Te dejé un mensaje directo, @{username}. Míralo cuando tengas un minuto. 📩",
            f"Ya te mandé el mensaje al privado, @{username}. 📜",
            f"Revisa tu bandeja de mensajes, @{username}. Te dejé lo prometido. ⚔️",
            f"Te acabo de escribir al DM, @{username}. 📩"
        ]

        if not api_key:
            return random.choice(fallback_options)

        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            prompt = f"""Eres Don Klaus respondiendo públicamente a un comentario en tu Reel de Instagram.
Usuario: @{username}
Comentario que dejó: "{comment_text}"

REGLAS:
- Redacta una respuesta de EXACTAMENTE 1 sola línea corta (máximo 12 palabras).
- Tono: Sobrio, educado, humano, directo y frío (estilo Don Klaus).
- Menciona que le dejaste un mensaje por privado (DM) para que lo revise.
- Incluye el @{username}.
- NO uses signos de exclamación exagerados ni suenes a bot corporativo.
- Devuelve ÚNICAMENTE el texto de la respuesta, nada más."""

            reply = self._call_gemini_with_fallback(
                client,
                contents=[prompt],
                max_tokens=60,
                temperature=0.8
            )
            # Limpiar comillas si las agregó
            clean_reply = reply.strip().strip('"').strip("'")
            if not clean_reply or len(clean_reply) > 120:
                return random.choice(fallback_options)
            return clean_reply
        except Exception as e:
            logger.warning(f"Error generando respuesta de comentario con IA: {e}")
            return random.choice(fallback_options)

    async def generate_optin_dm(self, username: str, comment_text: str) -> str:
        """
        Genera el primer mensaje privado (Opt-In) ultra-humano y SIN ENLACES.
        """
        settings = get_settings()
        api_key = settings.get("gemini_api_key", "").strip()

        fallback_optins = [
            f"Hola @{username}. Vi tu comentario en el reel.\n\nTe preparé el documento de las 7 Reglas Frías para que lo tengas a mano.\n\n¿Quieres que te lo pase por aquí? Respóndeme con un «SÍ» o «KLAUS» y te libero el acceso directo.",
            f"Hola @{username}. Vi que pediste las Reglas Frías de Don Klaus.\n\nSon 7 reglas prácticas para cuando el dinero entra y desaparece sin orden.\n\n¿Te las comparto por aquí? Escríbeme «SÍ» y te paso el documento.",
            f"Hola @{username}, vi tu comentario.\n\nTengo listo el PDF con las 7 Reglas Frías para enviártelo.\n\n¿Quieres que te lo pase por este chat? Dime «SÍ» o «KLAUS» para abrírtelo de inmediato."
        ]

        if not api_key:
            return random.choice(fallback_optins)

        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            prompt = f"""Eres Don Klaus enviando un primer mensaje privado (DM) en Instagram a @{username}, quien comentó: "{comment_text}" en tu reel.

REGLAS CRÍTICAS:
- PROHIBIDO TERMINANTEMENTE incluir enlaces web, URLs o http (Meta penaliza enlaces en el primer mensaje).
- Tono: Sobrio, pragmático, respetuoso, directo y humano.
- Saluda brevemente a @{username}.
- Dile que tienes listo el documento de las 7 Reglas Frías.
- Pregúntale si quiere que se lo pases por este chat y pídele que te responda «SÍ» o «KLAUS» para abrírselo.
- Máximo 3 a 4 líneas cortas.
- Devuelve solo el texto del mensaje."""

            dm_text = self._call_gemini_with_fallback(
                client,
                contents=[prompt],
                max_tokens=150,
                temperature=0.7
            )
            clean_dm = dm_text.strip().strip('"')
            # Seguridad: si la IA incluyó una URL por error, usamos fallback seguro
            if "http" in clean_dm.lower() or "www." in clean_dm.lower():
                return random.choice(fallback_optins)
            return clean_dm
        except Exception as e:
            logger.warning(f"Error generando Opt-In DM con IA: {e}")
            return random.choice(fallback_optins)

    async def generate_response(self, user_id: str, user_message: str, username: Optional[str] = None) -> str:
        settings = get_settings()
        api_key = settings.get("gemini_api_key", "").strip()

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

            reply_text = self._call_gemini_with_fallback(
                client,
                contents=contents,
                system_instruction=system_instruction,
                max_tokens=600,
                temperature=0.7
            )

            save_conversation_message(user_id, "assistant", reply_text)
            add_activity_log("AI_REPLY_SENT", f"Don Klaus IA respondió a {user_id}: '{reply_text[:60]}...'", f"User: {username or user_id}")
            return reply_text

        except Exception as e:
            logger.exception(f"Error en Gemini Sales Agent: {e}")
            fallback_reply = self._generate_rule_based_fallback(user_message)
            save_conversation_message(user_id, "assistant", fallback_reply)
            return fallback_reply

    def _generate_rule_based_fallback(self, message: str) -> str:
        msg = message.lower().strip()

        if any(k in msg for k in ["si", "sí", "klaus", "dale", "pasamelo", "pásamelo", "envialo", "envíalo", "claro", "porfa", "mandalo", "mándalo"]):
            return (
                "Aquí tienes las Reglas Frías de Don Klaus:\n\n"
                "👉 https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view\n\n"
                "No son frases para motivarte. Son reglas para cuando el dinero entra, sale y no tienes un sistema de control.\n\n"
                "Léelas con esta pregunta en mente:\n"
                "“¿Cuál de estas reglas estoy rompiendo hoy?”\n\n"
                "Cuando las revises, dime dónde necesitas más control hoy:\n\n"
                "💰 Escribe SUELDO — si el dinero entra y desaparece rápido\n"
                "⚔️ Escribe DEUDA — si pagas pero no sabes qué liquidar primero"
            )

        if any(k in msg for k in ["sueldo", "ingreso", "cobro", "gasto", "fuga", "desaparece", "gano", "alcanza", "opcion 1", "opción 1", "1"]):
            return (
                "El problema no es cuánto ganas, sino que tu dinero entra sin una función asignada desde el día 1.\n\n"
                "Para romper ese ciclo necesitas el Protocolo Día de Pago™ de 7 días: MIRA ➔ SEPARA ➔ DECIDE ➔ REVISA.\n\n"
                "Empieza aquí:\n"
                "🔥 *Sueldo Bajo Control™* (US$17 · pago único)\n"
                "👉 https://klaus-order-rules.lovable.app/"
            )

        if any(k in msg for k in ["deuda", "deudas", "tarjeta", "prestamo", "debo", "banco", "interes", "opcion 2", "opción 2", "2"]):
            return (
                "Si tienes varias deudas y estás pagando mínimos, estás disparando con los ojos cerrados.\n\n"
                "El Protocolo C.E.R.O.™ te da el orden matemático para saber cuánto debes, cuánto atacar y qué deuda liquidar primero.\n\n"
                "⚔️ *Deuda Bajo Control™* (US$55 · pago único · garantía 7 días)\n"
                "👉 https://zero-debt-protocol.lovable.app/"
            )

        return (
            "Dime dónde está tu mayor fuga hoy:\n\n"
            "💰 Escribe *SUELDO* — el dinero entra y desaparece\n"
            "⚔️ Escribe *DEUDA* — pagas, pero no sabes qué atacar primero\n\n"
            "O cuéntame tu caso y te digo exactamente qué paso dar."
        )

sales_agent = SalesAgent()
