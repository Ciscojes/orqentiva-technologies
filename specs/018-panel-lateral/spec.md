# SPEC-018 — Paneles con menú lateral y gestión de la base de conocimiento

## Objetivo
Ordenar los paneles de administración y de negocio para que cada función tenga un lugar fijo, y dar al negocio y a la administración herramientas para mantener la base de conocimiento que usa el RAG (SPEC-015).

## Alcance

### Navegación
- Menú lateral común (`PanelLayout.tsx`) con grupos, plegable a solo iconos (la preferencia se guarda en el navegador) y convertido en menú desplegable con ☰ por debajo de 900 px. Pie con la cuenta y «Cerrar sesión», también visible con el menú plegado.
- Panel del negocio: Resumen, Agenda, Servicios, Trabajadores, Horario, Base de conocimiento y Enlace de reservas. Sin agenda habilitada solo muestra el Resumen con el aviso de contacto.
- Resumen del negocio: citas de hoy, próximas citas, servicios activos, trabajadores, las cinco próximas citas y una lista de primeros pasos.
- Panel de administración: Resumen (estado del LLM, métricas y cambios recientes en las bases de conocimiento), Negocios y Nuevo negocio. Cada negocio abre una ficha con pestañas: Estado (acceso y agenda), Agenda (solo lectura), Cuentas, Base de conocimiento e Historial de cambios.

### Base de conocimiento
- Gestión desde el panel del negocio y desde la ficha de cada negocio en administración, con la misma lógica en el servidor.
- Eliminar documentos con confirmación; el chat deja de usarlos de inmediato.
- «Probar pregunta»: ejecuta la misma consulta RAG del chat y muestra la respuesta, si la redactó la IA y los párrafos citados. Puede incluir borradores; el chat público nunca los ve.
- Importar PDF (hasta 5 MB) con `pypdf`: el texto se separa en párrafos y en documentos de hasta 6 000 caracteres, que se guardan como borradores. Un PDF sin texto seleccionable, cifrado o inválido devuelve 422.
- Plantillas (Formas de pago, Cancelaciones, Ubicación y parqueo, Preguntas frecuentes) con el formato de un párrafo por idea.
- Aviso en los dos paneles cuando el LLM está desactivado.
- Historial (`knowledge_changes`): crear, editar, publicar, despublicar, eliminar e importar, con fecha, cuenta y versión anterior y nueva. La administración ve lo que cambió resaltado y puede recargar como borrador un documento eliminado. El negocio publica sin aprobación previa (decisión del autor: opción «publicar directamente con historial»).

### Demostración en el entorno de desarrollo
- `scripts/seed_demo_data.py` y `.\scripts\iniciar.ps1 -Demo`: datos ficticios y cuentas de prueba en el PostgreSQL local (puerto 5178). Repetible, sin duplicados; reactiva y restablece la contraseña solo de las tres cuentas @example.com. Se niega a ejecutarse si la base no es local.

## API añadida

| Ruta | Método | Resultado |
| --- | --- | --- |
| /client/documents/{id} | DELETE | Elimina un documento propio; 204, ajeno 404 |
| /client/documents/preview | POST | Respuesta RAG de prueba; `include_drafts` opcional |
| /client/documents/import?title= | POST | Cuerpo `application/pdf`; crea borradores; 201 |
| /client/documents/history | GET | Historial propio |
| /client/documents/status | GET | `llm_enabled` |
| /admin/businesses/{id}/documents[/…] | GET, POST, PUT, DELETE | Las mismas operaciones sobre cualquier negocio |
| /admin/businesses/{id}/documents/history | GET | Historial del negocio |
| /admin/businesses/{id}/dashboard | GET | Agenda, equipo, servicios y horario en solo lectura |
| /admin/knowledge-changes | GET | Cambios recientes de todos los negocios |
| /admin/llm-status | GET | `llm_enabled` |

Las rutas `/client` requieren business_admin y toman la empresa de la sesión; las `/admin`, super_admin. Las escrituras verifican Origin. Migración `f016knowledgechanges`: tabla `knowledge_changes` sin clave foránea al documento, para conservar el registro tras eliminarlo.

## Fuera de alcance
Acceso propio para trabajadores, aprobación previa de cambios, edición de citas desde administración, PDF escaneados (OCR), Word y embeddings.

## Verificación
- `tests/test_knowledge_admin.py`: eliminación y aislamiento entre negocios, historial con versiones, prueba con y sin borradores, importación de PDF y errores, división en documentos, gestión desde administración y agenda en solo lectura.
- `tests/test_seed_demo_data.py`: datos repetibles, inicio de sesión con la cuenta de prueba y rechazo de bases remotas.
- Revisión visual en Chromium (1440 px y 390 px) con la web compilada sobre una copia SQLite con datos ficticios: menú desplegado y plegado, menú móvil, Resumen, Agenda, Servicios, base de conocimiento, historial con cambios resaltados y pestaña Agenda de administración.
- En el entorno de desarrollo del autor (PostgreSQL, puerto 5178): inicio de sesión con la cuenta de prueba de Alfa y «Probar pregunta» con el LLM real, que respondió con cita y declaró correctamente la falta de información cuando no había documento.
