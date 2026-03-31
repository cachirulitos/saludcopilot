# PROMPTS_CODING.md — SaludCopilot
# Prompts de programación paso a paso

Instrucciones: copia el prompt completo de cada paso y pégalo en Claude.
No saltes pasos. No combines dos pasos en un solo prompt.
Cuando Claude entregue el código, corre el checklist de revisión correspondiente
antes de continuar al siguiente prompt.

---

## PASO 0 — Contexto inicial (ejecutar UNA VEZ al inicio de cada sesión)

```
Eres el programador del proyecto SaludCopilot. Tu rol es implementar
exactamente lo que se te indica, sin agregar funcionalidad extra,
sin cambiar decisiones de arquitectura ya tomadas, y sin refactorizar
código que no sea parte de la tarea actual.

Lee estos archivos en orden:
1. CLAUDE.md
2. ARQUITECTURA.md  
3. ADVERTENCIAS.md

Cuando termines confirma con exactamente este formato:
"Contexto cargado. Módulo activo: [nombre]. Tarea actual: [Task N — nombre]."

No escribas ningún código todavía.
```

---

## PASO 1 — Rules Engine: setup.py (resuelve ADVERTENCIA 1)

```
Crea el archivo packages/rules_engine/setup.py con exactamente este contenido:

from setuptools import setup, find_packages

setup(
    name="rules_engine",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.12",
)

Luego agrega esta línea al FINAL de apps/api/requirements.txt:
-e ../../packages/rules_engine

Luego crea packages/rules_engine/src/rules_engine/__init__.py vacío.

Verifica que el import funciona corriendo:
cd apps/api
pip install -e ../../packages/rules_engine
python -c "from rules_engine.engine import calculate_sequence; print('OK')"

Muéstrame el output del comando python.
```

---

## PASO 2 — Rules Engine: revisar y completar engine.py

```
Abre packages/rules_engine/src/engine.py.

El archivo ya existe con una implementación inicial.
Necesito que lo revises y completes lo siguiente:

1. El dataclass Study debe tener estos campos exactos:
   - id: str
   - type: str
   - requires_fasting: bool = False
   - is_urgent: bool = False
   - has_appointment: bool = False

2. La función calculate_sequence debe manejar correctamente
   TODAS estas reglas del documento operativo de Salud Digna:
   - R-00: urgentes primero, luego con cita, luego sin cita
   - R-01: papanicolaou antes que ultrasonido_transvaginal
   - R-02: en combinación VPH + papanicolaou + cultivo_vaginal → papanicolaou primero
   - R-03: densitometria antes que tomografia o resonancia
   - R-04: laboratorio con requires_fasting=True antes que ultrasonido
   - R-05: estudios sin preparación antes que estudios con preparación

3. Cada PasoSecuencia debe incluir rule_applied (el código R-XX o None)
   y razon (string legible en español explicando por qué ese orden).

4. El tiempo estimado usa: 15 minutos por estudio + 5 minutos de traslado entre áreas.

Muéstrame el archivo completo resultante.
```

---

## PASO 3 — Rules Engine: tests completos

```
Crea packages/rules_engine/tests/test_engine.py con tests para
CADA UNA de las reglas. Usa esta estructura exacta por test:

def test_[codigo_regla]_[descripcion_especifica]():
    # Arrange
    estudios = [...]
    
    # Act
    resultado = calculate_sequence(estudios)
    
    # Assert
    tipos = [p.estudio.type for p in resultado.pasos]
    assert ...

Tests requeridos (uno por comportamiento):
1. test_r00_urgent_patient_goes_first
2. test_r00_appointment_patient_before_walkin
3. test_r01_papanicolaou_before_transvaginal_ultrasound
4. test_r02_papanicolaou_first_in_vph_cultivo_combination
5. test_r03_densitometry_before_tomography
6. test_r03_densitometry_before_resonance
7. test_r04_fasting_lab_before_ultrasound
8. test_r04_non_fasting_lab_does_not_trigger_rule
9. test_r05_no_preparation_before_preparation_required
10. test_single_study_returns_that_study
11. test_empty_input_returns_empty_sequence
12. test_time_estimate_two_studies_equals_35_minutes
13. test_rule_applied_code_stored_in_step
14. test_reason_is_in_spanish

Corre los tests y muéstrame el output completo de pytest.
Todos deben pasar en verde.
```

---

## PASO 4 — API: SQLAlchemy models

```
Crea apps/api/app/models/models.py

Implementa EXACTAMENTE estos 9 modelos basándote en ARQUITECTURA.md
sección "Database schema":

Patient, Clinic, ClinicalArea, Visit, VisitStep,
Notification, ClinicalRule, WaitTimeEstimate, PatientEvent

Reglas estrictas:
- SQLAlchemy 2.0 style: usa Mapped y mapped_column, NUNCA Column legacy
- Todos los PKs: UUID con default=uuid.uuid4
- Todos los timestamps: DateTime(timezone=True) con server_default=func.now()
- PatientEvent NO tiene updated_at — es append-only por diseño
- Los ENUMs de Python van ANTES de los modelos que los usan
- Cada FK tiene su relationship() en ambos lados
- Cada modelo tiene __repr__ que muestra id y un campo legible

Los ENUMs necesarios son:
- VisitStatus: pending, in_progress, completed, cancelled
- VisitStepStatus: pending, in_progress, completed
- NotificationType: welcome, turn_ready, turn_approaching, results_ready, wait_time_updated
- NotificationStatus: sent, delivered, failed
- RuleType: order, priority, restriction

Al terminar corre:
cd apps/api
python -c "from app.models.models import Patient, Visit, VisitStep, ClinicalArea, ClinicalRule; print('All models imported OK')"

Muéstrame el output.
```

---

## PASO 5 — API: Alembic migration

```
Configura Alembic para que detecte los modelos correctamente.

1. Abre apps/api/migrations/env.py
   Reemplaza la línea de importación de Base por:
   from app.models.models import Base
   from app.core.config import settings
   Asegúrate que target_metadata = Base.metadata

2. Corre:
   cd apps/api
   alembic revision --autogenerate -m "initial_schema"

3. Muéstrame el contenido del archivo generado en migrations/versions/

4. Si el archivo se ve correcto (tiene create_table para las 9 tablas), corre:
   alembic upgrade head

5. Muéstrame el output completo de alembic upgrade head.

Si hay errores en cualquier paso, muéstrame el error completo
antes de intentar corregirlo.
```

---

## PASO 6 — API: Schemas Pydantic

```
Crea apps/api/app/schemas/schemas.py

Necesito schemas para los contratos definidos en ARQUITECTURA.md.
Usa Pydantic v2 (BaseModel de pydantic).

Schemas de request (entrada):
- CheckInRequest: phone_number (str, E.164 format), clinic_id (UUID),
  study_ids (list[UUID]), has_appointment (bool), is_urgent (bool)
- OccupancyUpdateRequest: people_count (int, ge=0), timestamp (datetime)
- AdvanceStepRequest: sin campos (solo el visit_id en la ruta)

Schemas de response (salida):
- SequenceStepResponse: order (int), area_name (str),
  estimated_wait_minutes (int), rule_applied (str | None)
- CheckInResponse: visit_id (UUID), patient_id (UUID),
  sequence (list[SequenceStepResponse]), total_estimated_minutes (int)
- VisitContextResponse: visit_id (UUID), patient_name (str),
  current_step (SequenceStepResponse), remaining_steps (list[SequenceStepResponse]),
  total_estimated_minutes (int)
- OccupancyResponse: wait_time_estimate_minutes (int)
- WaitTimeEstimateResponse: area_id (UUID), estimated_wait_minutes (int),
  current_queue_length (int), people_in_area (int), updated_at (datetime)
- ErrorResponse: error (str), code (str)

Valida que todos los campos tienen tipos correctos.
Muéstrame el archivo completo.
```

---

## PASO 7 — API: Check-in endpoint

```
Implementa POST /api/v1/visits/check-in en apps/api/app/routers/visitas.py

Lógica exacta paso a paso:
1. Valida el request con CheckInRequest schema
2. Busca Patient por phone_number en DB. Si no existe, crea uno nuevo.
3. Crea Visit con status=pending, has_appointment y is_urgent del request
4. Para cada study_id: busca ClinicalArea en DB. Si alguno no existe,
   retorna 404 con {"error": "Area not found", "code": "AREA_NOT_FOUND"}
5. Construye lista de objetos Study para el rules engine:
   Study(id=str(area.id), type=area.study_type,
         requires_fasting=(area.study_type == "laboratorio"),
         is_urgent=request.is_urgent,
         has_appointment=request.has_appointment)
6. Llama: resultado = calculate_sequence(studies)
7. Crea un VisitStep por cada paso del resultado:
   - step_order = paso.orden
   - clinical_area_id = UUID del área correspondiente
   - status = VisitStepStatus.pending
   - rule_applied = paso.regla_aplicada
   - estimated_wait_minutes = 15 (placeholder hasta integrar ML)
8. Crea PatientEvent con event_type="arrival", visit_id, metadata={}
9. Push visit_id a Redis: ZADD queue:{primer_area_id} {timestamp} {visit_id}
10. Retorna 201 con CheckInResponse

Para Redis usa: redis_client = redis.from_url(settings.redis_url)

Muéstrame el archivo completo de visitas.py.
Luego prueba con curl:
curl -X POST http://localhost:8000/api/v1/visits/check-in \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"+521234567890","clinic_id":"CLINIC_UUID","study_ids":["AREA_UUID"],"has_appointment":false,"is_urgent":false}'
```

---

## PASO 8 — API: Visit context endpoint

```
Agrega GET /api/v1/visits/{visit_id}/context al archivo visitas.py

Lógica exacta:
1. Busca Visit por visit_id. Si no existe: 404 VISIT_NOT_FOUND
2. Carga Patient relacionado
3. Carga todos los VisitSteps ordenados por step_order
4. Identifica current_step: primer step donde status != completed
   Si todos están completed: current_step es el último
5. Para current_step: busca WaitTimeEstimate por clinical_area_id
   Si no existe: usa estimated_wait_minutes del VisitStep
6. remaining_steps = todos los steps con status=pending excluyendo el current
7. total_estimated_minutes = suma de estimated_wait_minutes de current + remaining

Retorna VisitContextResponse.

Prueba:
curl http://localhost:8000/api/v1/visits/{VISIT_ID}/context
Debe retornar 200 con el contexto de la visita recién creada en el paso anterior.
Muéstrame el output.
```

---

## PASO 9 — API: Occupancy endpoint

```
Implementa POST /api/v1/areas/{area_id}/occupancy en apps/api/app/routers/areas.py

Lógica exacta:
1. Busca ClinicalArea por area_id. Si no existe: 404 AREA_NOT_FOUND
2. Guarda en Redis: SET occupancy:{area_id} {people_count} EX 30
3. Obtiene queue length de Redis: ZCARD queue:{area_id}
4. Calcula estimado (placeholder hasta integrar ML):
   base_times = {"laboratorio": 15, "ultrasonido": 20, "rayos_x": 12,
                 "electrocardiograma": 8, "papanicolaou": 10,
                 "densitometria": 15, "tomografia": 25}
   base = base_times.get(area.study_type, 15)
   estimated = base + (people_count * 3) + (queue_length * 5)
5. Upsert WaitTimeEstimate:
   Si existe: actualiza estimated_minutes, people_in_area, updated_at
   Si no existe: crea nuevo
6. Retorna OccupancyResponse con wait_time_estimate_minutes

Prueba:
curl -X POST http://localhost:8000/api/v1/areas/{AREA_ID}/occupancy \
  -H "Content-Type: application/json" \
  -d '{"people_count": 5, "timestamp": "2026-04-07T10:00:00Z"}'
Muéstrame el output.
```

---

## PASO 10 — API: Advance step endpoint

```
Agrega POST /api/v1/visits/{visit_id}/advance-step al archivo visitas.py

Lógica exacta:
1. Busca Visit. Si no existe: 404 VISIT_NOT_FOUND
2. Busca VisitStep con status=in_progress. 
   Si no hay ninguno: busca el primer step con status=pending.
   Si no hay ninguno: 400 con {"error": "No steps to advance", "code": "NO_STEPS"}
3. Marca current_step como completed:
   status = completed
   completed_at = now()
   actual_wait_minutes = minutos entre started_at y now()
4. Crea PatientEvent: event_type="step_completed",
   metadata={"area": current_area_name, "actual_wait": actual_wait_minutes}
5. Busca el siguiente VisitStep con status=pending (step_order = current + 1)
6. Si existe next_step:
   - Marca como in_progress, started_at = now()
   - Remueve visit de Redis: ZREM queue:{current_area_id} {visit_id}
   - Agrega a Redis: ZADD queue:{next_area_id} {timestamp} {visit_id}
7. Si NO existe next_step (último paso completado):
   - Visit.status = completed, completed_at = now()
   - Crea PatientEvent: event_type="visit_completed"
   - Remueve visit de Redis: ZREM queue:{current_area_id} {visit_id}
8. Retorna 200 con el estado actualizado de la visita

Muéstrame el archivo completo de visitas.py al terminar.
```

---

## PASO 11 — API: Wait time estimate endpoint

```
Agrega GET /api/v1/areas/{area_id}/wait-time-estimate en areas.py

Lógica exacta:
1. Busca ClinicalArea. Si no existe: 404 AREA_NOT_FOUND
2. Busca WaitTimeEstimate por clinical_area_id
   Si no existe: retorna estimado de 15 minutos por defecto
3. Obtiene queue length de Redis: ZCARD queue:{area_id}
4. Retorna WaitTimeEstimateResponse con todos los campos

Luego agrega GET /api/v1/areas/ que retorna todas las áreas activas
de una clínica. Query param: clinic_id (UUID, requerido).
Response: lista de ClinicalArea con id, name, study_type.

Estos dos endpoints los necesita el dashboard y el CV worker.
Muéstrame el archivo areas.py completo.
```

---

## PASO 12 — API: WebSocket para dashboard

```
Crea apps/api/app/routers/dashboard.py

Implementa:

1. Un registry de conexiones activas:
   _connections: dict[str, list[WebSocket]] = {}

2. El endpoint WebSocket:
   @router.websocket("/ws/dashboard/{clinic_id}")
   async def dashboard_websocket(websocket: WebSocket, clinic_id: str)
   - Acepta la conexión
   - Agrega a _connections[clinic_id]
   - Loop: receive_text() para mantener viva la conexión
   - En WebSocketDisconnect: remueve de _connections

3. La función de broadcast:
   async def broadcast_to_clinic(clinic_id: str, event: dict) -> None
   - Itera sobre _connections.get(clinic_id, [])
   - send_json a cada conexión
   - Si falla una conexión: la remueve silenciosamente (no lanza)

4. Importa y llama broadcast_to_clinic en:
   - POST /areas/{area_id}/occupancy → evento "wait_time_updated"
     data: {"estimated_minutes": N, "people_count": N}
   - POST /visits/{visit_id}/advance-step → evento "visit_updated"
     data: {"status": nuevo_status, "current_area": nombre_area}

5. Registra el router en main.py:
   from app.routers import dashboard
   app.include_router(dashboard.router, tags=["Dashboard"])

Muéstrame dashboard.py completo y los cambios en areas.py y visitas.py.
```

---

## PASO 13 — API: Notification service (trigger al bot)

```
Crea apps/api/app/services/notification_service.py

Implementa una sola función:

async def trigger_bot_notification(
    visit_id: str,
    notification_type: str,
    payload: dict,
) -> bool:
    """
    Envía trigger de notificación al bot vía HTTP.
    Nunca lanza excepciones — bot failure no debe romper el flujo del API.
    Retorna True si el bot respondió 200, False en cualquier otro caso.
    """

URL: settings.bot_base_url + "/bot/internal/notify"
Header: Authorization: Bearer {settings.internal_bot_token}
Body: {"visit_id": visit_id, "notification_type": notification_type, "payload": payload}
Timeout: 5 segundos
En cualquier Exception: log el error, retorna False

Agrega a config.py:
bot_base_url: str = "http://localhost:8001"
internal_bot_token: str = "saludcopilot-internal-token-change-in-prod"

Luego llama trigger_bot_notification desde:
1. POST /visits/check-in → notification_type="welcome"
   payload = CheckInResponse convertido a dict
2. POST /visits/{id}/advance-step → notification_type="turn_ready"
   payload = {"area_name": next_area_name, "estimated_wait_minutes": N,
              "position_in_queue": ZRANK de Redis}

Muéstrame notification_service.py y los cambios en los routers.
```

---

## PASO 14 — Bot: setup inicial y webhook verification

```
Crea apps/bot/main.py con una aplicación FastAPI en puerto 8001.

Implementa:

1. GET /bot/webhook — verificación de Meta:
   Query params: hub.mode, hub.verify_token, hub.challenge
   Si hub.mode == "subscribe" Y hub.verify_token == settings.whatsapp_verify_token:
     retorna hub.challenge como PlainTextResponse
   Si no: raise HTTPException(status_code=403)

2. Crea apps/bot/config.py con estos settings:
   - whatsapp_token: str
   - whatsapp_phone_id: str
   - whatsapp_verify_token: str = "saludcopilot_verify"
   - anthropic_api_key: str
   - api_base_url: str = "http://localhost:8000"
   - internal_api_token: str = "saludcopilot-internal-token-change-in-prod"
   - internal_bot_token: str = "saludcopilot-internal-token-change-in-prod"
   - redis_url: str = "redis://localhost:6379/0"
   Usa pydantic_settings.BaseSettings, env_file=".env"

3. Crea apps/bot/tests/test_webhook.py con dos tests:
   - test_verification_with_correct_token_returns_challenge
   - test_verification_with_wrong_token_returns_403

Corre los tests. Muéstrame el output de pytest.
```

---

## PASO 15 — Bot: Redis session service

```
Crea apps/bot/services/session_service.py

SESSION_TTL_SECONDS = 14400  # 4 horas

Implementa estas 4 funciones async con Redis:

async def save_session(
    phone_number: str,
    visit_id: str,
    bot_mode: str,
    current_step_order: int,
) -> None:
    key = f"session:{phone_number}"
    data = {
        "visit_id": visit_id,
        "bot_mode": bot_mode,
        "current_step_order": current_step_order,
        "awaiting_preparation_confirmation": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis.set(key, json.dumps(data), ex=SESSION_TTL_SECONDS)

async def get_session(phone_number: str) -> dict | None:
    # Retorna None si no existe, no lanza

async def delete_session(phone_number: str) -> None:
    # Borra la sesión completa

async def update_session_step(phone_number: str, new_step_order: int) -> None:
    # Actualiza current_step_order SIN resetear el TTL
    # Usa GETEX para obtener TTL restante, luego SET con ese TTL

async def set_awaiting_preparation(phone_number: str, value: bool) -> None:
    # Actualiza solo el campo awaiting_preparation_confirmation
    # Sin resetear TTL

Crea apps/bot/tests/test_session_service.py con tests que mockean Redis.
Tests requeridos:
- test_save_session_sets_correct_ttl
- test_get_session_returns_none_for_missing_key
- test_update_step_preserves_ttl
- test_set_awaiting_preparation_updates_flag

Muéstrame session_service.py completo y el output de pytest.
```

---

## PASO 16 — Bot: WhatsApp message sender

```
Crea apps/bot/services/whatsapp_service.py

WHATSAPP_API_URL = "https://graph.facebook.com/v19.0/{phone_id}/messages"

Implementa estas funciones. Todas usan httpx.AsyncClient.
Todas retornan bool. Ninguna lanza excepciones.

async def send_text_message(phone_number: str, message: str) -> bool:
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message},
    }
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
    url = WHATSAPP_API_URL.format(phone_id=settings.whatsapp_phone_id)
    # POST, retorna True si status_code < 300

async def send_welcome_message(
    phone_number: str,
    patient_name: str,
    sequence: list[dict],
    total_estimated_minutes: int,
) -> bool:
    # Formatea el mensaje así:
    # "¡Hola {name}! Esta es tu secuencia de atención hoy:\n
    #  1. {area_name} — ~{estimated} min de espera\n
    #  2. ...\n
    #  ⏱ Tiempo total estimado: ~{total} minutos.\n
    #  Te avisaremos cuando sea tu turno en cada área."
    # Llama send_text_message con el mensaje formateado

async def send_turn_notification(
    phone_number: str,
    area_name: str,
    estimated_wait_minutes: int,
    position_in_queue: int,
) -> bool:
    message = (f"🔔 Tu turno en {area_name} se acerca.\n"
               f"Posición en fila: {position_in_queue}\n"
               f"Tiempo estimado: ~{estimated_wait_minutes} minutos.")
    return await send_text_message(phone_number, message)

async def send_results_notification(
    phone_number: str,
    study_name: str,
    result_url: str,
    recommendation: str,
) -> bool:
    message = (f"✅ Tus resultados de {study_name} están listos.\n"
               f"Descárgalos aquí: {result_url}\n"
               f"📋 {recommendation}")
    return await send_text_message(phone_number, message)

Crea tests que mockean httpx. Tests requeridos:
- test_send_text_message_calls_correct_url
- test_send_text_message_returns_false_on_http_error
- test_send_welcome_message_formats_sequence_correctly
- test_send_welcome_message_numbers_are_sequential

Muéstrame whatsapp_service.py y el output de pytest.
```

---

## PASO 17 — Bot: API client

```
Crea apps/bot/services/api_client.py

Implementa estas dos funciones. Ambas usan httpx.AsyncClient.
Ambas retornan dict | None. Ninguna lanza excepciones.

async def register_visit(
    phone_number: str,
    clinic_id: str,
    study_ids: list[str],
    has_appointment: bool,
    is_urgent: bool,
) -> dict | None:
    POST {settings.api_base_url}/api/v1/visits/check-in
    Authorization: Bearer {settings.internal_api_token}
    Retorna response.json() si status 201, None en cualquier otro caso.

async def get_visit_context(visit_id: str) -> dict | None:
    GET {settings.api_base_url}/api/v1/visits/{visit_id}/context
    Authorization: Bearer {settings.internal_api_token}
    Retorna response.json() si status 200, None en cualquier otro caso.

En ambas funciones: timeout=10.0, captura Exception, log y retorna None.

Muéstrame api_client.py completo.
```

---

## PASO 18 — Bot: Internal notification endpoint

```
Agrega POST /bot/internal/notify a apps/bot/main.py

Autenticación: valida Authorization: Bearer {settings.internal_bot_token}
Si falta o es incorrecto: retorna 401 inmediatamente.

Request body: {"visit_id": str, "notification_type": str, "payload": dict}

Lógica por notification_type:

"welcome":
  1. Extrae patient_phone_number del payload (preguntar al API con get_visit_context)
  2. Llama send_welcome_message con los datos del payload
  3. Determina bot_mode: "proactive" si payload contiene has_appointment=True, else "reactive"
  4. Llama session_service.save_session(phone, visit_id, bot_mode, step_order=1)

"turn_ready":
  1. Obtiene contexto del API con get_visit_context(visit_id)
  2. Extrae phone del contexto
  3. Llama send_turn_notification
  4. Llama session_service.update_session_step(phone, nuevo_step)

"results_ready":
  1. Obtiene contexto del API
  2. Llama send_results_notification
  3. Llama session_service.delete_session(phone)

"wait_time_updated":
  1. Obtiene sesión actual de Redis
  2. Solo envía si delta > 5 minutos vs tiempo anterior en sesión
  3. Si envía: llama send_text_message con nuevo tiempo

Cualquier otro tipo: retorna 400 {"error": "Unknown type", "code": "UNKNOWN_NOTIFICATION_TYPE"}

Retorna siempre 200 {"status": "sent"} si llegó hasta el final sin error 4xx.

Muéstrame main.py completo.
```

---

## PASO 19 — Bot: Preparation validation flow

```
Esta es la feature nueva de validación de preparación.

Modifica el handler de "welcome" en POST /bot/internal/notify:

Antes de enviar el mensaje de bienvenida, verifica si algún estudio
en la secuencia requiere preparación Y has_appointment es True.

Los estudios con preparación requerida son:
PREPARATION_REQUIRED = {
    "laboratorio": "ayuno de 8 horas",
    "papanicolaou": "no usar desodorante y abstinencia sexual 48 horas previas",
    "tomografia": "preparación específica indicada por el médico",
    "resonancia": "preparación específica indicada por el médico",
}

Si aplica:
1. Llama set_awaiting_preparation(phone, True) en Redis
2. Envía primero el mensaje de verificación:
   "¡Hola {name}! Antes de registrarte, confirma que completaste:
    • {preparacion_del_estudio}
    ¿Lo completaste? Responde Sí o No."
3. NO envíes el mensaje de bienvenida todavía — espera la respuesta

El welcome message se envía después cuando el paciente confirma.

Agrega el handler de respuesta de preparación en POST /bot/webhook:

Al inicio del handler de mensajes entrantes, ANTES de pasar a Claude:
1. Obtiene sesión del Redis
2. Si session["awaiting_preparation_confirmation"] == True:
   a. Borra el flag INMEDIATAMENTE: await set_awaiting_preparation(phone, False)
   b. Si el mensaje contiene "sí", "si", "yes", "claro", "listo":
      - Envía mensaje de bienvenida completo ahora
      - PatientEvent: event_type="preparation_confirmed"
   c. Si contiene "no", "no pude", "no completé":
      - Envía: "Entendido. Para obtener resultados precisos te recomendamos
               reagendar tu cita. Puedes llamar a la clínica o visitar
               saluddigna.com para agendar."
      - PatientEvent: event_type="preparation_failed_rescheduled"
   d. En cualquier caso: retorna 200 sin pasar a Claude

Muéstrame los cambios en main.py.
```

---

## PASO 20 — Bot: Incoming WhatsApp message handler

```
Implementa POST /bot/webhook en apps/bot/main.py

REGLA CRÍTICA: este endpoint SIEMPRE retorna 200.
Si retorna cualquier otro código, Meta reintentará el mensaje indefinidamente.

Lógica completa:

1. Parsea el body. Si no tiene entry[0].changes[0].value.messages: retorna 200.
2. Si message.type != "text": retorna 200 silenciosamente.
3. Extrae phone_number = message["from"], text = message["text"]["body"]

4. Redis lock para evitar race condition (ver ADVERTENCIAS.md):
   lock_key = f"processing:{phone_number}"
   acquired = await redis.set(lock_key, "1", nx=True, ex=10)
   if not acquired: retorna 200 (ya se está procesando)

5. Obtiene sesión: session = await get_session(phone_number)
6. Si no hay sesión: envía "No tenemos una visita activa registrada para tu número. 
   Por favor acércate a recepción para registrarte." Retorna 200.

7. Si session["awaiting_preparation_confirmation"] == True:
   Maneja como respuesta de preparación (ver PASO 19). Retorna 200.

8. Obtiene contexto: context = await get_visit_context(session["visit_id"])

9. Llama Claude API:
   System prompt (exactamente este texto):
   "Eres SaludCopilot, asistente del paciente en clínicas Salud Digna.
   Ayudas al paciente a navegar su visita: secuencia de estudios,
   tiempos de espera, instrucciones de preparación e información general.

   REGLAS ESTRICTAS — nunca las violes:
   - Nunca interpretes, diagnostiques ni expliques qué significan los resultados clínicamente.
   - Nunca recomiendes medicamentos, tratamientos ni dosis específicas.
   - Si te preguntan sobre resultados, responde ÚNICAMENTE: 'Para interpretar tus resultados, consulta con un médico.'
   - Responde SIEMPRE en español.
   - Sé breve, cálido y claro. Máximo 3 oraciones por respuesta.

   Contexto actual del paciente:
   {context_json}"

   User message: text del paciente
   Model: claude-opus-4-5 (o el disponible)
   Max tokens: 200

10. Envía la respuesta al paciente con send_text_message.

11. En el bloque finally: await redis.delete(lock_key)

12. Retorna 200.

Muéstrame main.py completo al terminar.
```

---

## PASO 21 — Bot: Proactive appointment reminders

```
Crea apps/bot/services/reminder_service.py

async def send_appointment_confirmation(
    phone_number: str,
    patient_name: str,
    appointment_date: str,
    study_names: list[str],
    preparation_instructions: list[str],
) -> bool:
    message = (
        f"✅ Cita confirmada, {patient_name}.\n"
        f"📅 {appointment_date}\n"
        f"🔬 Estudios: {', '.join(study_names)}\n\n"
        f"📋 Preparación requerida:\n"
        + "\n".join(f"• {inst}" for inst in preparation_instructions)
        + "\n\nTe enviaremos un recordatorio 24 horas antes."
    )
    return await whatsapp_service.send_text_message(phone_number, message)

async def send_appointment_reminder(
    phone_number: str,
    patient_name: str,
    appointment_date: str,
    preparation_instructions: list[str],
) -> bool:
    message = (
        f"⏰ Recordatorio, {patient_name}.\n"
        f"Mañana tienes cita: {appointment_date}\n\n"
        f"📋 No olvides:\n"
        + "\n".join(f"• {inst}" for inst in preparation_instructions)
    )
    return await whatsapp_service.send_text_message(phone_number, message)

Muéstrame reminder_service.py completo.
```

---

## PASO 22 — CV: Config y people detector

```
Crea apps/cv/config.py:

from pydantic_settings import BaseSettings
import json

class CVSettings(BaseSettings):
    api_base_url: str = "http://localhost:8000"
    internal_cv_token: str = "saludcopilot-internal-token-change-in-prod"
    camera_index: int = 0
    capture_interval_seconds: int = 5
    yolo_model_name: str = "yolov8n.pt"
    confidence_threshold: float = 0.4
    target_class_id: int = 0
    camera_to_area_mapping: str = "{}"

    @property
    def area_mapping(self) -> dict:
        return json.loads(self.camera_to_area_mapping)

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = CVSettings()

---

Luego crea apps/cv/models/people_detector.py:

class PeopleDetector:
    def __init__(self, model_name: str, confidence_threshold: float) -> None:
        from ultralytics import YOLO
        self.model = YOLO(model_name)
        self.confidence_threshold = confidence_threshold
        self.target_class_id = 0

    def count_people_in_frame(self, frame: np.ndarray) -> int:
        results = self.model(frame, verbose=False)
        return sum(
            1 for box in results[0].boxes
            if int(box.cls) == self.target_class_id
            and float(box.conf) >= self.confidence_threshold
        )

    def count_people_with_annotated_frame(
        self, frame: np.ndarray
    ) -> tuple[int, np.ndarray]:
        results = self.model(frame, verbose=False)
        count = sum(
            1 for box in results[0].boxes
            if int(box.cls) == self.target_class_id
            and float(box.conf) >= self.confidence_threshold
        )
        annotated = results[0].plot()
        return count, annotated

Crea apps/cv/tests/test_people_detector.py con:
- test_count_returns_integer_for_black_frame
- test_count_returns_zero_for_empty_frame
Muéstrame ambos archivos y el output de pytest.
```

---

## PASO 23 — CV: Count publisher y main loop

```
Crea apps/cv/services/count_publisher.py:

async def publish_people_count(area_id: str, people_count: int) -> int | None:
    from datetime import datetime, timezone
    url = f"{settings.api_base_url}/api/v1/areas/{area_id}/occupancy"
    headers = {"Authorization": f"Bearer {settings.internal_cv_token}"}
    payload = {
        "people_count": people_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"Area {area_id}: {people_count} personas | Espera est: {data['wait_time_estimate_minutes']} min")
                return data["wait_time_estimate_minutes"]
            print(f"Error publicando conteo: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error de conexión al publicar conteo: {e}")
        return None

---

Luego crea apps/cv/main.py:

import argparse, asyncio, sys
import cv2
import numpy as np
from cv.models.people_detector import PeopleDetector
from cv.services.count_publisher import publish_people_count
from cv.config import settings

DEMO_PATTERN = [3,3,3,4,4,4,5,5,5,6,6,6,7,7,7,8,8,8,2,2,2]

async def run_loop(demo_mode: bool = False):
    detector = PeopleDetector(settings.yolo_model_name, settings.confidence_threshold)
    area_mapping = settings.area_mapping

    if not area_mapping:
        print("ERROR: CAMERA_TO_AREA_MAPPING está vacío. Configura el .env con los UUIDs de las áreas.")
        sys.exit(1)

    cap = None
    demo_index = 0

    if not demo_mode:
        cap = cv2.VideoCapture(settings.camera_index)
        if not cap.isOpened():
            print(f"Error: no se pudo abrir la cámara (índice {settings.camera_index}). Verifica que esté conectada.")
            sys.exit(1)

    print(f"SaludCopilot CV Worker iniciado. Modo: {'DEMO' if demo_mode else 'CÁMARA REAL'}")

    try:
        while True:
            if demo_mode:
                count = DEMO_PATTERN[demo_index % len(DEMO_PATTERN)]
                demo_index += 1
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, f"DEMO MODE — {count} personas detectadas",
                            (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                annotated = frame
            else:
                ret, frame = cap.read()
                if not ret:
                    print("Advertencia: frame no capturado, reintentando...")
                    await asyncio.sleep(1)
                    continue
                count, annotated = detector.count_people_with_annotated_frame(frame)

            for camera_idx, area_id in area_mapping.items():
                await publish_people_count(area_id, count)

            cv2.imshow("SaludCopilot — Sala de espera", annotated)
            cv2.waitKey(1)
            await asyncio.sleep(settings.capture_interval_seconds)

    except KeyboardInterrupt:
        print("\nCV Worker detenido.")
    finally:
        if cap:
            cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_loop(demo_mode=args.demo))

Muéstrame ambos archivos completos.
```

---

## PASO 24 — ML: Data loader y feature engineering

```
Crea ml/src/data_loader.py con las 4 funciones:
load_ventas(), load_promedios_espera(), load_consultorios(), validate_dataframe()

Reglas:
- load_ventas: parsea FechaServicio como datetime con pd.to_datetime()
  Verifica que incluye componente de tiempo (no solo fecha)
  Columnas requeridas: idSucursal, idEstudio, idPaciente, FechaServicio, Estatus, idReservacion
- Cada loader llama validate_dataframe antes de retornar
- validate_dataframe loga shape y null counts de cada columna requerida

---

Luego crea ml/src/feature_engineering.py:

FEATURE_COLUMNS = [
    "hour_of_day", "day_of_week", "is_weekend",
    "study_type_id", "clinic_id", "simultaneous_capacity",
    "current_queue_length", "has_appointment",
]

def build_training_features(ventas, promedios, consultorios) -> tuple[pd.DataFrame, dict]:
    # Extrae features de FechaServicio
    ventas["hour_of_day"] = ventas["FechaServicio"].dt.hour
    ventas["day_of_week"] = ventas["FechaServicio"].dt.dayofweek
    ventas["is_weekend"] = (ventas["day_of_week"] >= 5).astype(int)
    ventas["has_appointment"] = ventas["idReservacion"].notna().astype(int)
    ventas["current_queue_length"] = 0  # placeholder, se actualiza en inferencia

    # Label encoding
    study_encoding = {v: i for i, v in enumerate(ventas["idEstudio"].unique())}
    clinic_encoding = {v: i for i, v in enumerate(ventas["idSucursal"].unique())}
    ventas["study_type_id"] = ventas["idEstudio"].map(study_encoding)
    ventas["clinic_id"] = ventas["idSucursal"].map(clinic_encoding)

    # Join con consultorios y promedios
    # ... (implementa el merge)

    encoding_maps = {"study_type": study_encoding, "clinic": clinic_encoding}
    return features_df[FEATURE_COLUMNS + ["waiting_time_minutes"]], encoding_maps

def extract_inference_features(hour_of_day, day_of_week, study_type_raw_id,
    clinic_raw_id, simultaneous_capacity, current_queue_length,
    has_appointment, encoding_maps) -> pd.DataFrame:
    # Usa FEATURE_COLUMNS para garantizar mismo orden
    # Retorna DataFrame de una fila

Muéstrame ambos archivos completos.
```

---

## PASO 25 — ML: Training, serialización e inferencia

```
Crea ml/src/train.py:

HYPERPARAMETERS = {
    "n_estimators": 100,
    "max_depth": None,
    "min_samples_split": 2,
    "random_state": 42,
    "n_jobs": -1,
}

def train_model(features_df) -> tuple[RandomForestRegressor, dict]:
    X = features_df[FEATURE_COLUMNS]
    y = features_df["waiting_time_minutes"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(**HYPERPARAMETERS)
    model.fit(X_train, y_train)
    mae = mean_absolute_error(y_test, model.predict(X_test))
    r2 = r2_score(y_test, model.predict(X_test))
    print(f"MAE: {mae:.1f} min | R2: {r2:.2f} | Train: {len(X_train)} | Test: {len(X_test)}")
    return model, {"mae": mae, "r2": r2}

def save_artifacts(model, encoding_maps, output_dir):
    output_dir.mkdir(exist_ok=True)
    joblib.dump(model, output_dir / "model.pkl")
    joblib.dump(encoding_maps, output_dir / "encodings.pkl")

def load_artifacts(model_dir):
    model = joblib.load(model_dir / "model.pkl")
    encodings = joblib.load(model_dir / "encodings.pkl")
    return model, encodings

---

Luego crea ml/src/predictor.py:

class WaitTimePredictor:
    def __init__(self, model_dir=MODEL_DIR):
        self.model, self.encoding_maps = load_artifacts(model_dir)
        self._median_fallback = None  # se calcula al cargar

    def predict_wait_minutes(self, hour_of_day, day_of_week, study_type_raw_id,
        clinic_raw_id, simultaneous_capacity, current_queue_length, has_appointment) -> int:
        # Si label no está en encoding: usa mediana, log warning
        features = extract_inference_features(...)
        prediction = self.model.predict(features)[0]
        return max(1, round(int(prediction)))

    @property
    def is_ready(self) -> bool:
        return self.model is not None

Muéstrame ambos archivos completos.
```

---

## PASO 26 — Dashboard: Inicialización y layout

```
Corre en apps/dashboard:
npx create-next-app@14 . --typescript --tailwind --eslint --app --no-src-dir --yes
pnpm add recharts lucide-react
pnpm add -D @types/node

Extiende tailwind.config.ts con estos colores exactos:
extend: {
  colors: {
    brand: { green: "#008A4B", blue: "#005B9F" },
    surface: { base: "#0F1117", card: "#1A1D27", border: "#2A2D3A" },
    content: { primary: "#F0F0F0", secondary: "#8B8FA8" },
    alert: { red: "#E53E3E", yellow: "#F6AD55" },
  },
}

En app/globals.css: body { background-color: #0F1117; color: #F0F0F0; }

Crea components/layout/Sidebar.tsx:
- Fondo surface-card, ancho 240px, altura 100vh, fixed
- Top: "SaludCopilot" bold brand-green + "Salud Digna" text-xs content-secondary
- Nav items con lucide-react icons: Dashboard, MapPin, Bell, Clock
- Item activo: borde izquierdo 3px brand-green + texto brand-green
- Bottom: nombre de clínica + punto verde pulsante si isConnected

Crea components/layout/TopBar.tsx:
- Altura 64px, borde inferior surface-border
- Left: título de página
- Right: reloj en tiempo real (useEffect cada segundo) + badge "EN VIVO" o "DEMO"

Muéstrame Sidebar.tsx y TopBar.tsx completos.
```

---

## PASO 27 — Dashboard: Mock data, MetricCard y AreaTable

```
Crea lib/mock-data.ts con exactamente los datos definidos en
apps/dashboard/TASK.md sección Task 3. Copia estructura exacta.

---

Crea components/ui/MetricCard.tsx:
Props: label, value, unit?, accentColor, trend?
- Fondo surface-card, borde surface-border, rounded-lg, p-6
- Borde superior 4px del color accentColor
- Label: text-sm content-secondary mb-2
- Value: text-5xl font-bold del color accentColor
- Unit: text-sm content-secondary ml-1
- Trend: si positivo → flecha ↑ verde, si negativo → flecha ↓ roja

---

Crea components/ui/AreaTable.tsx:
Columnas: Área | Pacientes en cola | 📷 Personas físicas | Espera est. | Estado
- Headers fondo surface-card, texto content-secondary
- Filas con status "saturated": fondo red-950/20
- Status badges:
  normal → bg-green-900/50 text-green-400 "Normal"
  warning → bg-yellow-900/50 text-yellow-400 "Alerta"
  saturated → bg-red-900/50 text-red-400 "Saturado"
- Columna Personas físicas: ícono Camera de lucide-react antes del número

Muéstrame los tres archivos completos.
```

---

## PASO 28 — Dashboard: Chart, AlertsPanel y WebSocket hook

```
Crea components/ui/WaitTimeChart.tsx con Recharts LineChart:
- AREA_COLORS = {"Laboratorio":"#008A4B","Ultrasonido":"#005B9F","Rayos X":"#F6AD55","Electrocardiograma":"#9F7AEA"}
- LineChart con ResponsiveContainer, CartesianGrid en #2A2D3A
- Una Line por área, type="monotone", strokeWidth=2, dot=false
- Tooltip con fondo #1A1D27, border #2A2D3A
- Legend abajo

---

Crea components/ui/AlertsPanel.tsx:
- Cada alerta: card con borde izquierdo 4px (rojo/amarillo/azul por severidad)
- Formato timestamp: "hace N minutos" actualizado cada minuto
- Orden: más reciente primero
- Botón "Limpiar resueltas" remueve alerts con severity != critical
- Empty state: CheckCircle2 icon + "Sin alertas activas" en brand-green

---

Crea lib/websocket-client.ts:
class DashboardWebSocketClient {
  connect(clinicId, onEvent, onStatusChange): void
    URL: ws://localhost:8000/ws/dashboard/{clinicId}
    onStatusChange(true/false) para el badge EN VIVO/DEMO
    onError: reconectar después de 3 segundos
    onClose: reconectar después de 3 segundos

  disconnect(): void
  get isConnected(): boolean
}

Crea lib/hooks/useDashboardData.ts:
export function useDashboardData(clinicId) {
  // Estado inicial con mock data
  // useEffect: conecta WebSocket on mount, desconecta on unmount
  // Maneja eventos: wait_time_updated, queue_changed, visit_updated, alert
  // Retorna: { areas, activeVisits, summary, alerts, isConnected, waitTimeHistory }
}

Muéstrame los cuatro archivos completos.
```

---

## PASO 29 — Dashboard: Wire final

```
Actualiza app/dashboard/page.tsx para usar useDashboardData:

"use client"
import { useDashboardData } from "@/lib/hooks/useDashboardData"
import MetricCard from "@/components/ui/MetricCard"
import AreaTable from "@/components/ui/AreaTable"
import WaitTimeChart from "@/components/ui/WaitTimeChart"
import AlertsPanel from "@/components/ui/AlertsPanel"

export default function DashboardPage() {
  const { areas, activeVisits, summary, alerts, isConnected, waitTimeHistory } =
    useDashboardData(process.env.NEXT_PUBLIC_CLINIC_ID ?? "default")

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Pacientes activos" value={summary.total_active_visits} accentColor="#008A4B" />
        <MetricCard label="En espera" value={summary.total_waiting_patients} accentColor="#005B9F" />
        <MetricCard label="Espera promedio" value={summary.average_wait_minutes} unit="min" accentColor="#F0F0F0" />
        <MetricCard label="Áreas en riesgo" value={summary.areas_at_risk}
          accentColor={summary.areas_at_risk > 0 ? "#E53E3E" : "#008A4B"} />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-surface-card rounded-lg p-4">
          <h2 className="text-content-secondary text-sm mb-4">Tiempos de espera — Últimos 60 min</h2>
          <WaitTimeChart history={waitTimeHistory} />
        </div>
        <AlertsPanel alerts={alerts} />
      </div>

      <AreaTable areas={areas} />
    </div>
  )
}

Corre pnpm dev y verifica que la página carga sin errores.
Muéstrame el output de la consola del navegador.
```

---

## PASO 30 — Scripts: Seed data

```
Crea scripts/seed.py

El script conecta a PostgreSQL, inserta una clínica de demo
con todas sus áreas, y al terminar imprime los UUIDs.

Clínica a crear:
  name="Salud Digna Demo CDMX"
  address="Insurgentes Sur 1234, CDMX"
  latitude=19.3910, longitude=-99.1688

Áreas a crear (una por cada study_type):
  [laboratorio, ultrasonido, rayos_x, electrocardiograma,
   papanicolaou, densitometria, tomografia]
  simultaneous_capacity según Excel de Consultorios (usa 2 como default)

Al terminar el script imprime:
================================
SEED DATA CREADO
================================
CLINIC_ID={uuid}
AREA_LABORATORIO_ID={uuid}
AREA_ULTRASONIDO_ID={uuid}
AREA_RAYOS_X_ID={uuid}
AREA_ELECTROCARDIOGRAMA_ID={uuid}
AREA_PAPANICOLAOU_ID={uuid}
AREA_DENSITOMETRIA_ID={uuid}
AREA_TOMOGRAFIA_ID={uuid}
================================
Copia CLINIC_ID a: apps/dashboard/.env.local → NEXT_PUBLIC_CLINIC_ID
Copia AREA IDs a: apps/cv/.env → CAMERA_TO_AREA_MAPPING
================================

Muéstrame scripts/seed.py completo.
Luego corre: cd apps/api && python ../../scripts/seed.py
Muéstrame el output.
```

---

## PASO 31 — Integración: ML en API

```
Crea apps/api/app/core/predictor_client.py:

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../ml"))
from src.predictor import WaitTimePredictor

_predictor = None

def get_predictor() -> WaitTimePredictor:
    global _predictor
    if _predictor is None:
        _predictor = WaitTimePredictor()
    return _predictor

---

Modifica POST /api/v1/areas/{area_id}/occupancy en areas.py:
Reemplaza el cálculo placeholder por:

from app.core.predictor_client import get_predictor
from datetime import datetime

now = datetime.now()
estimated_minutes = get_predictor().predict_wait_minutes(
    hour_of_day=now.hour,
    day_of_week=now.weekday(),
    study_type_raw_id=area.study_type,
    clinic_raw_id=str(area.clinic_id),
    simultaneous_capacity=area.simultaneous_capacity,
    current_queue_length=queue_length,
    has_appointment=False,
)

Prueba:
curl -X POST http://localhost:8000/api/v1/areas/{AREA_UUID}/occupancy \
  -d '{"people_count": 3, "timestamp": "2026-04-07T10:00:00Z"}'

El estimado debe variar basado en la hora del día y el tipo de estudio.
Muéstrame el output y los logs de la API.
```

---

## PASO 32 — Integración: End-to-end completo

```
Ejecuta el smoke test completo del PROMPTS_REVIEW.md sección "REVIEW-09".

Si algún paso falla, muéstrame el error exacto.
No intentes corregir más de un error a la vez.
Corrígelo, vuelve a correr ese paso específico, confirma que pasa,
y continúa con el siguiente paso del smoke test.

Al terminar todos los pasos: muéstrame el resumen de resultados.
```
