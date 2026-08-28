# 🚀 InstaFlow Sales AI (Reemplazo Gratuito de ManyChat)

Sistema autónomo, gratuito y de código abierto para automatizar ventas en **Instagram Reels y Posts**. Detecta comentarios con palabras clave específicas, responde públicamente para evitar spam, envía secuencias de mensajes directos (DMs) con tus enlaces de pago y activa un **Agente de Ventas con IA (Gemini)** para responder preguntas y cerrar ventas por chat.

---

## 🌟 Características Principales

- **0 Costo de Suscripción:** Sin límites artificiales de contactos ni cobros mensuales por volumen.
- **Detección Inteligente de Palabras Clave:** Reconoce términos como `QUIERO`, `PRECIO`, `LINK`, `INFO`, `COMPRAR` o cualquier regla personalizada.
- **Respuestas Públicas Rotativas:** Responde en el post con variaciones de mensajes para proteger tu cuenta de filtros de spam.
- **Secuencias de Mensajes Directos (DMs):** Envío escalonado con pausas configurables (ej. 2s, 3s) para simular atención humana.
- **Agente de Ventas con IA (Google Gemini):** Atiende dudas de clientes sobre precios, métodos de pago, envíos y objeciones de venta usando tu catálogo oficial.
- **Simulador Móvil en Vivo:** Prueba todo el flujo (comentario ➔ respuesta pública ➔ secuencia de DMs ➔ conversación con IA) directamente en tu navegador sin necesidad de conectar Instagram primero.
- **Dashboard Web Completo:** Gestor de campañas, catálogo de productos, registro de leads y logs en vivo.

---

## ⚡ Inicio Rápido en Windows

1. Haz doble clic en `start.bat` o ejecuta en tu terminal:
```bash
python run.py
```
2. Abre tu navegador en:
```
http://localhost:8000
```

---

## 📱 Cómo Probar en el Simulador

1. Abre la pestaña **Simulador Móvil en Vivo**.
2. Escribe una palabra clave en el comentario (ejemplo: `QUIERO` o `PRECIO`) y pulsa **Comentar**.
3. Observa cómo el teléfono 1 muestra la respuesta pública y el teléfono 2 reproduce la secuencia de DMs.
4. En el chat del teléfono 2, escribe cualquier pregunta (ej: *"¿Aceptan transferencias bancarias?"* o *"¿En cuánto tiempo llega?"*) para hablar en vivo con el Agente de Ventas IA.

---

## 🔗 Conexión Oficial con Meta / Instagram (Paso a Paso)

### 1. Requisitos de Instagram
- Cuenta de Instagram Profesional (**Empresa** o **Creador**).
- Una **Página de Facebook** vinculada a tu cuenta de Instagram.

### 2. Exponer tu servidor a Internet (Gratis con Cloudflare Tunnel)
En una terminal nueva, ejecuta:
```bash
npx cloudflared tunnel --url http://localhost:8000
```
Copia la URL segura `https://xxx.trycloudflare.com` que te proporcionará Cloudflare.

### 3. Configurar en Meta for Developers (`developers.facebook.com`)
1. Crea una app de tipo **Negocios** o **Para todo tipo de apps**.
2. Agrega el producto **Instagram Graph API** o **Messenger**.
3. En la sección **Webhooks**:
   - **Callback URL:** `https://tu-url-de-cloudflare.trycloudflare.com/webhook`
   - **Verify Token:** `instaflow_verify_token_secure_2026` (o el que configures en el dashboard).
   - Suscríbete a los campos: `comments`, `feed` y `messages`.
4. Genera tu **Page / Instagram Access Token** y guárdalo en la pestaña **Conexión con Meta** del Dashboard.

---

## 🛠️ Tecnologías Utilizadas

- **Backend:** FastAPI (Python 3.10+) + Uvicorn + HTTPX
- **Base de Datos:** SQLite local y persistente (cero configuración requerida)
- **Frontend:** HTML5, Tailwind CSS, Alpine.js, Lucide Icons
- **Inteligencia Artificial:** Google GenAI SDK (Gemini 2.5 Flash - Free Tier)
