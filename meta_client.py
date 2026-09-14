import httpx
import logging
from typing import Dict, Any, Optional
from database import add_activity_log

logger = logging.getLogger("meta_client")

class InstagramGraphClient:
    def __init__(self, access_token: str = "", graph_version: str = "v20.0"):
        self.access_token = access_token.strip()
        self.graph_version = graph_version

    def _get_base_url(self, token: str) -> str:
        # If token is an Instagram User Token (IGAA...), use graph.instagram.com
        if token.startswith("IG"):
            return f"https://graph.instagram.com/{self.graph_version}"
        # Default Graph API (Facebook Page Tokens EAA...)
        return f"https://graph.facebook.com/{self.graph_version}"

    async def verify_connection(self, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Verifica el estado del token y obtiene datos de la cuenta vinculada.
        """
        t = token or self.access_token
        if not t:
            return {"connected": False, "message": "No hay token configurado"}
        
        base_url = self._get_base_url(t)
        fields = "id,username,account_type" if t.startswith("IG") else "id,name,link"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{base_url}/me", params={"access_token": t, "fields": fields})
                if res.status_code == 200:
                    data = res.json()
                    return {"connected": True, "account": data}
                else:
                    return {"connected": False, "error": res.json()}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def reply_to_comment(self, comment_id: str, message: str, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Publica una respuesta pública al comentario de Instagram.
        Endpoint: POST /{comment-id}/replies
        """
        token = access_token or self.access_token
        if not token or token.startswith("your_") or token == "":
            logger.warning(f"[Modo Simulado / Sin Token] Respuesta a comentario {comment_id}: {message}")
            add_activity_log("PUBLIC_REPLY_SENT", f"[Simulado] Respuesta al comentario {comment_id}: '{message}'", f"Comment ID: {comment_id}")
            return {"id": f"mock_reply_{comment_id}", "status": "simulated_success"}

        base_url = self._get_base_url(token)
        url = f"{base_url}/{comment_id}/replies"
        params = {"access_token": token}
        payload = {"message": message}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, params=params, json=payload)
                data = response.json()
                if response.status_code in [200, 201]:
                    add_activity_log("PUBLIC_REPLY_SENT", f"Respuesta pública enviada a comentario {comment_id}: '{message}'", f"Comment ID: {comment_id}")
                    return data
                else:
                    error_msg = data.get("error", {}).get("message", response.text)
                    logger.error(f"Error respondiendo al comentario {comment_id}: {error_msg}")
                    add_activity_log("ERROR", f"Fallo al responder comentario {comment_id}: {error_msg}", f"Comment ID: {comment_id}")
                    return {"error": error_msg, "status_code": response.status_code}
        except Exception as e:
            logger.exception(f"Excepción al responder comentario {comment_id}")
            add_activity_log("ERROR", f"Excepción al responder comentario {comment_id}: {str(e)}", f"Comment ID: {comment_id}")
            return {"error": str(e)}

    async def send_private_message_by_comment(self, page_or_ig_id: str, comment_id: str, message_text: str, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía un mensaje privado (DM) respondiendo directamente a un comentario.
        Endpoint: POST /{ig-user-id}/messages con recipient: {"comment_id": comment_id}
        """
        token = access_token or self.access_token
        target_id = page_or_ig_id if page_or_ig_id else "me"

        if not token or token.startswith("your_") or token == "":
            logger.warning(f"[Modo Simulado / Sin Token] DM por comentario {comment_id}: {message_text}")
            add_activity_log("DM_SENT", f"[Simulado] DM por comentario {comment_id}: '{message_text}'", f"Comment ID: {comment_id}")
            return {"recipient_id": "mock_recipient", "message_id": f"mock_msg_{comment_id}", "status": "simulated_success"}

        base_url = self._get_base_url(token)
        url = f"{base_url}/{target_id}/messages"
        params = {"access_token": token}
        payload = {
            "recipient": {"comment_id": comment_id},
            "message": {"text": message_text}
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, params=params, json=payload)
                data = response.json()
                if response.status_code in [200, 201]:
                    add_activity_log("DM_SENT", f"DM enviado al usuario del comentario {comment_id}: '{message_text}'", f"Comment ID: {comment_id}")
                    return data
                else:
                    error_msg = data.get("error", {}).get("message", response.text)
                    logger.error(f"Error enviando DM por comentario {comment_id}: {error_msg}")
                    add_activity_log("ERROR", f"Fallo al enviar DM por comentario {comment_id}: {error_msg}", f"Comment ID: {comment_id}")
                    return {"error": error_msg, "status_code": response.status_code}
        except Exception as e:
            logger.exception(f"Excepción al enviar DM por comentario {comment_id}")
            add_activity_log("ERROR", f"Excepción al enviar DM por comentario: {str(e)}")
            return {"error": str(e)}

    async def send_direct_message(self, page_or_ig_id: str, recipient_id: str, message_text: str, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía un mensaje directo (DM) a un usuario por su Instagram User Scoped ID (IGSID).
        Endpoint: POST /{ig-user-id}/messages con recipient: {"id": recipient_id}
        """
        token = access_token or self.access_token
        target_id = page_or_ig_id if page_or_ig_id else "me"

        if not token or token.startswith("your_") or token == "":
            logger.warning(f"[Modo Simulado / Sin Token] DM a usuario {recipient_id}: {message_text}")
            add_activity_log("DM_SENT", f"[Simulado] DM a usuario {recipient_id}: '{message_text}'", f"User ID: {recipient_id}")
            return {"recipient_id": recipient_id, "message_id": f"mock_msg_{recipient_id}", "status": "simulated_success"}

        base_url = self._get_base_url(token)
        url = f"{base_url}/{target_id}/messages"
        params = {"access_token": token}
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": message_text}
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, params=params, json=payload)
                data = response.json()
                if response.status_code in [200, 201]:
                    add_activity_log("DM_SENT", f"DM enviado al usuario {recipient_id}: '{message_text}'", f"User ID: {recipient_id}")
                    return data
                else:
                    error_msg = data.get("error", {}).get("message", response.text)
                    logger.error(f"Error enviando DM a {recipient_id}: {error_msg}")
                    add_activity_log("ERROR", f"Fallo al enviar DM a {recipient_id}: {error_msg}", f"User ID: {recipient_id}")
                    return {"error": error_msg, "status_code": response.status_code}
        except Exception as e:
            logger.exception(f"Excepción al enviar DM a {recipient_id}")
            add_activity_log("ERROR", f"Excepción al enviar DM: {str(e)}")
            return {"error": str(e)}

    async def send_generic_card(self, page_or_ig_id: str, recipient_id: str, title: str, subtitle: str, image_url: Optional[str] = None, buttons: Optional[list] = None, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía un Recuadro / Tarjeta Interactiva (Generic Template Card estilo ManyChat).
        """
        token = access_token or self.access_token
        target_id = page_or_ig_id if page_or_ig_id else "me"

        # Validar y truncar para cumplir límites estrictos de Meta Graph API
        safe_title = (title or "")[:80]
        safe_subtitle = (subtitle or "")[:80]

        element = {"title": safe_title, "subtitle": safe_subtitle}
        if image_url:
            element["image_url"] = image_url

        if buttons:
            safe_buttons = []
            for b in buttons[:3]:  # Meta permite máximo 3 botones por elemento
                btn = dict(b)
                if "title" in btn:
                    btn["title"] = str(btn["title"])[:20]
                if btn.get("type") == "postback" and "payload" in btn:
                    btn["payload"] = str(btn["payload"])[:1000]
                safe_buttons.append(btn)
            element["buttons"] = safe_buttons

        payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "generic",
                        "elements": [element]
                    }
                }
            }
        }

        base_url = self._get_base_url(token)
        url = f"{base_url}/{target_id}/messages"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, params={"access_token": token}, json=payload)
                data = response.json()
                if response.status_code in [200, 201]:
                    add_activity_log("CARD_SENT", f"Tarjeta interactiva enviada a {recipient_id}: '{safe_title}'", f"User ID: {recipient_id}")
                    return data
                else:
                    # Fallback a texto normal con enlace si el formato de tarjeta falla en Meta
                    logger.warning(f"Fallback de tarjeta a texto para {recipient_id}: {data}")
                    first_url = buttons[0].get("url") if (buttons and len(buttons) > 0 and isinstance(buttons[0], dict) and buttons[0].get("url")) else ""
                    fallback_text = f"**{safe_title}**\n\n{safe_subtitle}"
                    if first_url:
                        fallback_text += f"\n\n👉 {first_url}"
                    return await self.send_direct_message(target_id, recipient_id, fallback_text, access_token=token)
        except Exception as e:
            logger.exception(f"Error enviando tarjeta a {recipient_id}: {e}")
            first_url = buttons[0].get("url") if (buttons and len(buttons) > 0 and isinstance(buttons[0], dict) and buttons[0].get("url")) else ""
            fallback_text = f"**{safe_title}**\n\n{safe_subtitle}"
            if first_url:
                fallback_text += f"\n\n👉 {first_url}"
            return await self.send_direct_message(target_id, recipient_id, fallback_text, access_token=token)

    async def send_quick_replies(self, page_or_ig_id: str, recipient_id: str, text: str, quick_replies_list: list, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía un mensaje de texto con Botones Rápidos (Quick Replies pastillas interactivas estilo ManyChat).
        """
        token = access_token or self.access_token
        target_id = page_or_ig_id if page_or_ig_id else "me"

        # Formatear lista de quick replies si vienen como strings simples
        formatted_qr = []
        for qr in quick_replies_list[:13]:  # Meta permite max 13 quick replies
            if isinstance(qr, str):
                formatted_qr.append({"content_type": "text", "title": str(qr)[:20], "payload": str(qr)[:1000]})
            elif isinstance(qr, dict):
                qr_dict = dict(qr)
                if "title" in qr_dict:
                    qr_dict["title"] = str(qr_dict["title"])[:20]
                if "payload" in qr_dict:
                    qr_dict["payload"] = str(qr_dict["payload"])[:1000]
                formatted_qr.append(qr_dict)

        payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "text": text,
                "quick_replies": formatted_qr
            }
        }

        base_url = self._get_base_url(token)
        url = f"{base_url}/{target_id}/messages"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, params={"access_token": token}, json=payload)
                data = response.json()
                if response.status_code in [200, 201]:
                    add_activity_log("QUICK_REPLIES_SENT", f"Quick replies enviadas a {recipient_id}: '{text}'", f"User ID: {recipient_id}")
                    return data
                else:
                    logger.warning(f"Fallback de quick replies a texto para {recipient_id}: {data}")
                    return await self.send_direct_message(target_id, recipient_id, text, access_token=token)
        except Exception as e:
            logger.exception(f"Error enviando quick replies a {recipient_id}: {e}")
            return await self.send_direct_message(target_id, recipient_id, text, access_token=token)
