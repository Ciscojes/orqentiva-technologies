"""Embeddings para la búsqueda por significado del RAG (SPEC-019).

Un embedding convierte un párrafo en un vector que representa su significado: dos textos
que dicen lo mismo con palabras distintas quedan cerca. Proveedores (EMBEDDINGS_PROVIDER):

- local (predeterminado): modelo multilingüe que corre en el servidor con fastembed (ONNX),
  sin clave ni coste. Se descarga una vez (unos 220 MB) en EMBEDDINGS_CACHE.
- openai: API compatible con OpenAI (EMBEDDINGS_API_KEY, EMBEDDINGS_BASE_URL).
- none: desactivado; el RAG usa solo la búsqueda por palabras.

Nada aquí bloquea una respuesta: si el modelo local aún se está cargando o el proveedor
falla, embed() devuelve None y el RAG sigue con la búsqueda por palabras.
"""
import logging
import math
import os
import threading
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger("uvicorn.error.embeddings")
DEFAULT_MODELS = {"local": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                  "openai": "text-embedding-3-small"}
TIMEOUT_SECONDS = 8.0
RETRY_SECONDS = 300

for _key, _value in dotenv_values(ROOT / ".env").items():
    if _key.startswith("EMBEDDINGS_") and _value and _key not in os.environ:
        os.environ[_key] = _value

_lock = threading.Lock()
_model = None
_loading = False
_error: str | None = None
_failed_at = 0.0
_override = None  # Las pruebas instalan aquí un modelo simulado (set_backend).


def provider() -> str:
    value = os.getenv("EMBEDDINGS_PROVIDER", "local").strip().lower()
    return value if value in DEFAULT_MODELS or value == "none" else "none"


def model_name() -> str:
    if _override is not None:
        return "prueba"
    return os.getenv("EMBEDDINGS_MODEL") or DEFAULT_MODELS.get(provider(), "")


def model_id() -> str:
    """Identifica los vectores guardados: al cambiar de modelo se recalculan."""
    return f"{'prueba' if _override is not None else provider()}:{model_name()}"[:200]


def enabled() -> bool:
    return _override is not None or provider() != "none"


def set_backend(function) -> None:
    """Solo para pruebas: function(textos, tipo) -> vectores. None restablece el proveedor."""
    global _override
    _override = function


def status() -> dict:
    if _override is not None:
        return {"provider": "prueba", "model": "prueba", "ready": True, "error": None}
    current = provider()
    ready = current == "openai" and bool(os.getenv("EMBEDDINGS_API_KEY")) or current == "local" and _model is not None
    error = _error
    if current == "openai" and not os.getenv("EMBEDDINGS_API_KEY"):
        error = "Falta EMBEDDINGS_API_KEY"
    return {"provider": current, "model": model_name() if current != "none" else None, "ready": ready,
            "loading": current == "local" and _loading, "error": error}


def _load_local():
    global _model, _loading, _error, _failed_at
    try:
        from fastembed import TextEmbedding
        cache = os.getenv("EMBEDDINGS_CACHE") or str(ROOT / ".cache" / "embeddings")
        started = time.monotonic()
        model = TextEmbedding(model_name(), cache_dir=cache)
        list(model.embed(["calentamiento"]))
        with _lock:
            _model, _error = model, None
        logger.info("Embeddings locales listos: %s (%.1f s)", model_name(), time.monotonic() - started)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo deja el RAG en modo palabras
        with _lock:
            _error, _failed_at = f"No se pudo cargar el modelo local ({type(exc).__name__})", time.monotonic()
        logger.warning("%s; el RAG sigue con la búsqueda por palabras", _error)
    finally:
        with _lock:
            _loading = False


def warm_up(wait: bool = False) -> None:
    """Carga el modelo local en segundo plano (o esperando, para scripts)."""
    global _loading
    if _override is not None or provider() != "local":
        return
    with _lock:
        if _model is not None or _loading or (_error and time.monotonic() - _failed_at < RETRY_SECONDS):
            return
        _loading = True
    if wait:
        _load_local()
    else:
        threading.Thread(target=_load_local, name="embeddings-warm-up", daemon=True).start()


def _normalize(vector) -> list[float]:
    values = [float(x) for x in vector]
    norm = math.sqrt(sum(x * x for x in values)) or 1.0
    return [round(x / norm, 6) for x in values]


def embed(texts: list[str], kind: str = "passage") -> list[list[float]] | None:
    """Vectores normalizados para textos de documentos (passage) o preguntas (query)."""
    if not texts:
        return []
    try:
        if _override is not None:
            return [_normalize(v) for v in _override(texts, kind)]
        current = provider()
        if current == "local":
            if _model is None:
                warm_up()
                return None
            return [_normalize(v) for v in _model.embed(texts)]
        if current == "openai":
            key = os.getenv("EMBEDDINGS_API_KEY")
            if not key:
                return None
            base = os.getenv("EMBEDDINGS_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            response = httpx.post(f"{base}/embeddings", headers={"Authorization": f"Bearer {key}"},
                                  json={"model": model_name(), "input": texts}, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            rows = sorted(response.json()["data"], key=lambda row: row["index"])
            return [_normalize(row["embedding"]) for row in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embeddings no disponibles (%s); se usa la búsqueda por palabras", type(exc).__name__)
    return None


def cosine(a: list[float], b: list[float]) -> float:
    """Los vectores ya están normalizados: el producto escalar es la similitud del coseno."""
    return sum(x * y for x, y in zip(a, b))
