import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v19.0/{phone_id}/messages"
HTTP_TIMEOUT_SECONDS = 10.0


def _normalize_mx_phone(phone: str) -> str:
    """Strip leading + and remove the extra '1' Mexico mobile prefix (521XXXXXXXXXX → 52XXXXXXXXXX)."""
    digits = phone.lstrip("+")
    if digits.startswith("521") and len(digits) == 13:
        digits = "52" + digits[3:]
    return digits


async def send_text_message(phone_number: str, message: str) -> bool:
    """Send a plain text message via the WhatsApp Cloud API. Returns True on success."""
    request_payload = {
        "messaging_product": "whatsapp",
        "to": _normalize_mx_phone(phone_number),
        "type": "text",
        "text": {"body": message},
    }
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
    url = WHATSAPP_API_URL.format(phone_id=settings.whatsapp_phone_id)

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=request_payload, headers=headers)
            if response.status_code < 300:
                return True
            logger.warning(
                "WhatsApp API error: status=%d body=%s",
                response.status_code,
                response.text,
            )
            return False
    except Exception:
        logger.exception("WhatsApp send error to %s", phone_number)
        return False


async def send_welcome_message(
    phone_number: str,
    patient_name: str,
    sequence: list[dict],
    total_estimated_minutes: int,
) -> bool:
    """Format and send the welcome message with the patient's study sequence."""
    lines = [f"¡Hola {patient_name}! Esta es tu secuencia de atención hoy:\n"]
    for step_number, step in enumerate(sequence, start=1):
        area_name = step.get("area_name", "Área")
        wait_minutes = step.get("estimated_wait_minutes", 0)
        lines.append(f"{step_number}. {area_name} — ~{wait_minutes} min de espera")
    lines.append(f"\n⏱ Tiempo total estimado: ~{total_estimated_minutes} minutos.")
    lines.append("Te avisaremos cuando sea tu turno en cada área.")
    formatted_message = "\n".join(lines)
    return await send_text_message(phone_number, formatted_message)


async def send_turn_notification(
    phone_number: str,
    area_name: str,
    estimated_wait_minutes: int,
    position_in_queue: int,
) -> bool:
    """Notify the patient that their turn in the given area is approaching."""
    message = (
        f"🔔 Tu turno en {area_name} se acerca.\n"
        f"Posición en fila: {position_in_queue}\n"
        f"Tiempo estimado: ~{estimated_wait_minutes} minutos."
    )
    return await send_text_message(phone_number, message)


async def send_results_notification(
    phone_number: str,
    study_name: str,
    result_url: str,
    recommendation: str,
) -> bool:
    """Notify the patient that their study results are ready for download."""
    message = (
        f"✅ Tus resultados de {study_name} están listos.\n"
        f"Descárgalos aquí: {result_url}\n"
        f"📋 {recommendation}"
    )
    return await send_text_message(phone_number, message)
