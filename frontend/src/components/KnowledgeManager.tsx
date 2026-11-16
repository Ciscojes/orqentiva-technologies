import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import type { Language } from "../services";

/**
 * Base de conocimiento de un negocio. La usan el panel del negocio (/client/documents)
 * y la ficha de cada negocio en administración (/admin/businesses/{id}/documents).
 */
export type Doc = { id: number; title: string; body: string; published: boolean };
type Source = { title: string; paragraph: number; quote: string };
type Preview = { reply: string; sources: Source[]; generated: boolean; llm_enabled: boolean };
type Props = { language: Language; basePath: string; statusPath: string; onSessionEnded: () => void };

export class ApiError extends Error { status: number; constructor(status: number) { super("Request failed"); this.status = status; } }
export async function api(path: string, options: RequestInit = {}) {
  const response = await fetch(path, { credentials: "same-origin", cache: "no-store", ...options,
    headers: { "Content-Type": "application/json", ...options.headers }, signal: options.signal ?? AbortSignal.timeout(20000) });
  if (!response.ok) throw new ApiError(response.status);
  return response.status === 204 ? null : response.json();
}
export const lostSession = (error: unknown) => error instanceof ApiError && [401, 403].includes(error.status);

const TEMPLATES = {
  es: [
    { title: "Formas de pago", body: "Aceptamos efectivo, tarjeta y SINPE Móvil.\n\nEl pago se realiza al terminar el servicio.\n\nNo solicitamos depósito para reservar." },
    { title: "Cancelaciones", body: "Para cancelar o reprogramar una cita, avisa con al menos 24 horas de anticipación.\n\nSi llegas más de 15 minutos tarde, es posible que debamos reprogramar tu cita.\n\nPuedes cancelar escribiéndonos por WhatsApp." },
    { title: "Ubicación y parqueo", body: "Estamos en [dirección exacta, con una referencia conocida].\n\nHay parqueo gratuito frente al local.\n\nEl local es accesible para sillas de ruedas." },
    { title: "Preguntas frecuentes", body: "¿Atienden sin cita? Sí, según disponibilidad; con cita tienes prioridad.\n\n¿Atienden a niños? Sí, a partir de [edad] años.\n\n¿Venden productos? Sí, tenemos [productos] a la venta en el local." },
  ],
  en: [
    { title: "Payment methods", body: "We accept cash and cards.\n\nPayment is made after the service.\n\nNo deposit is required to book." },
    { title: "Cancellations", body: "To cancel or reschedule an appointment, let us know at least 24 hours in advance.\n\nIf you arrive more than 15 minutes late, we may need to reschedule.\n\nYou can cancel by sending us a WhatsApp message." },
    { title: "Location and parking", body: "We are at [exact address, with a well-known landmark].\n\nFree parking is available in front of the shop.\n\nThe shop is wheelchair accessible." },
    { title: "Frequently asked questions", body: "Do you take walk-ins? Yes, depending on availability; appointments have priority.\n\nDo you serve children? Yes, from [age] years old.\n\nDo you sell products? Yes, we sell [products] in the shop." },
  ],
};

const copy = {
  es: {
    title: "Base de conocimiento", intro: "Lo que publiques aquí es lo que el chat de reservas usa para responder a tus clientes. Escribe un tema por documento y separa cada idea con una línea en blanco.",
    llmOff: "El asistente de IA (LLM) está desactivado. El chat solo mostrará párrafos literales y no entenderá sinónimos. Revisa la configuración del servidor.",
    docs: "Documentos", none: "Todavía no hay documentos. Empieza con una plantilla o sube un PDF.", published: "Publicado", draft: "Borrador",
    edit: "Editar", remove: "Eliminar", confirmRemove: "¿Eliminar este documento? El chat dejará de usarlo de inmediato.", yesRemove: "Sí, eliminar", cancel: "Cancelar",
    newDoc: "Nuevo documento", editing: "Editar documento", docTitle: "Título del documento", body: "Contenido", publish: "Publicar para consultas del chat",
    save: "Guardar documento", saving: "Guardando…", saved: "Documento guardado.", removed: "Documento eliminado.", newBtn: "Crear documento nuevo",
    templates: "Plantillas", templatesHelp: "Rellena el formulario con un ejemplo que puedes adaptar. Cambia lo que está entre corchetes.",
    pdf: "Subir PDF", pdfHelp: "Se extrae el texto y se crea como borrador para que lo revises antes de publicarlo. Máximo 5 MB.", pdfBusy: "Leyendo el PDF…",
    pdfDone: (n: number) => n === 1 ? "PDF importado como borrador. Revísalo y publícalo." : `PDF importado en ${n} borradores. Revísalos y publícalos.`,
    test: "Probar pregunta", testHelp: "Escribe una pregunta como la haría un cliente y mira qué respondería el chat.", question: "Pregunta", ask: "Probar", asking: "Consultando…",
    drafts: "Incluir borradores en la prueba", answer: "Respuesta del chat", sourcesUsed: "Párrafos usados", noSources: "No usó ningún documento.",
    generatedNote: "Redactada por la IA a partir de tus documentos.", literalNote: "Párrafo literal de tus documentos (la IA no redactó esta respuesta).",
    aiNotFound: "La IA revisó tus documentos y no encontró esta información. Agrega un documento que la cubra.", noAi: "Sin IA: solo se buscan coincidencias de palabras.",
    error: "No se pudo completar la operación. Inténtalo de nuevo.", limit: "Llegaste al máximo de 50 documentos. Elimina alguno para añadir más.",
    pdfErrors: { 413: "El PDF supera 5 MB.", 415: "El archivo debe ser un PDF.", 422: "No se pudo extraer texto del PDF. Si es un documento escaneado o una imagen, copia el texto a mano." } as Record<number, string>,
    unsaved: "Tienes cambios sin guardar en el formulario.",
  },
  en: {
    title: "Knowledge base", intro: "What you publish here is what the booking chat uses to answer your customers. Write one topic per document and separate each idea with a blank line.",
    llmOff: "The AI assistant (LLM) is turned off. The chat will only show literal paragraphs and won't understand synonyms. Check the server configuration.",
    docs: "Documents", none: "No documents yet. Start with a template or upload a PDF.", published: "Published", draft: "Draft",
    edit: "Edit", remove: "Delete", confirmRemove: "Delete this document? The chat will stop using it immediately.", yesRemove: "Yes, delete", cancel: "Cancel",
    newDoc: "New document", editing: "Edit document", docTitle: "Document title", body: "Content", publish: "Publish for chat answers",
    save: "Save document", saving: "Saving…", saved: "Document saved.", removed: "Document deleted.", newBtn: "Create new document",
    templates: "Templates", templatesHelp: "Fill the form with an example you can adapt. Replace the text in brackets.",
    pdf: "Upload PDF", pdfHelp: "The text is extracted and saved as a draft so you can review it before publishing. 5 MB max.", pdfBusy: "Reading the PDF…",
    pdfDone: (n: number) => n === 1 ? "PDF imported as a draft. Review and publish it." : `PDF imported as ${n} drafts. Review and publish them.`,
    test: "Test a question", testHelp: "Type a question the way a customer would and see what the chat would answer.", question: "Question", ask: "Test", asking: "Checking…",
    drafts: "Include drafts in the test", answer: "Chat answer", sourcesUsed: "Paragraphs used", noSources: "No document was used.",
    generatedNote: "Written by the AI from your documents.", literalNote: "Literal paragraph from your documents (the AI did not write this answer).",
    aiNotFound: "The AI checked your documents and didn't find this information. Add a document that covers it.", noAi: "No AI: only matching words are searched.",
    error: "The operation could not be completed. Try again.", limit: "You reached the 50-document limit. Delete one to add more.",
    pdfErrors: { 413: "The PDF is larger than 5 MB.", 415: "The file must be a PDF.", 422: "No text could be extracted. If it's a scanned document or an image, copy the text manually." } as Record<number, string>,
    unsaved: "You have unsaved changes in the form.",
  },
};
const blank: Doc = { id: 0, title: "", body: "", published: false };

export default function KnowledgeManager({ language, basePath, statusPath, onSessionEnded }: Props) {
  const t = copy[language];
  const [docs, setDocs] = useState<Doc[]>([]);
  const [draft, setDraft] = useState<Doc>(blank);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [llmOn, setLlmOn] = useState(true);
  const [confirming, setConfirming] = useState<number | null>(null);
  const editor = useRef<HTMLFormElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api(basePath, { signal: controller.signal }), api(statusPath, { signal: controller.signal }).catch(() => null)])
      .then(([values, status]) => { setDocs(values); if (status) setLlmOn(status.llm_enabled); })
      .catch(error => { if (controller.signal.aborted) return; if (lostSession(error)) onSessionEnded(); else setNotice({ ok: false, text: t.error }); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [basePath, statusPath, onSessionEnded, t.error]);

  function fail(error: unknown) {
    if (lostSession(error)) { onSessionEnded(); return; }
    setNotice({ ok: false, text: error instanceof ApiError && error.status === 409 ? t.limit : t.error });
  }
  function open(doc: Doc) {
    setDraft(doc); setNotice(null); setConfirming(null);
    requestAnimationFrame(() => editor.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setNotice(null);
    try {
      const { id, ...body } = draft;
      const result: Doc = await api(basePath + (id ? `/${id}` : ""), { method: id ? "PUT" : "POST", body: JSON.stringify(body) });
      setDocs(previous => id ? previous.map(doc => doc.id === id ? result : doc) : [...previous, result]);
      setDraft(result); setNotice({ ok: true, text: t.saved });
    } catch (error) { fail(error); } finally { setBusy(false); }
  }

  async function remove(id: number) {
    if (busy) return;
    setBusy(true); setNotice(null);
    try {
      await api(`${basePath}/${id}`, { method: "DELETE" });
      setDocs(previous => previous.filter(doc => doc.id !== id));
      if (draft.id === id) setDraft(blank);
      setConfirming(null); setNotice({ ok: true, text: t.removed });
    } catch (error) { fail(error); } finally { setBusy(false); }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || busy) return;
    setBusy(true); setNotice({ ok: true, text: t.pdfBusy });
    try {
      const title = file.name.replace(/\.pdf$/i, "").replace(/[_-]+/g, " ").trim().slice(0, 100);
      const created: Doc[] = await api(`${basePath}/import?title=${encodeURIComponent(title)}`,
        { method: "POST", body: file, headers: { "Content-Type": "application/pdf" }, signal: AbortSignal.timeout(60000) });
      setDocs(previous => [...previous, ...created]);
      setDraft(created[0]);
      setNotice({ ok: true, text: t.pdfDone(created.length) });
    } catch (error) {
      if (lostSession(error)) onSessionEnded();
      else setNotice({ ok: false, text: (error instanceof ApiError && t.pdfErrors[error.status]) || (error instanceof ApiError && error.status === 409 ? t.limit : t.error) });
    } finally { setBusy(false); }
  }

  if (loading) return <section className="dashboard-card"><h4>{t.title}</h4><p role="status">…</p></section>;
  const dirty = draft.id === 0 ? !!(draft.title || draft.body) : JSON.stringify(docs.find(doc => doc.id === draft.id)) !== JSON.stringify(draft);

  return <div className="knowledge-manager">
    {!llmOn && <p className="panel-alert" role="alert">{t.llmOff}</p>}
    <section className="dashboard-card" aria-labelledby="knowledge-docs-title">
      <div className="card-heading"><h4 id="knowledge-docs-title">{t.docs}</h4>
        <div className="card-actions">
          <button type="button" className="dashboard-secondary" disabled={busy} onClick={() => fileInput.current?.click()}>{t.pdf}</button>
          <input ref={fileInput} type="file" accept="application/pdf,.pdf" hidden onChange={upload} />
          <button type="button" className="dashboard-secondary" disabled={busy} onClick={() => open(blank)}>{t.newBtn}</button>
        </div>
      </div>
      <p className="card-help">{t.intro}</p>
      <p className="card-help">{t.pdfHelp}</p>
      {notice && <p className={notice.ok ? "dashboard-success" : "dashboard-error"} role={notice.ok ? "status" : "alert"}>{notice.text}</p>}
      {docs.length === 0 ? <p>{t.none}</p> : <ul className="business-list knowledge-list">{docs.map(doc => <li key={doc.id} className={doc.id === draft.id ? "is-selected" : ""}>
        <div><strong>{doc.title}</strong>
          <span className={`business-badge ${doc.published ? "is-active" : "is-inactive"}`}>{doc.published ? t.published : t.draft}</span>
          <small>{doc.body.slice(0, 110)}{doc.body.length > 110 ? "…" : ""}</small></div>
        {confirming === doc.id ? <div className="inline-confirm" role="group" aria-label={t.confirmRemove}>
          <span>{t.confirmRemove}</span>
          <button type="button" className="dashboard-danger" disabled={busy} onClick={() => remove(doc.id)}>{t.yesRemove}</button>
          <button type="button" className="dashboard-secondary" disabled={busy} onClick={() => setConfirming(null)}>{t.cancel}</button>
        </div> : <div className="row-actions">
          <button type="button" className="dashboard-secondary" disabled={busy} onClick={() => open(doc)}>{t.edit}<span className="sr-only">: {doc.title}</span></button>
          <button type="button" className="dashboard-danger" disabled={busy} onClick={() => setConfirming(doc.id)}>{t.remove}<span className="sr-only">: {doc.title}</span></button>
        </div>}
      </li>)}</ul>}
    </section>

    <div className="dashboard-layout">
      <form ref={editor} className="dashboard-card knowledge-editor" onSubmit={save} aria-busy={busy}>
        <h4>{draft.id ? t.editing : t.newDoc}</h4>
        {!draft.id && <div className="template-picker"><p className="card-help"><strong>{t.templates}.</strong> {t.templatesHelp}</p>
          <div className="chip-row">{TEMPLATES[language].map(item => <button type="button" key={item.title} className="chip" disabled={busy}
            onClick={() => setDraft({ ...blank, title: item.title, body: item.body })}>{item.title}</button>)}</div></div>}
        <fieldset className="dashboard-fields" disabled={busy}>
          <label htmlFor="knowledge-title">{t.docTitle}</label>
          <input id="knowledge-title" required maxLength={120} value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} />
          <label htmlFor="knowledge-body">{t.body}</label>
          <textarea id="knowledge-body" required rows={10} maxLength={6000} value={draft.body} onChange={e => setDraft({ ...draft, body: e.target.value })} />
          <small>{draft.body.length} / 6000</small>
          <label className="client-checkbox"><input type="checkbox" checked={draft.published} onChange={e => setDraft({ ...draft, published: e.target.checked })} />{t.publish}</label>
          {dirty && <small className="unsaved-note">{t.unsaved}</small>}
          <button type="submit" className="btn btn-primary" disabled={!draft.title.trim() || !draft.body.trim()}>{busy ? t.saving : t.save}</button>
        </fieldset>
      </form>
      <QuestionTester language={language} basePath={basePath} onSessionEnded={onSessionEnded} />
    </div>
  </div>;
}

function QuestionTester({ language, basePath, onSessionEnded }: { language: Language; basePath: string; onSessionEnded: () => void }) {
  const t = copy[language];
  const [question, setQuestion] = useState("");
  const [drafts, setDrafts] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Preview | null>(null);
  const [failed, setFailed] = useState(false);
  async function ask(event: FormEvent) {
    event.preventDefault();
    if (busy || !question.trim()) return;
    setBusy(true); setFailed(false);
    try { setResult(await api(`${basePath}/preview`, { method: "POST", body: JSON.stringify({ question, language, include_drafts: drafts }) })); }
    catch (error) { if (lostSession(error)) onSessionEnded(); else setFailed(true); }
    finally { setBusy(false); }
  }
  return <section className="dashboard-card question-tester" aria-labelledby="knowledge-test-title">
    <h4 id="knowledge-test-title">{t.test}</h4>
    <p className="card-help">{t.testHelp}</p>
    <form onSubmit={ask}><fieldset className="dashboard-fields" disabled={busy}>
      <label htmlFor="knowledge-question">{t.question}</label>
      <input id="knowledge-question" required maxLength={500} value={question} placeholder={language === "es" ? "¿Puedo pagar con tarjeta?" : "Can I pay by card?"} onChange={e => setQuestion(e.target.value)} />
      <label className="client-checkbox"><input type="checkbox" checked={drafts} onChange={e => setDrafts(e.target.checked)} />{t.drafts}</label>
      <button className="dashboard-secondary" type="submit">{busy ? t.asking : t.ask}</button>
    </fieldset></form>
    {failed && <p className="dashboard-error" role="alert">{t.error}</p>}
    {result && <div className="chat-preview" aria-live="polite">
      <p className="chat-preview-label">{t.answer}</p>
      <div className="chat-bubble">{result.reply}</div>
      <small>{!result.llm_enabled ? t.noAi : result.generated ? t.generatedNote : result.sources.length ? t.literalNote : t.aiNotFound}</small>
      <p className="chat-preview-label">{t.sourcesUsed}</p>
      {result.sources.length === 0 ? <p>{t.noSources}</p> : <ul className="source-list">{result.sources.map(source =>
        <li key={`${source.title}-${source.paragraph}`}><strong>{source.title} · §{source.paragraph}</strong><q>{source.quote}</q></li>)}</ul>}
    </div>}
  </section>;
}
