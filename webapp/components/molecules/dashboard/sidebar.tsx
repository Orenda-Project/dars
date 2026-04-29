"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Logo } from "@/components/atoms/logo";

interface Session {
  api_key: string;
  client_id: string;
  name: string;
  email: string;
  teacher_id?: string;
  is_admin?: boolean;
}

interface NavItem {
  label: string;
  href: string | null;
  disabled: boolean;
  icon: React.ReactNode;
}

// ── Icons ────────────────────────────────────────────────────────────────────

const IconBook = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
  </svg>
);

const IconBookOpen = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
  </svg>
);

const IconUsers = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const IconLessonPlan = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
  </svg>
);

const IconAnalytics = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

const IconExam = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 11l3 3L22 4" />
    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
  </svg>
);

const IconChevron = ({ open }: { open: boolean }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    className={`h-3 w-3 transition-transform ${open ? "rotate-0" : "-rotate-90"}`}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

// ── Sections ─────────────────────────────────────────────────────────────────

const adminItems: NavItem[] = [
  { label: "Curricula", href: "/dashboard/curriculum", disabled: false, icon: IconBook },
  { label: "Books", href: null, disabled: true, icon: IconBookOpen },
  { label: "Clients", href: null, disabled: true, icon: IconUsers },
];

const dashboardEnabled = process.env.NEXT_PUBLIC_DASHBOARD_ENABLED === "true";

const clientItems: NavItem[] = [
  { label: "Lesson Plans", href: dashboardEnabled ? "/dashboard/lesson-plans" : null, disabled: !dashboardEnabled, icon: IconLessonPlan },
  { label: "Analytics", href: dashboardEnabled ? "/dashboard/analytics" : null, disabled: !dashboardEnabled, icon: IconAnalytics },
  { label: "Teachers", href: dashboardEnabled ? "/dashboard/teachers" : null, disabled: !dashboardEnabled, icon: IconUsers },
];

const teacherItems: NavItem[] = [
  { label: "Curriculum", href: dashboardEnabled ? "/dashboard/curriculum" : null, disabled: !dashboardEnabled, icon: IconBook },
  { label: "Exam Generator", href: null, disabled: true, icon: IconExam },
];

// ── NavEntry ──────────────────────────────────────────────────────────────────

function NavEntry({ item, pathname }: { item: NavItem; pathname: string }) {
  if (item.disabled) {
    return (
      <div className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium text-dars-muted/50 cursor-not-allowed select-none">
        {item.icon}
        <span>{item.label}</span>
        <span className="ml-auto text-[10px] font-semibold tracking-wide uppercase bg-dars-rule-light text-dars-muted px-1.5 py-0.5 rounded">
          Soon
        </span>
      </div>
    );
  }

  const active =
    item.href !== null &&
    (pathname === item.href || pathname.startsWith(item.href + "/"));

  return (
    <a
      href={item.href!}
      className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-colors no-underline ${
        active
          ? "bg-dars-terra text-white"
          : "text-dars-muted hover:bg-dars-parchment-deep hover:text-dars-ink"
      }`}
    >
      {item.icon}
      {item.label}
    </a>
  );
}

// ── SectionGroup ─────────────────────────────────────────────────────────────

function SectionGroup({
  title,
  items,
  pathname,
  storageKey,
}: {
  title: string;
  items: NavItem[];
  pathname: string;
  storageKey: string;
}) {
  const [open, setOpen] = useState(true);

  // Hydrate from localStorage after mount
  useEffect(() => {
    const stored = localStorage.getItem(storageKey);
    if (stored !== null) {
      setOpen(stored === "true");
    }
  }, [storageKey]);

  function toggle() {
    const next = !open;
    setOpen(next);
    localStorage.setItem(storageKey, String(next));
  }

  return (
    <div className="mb-1">
      <button
        onClick={toggle}
        className="w-full flex items-center gap-1 px-3 py-1.5 text-[10px] font-semibold tracking-widest uppercase text-dars-muted/70 hover:text-dars-muted transition-colors cursor-pointer bg-transparent border-none"
      >
        <span className="flex-1 text-left">{title}</span>
        <IconChevron open={open} />
      </button>
      {open && (
        <div className="space-y-0.5">
          {items.map((item) => (
            <NavEntry key={item.label} item={item} pathname={pathname} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

export function Sidebar() {
  const pathname = usePathname();
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("dars_session");
      if (raw) setSession(JSON.parse(raw) as Session);
    } catch {
      // ignore parse errors
    }
  }, []);

  const isAdmin = session?.is_admin === true;

  function handleSignOut() {
    localStorage.removeItem("dars_session");
    window.location.href = "/login";
  }

  return (
    <aside className="w-56 shrink-0 flex flex-col border-r border-dars-rule-light bg-dars-parchment min-h-screen">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-dars-rule-light">
        <a href="/" className="no-underline">
          <Logo size="sm" />
        </a>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4">
        {isAdmin && (
          <SectionGroup
            title="Admin"
            items={adminItems}
            pathname={pathname}
            storageKey="dars_sidebar_admin"
          />
        )}
        <SectionGroup
          title="Client"
          items={clientItems}
          pathname={pathname}
          storageKey="dars_sidebar_client"
        />
        <SectionGroup
          title="Teacher"
          items={teacherItems}
          pathname={pathname}
          storageKey="dars_sidebar_teacher"
        />
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-dars-rule-light">
        <button
          onClick={handleSignOut}
          className="w-full text-left px-3 py-2 text-xs text-dars-muted hover:text-dars-ink transition-colors rounded-md hover:bg-dars-parchment-deep cursor-pointer bg-transparent border-none"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
