# PROMPTS_REVIEW.md — SaludCopilot
# Prompts de revisión y evaluación de código

Estos prompts los ejecutas en un agente separado después de ciertos pasos de código.
Cada revisión es independiente — no acumules revisiones en un solo prompt.

Cuándo ejecutar cada revisión:
- REVIEW-01 (Calidad): después de cada PASO de PROMPTS_CODING.md
- REVIEW-02 (Seguridad): después de PASO 7, 14, 18, 20
- REVIEW-03 (Performance): después de PASO 9, 10, 12, 28
- REVIEW-04 (Bot): después de PASO 19, 20, 21
- REVIEW-05 (Rules Engine): después de PASO 3
- REVIEW-06 (ML): después de PASO 25
- REVIEW-07 (Database): después de PASO 5
- REVIEW-08 (API contracts): después de PASO 13
- REVIEW-09 (Smoke test completo): antes del demo

---

## REVIEW-01 — Calidad de código general

Usar después de: cada paso de programación.

```
Eres un revisor de código senior. Tu trabajo es encontrar problemas reales,
no sugerir refactorizaciones innecesarias.

Revisa el siguiente código:
[PEGA EL CÓDIGO AQUÍ]

Evalúa SOLO estos criterios. Por cada problema encontrado:
indica la línea exacta, el problema específico, y la corrección concreta.

CRITERIOS:

1. NOMBRES EXPLÍCITOS
   ❌ Problema si: nombre de una letra (excepto i en loops), abreviaciones
      (calc, tmp, val, obj, data), nombres que requieren un comentario para entenderse
   ✅ Correcto si: el nombre describe exactamente qué contiene o qué hace

2. FUNCIONES CON UNA RESPONSABILIDAD
   ❌ Problema si: la función hace más de una cosa, tiene más de 20 líneas,
      su nombre contiene "and" o "or"
   ✅ Correcto si: puedes describir lo que hace en una sola oración sin "y"

3. DOCSTRINGS EN FUNCIONES PÚBLICAS
   ❌ Problema si: función pública sin docstring, o docstring que solo repite el nombre
   ✅ Correcto si: describe qué hace, qué recibe, qué retorna

4. MAGIC NUMBERS Y STRINGS
   ❌ Problema si: número o string literal en el código sin nombre asignado
      (excepto 0, 1, True, False en contextos obvios)
   ✅ Correcto si: TODOS los valores tienen nombres de constante en UPPER_SNAKE_CASE

5. MANEJO DE ERRORES
   ❌ Problema si: except sin logging, excepción silenciada, traceback al cliente
   ✅ Correcto si: cada except loga el error con contexto antes de manejarlo

6. CÓDIGO COMENTADO
   ❌ Problema si: existe código comentado con #
   ✅ Correcto si: no hay código comentado — si no se usa, se borra

7. CONSISTENCIA CON ARQUITECTURA
   ❌ Problema si: nombre de entidad diferente a ARQUITECTURA.md
      (Patient vs User, Visit vs Appointment, Study vs Service)
   ✅ Correcto si: todos los nombres coinciden con el lenguaje ubicuo del proyecto

Formato de respuesta:
LÍNEA N: [criterio] — [problema específico] → [corrección exacta]

Si no hay problemas en un criterio: escribe "✅ [criterio]: sin problemas"
Al final: "APROBADO" o "REQUIERE CORRECCIONES (N problemas)"
```

---

## REVIEW-02 — Seguridad

Usar después de: PASO 7 (check-in), PASO 14 (webhook), PASO 18 (notify), PASO 20 (incoming messages).

```
Eres un revisor de seguridad. Analiza el siguiente código buscando
vulnerabilidades reales en el contexto de una API médica.

[PEGA EL CÓDIGO AQUÍ]

Evalúa cada punto. Sé específico: indica línea, vulnerabilidad, impacto, corrección.

1. AUTENTICACIÓN EN ENDPOINTS INTERNOS
   Verifica que TODOS los endpoints que no son públicos validan
   Authorization: Bearer {token} ANTES de ejecutar cualquier lógica.
   ❌ Si el token se valida después de leer la DB o hacer cualquier operación.
   ❌ Si el endpoint acepta requests sin header Authorization.
   ✅ Primera línea del handler: validar token, retornar 401 si falla.

2. VALIDACIÓN DE INPUT
   Verifica que todos los campos del request body son validados por Pydantic.
   ❌ Si se lee request.body directamente sin schema de validación.
   ❌ Si un UUID se usa sin validar que es un UUID válido.
   ✅ Todos los endpoints usan schemas Pydantic como tipo del parámetro.

3. SQL INJECTION
   Verifica que no hay queries SQL construidas con concatenación de strings.
   ❌ f"SELECT * FROM visits WHERE id = '{visit_id}'"
   ✅ session.get(Visit, visit_id) o select(Visit).where(Visit.id == visit_id)

4. SECRETS HARDCODEADOS
   Busca en el código cualquier string que parezca una credencial.
   ❌ api_key = "sk-ant-api03-..." en el código fuente
   ❌ token = "EAAxxxxx" hardcodeado
   ✅ Todas las credenciales vienen de settings (variables de entorno)

5. INFORMACIÓN SENSIBLE EN ERRORES
   Verifica que los mensajes de error no exponen detalles internos.
   ❌ {"error": "psycopg2.errors.UniqueViolation: duplicate key value violates..."}
   ✅ {"error": "Patient already registered", "code": "PATIENT_EXISTS"}

6. RESTRICCIÓN MÉDICA EN EL BOT
   Si el código incluye el system prompt de Claude, verifica que contiene
   EXACTAMENTE las restricciones médicas definidas en PROMPTS_CODING.md PASO 20.
   ❌ Si las restricciones están modificadas, resumidas o ausentes.
   ✅ System prompt idéntico al definido.

7. WHATSAPP SIEMPRE RETORNA 200
   Si el código es el webhook handler de WhatsApp, verifica que
   en TODOS los caminos de ejecución (incluyendo excepciones) retorna 200.
   ❌ Si puede retornar 500, 400, o cualquier otro código por un error interno.
   ✅ Try/except global que garantiza 200 en cualquier caso.

Formato: LÍNEA N: [criterio N] — [vulnerabilidad] → [corrección]
Al final: "SEGURO" o "VULNERABILIDADES ENCONTRADAS (N críticas, N medias)"
```

---

## REVIEW-03 — Performance

Usar después de: PASO 9 (occupancy), PASO 10 (advance step), PASO 12 (WebSocket), PASO 28 (dashboard hooks).

```
Analiza el siguiente código para problemas de performance en el contexto
de una clínica con 50-100 pacientes simultáneos.

[PEGA EL CÓDIGO AQUÍ]

1. N+1 QUERIES
   ❌ Problema: loop que hace una query a la DB por cada iteración
      for step in steps: area = await session.get(ClinicalArea, step.area_id)
   ✅ Correcto: una sola query con JOIN o selectinload:
      select(VisitStep).options(selectinload(VisitStep.clinical_area))

2. LAZY LOADING EN ASYNC
   ❌ Problema: acceso a relationship sin eager loading en contexto async
      step.clinical_area.name  ← si clinical_area no fue cargado con selectinload
      Genera: MissingGreenlet error o query implícita
   ✅ Correcto: siempre usar selectinload() o joinedload() en queries async

3. REDIS SIN TTL
   ❌ Problema: SET en Redis sin EX (expiry)
      await redis.set("key", value)  ← sin EX
   ✅ Correcto: siempre con TTL apropiado
      await redis.set("key", value, ex=TTL_SECONDS)

4. YOLO EN CADA FRAME (solo para cv/main.py)
   ❌ Problema: YOLO(model_name) dentro del loop de captura
   ✅ Correcto: YOLO cargado UNA VEZ en __init__ de PeopleDetector

5. WEBSOCKET BROADCAST CON CONEXIONES MUERTAS
   ❌ Problema: no hay manejo de conexiones que fallaron
      enviar a conexión muerta lanza excepción y corta el broadcast
   ✅ Correcto: captura excepciones por conexión, remueve las muertas

6. CONSULTAS SIN ÍNDICE (solo para queries frecuentes)
   ❌ Problema: WHERE en columna sin índice en tabla de alto volumen
      WHERE phone_number = '...' sin índice en patients
      WHERE status = 'pending' sin índice en visits
   ✅ Correcto: columnas de filtro frecuente tienen índice en el modelo

7. DASHBOARD RE-RENDERS (solo para componentes React)
   ❌ Problema: estado que cambia frecuentemente en el componente raíz
      causa re-render de todos los hijos innecesariamente
   ✅ Correcto: estado dividido por área de responsabilidad,
      componentes hijos con React.memo si son costosos

Formato: LÍNEA N: [criterio N] — [problema] → [corrección]
Al final: "PERFORMANTE" o "PROBLEMAS DE PERFORMANCE (N encontrados)"
```

---

## REVIEW-04 — Comportamiento del Bot

Usar después de: PASO 19 (preparation validation), PASO 20 (incoming handler), PASO 21 (reminders).

```
Evalúa el comportamiento del bot de WhatsApp desde la perspectiva
del paciente y de la operación clínica.

[PEGA EL CÓDIGO DEL BOT AQUÍ]

1. FLUJO DE BIENVENIDA
   Verifica que el mensaje de bienvenida incluye:
   ✅ Nombre del paciente
   ✅ Lista numerada de estudios en orden
   ✅ Tiempo estimado por estudio
   ✅ Tiempo total estimado
   ✅ Mensaje de que se avisará en cada turno
   ❌ Si falta alguno de estos elementos

2. VALIDACIÓN DE PREPARACIÓN
   Verifica el flujo completo:
   ✅ Solo se activa si has_appointment=True Y hay estudios con preparación
   ✅ El flag se borra ANTES de procesar la respuesta (no después)
   ✅ Respuesta afirmativa → envía welcome message completo
   ✅ Respuesta negativa → ofrece reagendar, NO continúa el flujo normal
   ✅ Walk-in (has_appointment=False) → nunca activa este flujo
   ❌ Si el flag puede quedar activo después de procesar la respuesta

3. MODO SILENCIOSO (walk-in)
   Verifica que pacientes sin cita:
   ✅ Solo reciben notificaciones de turno (no mensajes no solicitados)
   ✅ El bot responde cuando el paciente pregunta
   ✅ NO reciben el flujo de validación de preparación
   ❌ Si reciben mensajes no solicitados al llegar

4. RESTRICCIÓN MÉDICA
   Verifica que el system prompt de Claude:
   ✅ Contiene exactamente: "Nunca interpretes, diagnostiques..."
   ✅ Contiene exactamente: "Para interpretar tus resultados, consulta con un médico."
   ✅ Está en español
   ✅ Limita a máximo 3 oraciones por respuesta
   ❌ Si cualquiera de estas restricciones está modificada o ausente

5. IDIOMA
   ✅ Todos los mensajes al paciente en español
   ✅ El system prompt instruye responder en español
   ❌ Si hay algún mensaje al paciente en inglés

6. MANEJO DE SESIÓN EXPIRADA
   ✅ Si get_session retorna None: mensaje claro para ir a recepción
   ✅ NO intenta llamar a la API con un visit_id nulo
   ❌ Si hay algún camino donde visit_id puede ser None y se usa de todas formas

7. CIERRE DE REDIS LOCK
   ✅ El lock se libera en bloque finally (no en try)
   ✅ Funciona aunque el handler lance una excepción
   ❌ Si el lock puede quedar activo si el handler falla

Formato: [criterio N]: ✅ CORRECTO o ❌ PROBLEMA — [descripción exacta del problema]
Al final: "BOT APROBADO" o "CORRECCIONES REQUERIDAS (N problemas)"
```

---

## REVIEW-05 — Rules Engine

Usar después de: PASO 3 (tests completos del motor).

```
Eres un revisor especializado en lógica clínica y calidad de código.
Evalúa el motor de reglas de SaludCopilot.

[PEGA engine.py Y test_engine.py AQUÍ]

1. COBERTURA DE REGLAS CLÍNICAS
   Verifica que cada regla del documento operativo de Salud Digna tiene un test:
   ✅ R-00: urgentes antes que con cita, con cita antes que sin cita
   ✅ R-01: papanicolaou antes que ultrasonido_transvaginal
   ✅ R-02: papanicolaou primero en combinación VPH + cultivo_vaginal
   ✅ R-03: densitometria antes que tomografia
   ✅ R-03: densitometria antes que resonancia
   ✅ R-04: laboratorio con requires_fasting antes que ultrasonido
   ✅ R-04: laboratorio SIN requires_fasting NO activa la regla
   ✅ R-05: sin preparación antes que con preparación
   Para cada regla faltante: indica cuál falta y el test que hay que agregar.

2. TRAZABILIDAD
   ✅ Cada PasoSecuencia tiene rule_applied con el código R-XX o None
   ✅ Cada PasoSecuencia tiene razon en español legible para el paciente
   ❌ Si rule_applied puede ser un string arbitrario sin formato R-XX

3. AISLAMIENTO
   ✅ El módulo NO importa nada de apps/ ni de la DB
   ✅ Todos los imports son stdlib o el propio módulo
   ❌ Si hay cualquier import de sqlalchemy, fastapi, redis, httpx u otro framework

4. DETERMINISMO
   ✅ Misma entrada siempre produce misma salida
   ✅ No hay random, datetime.now(), ni estado global mutable
   ❌ Si el resultado puede variar entre llamadas con los mismos datos

5. EDGE CASES
   ✅ Lista vacía → retorna ResultadoSecuencia con pasos=[] sin error
   ✅ Un solo estudio → retorna ese estudio en orden 1
   ✅ Todos urgentes → respeta el orden original entre ellos
   ❌ Si falta cualquiera de estos tests

6. TIEMPO ESTIMADO
   ✅ Fórmula: N estudios × 15 min + (N-1) traslados × 5 min
   ✅ Test explícito que verifica la fórmula con 2 estudios = 35 min
   ❌ Si la fórmula es diferente o no hay test

Formato: [criterio N]: ✅ o ❌ — [detalle]
Al final: "MOTOR APROBADO" o "CORRECCIONES REQUERIDAS"
```

---

## REVIEW-06 — Modelo ML

Usar después de: PASO 25 (training + predictor).

```
Evalúa la implementación del modelo predictivo de tiempos de espera.

[PEGA train.py Y predictor.py AQUÍ]

1. CONSISTENCIA DE FEATURES
   CRÍTICO: el orden de features en training debe ser idéntico a inference.
   ✅ FEATURE_COLUMNS es una constante de módulo usada en AMBAS funciones
   ✅ build_training_features retorna columnas en el orden de FEATURE_COLUMNS
   ✅ extract_inference_features construye el DataFrame con el mismo orden
   ❌ Si el orden puede diferir entre training e inference
   Prueba manual: imprime features_df.columns.tolist() en training y compara con FEATURE_COLUMNS

2. HIPERPARÁMETROS CORRECTOS
   ✅ n_estimators=100, random_state=42, n_jobs=-1
   ✅ Train/test split con test_size=0.2, random_state=42
   ❌ Si algún hiperparámetro difiere del definido en TASK.md

3. MANEJO DE LABELS NO VISTOS
   ✅ predict_wait_minutes maneja study_type o clinic no vistos en training
   ✅ Usa mediana como fallback, NO lanza KeyError
   ✅ Log de warning cuando usa fallback
   ❌ Si puede lanzar KeyError o ValueError con un label nuevo

4. RETORNO GARANTIZADO
   ✅ predict_wait_minutes SIEMPRE retorna int >= 1
   ✅ max(1, round(int(prediction))) o equivalente
   ❌ Si puede retornar 0, negativo, float, o None

5. CARGA ÚNICA DEL MODELO
   ✅ WaitTimePredictor carga model.pkl y encodings.pkl en __init__ UNA VEZ
   ✅ predict_wait_minutes no recarga el modelo en cada llamada
   ❌ Si hay joblib.load() fuera de __init__

6. is_ready PROPERTY
   ✅ Retorna False si model.pkl no existe (no lanza FileNotFoundError)
   ✅ Retorna True cuando el modelo está cargado correctamente
   ❌ Si is_ready puede lanzar una excepción

7. ARTEFACTOS COMPROMETIDOS
   Verifica que ml/models/model.pkl y encodings.pkl existen.
   Si no existen: indica que hay que correr el notebook de training primero.

Formato: [criterio N]: ✅ o ❌ — [detalle]
Al final: "MODELO APROBADO" o "CORRECCIONES REQUERIDAS"
```

---

## REVIEW-07 — Base de datos

Usar después de: PASO 5 (migraciones).

```
Evalúa los modelos SQLAlchemy y la migración de Alembic.

[PEGA models.py Y el archivo de migración de alembic AQUÍ]

1. ESTILO SQLALCHEMY 2.0
   ✅ Todos los modelos usan Mapped y mapped_column
   ❌ Si hay Column, relationship sin Mapped, o Integer/String sin mapped_column
   Línea exacta de cualquier uso de estilo legacy.

2. TIPOS DE DATOS CORRECTOS
   ✅ Todos los PKs: UUID con default=uuid.uuid4
   ✅ Todos los timestamps: DateTime(timezone=True) — NUNCA DateTime sin timezone
   ✅ Strings de longitud definida: VARCHAR(N) no Text para campos cortos
   ❌ Si hay DateTime sin timezone=True

3. APPEND-ONLY EN PatientEvent
   ✅ PatientEvent NO tiene columna updated_at
   ✅ PatientEvent tiene occurred_at (no created_at — el nombre importa)
   ❌ Si PatientEvent tiene updated_at

4. RELACIONES COMPLETAS
   Verifica que CADA FK tiene su relationship() en AMBOS lados:
   ✅ Visit.patient + Patient.visits
   ✅ VisitStep.visit + Visit.steps
   ✅ VisitStep.clinical_area + ClinicalArea.visit_steps
   ✅ WaitTimeEstimate.clinical_area (unidireccional está bien)
   ❌ Si alguna relación está en solo un lado

5. __repr__ EN TODOS LOS MODELOS
   ✅ Cada modelo tiene __repr__ que muestra id + un campo legible
   ❌ Si algún modelo no tiene __repr__

6. MIGRACIÓN COMPLETA
   Cuenta los CREATE TABLE en el archivo de migración.
   ✅ Exactamente 9 tablas: patients, clinics, clinical_areas, visits,
      visit_steps, notifications, clinical_rules, wait_time_estimates, patient_events
   ❌ Si falta alguna tabla o hay tablas extra no esperadas

7. DOWNGRADE LIMPIO
   ✅ La función downgrade() elimina todas las tablas en orden inverso
   ❌ Si downgrade() está vacío o incompleto

Formato: [criterio N]: ✅ o ❌ — [detalle]
Al final: "BASE DE DATOS APROBADA" o "CORRECCIONES REQUERIDAS"
```

---

## REVIEW-08 — Contratos de API

Usar después de: PASO 13 (todos los endpoints implementados).

```
Compara los endpoints implementados contra los contratos definidos
en ARQUITECTURA.md sección "Contratos entre módulos".

[PEGA EL CÓDIGO DE visitas.py Y areas.py AQUÍ]

Para cada endpoint, verifica contrato exacto:

1. POST /api/v1/visits/check-in
   Request debe aceptar: phone_number, clinic_id, study_ids, has_appointment, is_urgent
   Response 201 debe retornar: visit_id, patient_id, sequence[], total_estimated_minutes
   sequence[] debe incluir: order, area_name, estimated_wait_minutes, rule_applied
   ✅ o ❌ por cada campo

2. GET /api/v1/visits/{visit_id}/context
   Response 200: visit_id, patient_name, current_step{}, remaining_steps[], total_estimated_minutes
   Response 404: {"error": "Visit not found", "code": "VISIT_NOT_FOUND"}
   ✅ o ❌ por cada campo y código de error

3. POST /api/v1/areas/{area_id}/occupancy
   Request: people_count (int), timestamp (ISO8601 string)
   Response 200: {"wait_time_estimate_minutes": int}
   Response 404: {"error": "Area not found", "code": "AREA_NOT_FOUND"}
   ✅ o ❌

4. POST /bot/internal/notify (si está en el código)
   Request: visit_id, notification_type, payload{}
   Response 200: {"status": "sent"}
   Response 401: token inválido
   Response 400: tipo desconocido con code UNKNOWN_NOTIFICATION_TYPE
   ✅ o ❌

5. CÓDIGOS HTTP CORRECTOS
   ✅ Creación de recursos: 201 (no 200)
   ✅ Recurso no encontrado: 404 (no 400)
   ✅ Input inválido: 422 (Pydantic lo maneja automáticamente)
   ✅ No autorizado: 401 (no 403 para token inválido)
   ❌ Cualquier código incorrecto

6. FORMATO DE ERRORES CONSISTENTE
   ✅ Todos los errores: {"error": "descripción", "code": "SNAKE_CASE_CODE"}
   ❌ Si algún error retorna formato diferente (string plano, solo message, etc.)

Formato: [endpoint] [campo]: ✅ o ❌ — [detalle del problema]
Al final: "CONTRATOS APROBADOS" o "N discrepancias encontradas"
```

---

## REVIEW-09 — Smoke test completo (pre-demo)

Ejecutar el día del demo, 2 horas antes de la presentación.

```
Ejecuta cada uno de estos comandos en orden. 
Para cada uno: muéstrame el output EXACTO.
Si alguno falla: DETENTE y muéstrame el error completo.
No continúes al siguiente si el actual falla.

PASO A — Infraestructura:
docker compose up postgres redis -d
sleep 5
docker compose ps

Esperado: postgres y redis en estado "healthy"

---

PASO B — API:
docker compose up api -d
sleep 5
curl -s http://localhost:8000/health

Esperado: {"status": "ok", "version": "0.1.0"}

---

PASO C — Rules engine tests:
cd packages/rules_engine
pytest tests/ -v --tb=short

Esperado: todos los tests en verde, 0 failed

---

PASO D — Seed data (solo si la DB fue reseteada):
cd apps/api
alembic upgrade head
python ../../scripts/seed.py

Esperado: output con todos los UUIDs impresos

---

PASO E — Bot:
cd apps/bot
python main.py &
sleep 3
curl -s http://localhost:8001/bot/webhook?hub.mode=subscribe\&hub.verify_token=saludcopilot_verify\&hub.challenge=test123

Esperado: "test123" como respuesta

---

PASO F — Dashboard:
cd apps/dashboard
pnpm dev &
sleep 5

Abre http://localhost:3000 en el navegador.
Esperado: página carga, badge "DEMO" visible (WebSocket no conectado todavía)

---

PASO G — CV worker demo:
cd apps/cv
python main.py --demo &
sleep 5

Esperado en logs: "Area {uuid}: 3 people | Est. wait: N min"
Esperado en dashboard: badge cambia a "EN VIVO", chart actualiza

---

PASO H — Check-in completo:
curl -s -X POST http://localhost:8000/api/v1/visits/check-in \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+52NUMERO_REAL",
    "clinic_id": "CLINIC_UUID_DEL_SEED",
    "study_ids": ["LABORATORIO_UUID", "ULTRASONIDO_UUID"],
    "has_appointment": false,
    "is_urgent": false
  }'

Esperado: respuesta 201 con visit_id y sequence de 2 pasos
Esperado en el teléfono: WhatsApp de bienvenida en < 10 segundos

---

PASO I — Avanzar turno:
curl -s -X POST http://localhost:8000/api/v1/visits/{VISIT_ID_DEL_PASO_H}/advance-step

Esperado: respuesta 200
Esperado en el teléfono: WhatsApp de notificación de turno
Esperado en dashboard: tabla de visitas activas actualizada

---

RESULTADO FINAL:
Si todos los pasos pasaron: "SISTEMA LISTO PARA EL DEMO ✅"
Si alguno falló: indica cuál paso y el error exacto.
```

---

## REVIEW-10 — Accesibilidad del dashboard

Usar después de: PASO 29 (dashboard completo).

```
Evalúa la accesibilidad del dashboard para usuarios con diferentes necesidades.

[PEGA EL CÓDIGO DE LOS COMPONENTES DEL DASHBOARD AQUÍ]

1. CONTRASTE DE COLORES
   ✅ Texto sobre fondo oscuro: ratio mínimo 4.5:1 (WCAG AA)
   Verifica específicamente:
   - #F0F0F0 sobre #0F1117: ratio ~16:1 ✅
   - #8B8FA8 sobre #1A1D27: verifica si es suficiente
   - Texto de badges sobre sus fondos de color
   ❌ Si cualquier combinación tiene ratio < 4.5:1

2. ELEMENTOS INTERACTIVOS
   ✅ Todos los botones tienen texto visible (no solo ícono)
   ✅ O tienen aria-label si son solo íconos
   ❌ Si hay botón con solo ícono sin aria-label

3. ESTADOS DE CARGA
   ✅ La página muestra contenido inmediatamente (mock data)
   ✅ No hay flash de contenido en blanco al cargar
   ❌ Si hay estado de loading que muestra pantalla vacía

4. INFORMACIÓN NO SOLO POR COLOR
   ✅ Los status badges tienen texto ("Normal", "Alerta", "Saturado")
      no solo color verde/amarillo/rojo
   ✅ Las alertas tienen texto de severidad, no solo borde de color
   ❌ Si la información se comunica únicamente mediante color

5. ACTUALIZACIONES EN TIEMPO REAL
   ✅ Las actualizaciones del WebSocket no causan saltos de layout
   ✅ Los números que cambian tienen transición suave o el cambio es predecible
   ❌ Si el dashboard "salta" visualmente cuando llegan datos nuevos

Formato: [criterio N]: ✅ o ❌ — [detalle]
Al final: "ACCESIBILIDAD APROBADA" o "CORRECCIONES REQUERIDAS"
```
