"""Base de conocimiento: eliminar, probar pregunta, PDF, historial y gestión desde administración."""
from app.routes.knowledge import chunks, MAX_BODY


def auth(name):
    return {"Cookie": f"orqentiva_session=test-{name}", "Origin": "http://testserver"}


ALFA, BETA, ADMIN = map(auth, ("alfa", "beta", "admin"))
URL = "/client/documents"
POLICY = {"title": "Condiciones", "body": "Aceptamos efectivo.\n\nPara cancelar, avisa con 24 horas de anticipación."}
QUESTION = "¿Con cuánta anticipación puedo cancelar?"


def pdf(lines):
    """PDF mínimo de una página con texto seleccionable."""
    stream = "BT /F1 12 Tf 50 750 Td 14 TL " + " ".join(f"({line}) Tj T*" for line in lines) + " ET"
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
               "/Resources << /Font << /F1 5 0 R >> >> >>",
               f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = "%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    return out.encode("latin-1")


def test_delete_requires_owner_and_is_recorded(client):
    doc = client.post(URL, headers=ALFA, json={**POLICY, "published": True}).json()
    assert client.delete(f"{URL}/{doc['id']}").status_code == 401
    assert client.delete(f"{URL}/{doc['id']}", headers=BETA).status_code == 404
    assert client.delete(f"{URL}/{doc['id']}", headers=ALFA).status_code == 204
    assert client.get(URL, headers=ALFA).json() == []
    assert client.delete(f"{URL}/{doc['id']}", headers=ALFA).status_code == 404
    actions = [row["action"] for row in client.get(f"{URL}/history", headers=ALFA).json()]
    assert actions == ["deleted", "published", "created"]
    deleted = client.get(f"{URL}/history", headers=ALFA).json()[0]
    assert deleted["before_body"] == POLICY["body"] and deleted["actor_email"] == "alfa@example.com"
    assert client.get(f"{URL}/history", headers=BETA).json() == []


def test_history_keeps_before_and_after(client):
    doc = client.post(URL, headers=ALFA, json=POLICY).json()
    changed = {**POLICY, "body": POLICY["body"].replace("24", "48"), "published": True}
    client.put(f"{URL}/{doc['id']}", headers=ALFA, json=changed)
    client.put(f"{URL}/{doc['id']}", headers=ALFA, json=changed)  # sin cambios: sin registro
    rows = client.get(f"{URL}/history", headers=ALFA).json()
    assert [row["action"] for row in rows] == ["published", "updated", "created"]
    assert "24" in rows[1]["before_body"] and "48" in rows[1]["after_body"]


def test_preview_sees_drafts_only_when_asked(client):
    client.post(URL, headers=ALFA, json=POLICY)
    draft = client.post(f"{URL}/preview", headers=ALFA, json={"question": QUESTION}).json()
    assert draft["sources"] and draft["llm_enabled"] is False
    public = client.post(f"{URL}/preview", headers=ALFA, json={"question": QUESTION, "include_drafts": False}).json()
    assert not public["sources"]
    assert not client.post("/book/alfa/chat", json={"message": QUESTION}).json().get("sources")
    assert client.post(f"{URL}/preview", headers=ADMIN, json={"question": QUESTION}).status_code == 403
    assert client.get(f"{URL}/status", headers=ALFA).json() == {"llm_enabled": False}


def test_pdf_import_creates_drafts(client):
    data = pdf(["Formas de pago", "Aceptamos efectivo y tarjeta.", "Para cancelar avisa con",
                "24 horas de anticipacion."])
    headers = {**ALFA, "Content-Type": "application/pdf"}
    created = client.post(f"{URL}/import?title=Politicas", headers=headers, content=data)
    assert created.status_code == 201, created.text
    [doc] = created.json()
    assert doc["title"] == "Politicas" and doc["published"] is False
    assert "Para cancelar avisa con 24 horas de anticipacion." in doc["body"].split("\n\n")
    assert client.get(f"{URL}/history", headers=ALFA).json()[0]["action"] == "imported"
    assert client.post(f"{URL}/import", headers={**ALFA, "Content-Type": "text/plain"}, content=b"x").status_code == 415
    assert client.post(f"{URL}/import", headers=headers, content=b"not a pdf").status_code == 422
    assert client.post(f"{URL}/import", headers=headers, content=pdf([])).status_code == 422


def test_chunks_respect_document_limit():
    parts = chunks(["a" * 4000, "b" * 4000, "c" * 13000])
    assert all(len(part) <= MAX_BODY for part in parts)
    assert "".join(parts).replace("\n", "") == "a" * 4000 + "b" * 4000 + "c" * 13000


def test_admin_manages_any_business_knowledge(client):
    base = "/admin/businesses/alfa/documents"
    assert client.get(base, headers=ALFA).status_code == 403
    assert client.get("/admin/businesses/nadie/documents", headers=ADMIN).status_code == 404
    doc = client.post(base, headers=ADMIN, json={**POLICY, "published": True}).json()
    assert client.get(URL, headers=ALFA).json()[0]["id"] == doc["id"]
    assert client.post("/book/alfa/chat", json={"message": QUESTION}).json()["sources"]
    assert client.put(f"/admin/businesses/beta/documents/{doc['id']}", headers=ADMIN, json=POLICY).status_code == 404
    assert client.post(f"{base}/preview", headers=ADMIN, json={"question": QUESTION}).json()["sources"]
    client.post(URL, headers=ALFA, json={"title": "Horario", "body": "Abrimos de lunes a sábado."})
    history = client.get(f"{base}/history", headers=ADMIN).json()
    assert {row["actor_email"] for row in history} == {"admin@example.com", "alfa@example.com"}
    recent = client.get("/admin/knowledge-changes", headers=ADMIN).json()
    assert recent[0]["business_name"] and recent[0]["after_title"] == "Horario"
    assert client.get("/admin/knowledge-changes", headers=ALFA).status_code == 403
    assert client.delete(f"{base}/{doc['id']}", headers=ADMIN).status_code == 204
    assert client.get("/admin/llm-status", headers=ADMIN).json() == {"llm_enabled": False}


def test_admin_reads_business_agenda(client):
    assert client.get("/admin/businesses/alfa/dashboard", headers=ALFA).status_code == 403
    assert client.get("/admin/businesses/nadie/dashboard", headers=ADMIN).status_code == 404
    data = client.get("/admin/businesses/alfa/dashboard", headers=ADMIN).json()
    assert data == client.get("/client/dashboard", headers=ALFA).json()
