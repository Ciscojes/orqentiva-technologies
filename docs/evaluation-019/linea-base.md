# Evaluación de la recuperación del RAG (SPEC-019)

Fecha: 2026-11-16. Embeddings: sin embeddings. Generado con `python scripts/eval_rag.py --report ...`.

Mide qué párrafos recibiría el LLM para responder cada pregunta, sin llamar al LLM. «Lo que recibe el LLM» son hasta 4 párrafos en los modos con embeddings; en el modo actual pueden ser todos los párrafos del negocio cuando la búsqueda por palabras no encuentra nada y el total cabe en 6 000 caracteres.

Base: 12 documentos, 35 párrafos, 3130 caracteres. Preguntas: 32 (10 con las mismas palabras del documento, 22 coloquiales).

| Modo | Párrafo correcto en lo que recibe el LLM | Correcto en primer lugar | Coloquiales: en lo que recibe el LLM | Párrafos enviados (promedio) |
| --- | --- | --- | --- | --- |
| Palabras (actual, con respaldo) | 30/32 | 8/32 | 20/22 | 24.4 |
| Palabras sin respaldo (base > 6 000 caracteres) | 8/32 | 8/32 | 0/22 | 0.4 |

Tiempo de las 64 consultas: 0.1 s.

## Preguntas no resueltas en modo palabras (actual, con respaldo)

- «¿Puedo pagar con el celular?»: esperado Pagos y depósitos §1; recibió Pagos y depósitos §4
- «Si me regalan una tarjeta, ¿me pueden dar el efectivo?»: esperado Tarjetas de regalo §2; recibió Pagos y depósitos §1

## Límites

- Conjunto pequeño y ficticio, escrito por el autor; no sustituye una evaluación con preguntas de clientes reales.
- Mide la recuperación, no la calidad de la respuesta redactada por el LLM ni sus validaciones.
