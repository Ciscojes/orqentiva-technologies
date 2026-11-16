# SPEC-019 — RAG semántico: búsqueda híbrida con embeddings locales

## Objetivo
Que el RAG (SPEC-015) encuentre el párrafo correcto aunque el cliente use otras palabras, sin depender de que todos los documentos del negocio quepan en 6 000 caracteres, y medirlo con un conjunto fijo de preguntas.

## Problema
La recuperación por palabras solo encuentra párrafos que comparten términos con la pregunta. Si no encuentra nada, el LLM recibe todos los párrafos del negocio, pero solo cuando suman menos de 6 000 caracteres. Con bases más grandes (por ejemplo, PDF importados) ese respaldo desaparece. La línea base (`docs/evaluation-019/linea-base.md`) lo cuantifica: con respaldo, el párrafo correcto llega al LLM en 30 de 32 preguntas, pero enviando 24,4 párrafos de media; sin respaldo, en 8 de 32 y en ninguna de las 22 preguntas coloquiales.

## Alcance
- `app/embeddings.py`: proveedor configurable con `EMBEDDINGS_PROVIDER`.
  - `local` (predeterminado): `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` con fastembed (ONNX, 384 dimensiones, unos 220 MB descargados una vez en `.cache/embeddings`). Sin clave, sin coste por consulta y sin enviar textos de clientes a terceros.
  - `openai`: API compatible (`EMBEDDINGS_API_KEY`, `EMBEDDINGS_MODEL`, `EMBEDDINGS_BASE_URL`).
  - `none`: solo búsqueda por palabras.
- El modelo local se carga en segundo plano al arrancar la API. Mientras carga, o si el proveedor falla, el RAG funciona exactamente como antes.
- Tabla `knowledge_vectors` (migración `g019knowledgevectors`): vector por párrafo, identificado por el hash de título y texto y por el modelo. Al crear, editar, importar o eliminar documentos se borran los vectores obsoletos y se calculan solo los párrafos nuevos o modificados; al cambiar de modelo se recalculan.
- Recuperación híbrida en `app/services/knowledge.py`: la lista por palabras y la lista por similitud del coseno se combinan con reciprocal rank fusion (k = 60) y el LLM recibe los párrafos de más a menos relevante hasta llenar 6 000 caracteres, con un mínimo de cuatro: con una base pequeña recibe todo, ordenado; con una grande, lo más relevante que quepa. Las validaciones de citas y cifras de SPEC-015 no cambian. Sin LLM, la respuesta literal sigue saliendo de la búsqueda por palabras, para no mostrar un párrafo solo por parecido.
- Los vectores se calculan para todos los documentos, pero el chat público solo compara con los publicados; los borradores solo los ve «Probar pregunta».
- Estado en el Resumen de administración (`GET /admin/llm-status` → `embeddings`): activa, cargando, desactivada o no disponible.
- `scripts/index_knowledge.py`: descarga el modelo y calcula los vectores de todos los negocios antes de una presentación.
- Evaluación: `evals/rag_cases.json` (barbería ficticia, 12 documentos, 35 párrafos, 32 preguntas: 10 con las mismas palabras del documento y 22 coloquiales) y `scripts/eval_rag.py`, que compara palabras con y sin respaldo, significado e híbrido sin llamar al LLM.

## Decisión tras la primera medición
La primera versión enviaba siempre los 4 mejores párrafos ([informe](../../docs/evaluation-019/informe-inicial-4-parrafos.md), modelo local real): el correcto quedaba primero en 22/32 preguntas (8/32 con palabras) y llegaba al LLM en 26/32, frente a 8/32 de la búsqueda por palabras sin respaldo. Pero en una base pequeña recuperaba menos que el respaldo anterior, que enviaba casi todo (30/32). Por eso el envío pasó de un número fijo de párrafos a un espacio de 6 000 caracteres ordenado por relevancia: no empeora a las bases pequeñas y mantiene la mejora en las grandes.

## Resultados con el modelo real

Ejecutados por el autor en Windows sobre `evals/rag_cases.json` (32 preguntas). «Base grande» deja espacio solo para 4 párrafos, para simular una base varias veces mayor que los 6 000 caracteres.

| Escenario | Palabras (antes) | MiniLM, 220 MB ([informe](../../docs/evaluation-019/informe-rag.md)) | mpnet, 1 GB ([informe](../../docs/evaluation-019/informe-rag-mpnet.md)) |
| --- | --- | --- | --- |
| Base pequeña: párrafo correcto en lo que recibe el LLM | 30/32 | 32/32 | 32/32 |
| Base grande: párrafo correcto en lo que recibe el LLM | 8/32 | 26/32 | 30/32 |
| Base grande: preguntas coloquiales | 0/22 | 16/22 | 20/22 |
| Correcto en primer lugar | 8/32 | 22/32 | 23/32 |
| Tiempo de 192 consultas | — | 3,7 s | 6,4 s |

Decisión del autor: `paraphrase-multilingual-MiniLM-L12-v2` como modelo predeterminado. En bases pequeñas, las habituales hoy, ambos aciertan 32/32; mpnet solo mejora en bases grandes, a cambio de cuatro veces más memoria y casi el doble de tiempo, lo que limita los servidores económicos. Un negocio con una base grande puede usar mpnet con `EMBEDDINGS_MODEL`; los vectores se recalculan solos.

## Fuera de alcance
pgvector e índices aproximados (la comparación se hace en Python; suficiente para cientos de párrafos por negocio), reordenamiento con un segundo modelo, umbrales de similitud para responder sin LLM, OCR y memoria de conversación.

## Verificación
- `tests/test_semantic_rag.py` con un modelo de embeddings simulado (sin descargas): encuentra por significado lo que la búsqueda por palabras no encuentra, reutiliza vectores y recalcula solo lo editado, vuelve a palabras si el proveedor falla, mantiene privados los borradores, informa el estado y comprueba la coherencia del conjunto de evaluación.
- `python scripts/eval_rag.py --report docs/evaluation-019/informe-rag.md` con el modelo local real, ejecutado por el autor (el entorno aislado de desarrollo no tiene acceso a Hugging Face). Resultados arriba.
