import logging

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from config import settings
from services.api_client import get_visit_context
from services.llm_service import generate_response
from services.session_service import (
    delete_session,
    get_session,
    save_session,
    save_welcome_payload,
    set_awaiting_preparation,
    update_session_step,
)
from services.whatsapp_service import (
    send_results_notification,
    send_text_message,
    send_turn_notification,
    send_welcome_message,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SaludCopilot Bot",
    description="WhatsApp bot for Salud Digna patient assistance",
    version="0.1.0",
)


# ── Constants ──────────────────────────────────────────────────────────────


PREPARATION_REQUIRED = {
    "laboratorio": "ayuno de 8 horas",
    "papanicolaou": "no usar desodorante y abstinencia sexual 48 horas previas",
    "tomografia": "preparación específica indicada por el médico",
    "resonancia": "preparación específica indicada por el médico",
}

PREPARATION_CONFIRM_WORDS = {"sí", "si", "yes", "claro", "listo"}
PREPARATION_DENY_WORDS = {"no", "no pude", "no completé"}

WAIT_TIME_DELTA_THRESHOLD_MINUTES = 5

RESCHEDULE_MESSAGE = (
    "Entendido. Para obtener resultados precisos te recomendamos "
    "reagendar tu cita. Puedes llamar a la clínica o visitar "
    "saluddigna.com para agendar."
)

NO_SESSION_MESSAGE = (
    "No tenemos una visita activa registrada para tu número. "
    "Por favor acércate a recepción para registrarte."
)

LLM_FALLBACK_MESSAGE = (
    "Disculpa, no pude procesar tu mensaje en este momento. "
    "Por favor intenta de nuevo en unos segundos."
)

MESSAGE_LOCK_TTL_SECONDS = 10

_redis_client = aioredis.from_url(settings.redis_url)


# ── Schemas ─────────────────────────────────────────────────────────────────


class NotifyRequest(BaseModel):
    visit_id: str
    notification_type: str
    payload: dict


# ── Webhook verification ────────────────────────────────────────────────────


@app.get("/bot/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Verify the Meta webhook subscription using the shared verify token."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


# ── Incoming WhatsApp messages ──────────────────────────────────────────────


@app.post("/bot/webhook")
async def incoming_webhook(request: Request):
    """Receive incoming WhatsApp messages from Meta. Always returns 200."""
    try:
        webhook_body = await request.json()
        for entry in webhook_body.get("entry", []):
            for change in entry.get("changes", []):
                messages = change.get("value", {}).get("messages", [])
                for incoming_message in messages:
                    await _handle_incoming_message(incoming_message)
    except Exception:
        logger.exception("Error processing incoming webhook")

    return {"status": "ok"}


async def _handle_incoming_message(incoming_message: dict) -> None:
    """Route an incoming WhatsApp message through preparation, session, and LLM flows."""
    if incoming_message.get("type") != "text":
        return

    phone_number = incoming_message.get("from", "")
    message_text = incoming_message.get("text", {}).get("body", "").strip()

    if not phone_number or not message_text:
        return

    # Acquire lock to prevent race conditions on concurrent messages
    lock_key = f"processing:{phone_number}"
    lock_acquired = await _redis_client.set(lock_key, "1", nx=True, ex=MESSAGE_LOCK_TTL_SECONDS)
    if not lock_acquired:
        return

    try:
        await _process_message(phone_number, message_text)
    finally:
        await _redis_client.delete(lock_key)


async def _process_message(phone_number: str, message_text: str) -> None:
    """Core message processing: session check, preparation flow, then LLM."""
    session = await get_session(phone_number)

    if session is None:
        await send_text_message(phone_number, NO_SESSION_MESSAGE)
        return

    if session.get("awaiting_preparation_confirmation"):
        await _handle_preparation_response(phone_number, message_text, session)
        return

    visit_context = await get_visit_context(session["visit_id"])
    if visit_context is None:
        await send_text_message(phone_number, NO_SESSION_MESSAGE)
        return

    llm_response = await generate_response(message_text, visit_context)
    if llm_response is None:
        await send_text_message(phone_number, LLM_FALLBACK_MESSAGE)
        return

    await send_text_message(phone_number, llm_response)


async def _handle_preparation_response(
    phone_number: str, message_text: str, session: dict
) -> None:
    """Process the patient's yes/no response to the preparation question."""
    await set_awaiting_preparation(phone_number, False)
    message_lower = message_text.lower()

    if any(word in message_lower for word in PREPARATION_CONFIRM_WORDS):
        await _send_deferred_welcome(phone_number, session)
    elif any(word in message_lower for word in PREPARATION_DENY_WORDS):
        await send_text_message(phone_number, RESCHEDULE_MESSAGE)
    else:
        await _send_deferred_welcome(phone_number, session)


async def _send_deferred_welcome(phone_number: str, session: dict) -> None:
    """Send the welcome message that was deferred pending preparation confirmation."""
    visit_id = session.get("visit_id", "")
    context = await get_visit_context(visit_id)
    if context is None:
        logger.warning("Could not get visit context for deferred welcome: %s", visit_id)
        return

    patient_name = context.get("patient_name", "Paciente")
    welcome_data = session.get("welcome_payload", {})
    sequence = welcome_data.get("sequence", [])
    total_minutes = welcome_data.get("total_estimated_minutes", 0)
    await send_welcome_message(phone_number, patient_name, sequence, total_minutes)


# ── Internal notification endpoint ──────────────────────────────────────────


@app.post("/bot/internal/notify")
async def internal_notify(
    body: NotifyRequest,
    authorization: str = Header(None),
):
    """Receive notification triggers from the API and dispatch to WhatsApp."""
    expected_token = f"Bearer {settings.internal_bot_token}"
    if authorization != expected_token:
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "code": "UNAUTHORIZED"},
        )

    handlers = {
        "welcome": _handle_welcome,
        "turn_ready": _handle_turn_ready,
        "results_ready": _handle_results_ready,
        "wait_time_updated": _handle_wait_time_updated,
    }

    handler = handlers.get(body.notification_type)
    if handler is None:
        return JSONResponse(
            status_code=400,
            content={"error": "Unknown type", "code": "UNKNOWN_NOTIFICATION_TYPE"},
        )

    await handler(body.visit_id, body.payload)
    return {"status": "sent"}


# ── Notification handlers ──────────────────────────────────────────────────


async def _handle_welcome(visit_id: str, payload: dict) -> None:
    """Send welcome message or preparation check, and create the bot session."""
    context = await get_visit_context(visit_id)
    if context is None:
        logger.warning("Could not get visit context for welcome: %s", visit_id)
        return

    phone_number = context.get("patient_phone", "")
    patient_name = context.get("patient_name", "Paciente")
    sequence = payload.get("sequence", [])
    total_minutes = payload.get("total_estimated_minutes", 0)
    has_appointment = payload.get("has_appointment", False)
    bot_mode = "proactive" if has_appointment else "reactive"

    await save_session(phone_number, visit_id, bot_mode, current_step_order=1)

    preparations_needed = _find_required_preparations(sequence, has_appointment)

    if preparations_needed:
        await save_welcome_payload(phone_number, {
            "sequence": sequence,
            "total_estimated_minutes": total_minutes,
        })
        await set_awaiting_preparation(phone_number, True)
        await _send_preparation_question(phone_number, patient_name, preparations_needed)
    else:
        await send_welcome_message(phone_number, patient_name, sequence, total_minutes)


def _find_required_preparations(
    sequence: list[dict], has_appointment: bool
) -> list[str]:
    """Return list of preparation instructions needed for the given sequence."""
    if not has_appointment:
        return []
    preparations = []
    for step in sequence:
        area_name_lower = step.get("area_name", "").lower()
        for study_type, preparation_text in PREPARATION_REQUIRED.items():
            if study_type in area_name_lower:
                preparations.append(preparation_text)
    return preparations


async def _send_preparation_question(
    phone_number: str,
    patient_name: str,
    preparations_needed: list[str],
) -> None:
    """Ask the patient to confirm they completed the required preparations."""
    preparation_list = "\n".join(f"  • {prep}" for prep in preparations_needed)
    message = (
        f"¡Hola {patient_name}! Antes de registrarte, confirma que completaste:\n"
        f"{preparation_list}\n"
        f"¿Lo completaste? Responde Sí o No."
    )
    await send_text_message(phone_number, message)


async def _handle_turn_ready(visit_id: str, payload: dict) -> None:
    """Notify the patient their turn is approaching and update the session step."""
    context = await get_visit_context(visit_id)
    if context is None:
        logger.warning("Could not get visit context for turn_ready: %s", visit_id)
        return

    phone_number = context.get("patient_phone", "")
    area_name = payload.get("area_name", "")
    estimated_wait = payload.get("estimated_wait_minutes", WAIT_TIME_DELTA_THRESHOLD_MINUTES)
    position = payload.get("position_in_queue", 0)

    await send_turn_notification(phone_number, area_name, estimated_wait, position)

    current_step = context.get("current_step", {})
    step_order = current_step.get("order", 1)
    await update_session_step(phone_number, step_order)


async def _handle_results_ready(visit_id: str, payload: dict) -> None:
    """Send results notification and clean up the session."""
    context = await get_visit_context(visit_id)
    if context is None:
        logger.warning("Could not get visit context for results_ready: %s", visit_id)
        return

    phone_number = context.get("patient_phone", "")
    study_name = payload.get("study_name", "estudio")
    result_url = payload.get("result_url", "")
    recommendation = payload.get("recommendation", "")

    await send_results_notification(phone_number, study_name, result_url, recommendation)
    await delete_session(phone_number)


async def _handle_wait_time_updated(visit_id: str, payload: dict) -> None:
    """Notify the patient only if the wait time changed by more than the threshold."""
    context = await get_visit_context(visit_id)
    if context is None:
        return

    phone_number = context.get("patient_phone", "")
    new_minutes = payload.get("estimated_minutes", 0)
    previous_minutes = payload.get("previous_minutes", 0)

    delta = abs(new_minutes - previous_minutes)
    if delta > WAIT_TIME_DELTA_THRESHOLD_MINUTES:
        await send_text_message(
            phone_number,
            f"⏱ Actualización: tu tiempo de espera cambió a ~{new_minutes} minutos.",
        )


# ── Health ──────────────────────────────────────────────────────────────────


@app.get("/health", tags=["System"])
async def health():
    """Return service health status."""
    return {"status": "ok", "service": "bot", "version": "0.1.0"}
