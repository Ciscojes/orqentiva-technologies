# Evaluación de la recuperación del RAG (SPEC-019)

Fecha: 2026-11-15. Embeddings: local · `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Generado con `python scripts/eval_rag.py --report ...`.

Mide qué párrafos recibiría el LLM para responder cada pregunta, sin llamar al LLM. En los modos con embeddings, el LLM recibe los párrafos de más a menos relevante hasta llenar 6 000 caracteres (en esta base cabe todo). Las filas «base grande» dejan espacio solo para 4 párrafos, para simular una base varias veces mayor que ese espacio; ahí la búsqueda por palabras ya no tiene respaldo.

Base: 12 documentos, 35 párrafos, 3130 caracteres. Preguntas: 32 (10 con las mismas palabras del documento, 22 coloquiales).

| Modo | Párrafo correcto en lo que recibe el LLM | Correcto en primer lugar | Coloquiales: en lo que recibe el LLM | Párrafos enviados (promedio) |
| --- | --- | --- | --- | --- |
| Palabras (antes, con respaldo) | 30/32 | 8/32 | 20/22 | 24.4 |
| Palabras, base grande (sin respaldo) | 8/32 | 8/32 | 0/22 | 0.4 |
| Significado | 32/32 | 18/32 | 22/22 | 35.0 |
| Híbrido (actual) | 32/32 | 22/32 | 22/22 | 35.0 |
| Significado, base grande (4 párrafos) | 26/32 | 18/32 | 16/22 | 4.0 |
| Híbrido, base grande (4 párrafos) | 26/32 | 22/32 | 16/22 | 4.0 |

Tiempo de las 192 consultas: 3.7 s.

## Preguntas no resueltas en modo híbrido, base grande (4 párrafos)

- «¿Dónde dejo el carro?»: esperado Ubicación y parqueo §2; recibió Ubicación y parqueo §3, Cancelaciones y cambios §3, Ubicación y parqueo §1, Mascotas y acompañantes §2
- «¿Las navajas son nuevas para cada persona?»: esperado Higiene y seguridad §1; recibió Tarjetas de regalo §1, Servicios y precios §1, Servicios para niños §1, Productos §1
- «¿Hay algún beneficio por ir seguido?»: esperado Promociones y fidelidad §1; recibió Promociones y fidelidad §3, Servicios para niños §1, Cancelaciones y cambios §3, Promociones y fidelidad §2
- «¿Puedo juntar el descuento de estudiante con otra oferta?»: esperado Promociones y fidelidad §3; recibió Promociones y fidelidad §2, Reservas en línea §2, Reservas en línea §4, Reservas en línea §1
- «¿Me cambian un champú que ya abrí?»: esperado Productos §2; recibió Cancelaciones y cambios §3, Reservas en línea §2, Pagos y depósitos §3, Horario y feriados §3
- «Somos cinco amigos para una despedida de soltero, ¿cómo hacemos?»: esperado Reservas en línea §4; recibió Mascotas y acompañantes §2, Cancelaciones y cambios §3, Horario y feriados §1, Reservas en línea §2

## Límites

- Conjunto pequeño y ficticio, escrito por el autor; no sustituye una evaluación con preguntas de clientes reales.
- Mide la recuperación, no la calidad de la respuesta redactada por el LLM ni sus validaciones.
