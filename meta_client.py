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
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{base_url}/me", params={"access_token": t, "fields": "id,username,account_type"})
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
