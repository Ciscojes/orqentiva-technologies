# Arquitectura de ORQENTIVA Technologies

## Componentes y responsabilidades

```mermaid
flowchart TD
  U[Visitante o usuario] --> R[React y TypeScript]
  R --> F[FastAPI]
  F --> A[Autenticación y autorización]
  F --> B[Servicios, profesionales y agenda]
  F --> G[LangGraph: understand, interpret y availability]
  G -. opcional .-> L[LLM compatible con OpenAI]
  F --> K[Recuperación de documentos publicados]
  A --> D[(SQLAlchemy y PostgreSQL)]
  B --> D
  G --> B
  K --> D
```

React muestra la interfaz, conserva el borrador de la conversación y solicita confirmación explícita. FastAPI valida entradas y permisos. SQLAlchemy coordina la persistencia. PostgreSQL es la base del desarrollo habitual. SQLite permite ejecutar las pruebas aisladas y una demostración portátil. Alembic versiona el esquema.

## Dos tipos de acceso

super_admin administra negocios y crea usuarios. business_admin opera sobre la empresa asociada a su cuenta. La API toma la empresa de la sesión en las rutas privadas. Los enlaces públicos toman la empresa del enlace y solo exponen catálogo reservable, disponibilidad y documentos publicados. Cambiar business_id en una instrucción del chat no concede permisos.

## Reserva conversacional

1. React envía mensaje y borrador a POST /book/{business_id}/chat.
2. El grafo de LangGraph ejecuta tres nodos. `understand` pide al LLM, si está configurado, una propuesta de servicio, profesional, fecha, hora y nombre en JSON. `interpret` aplica las reglas deterministas y usa la propuesta del LLM solo para los campos que las reglas no reconocieron. Cada campo del LLM se valida contra el catálogo del negocio; los ids inventados, fechas pasadas u horas mal formadas se descartan.
3. La consulta de disponibilidad comprueba duración, horarios y solapamientos.
4. El chat devuelve datos faltantes, alternativas o una propuesta. Este recorrido no escribe reservas.
5. La persona confirma en React. La interfaz envía la propuesta a POST /book/{business_id} con request_key.
6. El backend revalida y persiste. Solo tras una respuesta correcta aparece «Cita confirmada».

En el flujo de reservas, el LLM no escribe en la base de datos ni redacta la respuesta al cliente (la generación documental se describe más abajo), y el mensaje se le envía marcado como texto no confiable. Si falla, tarda más de 8 segundos, responde algo que no es JSON o se supera el límite de 20 llamadas por IP y minuto, el chat continúa solo con reglas.

La clave de solicitud evita duplicados por reintento. Una nueva solicitud a un turno ocupado recibe conflicto. En PostgreSQL, el bloqueo de negocio coordina las confirmaciones concurrentes. La validación SQLite no sustituye la de PostgreSQL.

## Consulta documental

Los documentos tienen empresa, título, texto y estado publicado. La consulta sigue el patrón RAG (SPEC-015):

1. **Recuperación híbrida (SPEC-019).** Filtra empresa y publicación antes de puntuar párrafos. La búsqueda por palabras normaliza texto y usa términos/alias y cobertura. La búsqueda por significado compara el embedding de la pregunta con el de cada párrafo, generado por un modelo multilingüe local. Las dos listas se combinan por posición (reciprocal rank fusion) y el LLM recibe los párrafos de más a menos relevante hasta llenar 6 000 caracteres, con un mínimo de cuatro: con una base pequeña recibe todo, ordenado; con una grande, lo más relevante que quepa. Sin embeddings, o si el modelo no está disponible, se usa solo la búsqueda por palabras y, si no hay coincidencias y todos los párrafos caben en 6 000 caracteres, se pasan todos como candidatos.
2. **Generación.** Con el LLM activo, el modelo recibe la pregunta y solo los candidatos de ese negocio, y devuelve una respuesta breve con los ids de los párrafos usados.
3. **Validación.** El servidor rechaza citas a párrafos no enviados y cifras que no aparezcan en los párrafos citados. Si el modelo no responde, falla o se rechaza su respuesta, se devuelve el párrafo literal (modo extractivo).

Los embeddings se calculan en el propio servidor con fastembed (ONNX), sin clave ni coste por consulta, y los textos de los clientes no salen a terceros. Los vectores se guardan en `knowledge_vectors`, identificados por el hash del párrafo y el modelo, y se comparan en Python: para cientos de párrafos por negocio no hace falta pgvector. El modelo se carga en segundo plano al arrancar; mientras tanto, y ante cualquier fallo, el sistema se comporta como antes. Las respuestas siempre muestran título y número de párrafo. La evaluación de recuperación está en `docs/evaluation-019/`.

La base de conocimiento se gestiona desde los dos paneles (SPEC-018) con la misma lógica en el servidor (`app/routes/knowledge.py`). «Probar pregunta» ejecuta la misma consulta que el chat y puede incluir borradores, que el chat público nunca recibe. Los PDF se convierten en borradores con `pypdf`. Cada cambio se registra en `knowledge_changes` con la versión anterior y la nueva; el registro no depende del documento, por lo que sobrevive a su eliminación.

## Seguridad y límites

Contraseñas Argon2, tokens aleatorios de sesión cuyo hash se guarda en base de datos, cookies HttpOnly y SameSite=Strict, Secure por defecto. Las escrituras privadas validan Origin. La revocación y el estado del negocio se comprueban en servidor. Los límites de envíos/login/reservas son locales al proceso. No se implementaron MFA, restablecimiento de contraseña ni auditoría completa de eventos.

## Decisiones y aprendizaje

Separar autorización y presentación evita depender de botones ocultos. Separar propuesta y confirmación evita escrituras por mensajes ambiguos. Usar una referencia literal permite verificar el origen de cada respuesta. El LLM aporta flexibilidad lingüística (frases como «la semana que viene a media mañana»), mientras que las reglas, la validación contra el catálogo y la confirmación explícita mantienen el comportamiento comprobable. Sin clave de API el sistema funciona igual que antes, sin coste de modelo.

La hipótesis de mejora de productividad frente a otros asistentes sigue sin evaluarse con usuarios reales. Las pruebas certifican únicamente los escenarios ejecutados.
