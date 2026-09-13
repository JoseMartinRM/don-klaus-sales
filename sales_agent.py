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
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash"
]

class SalesAgent:
    def __init__(self):
        pass

    def build_system_prompt(self) -> str:
        system_prompt = """Eres DON KLAUS respondiendo personalmente en los Mensajes Directos (DM) de tu Instagram (@sistemadonklaus) y Facebook.

TU IDENTIDAD Y POSTURA (ALEX HORMOZI & NEPQ CONSULTATIVE CLOSING):
- Eres un mentor financiero sobrio, empático con el dolor real pero implacable contra las excusas.
- Eres un cerrador de ventas de élite: NO empujas ventas forzadas, NO suenas desesperado ni envías cartas de venta largas.
- Hablas como un mentor real escribiendo mensajes cortos desde su teléfono (máximo 2 a 3 párrafos muy breves, entre 35 y 65 palabras en total).
- Tu objetivo es que el prospecto se sienta 100% comprendido, reconozca la fuga de dinero y pida la solución.

ESTRUCTURA DE CONVERSIÓN EN 3 PASOS (HORMOZI & VOSS):
1. EMPATÍA REAL & ESPEJO (Romper la culpa):
   • "Te entiendo perfectamente. A nadie nos enseñaron a blindar el dinero el día de pago; nos enseñaron a trabajar duro pero no a administrar lo que entra."
2. CERTEZA MATEMÁTICA ($100M Value Equation):
   • "Eso le pasaba a más de 1,400 personas en la comunidad. Al aplicar el protocolo descubrieron entre $150 y $300 en fugas invisibles que se les escapaban sin darse cuenta."
3. CIERRE CON PERMISO O ACCESO DIRECTO:
   • Si tiene dudas: "¿Quieres que te pase el protocolo de 7 días que usamos para frenar eso antes de tu próximo cobro?"
   • Si pide el link o quiere comprar: Dale el link directo con la garantía incondicional de 7 días (riesgo 100% nuestro).

CATÁLOGO EXACTO DE SOLUCIONES:
• 7 REGLAS FRÍAS DE DON KLAUS (PDF de Frases y Reglas de Control Financiero · 100% GRATIS):
  - Solución: Guía práctica en PDF para identificar las 7 fugas de dinero más comunes y ordenar tus números.
  - Enlace: https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view
  - Regla: Si el usuario dice "sí", "quiero", "pásame el pdf", "las frases", "el libro", "la guía", o confirma el regalo, entrégale el enlace del PDF de inmediato con total amabilidad y pregúntale dónde siente que se le escapa más dinero hoy (en su Sueldo o en sus Deudas).

• SUELDO BAJO CONTROL™ (US$17 · Pago único · Garantía 7 días):
  - Solución: Protocolo Día de Pago™ de 7 días (MIRA ➔ SEPARA ➔ DECIDE ➔ REVISA). Videos cortos de 5 min y plantillas listas (cero Excels complicados).
  - Enlace: https://klaus-order-rules.lovable.app/

• DEUDA BAJO CONTROL™ (US$55 · Pago único · Garantía 7 días):
  - Solución: Protocolo C.E.R.O.™ para liquidar deudas una por una sin regalarle intereses a los bancos.
  - Enlace: https://zero-debt-protocol.lovable.app/

MANEJO QUIRÚRGICO DE OBJECIONES (CORTO Y CONTUNDENTE):
• "No tengo dinero": "Precisamente por eso necesitas este sistema. No tener $17 para blindar tus números es la prueba de que el desorden te está robando dinero cada semana. Tienes 7 días de garantía total: pruébalo sin arriesgar nada."
• "Lo voy a pensar": "Pensar no frena fugas ni reduce intereses bancarios. Si dejas pasar este mes, el próximo cobro estarás en el mismo estrés. Tienes 7 días de garantía incondicional."
• "¿Tiene garantía / es seguro?": "100% seguro y con 7 días de garantía incondicional sin preguntas. Si no te da claridad matemática absoluta, se te devuelve el 100% de inmediato."
• "¿Sirve para mi país / moneda?": "Las matemáticas y los intereses son universales. Funciona con pesos, dólares o euros porque se basa en porcentajes y prioridades numéricas."

REGLAS DE ORO DE REDACCIÓN:
- Mensajes CORTOS, directos y humanos (35 a 65 palabras).
- Cero muros de texto abrumadores.
- No uses lenguaje robótico ni corporativo."""
        return system_prompt

    def _call_gemini_with_fallback(self, client, contents, system_instruction=None, max_tokens=2048, temperature=0.7) -> str:
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
            f"Te acabo de escribir al DM, @{username}. 📩",
            f"Listo @{username}. Te mandé el acceso a tu privado. ⚔️",
            f"Revisa tus mensajes directos, @{username}. Ahí tienes la información. 📩",
            f"Te dejé el acceso en tu bandeja privada, @{username}. 📜",
            f"Listo @{username}, revisa tu DM para que apliques el sistema. ⚔️",
            f"Te escribí al privado, @{username}. Revísalo cuando puedas. 📩"
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
- Redacta una respuesta de 1 sola frase corta, directa, variada y natural (estilo humano, nunca bot).
- Tono: Sobrio, educado, seguro (estilo Don Klaus).
- Menciona que le dejaste un mensaje por privado (DM) para que lo revise.
- Incluye obligatoriamente la mención @{username}.
- Devuelve ÚNICAMENTE el texto de la respuesta sin comillas ni explicaciones adicionales."""

            reply = self._call_gemini_with_fallback(
                client,
                contents=[prompt],
                max_tokens=120,
                temperature=0.8
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
            f"Hola @{username} 👋 Vi tu comentario en el reel.\n\nTengo lista la guía práctica con las 7 Reglas de Don Klaus para ayudarte a ordenar tu dinero, frenar fugas y tomar el control de tus finanzas (es 100% gratis).\n\n¿Quieres que te la pase por aquí? Respóndeme con un «SÍ» o «QUIERO» (o «LOGO») y te entrego la tarjeta de acceso de inmediato.",
            f"Hola @{username} 👋 Vi que te interesó la publicación sobre finanzas.\n\nTe preparé la guía gratuita con las 7 Reglas de Don Klaus: un método directo para organizar tus ingresos y evitar que el dinero se te escape a fin de mes.\n\n¿Te la comparto por este chat? Escríbeme «SÍ» o «QUIERO» y te paso el documento ahora mismo.",
            f"Hola @{username} 👋 Vi tu mensaje en el video.\n\nArmé un recurso práctico y 100% gratuito que te ayudará a ponerle orden a tus gastos y finanzas paso a paso.\n\n¿Quieres que te lo entregue por este medio? Dime «SÍ», «QUIERO» o «LOGO» y te lo paso al instante.",
            f"Hola @{username} 👋 Gracias por comentar en el reel.\n\nTe tengo listo el PDF de las 7 Reglas Frías de Don Klaus para dejar de improvisar con tus números (es totalmente gratis).\n\n¿Te lo envío por este chat? Respóndeme «QUIERO» y te entrego tu tarjeta de descarga ya mismo.",
            f"Hola @{username} 👋 Vi tu interés en ordenar tus números.\n\nTengo preparado el PDF gratuito con las 7 Reglas de Don Klaus para frenar fugas de dinero y tener control total.\n\n¿Quieres revisarlo? Escríbeme «SÍ» o «QUIERO» y te paso el acceso inmediato."
        ]

        if not api_key:
            return random.choice(fallback_optins)

        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            prompt = f"""Eres Don Klaus enviando un primer mensaje privado (DM) en Instagram a @{username}, quien comentó en tu reel: "{comment_text}".

OBJETIVO:
Escribir un mensaje ultra-humano, personalizado al comentario que dejó, empático, atractivo y de alto valor para que el usuario responda de inmediato.

REGLAS CRÍTICAS:
- PROHIBIDO TERMINANTEMENTE incluir enlaces web, URLs o http (Meta penaliza enlaces en el primer mensaje).
- Explica de forma sencilla y directa que le tienes listo un recurso / guía práctica 100% gratuita (7 Reglas Frías en PDF) que le ayudará a ordenar su dinero, frenar fugas y mejorar sus finanzas.
- Haz un llamado a la acción simple: pregúntale si quiere que se lo pases por este chat y pídele que responda con la palabra «SÍ», «QUIERO» o «LOGO».
- Tono: Cercano, sobrio, seguro y persuasivo (lenguaje simple, humano y fresco, variando el estilo).
- Longitud: Máximo 3 a 4 líneas cortas y limpias.
- Devuelve solo el texto del mensaje sin comillas."""

            dm_text = self._call_gemini_with_fallback(
                client,
                contents=[prompt],
                max_tokens=1500,
                temperature=0.8
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

            history = get_conversation_history(user_id, limit=10)
            contents = []

            for msg in history:
                text_content = (msg.get("content") or "").strip()
                if not text_content:
                    continue
                role = "user" if msg.get("role") == "user" else "model"
                if contents and contents[-1].role == role:
                    existing_text = contents[-1].parts[0].text
                    contents[-1] = types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=f"{existing_text}\n{text_content}")]
                    )
                else:
                    contents.append(types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=text_content)]
                    ))

            while contents and contents[0].role != "user":
                contents.pop(0)

            if not contents:
                contents = [types.Content(role="user", parts=[types.Part.from_text(text=user_message)])]

            reply_text = self._call_gemini_with_fallback(
                client,
                contents=contents,
                system_instruction=system_instruction,
                max_tokens=2048,
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

        if any(k in msg for k in ["si", "sí", "quiero", "klaus", "logo", "dale", "pasamelo", "pásamelo", "envialo", "envíalo", "claro", "porfa", "mandalo", "mándalo", "donde", "dónde", "frases", "frase", "pdf", "guia", "guía", "libro", "regalo", "gratis", "reglas", "regla"]):
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
