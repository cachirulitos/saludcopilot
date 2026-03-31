# TASK.md — apps/bot

> Read CLAUDE.md and ARQUITECTURA.md before starting.
> The bot depends on the API. Confirm tasks 3 and 4 in apps/api/TASK.md
> are complete before implementing tasks 4 and 5 here.

---

## Current status

- [x] Project scaffold created
- [x] requirements.txt
- [ ] FastAPI app entry point
- [ ] WhatsApp webhook verification
- [ ] Redis session management
- [ ] WhatsApp message sender service
- [ ] Internal notification endpoint (receives triggers from API)
- [ ] Incoming WhatsApp message handler
- [ ] Claude API integration
- [ ] Proactive mode — appointment confirmation and reminder

---

## How the bot works — read this first

The bot has two entry points:

**1. WhatsApp webhook** (`POST /bot/webhook`)
Meta sends every incoming patient message here.
The bot identifies the patient by phone number, retrieves their active
visit from Redis, calls the API for context, and responds via Claude API.

**2. Internal notification endpoint** (`POST /bot/internal/notify`)
The API calls this when it needs to push a message to a patient:
turn ready, results available, wait time updated.
This is API-triggered, not patient-triggered.

Both entry points send messages via WhatsApp Cloud API.
Neither writes to PostgreSQL — only the API does that.

---

## Task 1 — FastAPI app and webhook verification

Create `apps/bot/main.py`.
Implement `GET /bot/webhook` for Meta's verification handshake.

**How Meta verification works:**
When you register a webhook URL, Meta sends a GET with three query params:
- `hub.mode` = "subscribe"
- `hub.verify_token` = the token you configured in Meta dashboard
- `hub.challenge` = a random string Meta expects back as plain text

The endpoint returns `hub.challenge` as plain text if token matches, 403 if not.

```python
@app.get("/bot/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")
```

**Acceptance criteria:**
- GET with correct token returns challenge as plain text with status 200
- GET with wrong token returns 403
- Tests in `tests/test_webhook.py` cover both cases

---

## Task 1b — Navigation instructions per area

Each clinical area has a text description of how to reach it from
the clinic entrance. The bot includes this in the welcome message
so the patient knows exactly where to go — not just what study is next.

**Database change required (coordinate with Dev 1):**
Add column to clinical_areas table:
  navigation_instructions: TEXT nullable

Example values for seed data:
- Laboratorio: "Al entrar a la clínica, sigue recto al fondo y dobla
  a la izquierda. Busca el letrero azul que dice 'Toma de Muestras'."
- Ultrasonido: "Sube al segundo piso por las escaleras centrales.
  Ultrasonido está al fondo del pasillo, puerta 12."
- Rayos X: "En la planta baja, dobla a la derecha al entrar.
  Rayos X está frente a ti, letrero verde."

**Changes to send_welcome_message():**
Include navigation_instructions in the sequence message:

Current format:
"1. Laboratorio — ~15 min de espera"

New format:
"1. Laboratorio — ~15 min de espera
   📍 Cómo llegar: Al entrar sigue recto y dobla a la izquierda."

If navigation_instructions is null for an area: omit the 📍 line
for that area. Do not show "null" or an empty line.

**Roadmap — Fase 2 (do not implement now):**
The dashboard will allow clinic managers to upload a floor plan image
per area. When available, the bot sends the image instead of the text
instructions. The architecture already supports sending images via
WhatsApp Cloud API — only the trigger and storage need to be added.

**Acceptance criteria:**
- Welcome message includes navigation text when area has instructions
- Areas without instructions show only name and wait time
- scripts/seed.py includes navigation_instructions for all 7 demo areas
- No visible change for walk-in patients without appointment

## Task 2 — Redis session management

Create `apps/bot/services/session_service.py`.

**Purpose:** the bot's memory between patient messages.
Stores active visit context per phone number in Redis.

```python
async def save_session(
    phone_number: str,
    visit_id: str,
    bot_mode: str,           # "proactive" or "reactive"
    current_step_order: int,
) -> None:
    """
    Save active visit session for a patient.
    Key: session:{phone_number}
    TTL: 14400 seconds (4 hours)
    Value: JSON with visit_id, bot_mode, current_step_order, created_at
    """

async def get_session(phone_number: str) -> dict | None:
    """
    Retrieve active session.
    Returns None if session does not exist or has expired.
    """

async def delete_session(phone_number: str) -> None:
    """
    Delete session when visit is completed.
    """

async def update_session_step(phone_number: str, new_step_order: int) -> None:
    """
    Update current step without resetting the 4h TTL.
    Use Redis GETEX or manual TTL preservation.
    """
```

**Acceptance criteria:**
- `save_session` sets key with exactly 14400s TTL
- `get_session` returns None for expired or missing keys (no exceptions)
- `update_session_step` updates step_order, preserves remaining TTL
- Tests in `tests/test_session_service.py` mock Redis client

---

## Task 3 — WhatsApp message sender

Create `apps/bot/services/whatsapp_service.py`.

**Rule:** nothing else in the codebase sends WhatsApp messages directly.
All outgoing messages go through this service.

```python
async def send_text_message(phone_number: str, message: str) -> bool:
    """
    Send plain text message via WhatsApp Cloud API v19.
    Returns True if Meta accepted (2xx), False otherwise.
    Never raises — logs errors and returns False on failure.
    """

async def send_welcome_message(
    phone_number: str,
    patient_name: str,
    sequence: list[dict],
    total_estimated_minutes: int,
) -> bool:
    """
    Send initial welcome with full study sequence.
    sequence items: {order, area_name, estimated_wait_minutes, rule_applied}

    Output format (in Spanish):
    Hola [name], esta es tu secuencia de atención hoy:
    1. Laboratorio — ~15 min de espera
    2. Ultrasonido — ~20 min de espera
    Tiempo total estimado: ~35 minutos.
    Te avisaremos cuando sea tu turno en cada área.
    """

async def send_turn_notification(
    phone_number: str,
    area_name: str,
    estimated_wait_minutes: int,
    position_in_queue: int,
) -> bool:
    """
    Notify patient their turn is approaching.
    Output: "Tu turno en [area] se acerca. Posición en fila: [N].
             Tiempo estimado de espera: ~[N] minutos."
    """

async def send_results_notification(
    phone_number: str,
    study_name: str,
    result_url: str,
    recommendation: str,
) -> bool:
    """
    Notify patient results are ready.
    recommendation must be generic — no clinical interpretation.
    """
```

**WhatsApp API call:**
```python
url = f"https://graph.facebook.com/v19.0/{settings.whatsapp_phone_id}/messages"
headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
payload = {
    "messaging_product": "whatsapp",
    "to": phone_number,
    "type": "text",
    "text": {"body": message},
}
# Use httpx.AsyncClient — not requests
```

**Acceptance criteria:**
- All functions use `httpx.AsyncClient`
- Failed API calls log the error, return False, never raise
- `send_welcome_message` output is readable numbered Spanish list
- Tests mock HTTP calls and verify payload structure

---

## Task 4 — Internal notification endpoint

Implement `POST /bot/internal/notify` in `apps/bot/main.py`.

**Contract:** ARQUITECTURA.md → "API → Bot (internal notifications)"

**Logic by notification_type:**

`welcome`:
- Call `send_welcome_message()` with payload data
- Call `session_service.save_session()` — `bot_mode` derived from payload

`turn_ready`:
- Call `send_turn_notification()`
- Call `session_service.update_session_step()`

`results_ready`:
- Call `send_results_notification()`
- Call `session_service.delete_session()` — visit is over

`wait_time_updated`:
- Only send if `estimated_wait_minutes` delta > 5 minutes vs current session
- Call `send_text_message()` with updated estimate
- Avoids spamming patient for small fluctuations

**Authentication:**
Validate `Authorization: Bearer {token}` header against `settings.internal_bot_token`.
Return 401 if missing or wrong — before processing anything.

**Acceptance criteria:**
- Each notification type triggers the correct service function
- Unknown types return 400 `{"error": "...", "code": "UNKNOWN_NOTIFICATION_TYPE"}`
- Wrong token returns 401
- `wait_time_updated` only sends if delta > 5 minutes
- Tests cover all four types plus auth failure

---

## Task 5 — Incoming WhatsApp message handler

Implement `POST /bot/webhook` in `apps/bot/main.py`.

**Meta's message payload structure:**
```json
{
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "from": "521234567890",
          "type": "text",
          "text": {"body": "patient message here"}
        }]
      }
    }]
  }]
}
```

**Logic:**
1. Parse body. If `messages` is missing or empty, return 200 silently.
2. If message type is not "text", return 200 silently (ignore media, etc).
3. Extract `phone_number` from `message["from"]`.
4. Call `session_service.get_session(phone_number)`.
5. If no session: `send_text_message(phone_number, "No tenemos una visita activa para tu número. Por favor regístrate en recepción.")` then return 200.
6. Call `GET {API_BASE_URL}/api/v1/visits/{visit_id}/context`.
7. Build Claude API messages with system prompt + visit context + patient message.
8. Call Claude API. Extract text response.
9. Call `send_text_message(phone_number, response)`.
10. Return 200.

**Important:** always return 200 to Meta. If you return anything else,
Meta will retry the webhook repeatedly.

**Claude API system prompt — use exactly this:**
```
You are SaludCopilot, a patient assistant for Salud Digna clinics.
You help patients navigate their visit: study sequence, wait times,
preparation instructions, and general wellness information.

STRICT RULES — never violate these under any circumstances:
- Never interpret, diagnose, or explain what medical results mean clinically.
- Never recommend specific medications, treatments, or dosages.
- If asked about results interpretation, respond only with:
  "Para interpretar tus resultados, consulta con un médico."
- Answer only in Spanish.
- Be brief, warm, and clear. Maximum 3 sentences per response.

Current patient context:
{context_json}
```

**Acceptance criteria:**
- Returns 200 for ALL incoming requests without exception
- Non-text messages silently ignored
- Patients without session get clear message in Spanish
- Claude system prompt is always included, never skipped
- Tests mock API call, Claude call, and WhatsApp send

---

## Task 6 — Proactive mode: appointment confirmation and reminder

Create `apps/bot/services/reminder_service.py`.

Triggered by the API when an appointment is booked or 24h before it.
The bot only sends — scheduling is the API's responsibility.

```python
async def send_appointment_confirmation(
    phone_number: str,
    patient_name: str,
    appointment_date: str,       # human readable: "lunes 7 de abril a las 10:30"
    study_names: list[str],
    preparation_instructions: list[str],
) -> bool:
    """
    Send confirmation + preparation instructions at booking time.
    preparation_instructions: ["Ayuno de 8 horas", "No usar desodorante", ...]
    """

async def send_appointment_reminder(
    phone_number: str,
    patient_name: str,
    appointment_date: str,
    preparation_instructions: list[str],
) -> bool:
    """
    Send 24h reminder. Same format as confirmation but shorter intro.
    """
```

**Acceptance criteria:**
- Messages formatted in clear readable Spanish
- Preparation instructions as numbered list
- Both functions return False on failure, never raise
- Tests verify message formatting

---

## Do not implement yet

- Read receipts or delivery confirmation tracking
- Media / document message handling
- Multi-language support
- Rate limiting per phone number
