"""Búsqueda por significado (SPEC-019) con un modelo de embeddings simulado, sin descargas."""
import re
import unicodedata

import pytest
from sqlalchemy import func, select

from app import embeddings
from app.models import KnowledgeVector
from app.services import knowledge

# Conceptos del modelo simulado: palabras distintas con el mismo significado comparten dimensión.
CONCEPTS = {"money": "plata dinero efectivo deposito adelanto", "refund": "devuelven regresan devolvemos reembolso devolver",
            "car": "carro parqueo estacionamiento auto", "pet": "perro mascotas mascota gato", "late": "atraso tarde atrasarme"}
WORDS = {w: i for i, (_, ws) in enumerate(CONCEPTS.items()) for w in ws.split()}


def fake(texts, kind):
    vectors = []
    for text in texts:
        plain = "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c))
        vector = [0.0] * (len(CONCEPTS) + 1)
        for word in re.findall(r"[a-z]+", plain):
            vector[WORDS.get(word, len(CONCEPTS))] += 1.0 if word in WORDS else 0.05
        vectors.append(vector)
    calls.append(len(texts))
    return vectors


calls = []
DOCS = {"Pagos": "Aceptamos efectivo y tarjeta.\n\nSi cancelas a tiempo, te devolvemos el depósito.",
        "Ubicación": "Estamos frente al parque central.\n\nHay parqueo gratuito frente al local.",
        "Mascotas": "No se permiten mascotas dentro del local."}


def auth(name):
    return {"Cookie": f"orqentiva_session=test-{name}", "Origin": "http://testserver"}


@pytest.fixture
def semantic():
    calls.clear()
    embeddings.set_backend(fake)
    yield
    embeddings.set_backend(None)


def publish(client):
    ids = {}
    for title, body in DOCS.items():
        ids[title] = client.post("/client/documents", headers=auth("alfa"), json={"title": title, "body": body, "published": True}).json()["id"]
    return ids


def retrieve(session_factory, question, **kw):
    with session_factory() as session:
        return knowledge.retrieve(session, "alfa", question, "Barbería Alfa", **kw)


def test_meaning_is_found_when_words_differ(client, session_factory, semantic):
    publish(client)
    question = "¿Dónde dejo el carro?"
    sources, lexical, mode = retrieve(session_factory, question, mode="lexical")
    assert not sources and mode == "lexical"
    _, candidates, mode = retrieve(session_factory, question)
    assert mode == "hybrid" and candidates[0]["quote"] == "Hay parqueo gratuito frente al local."
    _, candidates, _ = retrieve(session_factory, "¿Me regresan la plata?", mode="semantic")
    assert candidates[0]["title"] == "Pagos" and candidates[0]["paragraph"] == 2
    assert len(candidates) == knowledge.MAX_CANDIDATES


def test_vectors_are_reused_and_follow_edits(client, session_factory, semantic):
    ids = publish(client)
    count = lambda: session_factory().scalar(select(func.count()).select_from(KnowledgeVector))
    assert count() == 5
    calls.clear()
    retrieve(session_factory, "¿Hay parqueo?")
    assert calls == [1]  # solo la pregunta: los párrafos ya estaban calculados
    calls.clear()
    client.put(f"/client/documents/{ids['Ubicación']}", headers=auth("alfa"),
               json={"title": "Ubicación", "body": DOCS["Ubicación"].replace("gratuito", "sin costo"), "published": True})
    assert calls == [1] and count() == 5  # se recalcula solo el párrafo editado
    client.delete(f"/client/documents/{ids['Mascotas']}", headers=auth("alfa"))
    assert count() == 4


def test_failure_falls_back_to_words(client, session_factory, semantic):
    publish(client)
    def broken(texts, kind):
        raise RuntimeError("sin modelo")
    embeddings.set_backend(broken)
    sources, candidates, mode = retrieve(session_factory, "¿Puedo llevar mascotas?")
    assert mode == "lexical" and sources[0]["title"] == "Mascotas"


def test_drafts_stay_private(client, session_factory, semantic):
    client.post("/client/documents", headers=auth("alfa"), json={"title": "Borrador", "body": "Hay parqueo gratuito.", "published": False})
    _, candidates, _ = retrieve(session_factory, "¿Dónde dejo el carro?")
    assert candidates == []
    _, candidates, _ = retrieve(session_factory, "¿Dónde dejo el carro?", include_drafts=True)
    assert candidates[0]["title"] == "Borrador"
    assert not client.post("/book/alfa/chat", json={"message": "¿Dónde dejo el carro?", "mode": "knowledge"}).json()["sources"]


def test_status_reports_semantic_search(client, semantic):
    data = client.get("/client/documents/status", headers=auth("alfa")).json()
    assert data["embeddings"]["ready"] is True


def test_rag_evaluation_set_is_consistent(tmp_path):
    """Cada respuesta esperada existe y la línea base por palabras no empeora sin avisar."""
    import json
    from scripts.eval_rag import CASES_FILE, build, evaluate, summary
    data = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    existing = {(d["title"], n) for d in data["documents"] for n, _ in enumerate(d["body"].split("\n\n"), 1)}
    assert all(tuple(item) in existing for case in data["cases"] for item in case["expected"])
    engine, factory = build(data, tmp_path)
    try:
        results = evaluate(data, factory, ["words", "strict"])
    finally:
        engine.dispose()
    assert summary(results["strict"])["sent"] >= 8 and summary(results["words"])["sent"] >= 30
