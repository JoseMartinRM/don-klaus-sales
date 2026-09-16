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
from typing import List, Dict, Any, Optional, Tuple
from database import (
    get_settings, list_products, get_conversation_history,
    save_conversation_message, add_activity_log, flag_human_escalation
)

logger = logging.getLogger("sales_agent")

FALLBACK_MODELS = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-pro-latest"
]

class SalesAgent:
    def __init__(self):
        pass

    def build_system_prompt(self, segment: str = "sin definir", stage: str = "comento") -> str:
        system_prompt = f"""Eres DON KLAUS respondiendo personalmente en los Mensajes Directos (DM) de tu Instagram (@sistemadonklaus) y Facebook.

TU IDENTIDAD Y POSTURA (ALEX HORMOZI & NEPQ CONSULTATIVE CLOSER):
- Eres un mentor financiero sobrio, frío y autoritario, pero con profunda empatía hacia el dolor financiero del usuario.
- TRATO EXCLUSIVO: Tratas SIEMPRE de "USTED" (NUNCA de "tú"). Eres formal, respetuoso, firme y directo.
- NO eres un bot entusiasta, no usas signos de exclamación excesivos ni lenguaje infantil. Eres un profesional que escribe desde su móvil.
- Mensajes CORTOS: Entre 35 y 65 palabras en total (máximo 2 párrafos breves). Una sola idea contundente por mensaje.
- Cada mensaje DEBE terminar con una pregunta cerrada de avance o una llamada a la acción clara.
- CERO promesas falsas o urgencia ficticia. La urgencia es el costo de inacción del usuario (seguir perdiendo dinero cada mes).

SEGMENTO ACTUAL DEL LEAD: {segment.upper()}
ETAPA ACTUAL DEL EMBUDO: {stage.upper()}

CATÁLOGO EXACTO DE SOLUCIONES:
1. 7 REGLAS FRÍAS DE DON KLAUS (PDF 100% GRATIS):
   - Enlace: https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view
   - Regla: Si el usuario confirma que quiere el regalo, entrégueselo y pregúntele cuál de las 7 reglas siente que está rompiendo hoy (número del 1 al 7).

2. SUELDO BAJO CONTROL™ (US$17 · Pago único de por vida · Garantía 7 días):
   - Solución: Protocolo Día de Pago™ de 7 días (MIRA ➔ SEPARA ➔ DECIDE ➔ REVISA). Videos cortos de 5 min y plantillas listas.
   - Enlace: https://klaus-order-rules.lovable.app/

3. DEUDA BAJO CONTROL™ (US$55 · Pago único de por vida · Garantía 7 días):
   - Solución: Protocolo C.E.R.O.™ para liquidar deudas paso a paso sin regalarle intereses a los bancos.
   - Enlace: https://zero-debt-protocol.lovable.app/

MANEJO DE OBJECIONES NEPQ (ALEX HORMOZI):
• "No tengo dinero / no me alcanza": "Si en este momento no dispone de $17 para blindar sus finanzas, el desorden le está costando diez veces más cada mes en fugas silenciosas. Dispone de 7 días de garantía incondicional: pruébelo sin arriesgar nada. ¿Blindamos su próximo cobro?"
• "No tengo tiempo": "Está diseñado exactamente para personas ocupadas: son videos directos de 5 minutos al día y plantillas listas para usar. Cero teoría innecesaria ni hojas de Excel complejas."
• "¿Tiene garantía / es seguro?": "Dispone de 7 días de garantía incondicional sin preguntas. Si en una semana no tiene claridad matemática absoluta sobre sus números, se le devuelve el 100% de inmediato. El riesgo es totalmente mío."
• "Lo voy a pensar": "Pensar no frena las fugas de dinero ni reduce los intereses bancarios. Si deja pasar este mes, el próximo cobro estará en la misma incertidumbre. ¿Prefiere tomar el control hoy o esperar otro mes?"
• "¿Sirve para mi país / moneda?": "Las matemáticas y los intereses bancarios son universales. El protocolo funciona en pesos, dólares o euros porque se basa en porcentajes y prioridades numéricas, sin importar su país de residencia."
• "Ya probé otros cursos y no me sirvieron": "Los cursos tradicionales saturan con teoría que nadie aplica. Esto es un protocolo de ejecución diaria de 7 días enfocado exclusivamente en ordenar sus números de inmediato."

CONSEJO POR REGLA (CUANDO EL USUARIO MENCIONA DEL 1 AL 7):
• Regla 1 (Separar antes de gastar): "Romper la Regla #1 es la causa de quedarse en cero a mitad de mes. Si no separa su dinero el día de cobro, el gasto se expande hasta devorarlo. En Sueldo Bajo Control™ ($17) aplicamos ese freno de mano."
• Regla 2 (No pagar mínimos en tarjetas): "Pagar mínimos es el negocio del banco y su mayor sangría. Para congelar los intereses necesita el Protocolo C.E.R.O.™ de Deuda Bajo Control™ ($55). ¿Empezamos a liquidarlas hoy?"
• Regla 3 (Freno de mano el día de cobro): "La Regla #3 es la más violada: gastar por impulso en las primeras 48 horas. Sueldo Bajo Control™ ($17) le da la plantilla exacta para frenar ese impulso en 5 minutos."
• Regla 4 (Fondo de emergencia): "Sin un fondo intocable, cualquier imprevisto se vuelve deuda con intereses. En Sueldo Bajo Control™ construimos ese colchón desde el primer mes."
• Regla 5 (Auditoría semanal de números): "No mirar sus números no elimina el problema, lo empeora. 5 minutos a la semana le ahorran hasta $300 en fugas silenciosas. Eso es lo que aplicamos en Sueldo Bajo Control™ ($17)."
• Regla 6 (Estrategia de amortización acelerada): "Abonar a todas las deudas por igual diluye su dinero. Con Deuda Bajo Control™ ($55) concentra toda su fuerza en la deuda matemáticamente correcta."
• Regla 7 (Invertir solo lo que sobre tras el protocolo): "Querer invertir sin tener el sueldo ordenado es poner el techo antes de los cimientos. Primero blindamos su cobro con Sueldo Bajo Control™ ($17)."

ESCALACIÓN HUMANA:
Si el usuario solicita expresamente hablar con una persona, asesor, llamada o tiene un reclamo técnico/legal complejo, responde educadamente que un asesor humano lo contactará e incluye la etiqueta: [ESCALATE_HUMAN: motivo]."""
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

    def detect_human_escalation(self, message: str) -> Optional[str]:
        """
        Detecta si el mensaje del usuario requiere escalación a un operador humano.
        """
        msg = message.lower()
        triggers = [
            ("humano", "Usuario solicita atención humana"),
            ("persona real", "Usuario solicita persona real"),
            ("asesor", "Usuario solicita asesor"),
            ("llamada", "Usuario pide llamada"),
            ("telefono", "Usuario pide teléfono"),
            ("número", "Usuario pide número telefónico"),
            ("hablar con alguien", "Usuario desea hablar con alguien"),
            ("estafa", "Alerta de queja / duda de seguridad"),
            ("fraude", "Alerta de fraude"),
            ("abogado", "Asunto legal"),
            ("devolucion", "Solicitud de reembolso"),
            ("reembolso", "Solicitud de reembolso")
        ]
        for trig, reason in triggers:
            if trig in msg:
                return reason
        return None

    def detect_objection(self, message: str) -> Optional[str]:
        """
        Detecta la categoría de objeción presente en el mensaje del lead.
        """
        msg = message.lower()
        if any(w in msg for w in ["no tengo dinero", "no me alcanza", "caro", "costoso", "sin plata", "no tengo fondos"]):
            return "precio"
        if any(w in msg for w in ["no tengo tiempo", "ocupado", "sin tiempo", "trabajo mucho", "no me da el dia"]):
            return "tiempo"
        if any(w in msg for w in ["seguro", "garantia", "garantía", "estafa", "confianza", "confiable", "cierto"]):
            return "garantia_confianza"
        if any(w in msg for w in ["voy a pensar", "pensarlo", "lo pienso", "luego veo", "despues", "más adelante"]):
            return "lo_voy_a_pensar"
        if any(w in msg for w in ["mi pais", "mi país", "moneda", "pesos", "soles", "dolares", "mexico", "colombia", "peru", "chile", "argentina", "espana"]):
            return "pais_moneda"
        if any(w in msg for w in ["otros cursos", "ya probe", "no me sirvio", "vendehumo", "otra academia"]):
            return "cursos_previos"
        return None

    async def generate_comment_reply(self, username: str, comment_text: str) -> str:
        """
        Genera una respuesta pública al comentario en Reel con 5 variantes rotativas formales.
        """
        fallback_options = [
            f"Listo @{username}, le escribí por mensaje privado para que lo revise con calma. ⚔️",
            f"Le dejé un mensaje directo, @{username}. Mírelo cuando tenga un minuto. 📩",
            f"Ya le envié el mensaje al privado, @{username}. 📜",
            f"Revise su bandeja de mensajes, @{username}. Le dejé lo prometido. ⚔️",
            f"Le acabo de escribir al DM, @{username}. 📩"
        ]
        return random.choice(fallback_options)

    def generate_optin_dm_variant(self, username: str, variant: str = "A") -> Tuple[str, List[Dict[str, str]]]:
        """
        Genera el primer mensaje privado (DM 1) con prueba A/B 50/50 y botones rápidos de diagnóstico.
        """
        if variant == "A":
            text = (
                f"Hola @{username} 👋 Vi su comentario en la publicación.\n\n"
                "Antes de entregarle las 7 Reglas Frías en PDF, necesito conocer su situación actual para darle la guía precisa:\n\n"
                "¿Su mayor problema hoy es ordenar su Sueldo o liquidar Deudas? 👇"
            )
            quick_replies = [
                {"content_type": "text", "title": "💰 Ordenar Sueldo", "payload": "SUELDO"},
                {"content_type": "text", "title": "⚔️ Liquidar Deudas", "payload": "DEUDA"}
            ]
            return text, quick_replies
        else:
            text = (
                f"Hola @{username} 👋 Tengo listo su PDF de las 7 Reglas Frías.\n\n"
                "Para entregarle el material exacto para sus finanzas:\n\n"
                "¿En qué área siente hoy la mayor fuga de dinero o estrés? 👇"
            )
            quick_replies = [
                {"content_type": "text", "title": "💰 En mi Sueldo", "payload": "SUELDO"},
                {"content_type": "text", "title": "⚔️ En mis Deudas", "payload": "DEUDA"}
            ]
            return text, quick_replies

    async def generate_response(
        self,
        user_id: str,
        user_message: str,
        username: Optional[str] = None,
        segment: str = "sin definir",
        stage: str = "comento"
    ) -> Tuple[str, Optional[str]]:
        """
        Genera la respuesta consultiva de Don Klaus.
        Retorna (reply_text, escalation_reason_if_any).
        """
        settings = get_settings()
        api_key = settings.get("gemini_api_key", "").strip()

        save_conversation_message(user_id, "user", user_message)

        # 1. Chequeo de escalación humana
        escalation_reason = self.detect_human_escalation(user_message)
        if escalation_reason:
            flag_human_escalation(user_id, escalation_reason)
            add_activity_log("HUMAN_ESCALATION", f"Lead {user_id} (@{username}) requiere atención humana: {escalation_reason}", f"User: @{username or user_id}")
            reply = "Comprendo su situación. He notificado a mi equipo para que un asesor revise su caso directamente en este chat a la brevedad. Si tiene una duda puntual sobre los protocolos, con gusto le sigo orientando."
            save_conversation_message(user_id, "assistant", reply)
            return reply, escalation_reason

        # 2. Chequeo de regla específica (1 al 7)
        rule_reply = self._check_rule_advice(user_message)
        if rule_reply:
            save_conversation_message(user_id, "assistant", rule_reply)
            add_activity_log("AI_REPLY_SENT", f"Don Klaus dio consejo de regla a {user_id}: '{rule_reply[:60]}...'", f"User: @{username or user_id}")
            return rule_reply, None

        if not api_key:
            fallback_reply = self._generate_rule_based_fallback(user_message, segment)
            save_conversation_message(user_id, "assistant", fallback_reply)
            add_activity_log("AI_REPLY_SENT", f"[Don Klaus Rules] Respondido a {user_id}: '{fallback_reply[:60]}...'", f"User: @{username or user_id}")
            return fallback_reply, None

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            system_instruction = self.build_system_prompt(segment=segment, stage=stage)

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
                max_tokens=1500,
                temperature=0.65
            )

            # Verificar si la IA insertó etiqueta de escalación
            if "[ESCALATE_HUMAN:" in reply_text:
                match = re.search(r'\[ESCALATE_HUMAN:\s*([^\]]+)\]', reply_text)
                esc_reason = match.group(1) if match else "Solicitud detectada por IA"
                flag_human_escalation(user_id, esc_reason)
                reply_text = re.sub(r'\[ESCALATE_HUMAN:[^\]]+\]', '', reply_text).strip()

            save_conversation_message(user_id, "assistant", reply_text)
            add_activity_log("AI_REPLY_SENT", f"Don Klaus IA respondió a {user_id}: '{reply_text[:60]}...'", f"User: @{username or user_id}")
            return reply_text, None

        except Exception as e:
            logger.exception(f"Error en Gemini Sales Agent: {e}")
            fallback_reply = self._generate_rule_based_fallback(user_message, segment)
            save_conversation_message(user_id, "assistant", fallback_reply)
            return fallback_reply, None

    def _check_rule_advice(self, message: str) -> Optional[str]:
        msg = message.lower().strip()
        words = set(re.findall(r'\w+', msg))

        if msg in ["1", "regla 1", "la 1", "primera"] or ("regla" in msg and "1" in words):
            return (
                "Romper la Regla #1 (Separar antes de gastar) es la causa exacta de quedarse en cero a mitad de mes. "
                "Si no asigna una función a su dinero el mismo día de cobro, el gasto se expande hasta devorarlo todo.\n\n"
                "En **Sueldo Bajo Control™** ($17) le enseño a aplicar el freno de mano el día de pago con videos de 5 minutos.\n\n"
                "👉 https://klaus-order-rules.lovable.app/\n\n"
                "¿Desea blindar su próximo cobro desde hoy?"
            )

        if msg in ["2", "regla 2", "la 2", "segunda"] or ("regla" in msg and "2" in words):
            return (
                "La Regla #2 (No pagar mínimos en tarjetas) es el negocio más lucrativo del banco y su mayor sangría financiera. "
                "Pagar mínimos solo engorda los intereses.\n\n"
                "Para congelar esa fuga necesita el Protocolo C.E.R.O.™ de **Deuda Bajo Control™** ($55 con 7 días de garantía incondicional).\n\n"
                "👉 https://zero-debt-protocol.lovable.app/\n\n"
                "¿Empezamos a liquidarlas hoy?"
            )

        if msg in ["3", "regla 3", "la 3", "tercera"] or ("regla" in msg and "3" in words):
            return (
                "La Regla #3 (Freno de mano el día de cobro) es donde el 80% tiene su fuga más grave: compras por impulso en las primeras 48 horas.\n\n"
                "**Sueldo Bajo Control™** ($17 pago único) le entrega la plantilla exacta para bloquear ese impulso en 5 minutos.\n\n"
                "👉 https://klaus-order-rules.lovable.app/\n\n"
                "¿Revisamos el protocolo?"
            )

        if msg in ["4", "regla 4", "la 4", "cuarta"] or ("regla" in msg and "4" in words):
            return (
                "Sin la Regla #4 (Fondo de emergencia intocable), cualquier imprevisto se convierte en deuda con tarjeta a intereses abusivos.\n\n"
                "En **Sueldo Bajo Control™** ($17) construimos ese colchón desde el primer mes sin sacrificios extremos.\n\n"
                "👉 https://klaus-order-rules.lovable.app/\n\n"
                "¿Desea blindar sus números?"
            )

        if msg in ["5", "regla 5", "la 5", "quinta"] or ("regla" in msg and "5" in words):
            return (
                "La Regla #5 (Auditoría semanal de números): ignorar sus números por miedo no elimina el desorden, lo multiplica.\n\n"
                "5 minutos a la semana le ahorran entre $150 y $300 en fugas silenciosas. Eso es lo que aplicamos en **Sueldo Bajo Control™** ($17).\n\n"
                "👉 https://klaus-order-rules.lovable.app/\n\n"
                "¿Tomamos el control hoy?"
            )

        if msg in ["6", "regla 6", "la 6", "sexta"] or ("regla" in msg and "6" in words):
            return (
                "La Regla #6 (Estrategia de amortización acelerada): abonar a todas las deudas por igual diluye su dinero.\n\n"
                "Con **Deuda Bajo Control™** ($55) concentra toda su fuerza en la deuda matemáticamente correcta hasta liquidarla por completo.\n\n"
                "👉 https://zero-debt-protocol.lovable.app/\n\n"
                "¿Empezamos el plan hoy?"
            )

        if msg in ["7", "regla 7", "la 7", "septima", "séptima"] or ("regla" in msg and "7" in words):
            return (
                "La Regla #7 (Invertir solo lo que sobre tras el protocolo): querer invertir sin tener el sueldo ordenado es poner el techo antes de los cimientos.\n\n"
                "Primero blindamos su cobro con **Sueldo Bajo Control™** ($17) y luego multiplicamos su excedente.\n\n"
                "👉 https://klaus-order-rules.lovable.app/\n\n"
                "¿Comenzamos?"
            )

        return None

    def _generate_rule_based_fallback(self, message: str, segment: str = "sin definir") -> str:
        msg = message.lower().strip()

        # Objeción de precio
        if any(k in msg for k in ["caro", "dinero", "plata", "no me alcanza", "no tengo"]):
            return (
                "Si en este momento no dispone de $17 para blindar sus finanzas, el desorden le está costando diez veces más cada mes en fugas silenciosas.\n\n"
                "Dispone de 7 días de garantía incondicional: pruébelo sin arriesgar nada. Si no le da orden absoluto, se le devuelve el 100%.\n\n"
                "👉 https://klaus-order-rules.lovable.app/"
            )

        # Intención de compra directa o enlace
        if any(k in msg for k in ["comprar", "precio", "link", "enlace", "adquirir", "cuanto cuesta", "cuánto cuesta"]):
            if segment == "DEUDA":
                return (
                    "El acceso de por vida a **Deuda Bajo Control™** es de US$55 (pago único) con 7 días de garantía incondicional.\n\n"
                    "👉 https://zero-debt-protocol.lovable.app/\n\n"
                    "¿Desea empezar a liquidarlas hoy?"
                )
            return (
                "El acceso de por vida a **Sueldo Bajo Control™** es de solo US$17 (pago único) con 7 días de garantía incondicional.\n\n"
                "👉 https://klaus-order-rules.lovable.app/\n\n"
                "¿Blindamos su próximo cobro?"
            )

        if segment == "DEUDA" or any(k in msg for k in ["deuda", "deudas", "tarjeta", "prestamo", "banco", "interes"]):
            return (
                "Pagar mínimos a ciegas es trabajar para enriquecer al banco. Necesita una ruta matemática exacta.\n\n"
                "Con el Protocolo C.E.R.O.™ de **Deuda Bajo Control™** ($55 con 7 días de garantía total) sabe qué deuda liquidar primero paso a paso.\n\n"
                "👉 https://zero-debt-protocol.lovable.app/\n\n"
                "¿Empezamos hoy?"
            )

        return (
            "Cobrar y ver cómo el dinero desaparece a los pocos días ocurre por no tener un protocolo estricto el día de pago.\n\n"
            "Con **Sueldo Bajo Control™** ($17 · pago único de por vida y 7 días de garantía total) blinda sus números en 5 minutos al día.\n\n"
            "👉 https://klaus-order-rules.lovable.app/\n\n"
            "¿Desea blindar su próximo cobro?"
        )

    def generate_followup_message(self, followup_num: int, username: Optional[str] = None, segment: str = "SUELDO", variant_f3: str = "A") -> Tuple[str, List[Dict[str, str]]]:
        """
        Genera los mensajes de la secuencia de 24 horas de Meta:
        - Follow-up 1 (+2h): Check-in curioso sobre la Regla #3 + botones de diagnóstico.
        - Follow-up 2 (+8h): Caso de estudio / prueba social según el segmento.
        - Follow-up 3 (+20h): Urgencia final 50/50 A/B test antes de cerrar la ventana de 24h.
        """
        user_greet = f"@{username} " if username else ""

        if followup_num == 1:
            text = (
                f"Hola {user_greet}👋 ¿Pudo revisar el PDF de las 7 Reglas Frías?\n\n"
                "La Regla #3 (el freno de mano el día de cobro) es donde el 80% tiene su mayor fuga de dinero.\n\n"
                "En su caso particular: ¿dónde siente hoy la mayor pérdida de tranquilidad? 👇"
            )
            quick_replies = [
                {"content_type": "text", "title": "💰 En mi Sueldo", "payload": "SUELDO"},
                {"content_type": "text", "title": "⚔️ En mis Deudas", "payload": "DEUDA"}
            ]
            return text, quick_replies

        elif followup_num == 2:
            if segment == "DEUDA":
                text = (
                    f"Hola {user_greet}⚔️ Le comparto un dato matemático:\n\n"
                    "El usuario promedio que aplica el Protocolo C.E.R.O.™ ahorra más de $420 en intereses bancarios en los primeros 60 días.\n\n"
                    "No se trata de ganar más, sino de amortizar en el orden correcto.\n\n"
                    "Puede revisar el protocolo completo aquí ($55 pago único con garantía de 7 días):\n"
                    "👉 https://zero-debt-protocol.lovable.app/\n\n"
                    "¿Le gustaría erradicar sus deudas este año?"
                )
            else:
                text = (
                    f"Hola {user_greet}📊 Le comparto un dato comprobado:\n\n"
                    "Quienes aplican los 5 minutos del Protocolo Día de Pago™ rescatan entre $150 y $300 cada mes que antes se evaporaban en gastos hormiga.\n\n"
                    "Puede blindar su próximo cobro con **Sueldo Bajo Control™** ($17 pago único con garantía de 7 días):\n"
                    "👉 https://klaus-order-rules.lovable.app/\n\n"
                    "¿Desea tener orden matemático en su próximo cobro?"
                )
            quick_replies = [
                {"content_type": "text", "title": "🔥 Ver Protocolo", "payload": segment if segment in ["SUELDO", "DEUDA"] else "SUELDO"},
                {"content_type": "text", "title": "❓ Tengo una duda", "payload": "DUDA"}
            ]
            return text, quick_replies

        elif followup_num == 3:
            # A/B Test 50/50 para Follow-up 3 (20h antes de cerrar ventana Meta)
            if variant_f3 == "A":
                # Variante A: Agitación del Costo de Inacción
                if segment == "DEUDA":
                    text = (
                        f"Hola {user_greet}⚔️ Una última reflexión:\n\n"
                        "Seguir pagando mínimos le costará cientos de dólares en intereses este mes. Con **Deuda Bajo Control™** ($55) frena esa sangría de por vida con garantía total de 7 días.\n\n"
                        "👉 https://zero-debt-protocol.lovable.app/\n\n"
                        "¿Prefiere frenar los intereses hoy o seguir pagando a ciegas?"
                    )
                else:
                    text = (
                        f"Hola {user_greet}⚔️ Una última reflexión:\n\n"
                        "¿Prefiere seguir perdiendo entre $150 y $300 cada mes en fugas silenciosas o blindar su sueldo hoy por solo $17?\n\n"
                        "El acceso a **Sueldo Bajo Control™** es de por vida con 7 días de garantía incondicional:\n"
                        "👉 https://klaus-order-rules.lovable.app/\n\n"
                        "¿Blindamos su próximo cobro?"
                    )
            else:
                # Variante B: Riesgo Cero Absoluto
                if segment == "DEUDA":
                    text = (
                        f"Hola {user_greet}🛡️ El riesgo es 100% mío:\n\n"
                        "Pruebe el Protocolo C.E.R.O.™ de **Deuda Bajo Control™** ($55) durante 7 días completos. Si no tiene una ruta matemática exacta para liquidar sus deudas, le devuelvo cada centavo sin preguntas.\n\n"
                        "👉 https://zero-debt-protocol.lovable.app/\n\n"
                        "¿Lo probamos sin riesgo hoy?"
                    )
                else:
                    text = (
                        f"Hola {user_greet}🛡️ El riesgo es 100% mío:\n\n"
                        "Pruebe **Sueldo Bajo Control™** ($17) durante 7 días. Si no siente orden absoluto en sus finanzas, le regreso el 100% de su dinero de inmediato.\n\n"
                        "👉 https://klaus-order-rules.lovable.app/\n\n"
                        "¿Lo probamos hoy sin arriesgar nada?"
                    )

            quick_replies = [
                {"content_type": "text", "title": "🚀 Empezar Hoy", "payload": segment if segment in ["SUELDO", "DEUDA"] else "SUELDO"},
                {"content_type": "text", "title": "🛡️ Ver Garantía", "payload": "GARANTIA"}
            ]
            return text, quick_replies

        return "", []

sales_agent = SalesAgent()

