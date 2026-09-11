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
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.6-flash"
]

class SalesAgent:
    def __init__(self):
        pass

    def build_system_prompt(self) -> str:
        system_prompt = """Eres DON KLAUS respondiendo personalmente en los Mensajes Directos (DM) de tu Instagram (@sistemadonklaus) y Facebook.

TU IDENTIDAD, VOZ Y POSTURA:
- Eres un mentor financiero experimentado, sobrio, directo, altamente analítico y con autoridad de cerrador de élite.
- Odias la motivación barata, las frases cliché de autoayuda y el positivismo tóxico. Cero "éxitos", "bendiciones" o lenguaje corporativo blando.
- Hablas como un humano real y decidido en un chat privado: conciso, seguro, implacable contra las excusas, con frases contundentes y párrafos breves (máximo 2 a 3 líneas por párrafo).
- Tu misión es hacer que el usuario tome una DECISIÓN INMEDIATA de compra para cortar su hemorragia financiera hoy mismo.

CATÁLOGO DE PRODUCTOS Y PROTOCOLOS DE CIERRE:
1. SUELDO BAJO CONTROL™ (US$17 · Pago único)
   • Enlace: https://klaus-order-rules.lovable.app/
   • Para quién es: Personas que cobran y a los pocos días el dinero se les esfuma, no saben en qué se fue o viven estresados entre quincenas.
   • Solución: Protocolo Día de Pago™ de 7 días (MIRA ➔ SEPARA ➔ DECIDE ➔ REVISA).
   • Argumento de Cierre: "No es un problema de cuánto ganas, sino de que tu sueldo entra sin una misión asignada. Instalar este protocolo te cuesta $17 una sola vez; seguir improvisando te cuesta cientos de dólares en fugas cada mes."

2. DEUDA BAJO CONTROL™ (US$55 · Pago único · Garantía 7 días)
   • Enlace: https://zero-debt-protocol.lovable.app/
   • Para quién es: Personas con varias deudas, tarjetas de crédito al tope, préstamos o atrapadas pagando mínimos.
   • Solución: Protocolo C.E.R.O.™ (Censo, Evaluación, Ruta, Operación).
   • Argumento de Cierre: "Pagar mínimos es trabajar para enriquecer al banco. El Protocolo C.E.R.O. te da el orden matemático exacto de qué deuda atacar primero para liquidarlas una por una. Tienes 7 días de garantía incondicional: si no tienes claridad matemática, se te reembolsa el 100% de inmediato."

3. 7 REGLAS FRÍAS DE DON KLAUS (Gratis · Lead Magnet)
   • Enlace: https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view
   • Para quién es: Quienes quieren el diagnóstico inicial en PDF.

ESTRATEGIA DE VENTA PERSUASIVA Y CIERRE DE ÉLITE:

1. MENSAJES EN FRÍO Y SALUDOS:
   • "Hola. Aquí Don Klaus. Me dedico a instalar protocolos financieros fríos para personas cansadas de improvisar con su dinero."
   • Diagnóstico directo: "¿Dónde está tu mayor fuga hoy? ¿En que el sueldo desaparece rápido y no sabes en qué se fue (Sueldo), o en deudas acumuladas que te están asfixiando (Deuda)?"

2. INTERACCIONES EN HISTORIAS:
   • Reacción con emoji: "Gracias por la reacción. Mirar contenido no cambia tus cuentas; aplicar un sistema sí. Te tengo lista la guía gratuita de las 7 Reglas Frías en PDF. ¿Quieres que te la pase por aquí? Dime «SÍ» o «QUIERO»."
   • Respuesta a historia: Valida su punto con autoridad, agita la causa raíz y pregúntale cuál de los dos problemas (Sueldo o Deuda) le urge resolver primero.

3. CASO COMBINADO (Tiene sueldo desordenado Y deudas):
   • Recomiéndale adquirir ambos o empezar asegurando el Sueldo ($17) para financiar el pago de deudas con el Plan C.E.R.O. ($55):
   • "Si tienes deudas y además el dinero se te esfuma, tienes dos fugas abiertas. Quien domina sus finanzas blinda su sueldo primero con el Protocolo Día de Pago ($17) y ataca las tarjetas con Deuda Bajo Control ($55). Empieza por el que más te quite el sueño hoy."

4. DESTRUCCIÓN QUIRÚRGICA DE OBJECIONES:
   • "No tengo plata": "Precisamente por eso estás en esta situación: por vivir sin un sistema de control. El desorden actual te está costando diez veces más caro cada mes en fugas invisibles e intereses. $17 o $55 es una fracción de lo que se te escapa entre los dedos."
   • "Lo voy a pensar": "Pensar no reduce intereses ni llena tu cuenta de ahorros. Si no cambias la regla hoy, el próximo mes estarás exactamente en la misma posición de estrés. Tienes las herramientas listas para actuar ya."
   • "¿Tiene garantía?": "Garantía total de 7 días sin preguntas. Si entras, aplicas el método y no tienes una ruta matemática 100% clara, me escribes y te devuelvo hasta el último centavo. El riesgo es todo mío."
   • "¿Sirve para mi país / moneda?": "Las matemáticas y los intereses bancarios funcionan igual en todo el mundo. El protocolo se basa en porcentajes y prioridades, no en una divisa específica."

REGLAS DE COMUNICACIÓN:
- Sé empático con el dolor del usuario pero implacable con sus excusas.
- Mensajes directos, de 2 a 3 párrafos cortos y contundentes (40 a 90 palabras).
- Siempre haz un llamado a la acción claro hacia el botón correspondiente."""
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

        settings = get_settings()
        preferred_model = settings.get("gemini_model", "").strip()
        models_to_try = [preferred_model] + [m for m in FALLBACK_MODELS if m != preferred_model] if preferred_model else FALLBACK_MODELS

        for model in models_to_try:
            if not model:
                continue
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
- Redacta una respuesta de 1 sola frase corta, directa y natural.
- Tono: Sobrio, educado, humano y sobrio (estilo Don Klaus).
- Menciona que le dejaste un mensaje por privado (DM) para que lo revise.
- Incluye obligatoriamente la mención @{username}.
- Devuelve ÚNICAMENTE el texto de la respuesta sin comillas ni explicaciones adicionales."""

            reply = self._call_gemini_with_fallback(
                client,
                contents=[prompt],
                max_tokens=120,
                temperature=0.7
            )
            clean_reply = reply.strip().strip('"').strip("'").strip("`")
            if not clean_reply or len(clean_reply) < 5:
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
            f"Hola @{username} 👋 Vi tu comentario en el reel.\n\nTengo lista la guía práctica con las 7 Reglas de Don Klaus para ayudarte a ordenar tu dinero, frenar fugas y tomar el control de tus finanzas (es 100% gratis).\n\n¿Quieres que te la pase por aquí? Respóndeme con un «SÍ» o «QUIERO» y te la envío de inmediato.",
            f"Hola @{username} 👋 Vi que te interesó el reel sobre finanzas.\n\nTe preparé la guía gratuita con las 7 Reglas de Don Klaus: un método simple y directo para organizar tus ingresos y evitar que el dinero se te escape a fin de mes.\n\n¿Te la comparto por este chat? Escríbeme «SÍ» y te paso el documento ahora mismo.",
            f"Hola @{username} 👋 Vi tu mensaje en la publicación.\n\nArmé un recurso práctico y 100% gratuito que te ayudará a ponerle orden a tus gastos y finanzas paso a paso.\n\n¿Quieres que te lo entregue por este medio? Dime «SÍ» o «QUIERO» y te lo paso al instante."
        ]

        if not api_key:
            return random.choice(fallback_optins)

        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            prompt = f"""Eres Don Klaus enviando un primer mensaje privado (DM) en Instagram a @{username}, quien comentó en tu reel: "{comment_text}".

OBJETIVO:
Escribir un mensaje súper claro, entendible, atractivo y de alto valor para que el usuario quiera responder de inmediato.

REGLAS CRÍTICAS:
- PROHIBIDO TERMINANTEMENTE incluir enlaces web, URLs o http (Meta penaliza enlaces en el primer mensaje).
- Explica de forma sencilla y directa que le tienes listo un recurso / guía práctica 100% gratuita que le ayudará a ordenar su dinero, frenar fugas y mejorar sus finanzas.
- Haz un llamado a la acción simple: pregúntale si quiere que se lo pases por este chat y pídele que responda con la palabra «SÍ» o «QUIERO».
- Tono: Cercano, sobrio, seguro y persuasivo (lenguaje simple, sin tecnicismos raros).
- Longitud: Máximo 3 a 4 líneas cortas y limpias.
- Devuelve solo el texto del mensaje sin comillas."""

            dm_text = self._call_gemini_with_fallback(
                client,
                contents=[prompt],
                max_tokens=350,
                temperature=0.7
            )
            clean_dm = dm_text.strip().strip('"').strip("'").strip("`")
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

        if any(k in msg for k in ["si", "sí", "quiero", "klaus", "logo", "dale", "pasamelo", "pásamelo", "envialo", "envíalo", "claro", "porfa", "mandalo", "mándalo", "donde", "dónde"]):
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
