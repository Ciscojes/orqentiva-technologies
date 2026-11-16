"""Prepara la búsqueda por significado: descarga el modelo y calcula los vectores de todos los negocios.

    python scripts/index_knowledge.py

No es obligatorio (la API calcula los vectores que falten al guardar documentos o al recibir
preguntas), pero conviene ejecutarlo una vez antes de una presentación: la primera carga del
modelo local descarga unos 220 MB y, mientras tanto, el RAG solo busca por palabras.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app import embeddings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import Business  # noqa: E402
from app.services import knowledge  # noqa: E402


def main():
    if not embeddings.enabled():
        raise SystemExit("EMBEDDINGS_PROVIDER=none: la búsqueda por significado está desactivada.")
    print(f"Cargando {embeddings.provider()} ({embeddings.model_name()})...")
    started = time.monotonic()
    embeddings.warm_up(wait=True)
    state = embeddings.status()
    if not state["ready"]:
        raise SystemExit(f"No disponible: {state['error']}")
    print(f"Modelo listo en {time.monotonic() - started:.1f} s")
    try:
        with SessionLocal() as session:
            for business_id, name in session.execute(select(Business.id, Business.name).order_by(Business.id)):
                items = knowledge.paragraphs(session, business_id, all_documents=True)
                knowledge.index_business(session, business_id)
                print(f"  - {name}: {len(items)} párrafos indexados")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
