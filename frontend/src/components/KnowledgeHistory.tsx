import { useEffect, useState } from "react";
import type { Language } from "../services";
import { api, lostSession } from "./KnowledgeManager";

/** Historial de la base de conocimiento de un negocio, con lo que cambió resaltado. */
export type Change = {
  id: number; business_id: string; business_name?: string; document_id: number | null; action: string; actor_email: string;
  before_title: string | null; before_body: string | null; after_title: string | null; after_body: string | null; created_at: string;
};
type Props = { language: Language; businessId: string; onSessionEnded: () => void };

export const actionLabels = {
  es: { created: "Creó", updated: "Editó", published: "Publicó", unpublished: "Despublicó", deleted: "Eliminó", imported: "Importó desde PDF" } as Record<string, string>,
  en: { created: "Created", updated: "Edited", published: "Published", unpublished: "Unpublished", deleted: "Deleted", imported: "Imported from PDF" } as Record<string, string>,
};
const copy = {
  es: { title: "Historial de cambios", intro: "Todo lo que se cambió en la base de conocimiento de este negocio, del más reciente al más antiguo.",
    empty: "Todavía no hay cambios registrados.", show: "Ver cambios", hide: "Ocultar", before: "Antes", after: "Después", restore: "Volver a cargar como borrador",
    restored: "Documento recargado como borrador. Puedes revisarlo en la pestaña Base de conocimiento.", error: "No se pudo cargar el historial.", retry: "Reintentar",
    removedText: "Texto eliminado", addedText: "Texto agregado", document: "Documento" },
  en: { title: "Change history", intro: "Everything changed in this business's knowledge base, newest first.",
    empty: "No changes recorded yet.", show: "Show changes", hide: "Hide", before: "Before", after: "After", restore: "Reload as draft",
    restored: "Document reloaded as a draft. You can review it in the Knowledge base tab.", error: "The history could not be loaded.", retry: "Retry",
    removedText: "Removed text", addedText: "Added text", document: "Document" },
};

type Piece = { kind: "same" | "add" | "del"; text: string };
/** Diferencia por palabras (LCS). En textos muy largos compara por párrafos para no bloquear la página. */
export function diff(before: string, after: string): Piece[] {
  const split = (text: string) => text.split(/(\s+)/).filter(Boolean);
  let a = split(before), b = split(after);
  if (a.length * b.length > 1_500_000) { a = before.split(/(\n\s*\n)/); b = after.split(/(\n\s*\n)/); }
  const rows = a.length + 1, cols = b.length + 1;
  const table = new Uint16Array(rows * cols);
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      table[i * cols + j] = a[i] === b[j] ? table[(i + 1) * cols + j + 1] + 1 : Math.max(table[(i + 1) * cols + j], table[i * cols + j + 1]);
  const out: Piece[] = [];
  const push = (kind: Piece["kind"], text: string) => {
    const last = out[out.length - 1];
    if (last && last.kind === kind) last.text += text; else out.push({ kind, text });
  };
  let i = 0, j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { push("same", a[i]); i++; j++; }
    else if (table[(i + 1) * cols + j] >= table[i * cols + j + 1]) push("del", a[i++]);
    else push("add", b[j++]);
  }
  while (i < a.length) push("del", a[i++]);
  while (j < b.length) push("add", b[j++]);
  return out;
}

export function formatDate(value: string, language: Language) {
  return new Intl.DateTimeFormat(language === "es" ? "es-CR" : "en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Costa_Rica" }).format(new Date(value));
}

export default function KnowledgeHistory({ language, businessId, onSessionEnded }: Props) {
  const t = copy[language];
  const base = `/admin/businesses/${encodeURIComponent(businessId)}/documents`;
  const [rows, setRows] = useState<Change[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const [reload, setReload] = useState(0);
  const [restored, setRestored] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api(`${base}/history?limit=100`, { signal: controller.signal }).then(setRows).catch(error => {
      if (controller.signal.aborted) return;
      if (lostSession(error)) onSessionEnded(); else setFailed(true);
    });
    return () => controller.abort();
  }, [base, reload, onSessionEnded]);

  async function restore(row: Change) {
    if (busy || !row.before_title || !row.before_body) return;
    setBusy(true);
    try {
      await api(base, { method: "POST", body: JSON.stringify({ title: row.before_title, body: row.before_body, published: false }) });
      setRestored(row.id); setReload(value => value + 1);
    } catch (error) { if (lostSession(error)) onSessionEnded(); else setFailed(true); }
    finally { setBusy(false); }
  }

  return <section className="dashboard-card" aria-labelledby="history-title">
    <h4 id="history-title">{t.title}</h4>
    <p className="card-help">{t.intro}</p>
    {failed ? <p className="dashboard-error" role="alert">{t.error} <button type="button" className="dashboard-secondary" onClick={() => { setFailed(false); setReload(value => value + 1); }}>{t.retry}</button></p>
      : rows === null ? <p role="status">…</p> : rows.length === 0 ? <p>{t.empty}</p> :
      <ol className="history-list">{rows.map(row => {
        const title = row.after_title ?? row.before_title ?? "";
        const hasDiff = row.action === "updated" && row.before_body !== null && row.after_body !== null;
        const hasText = !hasDiff && (row.after_body || row.before_body);
        return <li key={row.id} className={`history-item is-${row.action}`}>
          <div className="history-head">
            <span className="history-action">{actionLabels[language][row.action] ?? row.action}</span>
            <strong>{title}</strong>
            <small>{formatDate(row.created_at, language)} · {row.actor_email}</small>
            {(hasDiff || hasText) && <button type="button" className="dashboard-secondary" aria-expanded={open === row.id}
              onClick={() => setOpen(open === row.id ? null : row.id)}>{open === row.id ? t.hide : t.show}</button>}
          </div>
          {open === row.id && hasDiff && <div className="history-diff">
            {row.before_title !== row.after_title && <p><del>{row.before_title}</del> → <ins>{row.after_title}</ins></p>}
            <p className="diff-legend"><del>{t.removedText}</del> <ins>{t.addedText}</ins></p>
            <div className="diff-text">{diff(row.before_body!, row.after_body!).map((piece, index) =>
              piece.kind === "same" ? <span key={index}>{piece.text}</span> : piece.kind === "add" ? <ins key={index}>{piece.text}</ins> : <del key={index}>{piece.text}</del>)}</div>
          </div>}
          {open === row.id && hasText && <div className="history-diff"><div className="diff-text">{row.after_body ?? row.before_body}</div>
            {row.action === "deleted" && <p>{restored === row.id ? <span className="dashboard-success" role="status">{t.restored}</span> :
              <button type="button" className="dashboard-secondary" disabled={busy} onClick={() => restore(row)}>{t.restore}</button>}</p>}
          </div>}
        </li>;
      })}</ol>}
  </section>;
}
