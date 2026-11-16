# Verificación consolidada del TFM

Fecha: 10 de noviembre de 2026, Costa Rica.

## Alcance

Se revisa la implementación local basada en 11f075b (rama mejoras-chat), con las
correcciones de esta consolidación. La evidencia forma parte del commit que contiene
este informe. Se integra el trabajo mediante el PR #1 hacia main. No se modifica
.env ni se restablecen contraseñas ni se sobrescriben bases existentes.

## Correcciones

- La demo admite Origin http://127.0.0.1:5179 y http://localhost:5179. Cada hostname
  tiene su cookie; mantener el mismo durante la sesión. Reiniciar el componente api
  para aplicar el cambio si ya estaba ejecutándose.
- FastAPI registra únicamente los archivos reales de la compilación. Se elimina
  la ruta comodín que convertía GET /leads en 404 en lugar de 405. Se conserva el
  encabezado Allow y las rutas de API no pueden ser ocultadas por un archivo.
- README, arquitectura, charter y alcance distinguen extracción para reservas,
  generación documental con citas y respaldo extractivo. Las specs históricas
  enlazan la ampliación SPEC-015.
- Se conserva el informe histórico de 137 pruebas sin atribuirle la cobertura actual.

## Resultados

| Verificación | Resultado |
| --- | --- |
| Suite Python | 240 pruebas aprobadas; incluye dos regresiones con/sin frontend compilado |
| Compilación TypeScript/Vite | Aprobada |
| Lint oxlint | Aprobado |
| PostgreSQL 17 temporal con frontend compilado | Aprobado, incluido GET /leads = 405 |
| Credenciales de demo existentes | Admin, Alfa y Beta verificadas sobre copia aislada; login, identidad, panel y logout |
| Extracción con LLM real | 39/40 casos completos con reglas + LLM; 0 llamadas fallidas |
| Latencia del LLM | Mediana 1,46 s; p95 1,95 s; máxima 2,06 s |

Evidencias: [pytest](evaluation-final-tests.xml), [PostgreSQL](evaluation-final-postgres.txt),
[evaluación LLM](evaluation-017/informe-extraccion.md).

La suite y PostgreSQL usan bases temporales. El proveedor real solo recibe casos
ficticios de extracción. No se midieron tokens/coste, carga de producción ni calidad
semántica del RAG con modelo real. El LLM confundió en un caso el nombre de la
profesional con el del cliente; no se afirma exactitud perfecta.

## Revisión visual: incompleta

Se abrió en Edge la web compilada de una instancia aislada con copia de la base,
en http://localhost:8013/#login. Se verificó visualmente el formulario de acceso en
escritorio. La automatización del navegador falló al pulsar el acceso y finalmente
se detuvo porque no podía verificar con suficiente confianza la URL de la ventana.
No se certifica el recorrido visual de paneles, confirmación de reservas ni móvil.
Las comprobaciones por API no sustituyen ese recorrido.

Para completar manualmente: iniciar sesión como Alfa y Beta; revisar ambos paneles;
abrir el enlace público, reservar Corte demo con contacto ficticio y confirmar;
comprobar la cita en agenda y el rechazo del mismo turno; consultar Cancelaciones
durante otro borrador; repetir en ancho móvil y verificar cierre de sesión.

## Estado académico

Presentación y vídeo excluidos de la intervención del 10 de noviembre por instrucción
del autor. La ampliación del 11 de noviembre (ver abajo) añade un video comercial de
presentación; no es el vídeo de defensa del TFM. No se inventaron enlaces ni se declara
realizada la entrega. El despliegue público
no está realizado y WhatsApp sigue como piloto sin conexión Meta real. La revisión
no certifica cumplimiento de una rúbrica externa ni seguridad de producción.

## Ampliación del 11 de noviembre de 2026: video de presentación y demo con Docker

Commit a9f047b sobre main. No se modifican el backend, las migraciones ni las pruebas.

Cambios: sección de video en la página de inicio (`VideoPresentation.tsx`) con tres
capítulos y subtítulos ES/EN; carpeta `video/` que regenera el video desde la aplicación
en local con datos ficticios (`npm run video`); `compose.demo.yaml` para la demostración
con un solo comando; `scripts/iniciar.ps1` para el arranque diario.

| Verificación | Resultado |
| --- | --- |
| Suite Python | 240 pruebas aprobadas tras los cambios, ejecutada por el autor en Windows |
| Compilación TypeScript/Vite y lint oxlint | Aprobados sobre el mismo código, en un entorno Linux aislado |
| Reproductor en la web compilada servida por FastAPI | Chromium, escritorio y 390 px: el video no se descarga hasta pulsar, los capítulos saltan a su inicio, subtítulos ES/EN según el idioma, sin desbordes; el archivo admite peticiones por rangos (206) |
| Generación del video en Windows | `npm run video` completo: datos ficticios, narración, grabación a 1920x1080 y montaje; 77,8 s |
| Arranque con `scripts/iniciar.ps1` | Ejecutado por el autor en Windows: PostgreSQL, migraciones, API y web |
| Demostración con Docker | El autor ejecutó `docker compose -f compose.demo.yaml up --build` y confirmó que funciona; no se documenta un recorrido detallado |

Límites de esta ampliación:

- El video es una pieza comercial. No se han medido resultados en negocios reales y el
  guion no afirma cifras. Los datos que muestra son ficticios (`video/seed_demo.py`).
- La escena de WhatsApp es una ilustración rotulada como «Próximamente»; WhatsApp sigue
  como piloto sin conexión Meta real.
- La narración usa una voz sintética clonada del autor (ElevenLabs). La clave y el
  identificador de voz se leen de variables de entorno y no están en el repositorio.
  La calidad del audio la revisó el autor de oído; no hay comprobación automática.
- El chat se graba en modo solo reglas para que el resultado sea reproducible; no
  muestra respuestas redactadas por el LLM.
- No se probó el reproductor en Safari ni en teléfonos reales, ni con lectores de pantalla.
- La construcción de la imagen Docker no pudo repetirse en el entorno aislado (sin acceso
  al registro de imágenes); allí solo se validó el archivo y el comando de arranque.
- No se registra aquí el resultado de GitHub Actions para este commit.
- La revisión visual de paneles descrita arriba sigue incompleta.

## Ampliación del 15 de noviembre de 2026: paneles con menú lateral y base de conocimiento

Rama `panel-lateral`, integrada en main. Especificación: [SPEC-018](../specs/018-panel-lateral/spec.md). Incluye la migración `f016knowledgechanges` y la dependencia `pypdf`.

| Verificación | Resultado |
| --- | --- |
| Suite Python | 248 pruebas aprobadas, 9 nuevas, en un entorno Linux aislado con Python 3.10. Falla `test_legacy_import.py::test_new_business_service_and_booking_are_inserted_together`, previa a esta ampliación: usa `datetime.fromisoformat` con sufijo `Z`, admitido desde Python 3.11; el proyecto usa 3.13 |
| Compilación TypeScript/Vite y lint oxlint | Aprobados |
| Revisión visual en Chromium | Web compilada sobre una copia SQLite con datos ficticios, 1440 px y 390 px: menú desplegado, plegado y móvil; Resumen, Agenda, Servicios, Trabajadores, base de conocimiento, historial con cambios resaltados y pestaña Agenda de administración |
| Entorno de desarrollo del autor (PostgreSQL, 5178) | Inicio de sesión con la cuenta de prueba de Alfa; «Probar pregunta» con el LLM real: respuesta redactada con cita a un documento propio y respuesta «sin información» cuando no había documento |

Límites de esta ampliación:

- No se ejecutó `scripts/verify_postgres.py` ni la migración nueva sobre un PostgreSQL temporal; el autor la aplicó con `iniciar.ps1` en su base de desarrollo.
- La importación de PDF se probó con PDF generados en las pruebas; no con documentos reales de negocios ni escaneados.
- No se probó en Safari, teléfonos reales ni con lectores de pantalla.
- El recorrido visual de reservas públicas y confirmación sigue sin certificarse.

## Ampliación del 15 de noviembre de 2026: RAG semántico (SPEC-019)

Rama `rag-semantico`. Especificación: [SPEC-019](../specs/019-rag-semantico/spec.md). Migración `g019knowledgevectors` y dependencia `fastembed`.

| Verificación | Resultado |
| --- | --- |
| Suite Python | 254 pruebas aprobadas, 6 nuevas con un modelo de embeddings simulado; la misma falla previa de Python 3.10 indicada arriba |
| Compilación TypeScript/Vite y lint oxlint | Aprobados |
| Línea base de recuperación ([informe](evaluation-019/linea-base.md)) | Palabras con respaldo: párrafo correcto en 30/32 enviando 24,4 párrafos de media; sin respaldo (base > 6 000 caracteres): 8/32, y 0/22 coloquiales |
| Primera medición con el modelo local real, ejecutada por el autor en Windows ([informe](evaluation-019/informe-inicial-4-parrafos.md)) | Enviando siempre 4 párrafos: correcto en primer lugar 22/32 (palabras: 8/32); correcto en lo enviado 26/32 (palabras sin respaldo: 8/32; con respaldo: 30/32 enviando 24,4 párrafos). Motivó el envío por espacio descrito en SPEC-019 |
| Medición del diseño final con el modelo local real | Pendiente: `python scripts/eval_rag.py --report docs/evaluation-019/informe-rag.md` en el equipo del autor |

Límites: el entorno aislado de desarrollo no puede descargar modelos de Hugging Face, por lo que la integración con fastembed no se ejecutó allí con el modelo real. El conjunto de evaluación es pequeño y ficticio, y mide la recuperación, no la calidad de la respuesta redactada por el LLM.
