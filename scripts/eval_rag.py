"""Mide la recuperación del RAG: qué párrafos recibiría el LLM para cada pregunta (SPEC-019).

    python scripts/eval_rag.py --lexical-only     # sin modelo de embeddings (línea base)
    python scripts/eval_rag.py                    # descarga el modelo local la primera vez (~220 MB)
    python scripts/eval_rag.py --report docs/evaluation-019/informe-rag.md
    python scripts/eval_rag.py --model sentence-transformers/paraphrase-multilingual-mpnet-base-v2

Usa evals/rag_cases.json: una barbería ficticia con sus documentos y preguntas, cada una con
el párrafo que la responde. Crea una base SQLite temporal; no toca tus datos ni llama al LLM,
así que el resultado no depende de la redacción del modelo y se puede repetir sin coste.

Modos comparados:
- palabras (actual): búsqueda léxica y, si no encuentra nada y todo cabe en 6 000 caracteres,
  todos los párrafos del negocio.
- palabras sin respaldo: lo que ocurre cuando la base supera esos 6 000 caracteres.
- significado: solo embeddings.
- híbrido: fusión de ambas listas (el modo que usa la aplicación). El LLM recibe los párrafos de
  más a menos relevante hasta llenar 6 000 caracteres; en esta base cabe todo.
- «base grande»: el mismo orden, pero con espacio solo para 4 párrafos, que simula una base
  varias veces mayor que el espacio disponible (lo habitual con PDF importados).
"""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import embeddings  # noqa: E402
from app.models import Base, Business, KnowledgeDocument  # noqa: E402
from app.services import knowledge  # noqa: E402

CASES_FILE = ROOT / "evals" / "rag_cases.json"
LABELS = {"words": "Palabras (antes, con respaldo)", "strict": "Palabras, base grande (sin respaldo)",
          "semantic": "Significado", "hybrid": "Híbrido (actual)",
          "semantic_large": "Significado, base grande (4 párrafos)", "hybrid_large": "Híbrido, base grande (4 párrafos)"}


def build(data, folder):
    engine = create_engine("sqlite:///" + str(Path(folder) / "rag-eval.sqlite3"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(Business(id=data["business"]["id"], name=data["business"]["name"]))
        session.flush()
        for doc in data["documents"]:
            session.add(KnowledgeDocument(business_id=data["business"]["id"], **doc))
    return engine, factory


def candidates(session, data, question, mode):
    business = data["business"]
    if mode == "strict":
        items = knowledge.paragraphs(session, business["id"])
        return [source for _, source in knowledge.lexical_rank(question, business["name"], items)][:knowledge.MAX_CANDIDATES]
    base = mode.removesuffix("_large")
    _, found, used = knowledge.retrieve(session, business["id"], question, business["name"],
                                        mode={"words": "lexical"}.get(base, base),
                                        budget=0 if mode.endswith("_large") else knowledge.MAX_CONTEXT_CHARS)
    if base in ("semantic", "hybrid") and used != base:
        raise SystemExit("Los embeddings dejaron de responder durante la evaluación.")
    return found


def evaluate(data, factory, modes):
    results = {}
    for mode in modes:
        rows = []
        with factory() as session:
            for case in data["cases"]:
                expected = {tuple(item) for item in case["expected"]}
                found = candidates(session, data, case["question"], mode)
                keys = [(c["title"], c["paragraph"]) for c in found]
                rows.append({"case": case, "first": bool(keys) and keys[0] in expected,
                             "sent": bool(expected & set(keys)), "count": len(keys), "keys": keys})
        results[mode] = rows
    return results


def summary(rows, kind=None):
    rows = [r for r in rows if kind is None or r["case"]["kind"] == kind]
    n = len(rows) or 1
    return {"n": len(rows), "first": sum(r["first"] for r in rows), "sent": sum(r["sent"] for r in rows),
            "avg": sum(r["count"] for r in rows) / n}


def table(results, data):
    total_chars = sum(len(d["body"]) for d in data["documents"])
    paragraphs = sum(len([p for p in d["body"].split("\n\n") if p.strip()]) for d in data["documents"])
    lines = [f"Base: {len(data['documents'])} documentos, {paragraphs} párrafos, {total_chars} caracteres. "
             f"Preguntas: {len(data['cases'])} ({summary(next(iter(results.values())), 'literal')['n']} con las mismas palabras "
             f"del documento, {summary(next(iter(results.values())), 'coloquial')['n']} coloquiales).", "",
             "| Modo | Párrafo correcto en lo que recibe el LLM | Correcto en primer lugar | Coloquiales: en lo que recibe el LLM | Párrafos enviados (promedio) |",
             "| --- | --- | --- | --- | --- |"]
    for mode, rows in results.items():
        a, c = summary(rows), summary(rows, "coloquial")
        lines.append(f"| {LABELS[mode]} | {a['sent']}/{a['n']} | {a['first']}/{a['n']} | {c['sent']}/{c['n']} | {a['avg']:.1f} |")
    return "\n".join(lines)


def failures(rows):
    return [f"- «{r['case']['question']}»: esperado {', '.join(f'{t} §{p}' for t, p in r['case']['expected'])}; "
            f"recibió {', '.join(f'{t} §{p}' for t, p in r['keys'][:4]) or 'nada'}" for r in rows if not r["sent"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lexical-only", action="store_true", help="Solo los modos por palabras (sin modelo).")
    parser.add_argument("--report", help="Escribe el informe en Markdown en esta ruta.")
    parser.add_argument("--model", help="Modelo de embeddings a comparar (por defecto, el configurado).")
    args = parser.parse_args()
    if args.model:
        os.environ["EMBEDDINGS_MODEL"] = args.model
    data = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    modes = ["words", "strict"]
    if not args.lexical_only:
        if not embeddings.enabled():
            raise SystemExit("EMBEDDINGS_PROVIDER=none: usa --lexical-only o activa un proveedor.")
        print(f"Cargando embeddings {embeddings.provider()} ({embeddings.model_name()}); la primera vez se descarga el modelo...")
        started = time.monotonic()
        embeddings.warm_up(wait=True)
        state = embeddings.status()
        if not state["ready"]:
            raise SystemExit(f"Embeddings no disponibles: {state['error']}")
        print(f"Modelo listo en {time.monotonic() - started:.1f} s")
        modes += ["semantic", "hybrid", "semantic_large", "hybrid_large"]
    with tempfile.TemporaryDirectory() as folder:
        engine, factory = build(data, folder)
        try:
            started = time.monotonic()
            results = evaluate(data, factory, modes)
            elapsed = time.monotonic() - started
        finally:
            engine.dispose()
    report = table(results, data)
    print(report)
    best = "hybrid_large" if "hybrid_large" in results else "words"
    missed = failures(results[best])
    print(f"\nPreguntas sin el párrafo correcto en modo {LABELS[best].lower()}:" if missed else "\nTodas las preguntas recibieron el párrafo correcto.")
    print("\n".join(missed))
    if args.report:
        model = f"{embeddings.provider()} · `{embeddings.model_name()}`" if not args.lexical_only else "sin embeddings"
        text = "\n".join([
            "# Evaluación de la recuperación del RAG (SPEC-019)", "",
            f"Fecha: {time.strftime('%Y-%m-%d')}. Embeddings: {model}. Generado con `python scripts/eval_rag.py --report ...`.", "",
            "Mide qué párrafos recibiría el LLM para responder cada pregunta, sin llamar al LLM. En los modos con embeddings, "
            "el LLM recibe los párrafos de más a menos relevante hasta llenar 6 000 caracteres (en esta base cabe todo). "
            f"Las filas «base grande» dejan espacio solo para {knowledge.MAX_CANDIDATES} párrafos, para simular una base varias veces mayor "
            "que ese espacio; ahí la búsqueda por palabras ya no tiene respaldo.", "",
            report, "",
            f"Tiempo de las {len(data['cases']) * len(modes)} consultas: {elapsed:.1f} s.", "",
            f"## Preguntas no resueltas en modo {LABELS[best].lower()}", "",
            *(missed or ["Ninguna."]), "",
            "## Límites", "",
            "- Conjunto pequeño y ficticio, escrito por el autor; no sustituye una evaluación con preguntas de clientes reales.",
            "- Mide la recuperación, no la calidad de la respuesta redactada por el LLM ni sus validaciones.",
        ])
        # El informe solo se guarda como .md dentro del proyecto, nunca en otra ruta del equipo.
        target = (ROOT / args.report).resolve()
        if not target.is_relative_to(ROOT) or target.suffix != ".md":
            raise SystemExit("--report debe ser un archivo .md dentro del proyecto.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.replace("\n", os.linesep if os.name == "nt" else "\n").encode("utf-8") + b"\n")
        print(f"\nInforme escrito en {target}")


if __name__ == "__main__":
    main()
