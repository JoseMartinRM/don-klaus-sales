import sys
import io

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

import sqlite3
import json
from datetime import datetime
from config import config

def setup_don_klaus_funnel():
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    # 1. Settings
    settings = {
        "company_name": "Don Klaus — Sistema Financiero",
        "company_description": "Protocolos financieros fríos y sistemáticos para dejar de improvisar con tu dinero. Sueldo Bajo Control™ (US$17) en https://klaus-order-rules.lovable.app/ y Deuda Bajo Control™ (US$55) en https://zero-debt-protocol.lovable.app/.",
        "sales_tone": "Frío, directo, implacable contra las excusas, sin motivación vacía. Enfocado en identificación quirúrgica y decisión de compra inmediata.",
    }
    for k, v in settings.items():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # 2. Update Campaigns
    cursor.execute("DELETE FROM campaigns")

    # Campaña 1: Lead Magnet Principal (7 Reglas Frías)
    camp_lead_magnet = {
        "name": "1. Lead Magnet - 7 Reglas Frías de Don Klaus",
        "keywords": "reglas, regla, klaus, don klaus, quiero, quiero las reglas, pdf, guia, guía, info, informacion, información, dinero, plata, la plata, mi plata, plata gracias, quiero plata, respeto, el respeto, mis respetos, con respeto, sistema, frases, frias, frías, libro, libreta, consejo, consejos, enviar, enviamelo, envíamelo, link, enlace, acceso, pasamelo, pásamelo, me interesa, yo, yo quiero",
        "match_mode": "contains",
        "post_id_filter": "",
        "public_replies": [
            "Te dejé las Reglas Frías en tu mensaje privado. No es motivación, es un sistema. 📩",
            "Revisa tu DM. Te envié el acceso directo a las Reglas de Don Klaus. ⚔️",
            "Listo. Ya tienes las Reglas Frías en tu privado. Léelas con una sola pregunta en mente. 📜"
        ],
        "dm_messages": [
            {
                "text": "Aquí tienes las Reglas Frías de Don Klaus.\n\nNo son frases para motivarte.\n\nSon reglas para esos momentos en los que el dinero entra, sale y terminas tomando decisiones demasiado tarde.\n\nLéelas con una sola pregunta en mente:\n\n“¿Cuál de estas reglas estoy rompiendo hoy?”\n\nPorque muchas veces el problema no es que no sepas de dinero.\n\nEs que sabes lo que deberías hacer… pero no tienes un sistema que te obligue a decidir antes de gastar, pagar o endeudarte.\n\nDescarga el PDF aquí 👇\n\n👉 https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view\n\nCuando termines, dime dónde necesitas más control:\n\n💰 Escribe SUELDO — el dinero entra y desaparece\n⚔️ Escribe DEUDA — pagas, pero no sabes qué atacar primero",
                "delay_seconds": 0
            }
        ],
        "is_active": 1,
        "enable_ai_agent": 1
    }

    # Campaña 2: Rama SUELDO BAJO CONTROL™ (Link: klaus-order-rules.lovable.app)
    camp_sueldo = {
        "name": "2. Rama SUELDO - Sueldo Bajo Control™ (US$17)",
        "keywords": "sueldo, sueldos, mi sueldo, el sueldo, sueldo bajo control, gastos, gasto, mis gastos, ahorro, ahorrar, ingreso, ingresos, no me alcanza, salario, cobro, cobrar, quincena, mes, dinero entra, opcion 1, opción 1, 1",
        "match_mode": "contains",
        "post_id_filter": "",
        "public_replies": [
            "Te envié el protocolo de Sueldo Bajo Control™ por mensaje privado. 💰"
        ],
        "dm_messages": [
            {
                "text": "Si cada vez que cobras sientes que el dinero dura menos de lo que debería, probablemente el problema no empieza en cuánto ganas.\n\nEmpieza en que tu sueldo entra sin una orden clara.\n\nCobras. Pagas algunas cosas. Gastas otras. Pasan unos días… y terminas preguntándote:\n\n“¿En qué se fue todo?”\n\nSueldo Bajo Control™ fue creado para romper ese ciclo.\n\nEn 7 días aplicas el Protocolo Día de Pago™ para detectar fugas, separar lo que no deberías tocar, decidir qué sí puedes usar y llegar al próximo cobro con un plan.\n\nMIRA ➔ SEPARA ➔ DECIDE ➔ REVISA\n\nNo necesitas controlar cada centavo.\n\nNecesitas que tu dinero tenga una función antes de empezar a desaparecer.",
                "delay_seconds": 0
            },
            {
                "text": "Imagina recibir tu próximo sueldo y ya saber:\n\n• qué debes separar,\n• qué dinero debes proteger,\n• qué puedes usar sin culpa,\n• y qué revisar antes del siguiente cobro.\n\nEso es Sueldo Bajo Control™.\n\nNo es otro ebook lleno de consejos para “gastar menos”.\n\nEs un sistema que puedes volver a utilizar cada vez que cobras.\n\n🔥 US$17 · un solo pago\n\nSi no quieres repetir otro mes preguntándote dónde se fue tu dinero, empieza antes de tu próximo cobro.\n\n👉 [ QUIERO PONER MI SUELDO BAJO CONTROL → ]\nhttps://klaus-order-rules.lovable.app/",
                "delay_seconds": 3
            }
        ],
        "is_active": 1,
        "enable_ai_agent": 1
    }

    # Campaña 3: Rama DEUDA BAJO CONTROL™ (Link: zero-debt-protocol.lovable.app)
    camp_deuda = {
        "name": "3. Rama DEUDA - Deuda Bajo Control™ (US$55)",
        "keywords": "deuda, deudas, mis deudas, la deuda, las deudas, deuda bajo control, tarjeta, tarjetas, prestamo, prestamos, préstamo, préstamos, debo, banco, bancos, intereses, interes, interés, pagar deudas, opcion 2, opción 2, 2, cero, plan cero",
        "match_mode": "contains",
        "post_id_filter": "",
        "public_replies": [
            "Te envié el Protocolo C.E.R.O.™ para deudas por privado. ⚔️"
        ],
        "dm_messages": [
            {
                "text": "Si hoy aparecieran $300 extra para tus deudas…\n\n¿sabrías exactamente cuál atacar primero y por qué?\n\nSi tienes que pensarlo demasiado, ahí está parte del problema.\n\nNo solo tienes deuda.\n\nEstás intentando pagarla sin una orden clara de ataque.\n\nMínimos aquí. Un abono allá. Una tarjeta parece urgente. Luego otra.\n\nPagas… pero sigues sin saber si realmente estás avanzando.\n\nDeuda Bajo Control™ organiza todo eso con el Protocolo C.E.R.O.™:\n\nC — cuánto debes exactamente\nE — cuánto puedes destinar realmente\nR — qué deuda va primero\nO — cuánto pagar y qué día\n\nPorque pagar deuda no debería sentirse como disparar con los ojos cerrados.",
                "delay_seconds": 0
            },
            {
                "text": "En 7 días, el objetivo es que puedas dejar de decir:\n\n“Tengo muchas deudas.”\n\ny empezar a decir:\n\n“Debo $____. Puedo destinar $____. Mi ruta es ____. Esta es la deuda que voy a atacar. Este mes pagaré $____ el día ____.”\n\nPara eso recibes el sistema completo:\n\nTablero C.E.R.O.™, protocolo de 7 días, 7 videos de implementación, simulador, calendario, Auditoría C.E.R.O.™ y herramientas Antirrecaída.\n\nNo prometemos borrar todas tus deudas en una semana.\n\nTe damos el sistema para dejar de pagar a ciegas y empezar a eliminarlas una por una.\n\n⚔️ US$55 · pago único · garantía de 7 días\n\nSi vas a seguir pagando deuda de todos modos, que al menos cada dólar tenga una misión.\n\n👉 [ QUIERO MI PLAN C.E.R.O.™ → ]\nhttps://zero-debt-protocol.lovable.app/",
                "delay_seconds": 3
            }
        ],
        "is_active": 1,
        "enable_ai_agent": 1
    }

    for camp in [camp_lead_magnet, camp_sueldo, camp_deuda]:
        cursor.execute("""
        INSERT INTO campaigns (name, keywords, match_mode, post_id_filter, public_replies, dm_messages, is_active, enable_ai_agent, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            camp["name"],
            camp["keywords"],
            camp["match_mode"],
            camp["post_id_filter"],
            json.dumps(camp["public_replies"], ensure_ascii=False),
            json.dumps(camp["dm_messages"], ensure_ascii=False),
            camp["is_active"],
            camp["enable_ai_agent"],
            datetime.now().isoformat()
        ))

    # 3. Products
    cursor.execute("DELETE FROM products")
    products = [
        {
            "name": "Sueldo Bajo Control™",
            "description": "Protocolo de 7 días Día de Pago™. MIRA -> SEPARA -> DECIDE -> REVISA. Para dejar de preguntarte dónde se fue todo y llegar al próximo cobro con una orden clara.",
            "price": "$17 USD",
            "payment_link": "https://klaus-order-rules.lovable.app/",
            "benefits": "• Romper el ciclo de cobro y desaparición de dinero\n• Separar y proteger dinero antes de gastar\n• Usar dinero sin culpa con límites claros\n• Sistema reutilizable cada vez que cobras",
            "faq": "Pago único de US$17. Acceso inmediato."
        },
        {
            "name": "Deuda Bajo Control™ (Protocolo C.E.R.O.™)",
            "description": "Sistema completo para dejar de pagar a ciegas y eliminar deudas una por una con el método C.E.R.O. (Censo, Evaluación, Ruta, Operación).",
            "price": "$55 USD",
            "payment_link": "https://zero-debt-protocol.lovable.app/",
            "benefits": "• Tablero C.E.R.O.™\n• Protocolo de 7 días y 7 videos prácticos\n• Simulador y calendario de pagos\n• Auditoría C.E.R.O.™ y herramientas Antirrecaída\n• Garantía total de 7 días",
            "faq": "Pago único de US$55. Garantía incondicional de 7 días."
        },
        {
            "name": "7 Reglas Frías de Don Klaus (Lead Magnet)",
            "description": "Reglas para esos momentos en los que el dinero entra, sale y terminas tomando decisiones demasiado tarde.",
            "price": "Gratis",
            "payment_link": "https://drive.google.com/file/d/1V11Z2g20b0a71QquFVUbgNrUsmogWK5q/view",
            "benefits": "• Diagnóstico en 1 clic: Sueldo vs Deuda\n• Reglas prácticas sin motivación barata",
            "faq": "Descarga gratuita inmediata."
        }
    ]

    for p in products:
        cursor.execute("""
        INSERT INTO products (name, description, price, payment_link, benefits, faq, is_available, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            p["name"],
            p["description"],
            p["price"],
            p["payment_link"],
            p["benefits"],
            p["faq"],
            datetime.now().isoformat()
        ))

    conn.commit()
    conn.close()
    print("[OK] Link de Sueldo Bajo Control™ actualizado a: https://klaus-order-rules.lovable.app/")

if __name__ == "__main__":
    setup_don_klaus_funnel()
