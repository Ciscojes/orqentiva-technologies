import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import type { Language } from "../services";
import KnowledgeHistory, { actionLabels, formatDate, type Change } from "./KnowledgeHistory";
import KnowledgeManager from "./KnowledgeManager";
import { Agenda, type Dashboard } from "./ClientDashboard";
import PanelLayout, { type PanelGroup } from "./PanelLayout";

type Business = { id: string; name: string; is_active: boolean; booking_enabled: boolean };
type BusinessUser = { id: number; email: string; is_active: boolean };
type Props = { language: Language; onSessionEnded: () => void };
const copy = {
  es: {
    title: "Panel de administración", intro: "Gestiona los negocios y sus accesos a ORQENTIVA.",
    businesses: "Negocios", loading: "Cargando…", refresh: "Actualizar lista", empty: "Todavía no hay negocios. Crea el primero para comenzar.",
    active: "Activo", inactive: "Inactivo", manage: "Gestionar", selected: "Seleccionado", create: "Crear negocio", id: "Identificador del negocio", name: "Nombre del negocio",
    idHelp: "Usa minúsculas, números y guiones; por ejemplo, barberia-centro. Este identificador no se modifica después.",
    save: "Crear negocio", saving: "Guardando…", error: "No se pudo completar la operación. Actualiza la lista para comprobar el estado antes de reintentar.",
    duplicateBusiness: "Ese identificador ya existe. Elige otro o selecciona el negocio existente.", invalid: "Revisa los datos. El nombre es obligatorio y la contraseña debe tener entre 12 y 128 caracteres.",
    businessCreated: "Negocio creado.", choose: "Selecciona un negocio para gestionar su estado y sus usuarios.",
    access: "Acceso del negocio", enable: "Activar negocio", disable: "Desactivar negocio", confirm: "Confirmar desactivación", cancel: "Cancelar",
    warning: "Se cerrarán las sesiones de este negocio y sus usuarios no podrán entrar. Sus servicios y reservas se conservarán.",
    disabledHelp: "Este negocio está desactivado. Sus usuarios podrán iniciar sesión cuando lo actives de nuevo.",
    enabled: "Negocio activado. Sus usuarios ya pueden iniciar sesión.", disabled: "Negocio desactivado. Se cerraron sus sesiones.",
    users: "Administradores del negocio", noUsers: "Este negocio todavía no tiene cuentas de acceso.",
    newUser: "Crear cuenta de cliente", email: "Correo electrónico", password: "Contraseña inicial", repeat: "Repite la contraseña",
    passwordHelp: "Entre 12 y 128 caracteres. Comunícala al titular por un canal privado; no se envía por correo automáticamente.",
    createUser: "Crear cuenta", userCreated: "Cuenta creada y asignada a este negocio.", duplicateUser: "Ese correo ya tiene una cuenta. No se ha modificado ni trasladado.",
    mismatch: "Las contraseñas no coinciden.", unavailable: "El negocio ya no está disponible. Actualiza la lista.",
    total: "negocios registrados", status: "Estado", accountState: "Cuenta", retry: "Volver a cargar usuarios",
  },
  en: {
    title: "Administration dashboard", intro: "Manage businesses and their access to ORQENTIVA.",
    businesses: "Businesses", loading: "Loading…", refresh: "Refresh list", empty: "No businesses yet. Create the first one to get started.",
    active: "Active", inactive: "Inactive", manage: "Manage", selected: "Selected", create: "Create business", id: "Business identifier", name: "Business name",
    idHelp: "Use lowercase letters, numbers and hyphens; for example, downtown-barbershop. This identifier cannot be changed later.",
    save: "Create business", saving: "Saving…", error: "The operation could not be completed. Refresh the list to check the current state before trying again.",
    duplicateBusiness: "That identifier already exists. Choose another or select the existing business.", invalid: "Check the fields. A name is required and passwords must contain 12–128 characters.",
    businessCreated: "Business created.", choose: "Select a business to manage its status and users.",
    access: "Business access", enable: "Activate business", disable: "Deactivate business", confirm: "Confirm deactivation", cancel: "Cancel",
    warning: "This business's sessions will be closed and its users will be unable to sign in. Services and bookings will be preserved.",
    disabledHelp: "This business is inactive. Its users will be able to sign in after you activate it again.",
    enabled: "Business activated. Its users can now sign in.", disabled: "Business deactivated. Its sessions have been closed.",
    users: "Business administrators", noUsers: "This business does not have any accounts yet.",
    newUser: "Create client account", email: "Email address", password: "Initial password", repeat: "Repeat password",
    passwordHelp: "Use 12–128 characters. Share it with the account holder through a private channel; no email is sent automatically.",
    createUser: "Create account", userCreated: "Account created and assigned to this business.", duplicateUser: "That email already has an account. It has not been changed or moved.",
    mismatch: "Passwords do not match.", unavailable: "The business is no longer available. Refresh the list.",
    total: "registered businesses", status: "Status", accountState: "Account", retry: "Reload users",
  },
};
type Message = "error" | "invalid" | "duplicateBusiness" | "businessCreated" | "enabled" | "disabled" | "userCreated" | "duplicateUser" | "mismatch" | "unavailable" | null;
const successes = new Set(["businessCreated", "enabled", "disabled", "userCreated"]);

class ApiError extends Error { status: number; constructor(status: number) { super("Request failed"); this.status = status; } }
async function adminRequest(path: string, options: RequestInit = {}) {
  const response = await fetch(`/admin/businesses${path}`, {
    credentials: "same-origin", cache: "no-store", ...options,
    headers: {"Content-Type": "application/json", ...options.headers},
    signal: options.signal ?? AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new ApiError(response.status);
  return response.json();
}
function classify(error: unknown, duplicate: Message = "error"): Message {
  if (!(error instanceof ApiError)) return "error";
  return error.status === 409 ? duplicate : error.status === 422 ? "invalid" : error.status === 404 ? "unavailable" : "error";
}
function sessionLost(error: unknown) { return error instanceof ApiError && (error.status === 401 || error.status === 403); }
function Feedback({ message, language }: {message: Message; language: Language}) {
  return message && <p className={successes.has(message) ? "dashboard-success" : "dashboard-error"} role={successes.has(message) ? "status" : "alert"}>{copy[language][message]}</p>;
}

type Section = "resumen" | "negocios" | "nuevo";
type Tab = "estado" | "agenda" | "cuentas" | "conocimiento" | "historial";
const nav = {
  es: { group: "Gestión", resumen: "Resumen", negocios: "Negocios", nuevo: "Nuevo negocio", panel: "Administración",
    total: "Negocios", activeCount: "Activos", withAgenda: "Con agenda", changedWeek: "Cambiaron su base esta semana",
    llmOn: "Asistente de IA activo", llmOff: "Asistente de IA desactivado: el chat de todos los negocios responde sin IA. Revisa LLM_API_KEY y LLM_MODEL en el servidor.",
    recent: "Cambios recientes en las bases de conocimiento", noRecent: "Todavía no hay cambios.", open: "Ver negocio", back: "Volver a la lista de negocios",
    tabs: { estado: "Estado", agenda: "Agenda", cuentas: "Cuentas", conocimiento: "Base de conocimiento", historial: "Historial de cambios" } as Record<Tab, string>,
    agendaTitle: "Agenda del negocio", agendaRead: "Vista de solo lectura: las citas las gestiona el negocio desde su panel.", agendaDisabled: "Este negocio no tiene la agenda de citas habilitada. Actívala en la pestaña Estado.", noBookings: "Todavía no hay reservas registradas.", team: "Trabajadores", services: "Servicios activos", upcoming: "Próximas citas",
    agendaHelp: "Con la agenda habilitada, el negocio ve Agenda, Servicios, Trabajadores, Horario y su base de conocimiento.",
    agendaOn: "Agenda activada.", agendaOff: "Agenda desactivada.", tabsLabel: "Secciones del negocio", createdGo: "Ir a su ficha" },
  en: { group: "Management", resumen: "Overview", negocios: "Businesses", nuevo: "New business", panel: "Administration",
    total: "Businesses", activeCount: "Active", withAgenda: "With scheduling", changedWeek: "Changed their knowledge base this week",
    llmOn: "AI assistant on", llmOff: "AI assistant off: every business's chat answers without AI. Check LLM_API_KEY and LLM_MODEL on the server.",
    recent: "Recent knowledge base changes", noRecent: "No changes yet.", open: "View business", back: "Back to business list",
    tabs: { estado: "Status", agenda: "Schedule", cuentas: "Accounts", conocimiento: "Knowledge base", historial: "Change history" } as Record<Tab, string>,
    agendaTitle: "Business schedule", agendaRead: "Read-only view: the business manages appointments from its own dashboard.", agendaDisabled: "This business doesn't have appointment scheduling enabled. Turn it on in the Status tab.", noBookings: "No bookings recorded yet.", team: "Staff", services: "Active services", upcoming: "Upcoming appointments",
    agendaHelp: "With scheduling enabled, the business sees Schedule, Services, Staff, Opening hours and its knowledge base.",
    agendaOn: "Scheduling enabled.", agendaOff: "Scheduling disabled.", tabsLabel: "Business sections", createdGo: "Go to its page" },
};

export default function AdminDashboard({ language, onSessionEnded, footer }: Props & { footer?: ReactNode }) {
  const t = copy[language];
  const n = nav[language];
  const [section, setSection] = useState<Section>("resumen");
  const [tab, setTab] = useState<Tab>("estado");
  const [agenda,setAgenda]=useState(false);
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [reload, setReload] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<Message>(null);
  const [created, setCreated] = useState<string | null>(null);
  const [changes, setChanges] = useState<Change[]>([]);
  const [llmOn, setLlmOn] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    let alive = true;
    adminRequest("", {signal:controller.signal}).then(data => {
      if (alive) { setBusinesses(data); setSelected(previous => data.some((item: Business) => item.id === previous) ? previous : null); }
    }).catch(error => {
      if (!alive) return;
      if (sessionLost(error)) onSessionEnded();
      else setLoadError(true);
    }).finally(() => { clearTimeout(timeout); if (alive) setLoading(false); });
    const side = (path: string) => fetch(path, {credentials:"same-origin", cache:"no-store", signal:controller.signal}).then(r => r.ok ? r.json() : null);
    side("/admin/knowledge-changes?limit=100").then(rows => { if (alive && rows) setChanges(rows); }).catch(() => {});
    side("/admin/llm-status").then(status => { if (alive && status) setLlmOn(status.llm_enabled); }).catch(() => {});
    return () => { alive = false; clearTimeout(timeout); controller.abort(); };
  }, [reload, onSessionEnded]);

  async function createBusiness(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    if (!name.trim()) { setMessage("invalid"); return; }
    setSaving(true); setMessage(null); setCreated(null);
    try {
      const business = await adminRequest("", {method:"POST", body:JSON.stringify({id:id.trim(), name:name.trim(), booking_enabled:agenda})});
      setBusinesses(previous => [...previous, business].sort((a,b) => a.name.localeCompare(b.name)));
      setAgenda(false); setCreated(business.id); setId(""); setName(""); setMessage("businessCreated");
    } catch (error) {
      if (sessionLost(error)) onSessionEnded();
      else setMessage(classify(error, "duplicateBusiness"));
    } finally { setSaving(false); }
  }
  function openBusiness(businessId: string, target: Tab = "estado") { setSelected(businessId); setTab(target); setSection("negocios"); }
  const business = businesses.find(item => item.id === selected);
  const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
  const changedWeek = new Set(changes.filter(row => new Date(row.created_at).getTime() >= weekAgo).map(row => row.business_id)).size;
  const groups: PanelGroup[] = [{label: n.group, sections: [
    {id: "resumen", label: n.resumen, icon: "home"},
    {id: "negocios", label: n.negocios, icon: "store", badge: businesses.length || undefined},
    {id: "nuevo", label: n.nuevo, icon: "plus"},
  ]}];
  const heading = section === "negocios" && business ? business.name : section === "resumen" ? t.title : section === "nuevo" ? n.nuevo : n.negocios;

  let body;
  if (loading) body = <p role="status">{t.loading}</p>;
  else if (loadError) body = <p role="alert" className="dashboard-error">{t.error}</p>;
  else if (section === "resumen") body = <>
    <p className={llmOn ? "panel-ok" : "panel-alert"} role={llmOn ? "status" : "alert"}>{llmOn ? n.llmOn : n.llmOff}</p>
    <div className="metric-grid">
      <button type="button" className="metric" onClick={() => setSection("negocios")}><span>{n.total}</span><strong>{businesses.length}</strong></button>
      <div className="metric"><span>{n.activeCount}</span><strong>{businesses.filter(b => b.is_active).length}</strong></div>
      <div className="metric"><span>{n.withAgenda}</span><strong>{businesses.filter(b => b.booking_enabled).length}</strong></div>
      <div className="metric"><span>{n.changedWeek}</span><strong>{changedWeek}</strong></div>
    </div>
    <section className="dashboard-card"><h4>{n.recent}</h4>
      {changes.length === 0 ? <p>{n.noRecent}</p> : <ul className="business-list">{changes.slice(0, 8).map(row => <li key={row.id}>
        <div><strong>{row.business_name}</strong>
          <small>{actionLabels[language][row.action] ?? row.action} «{row.after_title ?? row.before_title}» · {formatDate(row.created_at, language)} · {row.actor_email}</small></div>
        <button type="button" className="dashboard-secondary" onClick={() => openBusiness(row.business_id, "historial")}>{n.open}<span className="sr-only">: {row.business_name}</span></button>
      </li>)}</ul>}
    </section>
  </>;
  else if (section === "nuevo") body = <section className="dashboard-card narrow-card" aria-labelledby="business-create-title"><h4 id="business-create-title">{t.create}</h4>
    <form onSubmit={createBusiness} aria-busy={saving}><fieldset disabled={saving} className="dashboard-fields">
      <label htmlFor="business-id">{t.id}</label><input id="business-id" value={id} onChange={e=>setId(e.target.value)} required maxLength={50} pattern="[a-z0-9][a-z0-9\-]*" aria-describedby="business-id-help" autoCapitalize="none" autoComplete="off" />
      <small id="business-id-help">{t.idHelp}</small>
      <label htmlFor="business-name">{t.name}</label><input id="business-name" value={name} onChange={e=>setName(e.target.value)} required maxLength={150} autoComplete="organization" />
      <label className="client-checkbox"><input type="checkbox" checked={agenda} onChange={e=>setAgenda(e.target.checked)}/> {language==="es"?"Incluir agenda de citas":"Include appointment scheduling"}</label>
      <button className="btn btn-primary" type="submit">{saving ? t.saving : t.save}</button>
    </fieldset></form><Feedback message={message} language={language} />
    {created && <button type="button" className="dashboard-secondary" onClick={() => openBusiness(created, "cuentas")}>{n.createdGo}</button>}
  </section>;
  else if (business) body = <>
    <button type="button" className="panel-back" onClick={() => setSelected(null)}>← {n.back}</button>
    <div className="panel-tabs" role="tablist" aria-label={n.tabsLabel}>
      {(Object.keys(n.tabs) as Tab[]).map(key => <button key={key} type="button" role="tab" id={`tab-${key}`} aria-selected={tab === key}
        aria-controls="business-tabpanel" onClick={() => setTab(key)}>{n.tabs[key]}</button>)}
    </div>
    <div id="business-tabpanel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
      {tab === "conocimiento" ? <KnowledgeManager key={business.id} language={language} basePath={`/admin/businesses/${encodeURIComponent(business.id)}/documents`} statusPath="/admin/llm-status" onSessionEnded={onSessionEnded} />
        : tab === "agenda" ? <BusinessAgenda key={business.id} businessId={business.id} language={language} onSessionEnded={onSessionEnded} />
        : tab === "historial" ? <KnowledgeHistory key={business.id} language={language} businessId={business.id} onSessionEnded={onSessionEnded} />
        : <BusinessManager key={business.id} business={business} language={language} view={tab} onSessionEnded={onSessionEnded}
          onChange={updated => setBusinesses(previous => previous.map(item => item.id === updated.id ? updated : item))} />}
    </div>
  </>;
  else body = <section className="dashboard-card" aria-labelledby="business-list-title"><h4 id="business-list-title">{t.businesses}</h4>
    <p className="dashboard-count">{businesses.length} {t.total}</p>
    {businesses.length === 0 ? <p>{t.empty}</p> : <ul className="business-list">{businesses.map(item => <li key={item.id}>
      <div><strong>{item.name}</strong><small>{item.id}</small>
        <span className={`business-badge ${item.is_active ? "is-active" : "is-inactive"}`}>{item.is_active ? t.active : t.inactive}</span>
        {item.booking_enabled && <span className="business-badge is-agenda">{n.withAgenda}</span>}</div>
      <button type="button" className="dashboard-secondary" onClick={() => openBusiness(item.id)}>{t.manage}<span className="sr-only">: {item.name}</span></button>
    </li>)}</ul>}
  </section>;

  return <PanelLayout language={language} title="ORQENTIVA" subtitle={n.panel} groups={groups} active={section}
    onSelect={id => { setSection(id as Section); if (id === "negocios") setSelected(null); setMessage(null); }} footer={footer}>
    <div className="admin-dashboard" aria-labelledby="admin-title">
      <header className="dashboard-heading"><div><span className="eyebrow">ORQENTIVA</span><h3 id="admin-title">{heading}</h3>{section === "resumen" && <p>{t.intro}</p>}</div>
        <button type="button" className="dashboard-secondary" disabled={loading || saving} onClick={() => { setLoading(true); setLoadError(false); setReload(value => value + 1); }}>{t.refresh}</button></header>
      {body}
    </div>
  </PanelLayout>;
}

function BusinessManager({ business, language, view, onChange, onSessionEnded }: Props & {business: Business; view: "estado" | "cuentas"; onChange: (value: Business) => void}) {
  const t = copy[language];
  const n = nav[language];
  const [users, setUsers] = useState<BusinessUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [message, setMessage] = useState<Message>(null);
  const [agendaNote, setAgendaNote] = useState<string | null>(null);
  const endpoint = `/${encodeURIComponent(business.id)}`;
  useEffect(() => {
    if (view !== "cuentas") return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    let alive = true;
    adminRequest(`${endpoint}/users`, {signal:controller.signal}).then(data => {if (alive) setUsers(data);}).catch(error => {
      if (!alive) return;
      if (sessionLost(error)) onSessionEnded(); else setLoadError(true);
    }).finally(() => {clearTimeout(timeout); if (alive) setLoading(false);});
    return () => {alive = false; clearTimeout(timeout); controller.abort();};
  }, [endpoint, reload, onSessionEnded, view]);

  async function changeState(active: boolean) {
    if (busy) return;
    setBusy(true); setMessage(null);
    try {
      const updated = await adminRequest(endpoint, {method:"PATCH", body:JSON.stringify({is_active:active})});
      onChange(updated); setConfirm(false); setMessage(active ? "enabled" : "disabled");
    } catch(error) {if (sessionLost(error)) onSessionEnded(); else setMessage(classify(error));}
    finally {setBusy(false);}
  }
  async function addUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (password !== repeat) {setMessage("mismatch"); return;}
    if (!password.trim()) {setMessage("invalid"); return;}
    setBusy(true); setMessage(null);
    try {
      const user = await adminRequest(`${endpoint}/users`, {method:"POST", body:JSON.stringify({email:email.trim(),password})});
      setUsers(previous => [...previous,user].sort((a,b) => a.email.localeCompare(b.email)));
      setEmail(""); setMessage("userCreated");
    } catch(error) {if (sessionLost(error)) onSessionEnded(); else setMessage(classify(error,"duplicateUser"));}
    finally {setPassword(""); setRepeat(""); setBusy(false);}
  }
  if (view === "estado") return <section className="dashboard-card business-manager" aria-labelledby="business-manager-title" aria-busy={busy}>
    <h4 id="business-manager-title">{t.access}</h4>
    <div className="business-access"><div><p>{t.status}: <strong>{business.is_active ? t.active : t.inactive}</strong></p><small>{business.id}</small></div>
      <button type="button" disabled={busy} className={business.is_active ? "dashboard-danger" : "btn btn-primary"}
        onClick={() => business.is_active ? setConfirm(true) : changeState(true)}>{business.is_active ? t.disable : t.enable}</button></div>
    {confirm && business.is_active && <div className="dashboard-confirm" role="group" aria-label={t.confirm}>
      <p>{t.warning}</p><button type="button" className="dashboard-danger" disabled={busy} onClick={()=>changeState(false)}>{t.confirm}</button>
      <button type="button" className="dashboard-secondary" disabled={busy} onClick={()=>setConfirm(false)}>{t.cancel}</button>
    </div>}
    {!business.is_active && <p className="dashboard-confirm">{t.disabledHelp}</p>}
    <Feedback message={message} language={language} />
    <h5>{language==="es"?"Agenda de citas":"Appointment scheduling"}</h5>
    <label className="client-checkbox"><input type="checkbox" checked={business.booking_enabled} disabled={busy} onChange={async event=>{
      const enabled=event.target.checked;
      setBusy(true); setMessage(null); setAgendaNote(null);
      try {onChange(await adminRequest(endpoint+"/agenda",{method:"PUT",body:JSON.stringify({booking_enabled:enabled})})); setAgendaNote(enabled ? n.agendaOn : n.agendaOff);}
      catch(error){if(sessionLost(error))onSessionEnded();else setMessage(classify(error));}
      finally{setBusy(false);}
    }}/> {language==="es"?"Agenda de citas habilitada":"Appointment scheduling enabled"}</label>
    <small className="card-help">{n.agendaHelp}</small>
    {agendaNote && <p className="dashboard-success" role="status">{agendaNote}</p>}
  </section>;
  return <section className="dashboard-card business-manager" aria-busy={busy}>
    <Feedback message={message} language={language} />
    <div className="dashboard-layout">
      <section aria-labelledby="business-users-title"><h5 id="business-users-title">{t.users}</h5>
        {loading ? <p role="status">{t.loading}</p> : loadError ? <><p className="dashboard-error" role="alert">{t.error}</p><button className="dashboard-secondary" onClick={()=>{setLoading(true); setLoadError(false); setReload(value=>value+1);}}>{t.retry}</button></> :
          users.length === 0 ? <p>{t.noUsers}</p> : <ul className="business-users">{users.map(user=><li key={user.id}><strong>{user.email}</strong><span>{t.accountState}: {user.is_active ? t.active : t.inactive}</span></li>)}</ul>}
      </section>
      <section aria-labelledby="business-user-create-title"><h5 id="business-user-create-title">{t.newUser}</h5>
        <form onSubmit={addUser}><fieldset className="dashboard-fields" disabled={busy || loading || loadError}>
          <label htmlFor="business-user-email">{t.email}</label><input id="business-user-email" type="email" autoComplete="off" value={email} onChange={e=>setEmail(e.target.value)} required maxLength={254} />
          <label htmlFor="business-user-password">{t.password}</label><input id="business-user-password" type="password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} required minLength={12} maxLength={128} aria-describedby="business-password-help" />
          <small id="business-password-help">{t.passwordHelp}</small>
          <label htmlFor="business-user-repeat">{t.repeat}</label><input id="business-user-repeat" type="password" autoComplete="new-password" value={repeat} onChange={e=>setRepeat(e.target.value)} required minLength={12} maxLength={128} />
          <button className="btn btn-primary" type="submit">{busy ? t.saving : t.createUser}</button>
        </fieldset></form>
      </section>
    </div>
  </section>;
}

function BusinessAgenda({ businessId, language, onSessionEnded }: { businessId: string; language: Language; onSessionEnded: () => void }) {
  const t = copy[language];
  const n = nav[language];
  const [data, setData] = useState<Dashboard | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    adminRequest(`/${encodeURIComponent(businessId)}/dashboard`, {signal: controller.signal}).then(setData).catch(error => {
      if (controller.signal.aborted) return;
      if (sessionLost(error)) onSessionEnded(); else setFailed(true);
    });
    return () => controller.abort();
  }, [businessId, onSessionEnded]);
  if (failed) return <p className="dashboard-error" role="alert">{t.error}</p>;
  if (!data) return <p role="status">{t.loading}</p>;
  if (!data.booking_enabled) return <section className="dashboard-card"><p>{n.agendaDisabled}</p></section>;
  const upcoming = data.appointments.filter(b => new Date(b.starts_at) >= new Date()).length;
  return <>
    <div className="metric-grid">
      <div className="metric"><span>{n.upcoming}</span><strong>{upcoming}</strong></div>
      <div className="metric"><span>{n.team}</span><strong>{data.team.length}</strong></div>
      <div className="metric"><span>{n.services}</span><strong>{data.services.filter(s => s.is_active).length}</strong></div>
    </div>
    <section className="dashboard-card" aria-labelledby="admin-agenda-title"><h4 id="admin-agenda-title">{n.agendaTitle}</h4>
      <p className="card-help">{n.agendaRead}</p>
      {data.appointments.length === 0 ? <p>{n.noBookings}</p> : <Agenda data={data} language={language} />}
    </section>
  </>;
}
