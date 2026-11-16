"""Consulta de documentos del negocio con RAG.

Recuperación híbrida (SPEC-019):
- Por palabras: párrafos publicados que comparten términos con la pregunta (sin costo ni red).
- Por significado: con embeddings activos (app/embeddings.py), los párrafos más cercanos a la
  pregunta aunque usen otras palabras. Los vectores se guardan en knowledge_vectors y solo se
  recalculan los párrafos nuevos o modificados.
- Fusión: ambas listas se combinan por posición (reciprocal rank fusion) y el LLM recibe los
  párrafos de más a menos relevante hasta llenar MAX_CONTEXT_CHARS (mínimo MAX_CANDIDATES):
  con una base pequeña recibe todo, ordenado; con una grande, lo más relevante que quepa.
Sin embeddings, o si fallan, se comporta como antes: búsqueda por palabras y, si no encuentra
nada y el total cabe en MAX_CONTEXT_CHARS, todos los párrafos del negocio.
Generación: si el LLM está activo, redacta la respuesta solo con esos párrafos y cita
cuáles usó (app/llm.py). Sin LLM, o si su respuesta no es válida, se devuelve el párrafo
literal encontrado por palabras.
"""
import hashlib
import re
import unicodedata

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from app import embeddings, llm
from app.models import KnowledgeDocument, KnowledgeVector

STOP = set("que cual cuales cuanto cuanta puedo puedo pueden tiene tienen tiene con sin una uno los las para por como este esta del hay sobre cita citas negocio negocios politica politicas reserva reservas policy policies booking appointment appointments what when how much the can with your are you and about does have their this business".split())
GROUPS = {
    "cancel": "cancelar cancelacion cancelaciones cancelo cancela cancelar cancelan cancel cancellation cancellations cancelling canceled",
    "notice": "anticipacion antelacion aviso preaviso anticipada antes beforehand advance notice",
    "payment": "pago pagos pagar payment payments pay",
    "refund": "reembolso reembolsos devolucion devoluciones refund refunds",
    "late": "tarde tardanza retraso retrasos late lateness",
    "change": "reprogramar reprogramacion reagendar reschedule rescheduling",
    "card": "tarjeta tarjetas card cards",
    "cash": "efectivo cash",
    "deposit": "anticipo anticipos deposito deposit deposits",
}
ALIASES = {word:key for key,words in GROUPS.items() for word in words.split()}


def tokens(text):
    plain = "".join(c for c in unicodedata.normalize("NFD",text.lower()) if not unicodedata.combining(c))
    return {ALIASES.get(w,w) for w in re.findall(r"[a-z0-9]+",plain) if len(w)>2 and w not in STOP}


def policy_question(message):
    return bool(tokens(message) & set(GROUPS)) or bool(re.search(r"\b(pol[ií]ticas?|polic(?:y|ies))\b",message,re.I))


# Si la búsqueda léxica no encuentra nada, el LLM puede leer todos los párrafos del negocio
# cuando caben en este tamaño; así entiende sinónimos sin embeddings ni costos extra.
MAX_CONTEXT_CHARS = 6000
MAX_CANDIDATES = 4
RRF_K = 60


def paragraphs(session, business_id, include_drafts=False, all_documents=False):
    query = select(KnowledgeDocument).where(KnowledgeDocument.business_id==business_id)
    if not (include_drafts or all_documents):
        query = query.where(KnowledgeDocument.published.is_(True))
    found = []
    for doc in session.scalars(query.order_by(KnowledgeDocument.id)):
        parts = [p.strip() for p in re.split(r"\n\s*\n", doc.body) if p.strip()]
        for number, paragraph in enumerate(parts, 1):
            found.append({"title": doc.title, "paragraph": number, "quote": paragraph, "single": len(parts) == 1})
    return found


def lexical_rank(question, business_name, candidates):
    """Búsqueda por palabras de SPEC-011: (puntuación, párrafo) de mayor a menor."""
    terms = tokens(question) - tokens(business_name)
    hits = []
    for item in candidates:
        paragraph, title_words = item["quote"], tokens(item["title"])
        words = tokens(paragraph)
        common = terms & words
        title = terms & title_words
        topics = terms & set(GROUPS)
        evidence = words | (title_words if item["single"] else set())
        if not terms or not topics.issubset(evidence):
            continue
        if not common and not (item["single"] and title):
            continue
        coverage = len(terms & evidence)/len(terms)
        if coverage < 0.5:
            continue
        hits.append(((coverage, len(common), len(title)), public(item)))
    hits.sort(key=lambda pair: pair[0], reverse=True)
    return hits


def public(item):
    return {"title": item["title"], "paragraph": item["paragraph"], "quote": item["quote"]}


def text_hash(item):
    return hashlib.sha256(f"{item['title']}\n{item['quote']}".encode("utf-8")).hexdigest()


def vectors_for(session, business_id, items):
    """Vectores de los párrafos; calcula y guarda solo los que faltan. None si no hay embeddings."""
    if not embeddings.enabled() or not items:
        return None
    model = embeddings.model_id()
    stored = {row.text_hash: row.vector for row in session.scalars(select(KnowledgeVector).where(
        KnowledgeVector.business_id==business_id, KnowledgeVector.model==model))}
    hashes = [text_hash(item) for item in items]
    missing = {h: item for h, item in zip(hashes, items) if h not in stored}
    if missing:
        texts = [f"{item['title']}. {item['quote']}" for item in missing.values()]
        vectors = embeddings.embed(texts, "passage")
        if vectors is None:
            return None
        for h, vector in zip(missing, vectors):
            stored[h] = vector
        try:
            session.add_all(KnowledgeVector(business_id=business_id, model=model, text_hash=h, vector=v)
                            for h, v in zip(missing, vectors))
            session.commit()
        except SQLAlchemyError:
            session.rollback()  # Otra petición los guardó a la vez: se usan los calculados aquí.
    return [stored[h] for h in hashes]


def prune_vectors(session, business_id):
    """Borra vectores de párrafos que ya no existen o de otro modelo. Lo llama la gestión de documentos."""
    current = {text_hash(item) for item in paragraphs(session, business_id, all_documents=True)}
    rows = session.scalars(select(KnowledgeVector).where(KnowledgeVector.business_id==business_id))
    stale = [(row.model, row.text_hash) for row in rows
             if row.text_hash not in current or row.model != embeddings.model_id()]
    for model, h in stale:
        session.execute(delete(KnowledgeVector).where(KnowledgeVector.business_id==business_id,
                                                      KnowledgeVector.model==model, KnowledgeVector.text_hash==h))
    return len(stale)


def index_business(session, business_id):
    """Tras guardar documentos: borra vectores obsoletos y calcula los nuevos si el modelo está listo."""
    if not embeddings.enabled():
        return
    try:
        if prune_vectors(session, business_id):
            session.commit()
        vectors_for(session, business_id, paragraphs(session, business_id, all_documents=True))
    except SQLAlchemyError:
        session.rollback()


def semantic_rank(session, business_id, question, items):
    """(similitud, párrafo) de mayor a menor, o None si los embeddings no están disponibles."""
    vectors = vectors_for(session, business_id, items)
    if vectors is None:
        return None
    query = embeddings.embed([question], "query")
    if not query:
        return None
    ranked = [(embeddings.cosine(query[0], vector), public(item)) for vector, item in zip(vectors, items)]
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return ranked


def fuse(*rankings):
    """Reciprocal rank fusion: premia los párrafos bien situados en cualquiera de las listas."""
    scores, order = {}, {}
    for ranking in rankings:
        for position, (_, source) in enumerate(ranking):
            key = (source["title"], source["paragraph"])
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + position + 1)
            order.setdefault(key, source)
    return [order[key] for key in sorted(scores, key=lambda key: scores[key], reverse=True)]


def within_budget(ranked, budget):
    """Los primeros párrafos hasta llenar budget caracteres, y al menos MAX_CANDIDATES."""
    chosen, used = [], 0
    for source in ranked:
        if len(chosen) >= MAX_CANDIDATES and used + len(source["quote"]) > budget:
            break
        chosen.append(source)
        used += len(source["quote"])
    return chosen


def retrieve(session, business_id, question, business_name, include_drafts=False, mode="hybrid",
             budget=MAX_CONTEXT_CHARS):
    """Devuelve (fuentes literales por palabras, candidatos para el LLM, modo usado).

    mode: "hybrid" (predeterminado), "lexical" o "semantic"; los dos últimos los usa la evaluación.
    budget: caracteres de contexto para el LLM; la evaluación lo reduce para simular bases grandes.
    """
    items = paragraphs(session, business_id, include_drafts)
    hits = lexical_rank(question, business_name, items)
    sources = [source for score, source in hits if score==hits[0][0]][:3] if hits else []
    semantic = semantic_rank(session, business_id, question, items) if mode != "lexical" else None
    if semantic is None:
        candidates = [source for _, source in hits][:MAX_CANDIDATES] or fit([public(i) for i in items])
        return sources, candidates, "lexical"
    if mode == "semantic":
        return sources, within_budget([source for _, source in semantic], budget), "semantic"
    return sources, within_budget(fuse(hits, semantic), budget), "hybrid"


def answer(session, business_id, question, language, business_name, use_llm=False, include_drafts=False):
    """include_drafts solo lo usa "Probar pregunta" del panel; el chat público nunca ve borradores."""
    sources, candidates, _ = retrieve(session, business_id, question, business_name, include_drafts)
    if use_llm:
        generated = generate(question, language, candidates, bool(sources))
        if generated is not None:
            return generated
    if sources:
        reply = "Esto indica el negocio en su documentación:" if language=="es" else "The business gives the following information:"
    else:
        reply = ("No encontré una respuesta documentada. Consulta directamente con el negocio."
                 if language=="es" else "I couldn't find a documented answer. Please ask the business directly.")
    return {"kind":"knowledge","reply":reply,"sources":sources,"generated":False}


def fit(paragraphs):
    """Todos los párrafos publicados si caben en el contexto; si no, ninguno."""
    return paragraphs if sum(len(p["quote"]) for p in paragraphs) <= MAX_CONTEXT_CHARS else []


def generate(question, language, candidates, has_extractive):
    """Paso de generación del RAG; None para volver al modo extractivo."""
    numbered = [{**c, "id": f"p{i}"} for i, c in enumerate(candidates, 1)]
    result = llm.answer_from_sources(question, numbered, language)
    if result is None:
        return None
    if result["answer"] is None:
        # El LLM no ve respuesta: si la búsqueda léxica sí encontró algo, se muestra literal.
        if has_extractive:
            return None
        reply = ("No encontré una respuesta documentada. Consulta directamente con el negocio."
                 if language=="es" else "I couldn't find a documented answer. Please ask the business directly.")
        return {"kind":"knowledge","reply":reply,"sources":[],"generated":False}
    by_id = {c["id"]: c for c in numbered}
    sources = [{k: by_id[i][k] for k in ("title","paragraph","quote")} for i in result["source_ids"]]
    return {"kind":"knowledge","reply":result["answer"],"sources":sources,"generated":True}
