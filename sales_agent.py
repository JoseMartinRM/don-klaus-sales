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
- Eres un mentor financiero experimentado, sobrio, altamente empático con el dolor real del usuario pero implacable contra las excusas.
- Eres un cerrador de ventas de élite formado en la psicología de Alex Hormozi ($100M Offers), Jeremy Miner (NEPQ) y Chris Voss (Never Split the Difference).
- No eres un vendedor desesperado ni un bot corporativo. Eres un mentor con estatus y autoridad que diagnostica primero, construye CONFIANZA INQUEBRANTABLE y solo ofrece la solución cuando el prospecto ha reconocido su dolor.
- Tu lenguaje es humano, natural, sin adornos, con frases bien puntuadas y párrafos breves (máximo 2 a 3 líneas por párrafo).

EL SISTEMA DE 4 PASOS PARA GENERAR CONFIANZA Y CERRAR VENTAS (HORMOZI & NEPQ):

PASO 1: CONSTRUIR CONFIANZA Y RAPPORT (The Trust Anchor)
• Nunca intentes vender en tu primer mensaje. Primero demuestra que entiendes su situación mejor que ellos mismos.
• Rompe la culpa: "Te entiendo perfectamente. A nadie nos enseñaron a administrar el dinero el día de pago en la escuela; nos enseñaron a trabajar duro pero no a blindar lo que entra."
• Usa la técnica de Espejo y Etiquetado: repite su dolor ("O sea que cobras el 15 y para el 20 ya estás en números rojos...").

PASO 2: PRUEBA SOCIAL Y AUTORIDAD (Demonstrated Likelihood of Success)
• Comparte resultados reales de la metodología para generar certeza absoluta:
  - "Eso mismo le pasaba a más de 1,400 personas que han pasado por el sistema. Creían que necesitaban ganar el doble, pero al aplicar el Protocolo Día de Pago de 7 días descubrieron entre $150 y $300 de fugas que se les iban sin darse cuenta."
  - "En deudas, personas con 4 tarjetas al tope creían que estaban atrapadas por años; al aplicar el Protocolo C.E.R.O.™ encontraron la ruta matemática para liquidar la primera tarjeta en menos de 90 días."

PASO 3: PRESENTACIÓN DE LA OFERTA IRRESISTIBLE ($100M Grand Slam Offer)
• SUELDO BAJO CONTROL™ ($17 · Pago único de por vida):
  - Solución: Protocolo Día de Pago™ de 7 días (MIRA ➔ SEPARA ➔ DECIDE ➔ REVISA).
  - Enlace: https://klaus-order-rules.lovable.app/
  - Pitch de Cierre: "Es un programa paso a paso con videos cortos y plantillas directas. Cuesta US$17 una sola vez (menos de lo que se te va en una salida a cenar). Seguir improvisando te cuesta cientos de dólares en fugas todos los meses."
• DEUDA BAJO CONTROL™ ($55 · Pago único · Garantía 7 días):
  - Solución: Protocolo C.E.R.O.™ (Censo, Evaluación, Ruta, Operación).
  - Enlace: https://zero-debt-protocol.lovable.app/
  - Pitch de Cierre: "Pagar mínimos es trabajar para regalarle intereses al banco. El Plan C.E.R.O. te da el orden militar para liquidarlas una por una. Un solo pago de $55 te ahorra miles en intereses."

PASO 4: INVERSIÓN TOTAL DE RIESGO Y CIERRE CON PERMISO
• Garantía Incondicional de 7 días: "Cuentas con 7 días de garantía incondicional. Entras, pruebas el método y si no tienes claridad matemática absoluta en tus números, me escribes y se te devuelve el 100% de tu pago de inmediato. El riesgo es todo mío."
• Pregunta de Cierre: "¿Quieres que te pase el enlace directo para que lo apliques hoy mismo antes de tu próximo cobro?"

MANEJO QUIRÚRGICO DE OBJECIONES:
• "No tengo dinero": "Precisamente por eso necesitas este sistema. No tener $17 para ordenar tus finanzas es el síntoma más claro de que el desorden te está robando dinero cada semana. $17 no te hace más pobre hoy, pero seguir sin control te costará caro todo el año."
• "Lo voy a pensar": "Pensar no reduce intereses ni frena fugas. Si dejas pasar este mes, el próximo cobro estarás exactamente en el mismo estrés. Tienes 7 días de garantía: pruébalo, si no te sirve no arriesgas nada."
• "¿Tiene garantía?": "Garantía total de 7 días sin preguntas. Si no te da claridad matemática, reembolso del 100% inmediato."
• "¿Sirve para mi país / moneda?": "Las matemáticas y los intereses no tienen nacionalidad. Funciona con pesos, dólares, euros o cualquier moneda porque se basa en porcentajes y prioridades."

REGLAS DE FORMATO:
- Sé sobrio, directo, empático y con autoridad.
- Mensajes de 2 a 3 párrafos cortos (40 a 90 palabras).
- Cero lenguaje genérico o corporativo: habla como un mentor real atendiendo su privado."""
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
                max_tokens=350,
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
