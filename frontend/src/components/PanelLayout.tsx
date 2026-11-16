import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Language } from "../services";

/** Menú lateral compartido por el panel de administración y el panel del negocio. */
export type IconName = "home" | "calendar" | "tag" | "users" | "clock" | "book" | "link" | "store" | "plus" | "history" | "key" | "shield" | "logout";
export type PanelSection = { id: string; label: string; icon: IconName; badge?: number };
export type PanelGroup = { label: string; sections: PanelSection[] };
type Props = {
  language: Language; title: string; subtitle: string; groups: PanelGroup[]; active: string;
  onSelect: (id: string) => void; footer?: ReactNode; children: ReactNode;
};

const PATHS: Record<IconName, string> = {
  home: "M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-3H4zM14 7h6V4h-6z",
  calendar: "M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM16 3v4M8 3v4M4 11h16",
  tag: "M7.5 7.5h.01M3 6v5.2a2 2 0 0 0 .6 1.4l7.8 7.8a2 2 0 0 0 2.8 0l5.2-5.2a2 2 0 0 0 0-2.8L11.6 4.6A2 2 0 0 0 10.2 4H5a2 2 0 0 0-2 2z",
  users: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2M16 3.1a4 4 0 0 1 0 7.8M21 21v-2a4 4 0 0 0-3-3.9",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 3",
  book: "M3 19a9 9 0 0 1 9 0 9 9 0 0 1 9 0M3 6a9 9 0 0 1 9 0 9 9 0 0 1 9 0M3 6v13M12 6v13M21 6v13",
  link: "M9 15l6-6M11 6l.5-.5a5 5 0 0 1 7 7l-.5.5M13 18l-.4.5a5 5 0 0 1-7-7l.4-.5",
  store: "M3 21h18M3 7v1a3 3 0 0 0 6 0V7m0 1a3 3 0 0 0 6 0V7m0 1a3 3 0 0 0 6 0V7H3l2-4h14l2 4M5 21V10.8M19 21V10.8M9 21v-4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v4",
  plus: "M12 5v14M5 12h14",
  history: "M12 8v4l2 2M3.05 11a9 9 0 1 1 .5 4M3 20v-5h5",
  key: "M16.5 3a4.5 4.5 0 0 1 .5 8.97L13 16H11v2H9v2H4v-3.5l6.03-6.03A4.5 4.5 0 0 1 16.5 3zM17 7.5h.01",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
  logout: "M14 8V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-2M9 12h12l-3-3m0 6l3-3",
};

export function Icon({ name }: { name: IconName }) {
  return <svg className="panel-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">
    <path d={PATHS[name]} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>;
}

const copy = {
  es: { collapse: "Plegar menú", expand: "Desplegar menú", open: "Abrir menú del panel", close: "Cerrar menú", nav: "Secciones del panel" },
  en: { collapse: "Collapse menu", expand: "Expand menu", open: "Open dashboard menu", close: "Close menu", nav: "Dashboard sections" },
};

function readCollapsed() {
  try { return localStorage.getItem("orqentiva-panel-collapsed") === "1"; } catch { return false; }
}

export default function PanelLayout({ language, title, subtitle, groups, active, onSelect, footer, children }: Props) {
  const t = copy[language];
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [mobileOpen, setMobileOpen] = useState(false);
  const content = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const current = groups.flatMap(group => group.sections).find(section => section.id === active);

  useEffect(() => {
    try { localStorage.setItem("orqentiva-panel-collapsed", collapsed ? "1" : "0"); } catch { /* sin almacenamiento */ }
  }, [collapsed]);

  useEffect(() => {
    if (!mobileOpen) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") { setMobileOpen(false); toggle.current?.focus(); } };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [mobileOpen]);

  function select(id: string) {
    onSelect(id);
    setMobileOpen(false);
    requestAnimationFrame(() => content.current?.focus({ preventScroll: true }));
    content.current?.scrollIntoView({ block: "start" });
  }

  return <div className={`panel-shell${collapsed ? " is-collapsed" : ""}${mobileOpen ? " is-open" : ""}`}>
    <aside className="panel-sidebar" aria-label={t.nav}>
      <div className="panel-sidebar-head">
        <span className="panel-brand" aria-hidden="true">O</span>
        <div className="panel-sidebar-title"><strong>{title}</strong><small>{subtitle}</small></div>
        <button type="button" className="panel-collapse" onClick={() => setCollapsed(value => !value)}
          aria-label={collapsed ? t.expand : t.collapse} title={collapsed ? t.expand : t.collapse} aria-expanded={!collapsed}>
          <span aria-hidden="true">{collapsed ? "»" : "«"}</span>
        </button>
        <button type="button" className="panel-close" onClick={() => { setMobileOpen(false); toggle.current?.focus(); }} aria-label={t.close}>×</button>
      </div>
      <nav className="panel-nav">
        {groups.map(group => <div className="panel-group" key={group.label}>
          <p className="panel-group-label">{group.label}</p>
          <ul>{group.sections.map(section => <li key={section.id}>
            <button type="button" className="panel-link" aria-current={section.id === active ? "page" : undefined}
              title={collapsed ? section.label : undefined} onClick={() => select(section.id)}>
              <Icon name={section.icon} /><span className="panel-link-label">{section.label}</span>
              {!!section.badge && <span className="panel-badge">{section.badge}</span>}
            </button>
          </li>)}</ul>
        </div>)}
      </nav>
      {footer && <div className="panel-footer">{footer}</div>}
    </aside>
    <div className="panel-backdrop" onClick={() => setMobileOpen(false)} aria-hidden="true" />
    <div className="panel-main">
      <div className="panel-topbar">
        <button ref={toggle} type="button" className="panel-menu-toggle" onClick={() => setMobileOpen(true)}
          aria-label={t.open} aria-expanded={mobileOpen}>
          <span aria-hidden="true">☰</span>
        </button>
        <p className="panel-breadcrumb"><span>{title}</span> / <strong>{current?.label}</strong></p>
      </div>
      <div className="panel-content" ref={content} tabIndex={-1}>{children}</div>
    </div>
  </div>;
}
