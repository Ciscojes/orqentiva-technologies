"""Base de conocimiento de cada negocio: documentos, prueba de preguntas, PDF e historial.

El negocio gestiona la suya en /client/documents; la administración de la plataforma gestiona
la de cualquier negocio en /admin/businesses/{id}/documents. Ambas rutas comparten la misma
lógica y dejan registro en el historial (KnowledgeChange). La consulta con RAG está en
app/services/knowledge.py.
"""
import io
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import llm
from app.auth import current_user, require_super_admin
from app.deps import Database, Tenant
from app.models import Business, KnowledgeChange, KnowledgeDocument, User
from app.services import knowledge
from app.services.knowledge import MAX_CONTEXT_CHARS  # noqa: F401  (límite documentado; lo consulta tests/test_rag.py)

MAX_DOCUMENTS = 50
MAX_BODY = 6000
MAX_PDF_BYTES = 5 * 1024 * 1024
Actor = Annotated[User, Depends(current_user)]

router = APIRouter(prefix="/client/documents", tags=["knowledge"])
admin_router = APIRouter(prefix="/admin", tags=["knowledge"], dependencies=[Depends(require_super_admin)])


class DocumentIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=MAX_BODY)
    published: StrictBool = False


class QuestionIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=500)
    language: str = Field("es", pattern="^(es|en)$")
    include_drafts: StrictBool = True


def view(doc):
    return {"id":doc.id,"title":doc.title,"body":doc.body,"published":doc.published}


def change_view(row, business_name=None):
    data = {"id":row.id,"business_id":row.business_id,"document_id":row.document_id,"action":row.action,
            "actor_email":row.actor_email,"before_title":row.before_title,"before_body":row.before_body,
            "after_title":row.after_title,"after_body":row.after_body,"created_at":row.created_at.isoformat()}
    if business_name is not None:
        data["business_name"] = business_name
    return data


def record(session, business_id, actor, action, doc_id, before=None, after=None):
    session.add(KnowledgeChange(business_id=business_id, document_id=doc_id, action=action, actor_email=actor.email,
                                before_title=before and before[0], before_body=before and before[1],
                                after_title=after and after[0], after_body=after and after[1]))


def find_document(session, business_id, document_id):
    doc = session.scalar(select(KnowledgeDocument).where(KnowledgeDocument.business_id==business_id,
                                                         KnowledgeDocument.id==document_id))
    if doc is None:
        raise HTTPException(404, "Documento no encontrado")
    return doc


def ensure_business(session, business_id):
    if session.scalar(select(Business.id).where(Business.id==business_id).with_for_update()) is None:
        raise HTTPException(404, "Empresa no encontrada")


def ensure_capacity(session, business_id, adding=1):
    count = session.scalar(select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.business_id==business_id))
    if count + adding > MAX_DOCUMENTS:
        raise HTTPException(409, "Límite de documentos alcanzado")


# --- Operaciones compartidas -------------------------------------------------------------

def list_documents(session, business_id):
    return [view(d) for d in session.scalars(select(KnowledgeDocument).where(
        KnowledgeDocument.business_id==business_id).order_by(KnowledgeDocument.id))]


def create_document(session, business_id, actor, payload: DocumentIn):
    ensure_business(session, business_id)
    ensure_capacity(session, business_id)
    doc = KnowledgeDocument(business_id=business_id, **payload.model_dump())
    session.add(doc)
    session.flush()
    record(session, business_id, actor, "created", doc.id, after=(doc.title, doc.body))
    if doc.published:
        record(session, business_id, actor, "published", doc.id, after=(doc.title, doc.body))
    session.commit()
    return view(doc)


def update_document(session, business_id, actor, document_id, payload: DocumentIn):
    doc = find_document(session, business_id, document_id)
    before = (doc.title, doc.body)
    was_published = doc.published
    for key, value in payload.model_dump().items():
        setattr(doc, key, value)
    after = (doc.title, doc.body)
    if after != before:
        record(session, business_id, actor, "updated", doc.id, before=before, after=after)
    if doc.published != was_published:
        record(session, business_id, actor, "published" if doc.published else "unpublished", doc.id, after=after)
    session.commit()
    return view(doc)


def delete_document(session, business_id, actor, document_id):
    doc = find_document(session, business_id, document_id)
    record(session, business_id, actor, "deleted", doc.id, before=(doc.title, doc.body))
    session.delete(doc)
    session.commit()


def history(session, business_id, limit):
    rows = session.scalars(select(KnowledgeChange).where(KnowledgeChange.business_id==business_id)
                           .order_by(KnowledgeChange.created_at.desc(), KnowledgeChange.id.desc()).limit(limit))
    return [change_view(row) for row in rows]


def preview(session, business_id, payload: QuestionIn):
    name = session.scalar(select(Business.name).where(Business.id==business_id))
    if name is None:
        raise HTTPException(404, "Empresa no encontrada")
    result = knowledge.answer(session, business_id, payload.question, payload.language, name,
                              use_llm=llm.enabled(), include_drafts=payload.include_drafts)
    return {**result, "llm_enabled": llm.enabled()}


def pdf_paragraphs(data: bytes) -> list[str]:
    """Texto del PDF en párrafos: une las líneas cortadas y separa al final de cada frase o viñeta."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise HTTPException(422, "El PDF está protegido con contraseña")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except HTTPException:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError):
        raise HTTPException(422, "No se pudo leer el PDF") from None
    paragraphs, current = [], []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current)); current = []
            continue
        if current and re.match(r"^([-•·*▪●]|\d+[.)])\s", line):
            paragraphs.append(" ".join(current)); current = []
        current.append(line)
        if re.search(r"[.!?:]$", line):
            paragraphs.append(" ".join(current)); current = []
    if current:
        paragraphs.append(" ".join(current))
    return [p for p in paragraphs if len(p) > 1]


def chunks(paragraphs: list[str]) -> list[str]:
    """Agrupa párrafos en documentos de hasta MAX_BODY caracteres, sin partir ningún párrafo corto."""
    parts, current = [], ""
    for paragraph in paragraphs:
        while len(paragraph) > MAX_BODY:
            if current:
                parts.append(current); current = ""
            parts.append(paragraph[:MAX_BODY]); paragraph = paragraph[MAX_BODY:]
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > MAX_BODY:
            parts.append(current); current = paragraph
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


async def import_pdf(request: Request, session: Session, business_id: str, actor: User, title: str):
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/pdf":
        raise HTTPException(415, "Envía un archivo PDF")
    data = await request.body()
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(413, "El PDF supera 5 MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(422, "No se pudo leer el PDF")
    parts = chunks(pdf_paragraphs(data))
    if not parts:
        raise HTTPException(422, "El PDF no tiene texto seleccionable")
    ensure_business(session, business_id)
    ensure_capacity(session, business_id, len(parts))
    base = (title.strip() or "Documento importado")[:100]
    created = []
    for number, body in enumerate(parts, 1):
        name = base if len(parts) == 1 else f"{base} (parte {number})"
        doc = KnowledgeDocument(business_id=business_id, title=name[:120], body=body, published=False)
        session.add(doc)
        session.flush()
        record(session, business_id, actor, "imported", doc.id, after=(doc.title, doc.body))
        created.append(doc)
    session.commit()
    return [view(doc) for doc in created]


# --- Panel del negocio -------------------------------------------------------------------

@router.get("")
def documents(business_id: Tenant, session: Database):
    return list_documents(session, business_id)


@router.get("/status")
def status(business_id: Tenant):
    return {"llm_enabled": llm.enabled()}


@router.get("/history")
def own_history(business_id: Tenant, session: Database, limit: int = Query(30, ge=1, le=100)):
    return history(session, business_id, limit)


@router.post("", status_code=201)
def create(payload: DocumentIn, business_id: Tenant, actor: Actor, session: Database):
    return create_document(session, business_id, actor, payload)


@router.post("/preview")
def ask(payload: QuestionIn, business_id: Tenant, session: Database):
    return preview(session, business_id, payload)


@router.post("/import", status_code=201)
async def upload(request: Request, business_id: Tenant, actor: Actor, session: Database,
                 title: str = Query("", max_length=100)):
    return await import_pdf(request, session, business_id, actor, title)


@router.put("/{document_id}")
def update(document_id: int, payload: DocumentIn, business_id: Tenant, actor: Actor, session: Database):
    return update_document(session, business_id, actor, document_id, payload)


@router.delete("/{document_id}", status_code=204)
def remove(document_id: int, business_id: Tenant, actor: Actor, session: Database):
    delete_document(session, business_id, actor, document_id)


# --- Administración de la plataforma -----------------------------------------------------

def admin_business(session, business_id):
    if session.scalar(select(Business.id).where(Business.id==business_id)) is None:
        raise HTTPException(404, "Empresa no encontrada")
    return business_id


@admin_router.get("/llm-status")
def admin_status():
    return {"llm_enabled": llm.enabled()}


@admin_router.get("/knowledge-changes")
def recent_changes(session: Database, limit: int = Query(20, ge=1, le=100)):
    rows = session.execute(select(KnowledgeChange, Business.name).join(Business, Business.id==KnowledgeChange.business_id)
                           .order_by(KnowledgeChange.created_at.desc(), KnowledgeChange.id.desc()).limit(limit))
    return [change_view(row, name) for row, name in rows]


@admin_router.get("/businesses/{business_id}/documents")
def admin_documents(business_id: str, session: Database):
    return list_documents(session, admin_business(session, business_id))


@admin_router.get("/businesses/{business_id}/documents/history")
def admin_history(business_id: str, session: Database, limit: int = Query(50, ge=1, le=100)):
    return history(session, admin_business(session, business_id), limit)


@admin_router.post("/businesses/{business_id}/documents", status_code=201)
def admin_create(business_id: str, payload: DocumentIn, actor: Actor, session: Database):
    return create_document(session, admin_business(session, business_id), actor, payload)


@admin_router.post("/businesses/{business_id}/documents/preview")
def admin_ask(business_id: str, payload: QuestionIn, session: Database):
    return preview(session, admin_business(session, business_id), payload)


@admin_router.post("/businesses/{business_id}/documents/import", status_code=201)
async def admin_upload(business_id: str, request: Request, actor: Actor, session: Database,
                       title: str = Query("", max_length=100)):
    return await import_pdf(request, session, admin_business(session, business_id), actor, title)


@admin_router.put("/businesses/{business_id}/documents/{document_id}")
def admin_update(business_id: str, document_id: int, payload: DocumentIn, actor: Actor, session: Database):
    return update_document(session, admin_business(session, business_id), actor, document_id, payload)


@admin_router.delete("/businesses/{business_id}/documents/{document_id}", status_code=204)
def admin_remove(business_id: str, document_id: int, actor: Actor, session: Database):
    delete_document(session, admin_business(session, business_id), actor, document_id)
