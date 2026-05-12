"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { Logo } from "@/components/atoms/logo";
import { isAdmin } from "@/lib/session";

const IconLessonPlan = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
  </svg>
);

const IconExam = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 11l3 3L22 4" />
    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
  </svg>
);

const IconBook = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
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

const IconSettings = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

const isBeta = process.env.NEXT_PUBLIC_BETA === "true";

const IconAnalytics = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

const IconCalendar = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </svg>
);

const mainNavItems = [
  { label: "Lesson Plans", href: "/dashboard/lesson-plans", icon: IconLessonPlan },
  { label: "Exam Generator", href: "/dashboard/exam-generator", icon: IconExam },
  { label: "Analytics", href: "/dashboard/analytics", icon: IconAnalytics },
  { label: "Planner", href: "/dashboard/curriculum-demo", icon: IconCalendar },
];

const IconDownload = (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);

const adminNavItems = [
  { label: "Curriculum", href: "/dashboard/curriculum", icon: IconBook },
  { label: "Books", href: "/dashboard/admin/books", icon: IconDownload },
  { label: "Clients", href: "/dashboard/admin/clients", icon: IconUsers },
];

const betaNavItems: { label: string; href: string; icon: React.ReactNode }[] = [];

function NavEntry({ label, href, icon, pathname }: { label: string; href: string; icon: React.ReactNode; pathname: string }) {
  const active = pathname === href || pathname.startsWith(href + "/");

  return (
    <a
      href={href}
      className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-colors no-underline ${
        active
          ? "bg-dars-terra text-white"
          : "text-dars-muted-light hover:bg-white/10 hover:text-dars-parchment"
      }`}
    >
      {icon}
      {label}
    </a>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [admin, setAdmin] = useState(false);

  useEffect(() => { setAdmin(isAdmin()); }, []);

  function handleSignOut() {
    localStorage.removeItem("dars_pef_session");
    window.location.href = "/dashboard/login";
  }

  return (
    <aside className="w-56 shrink-0 flex flex-col border-r border-dars-rule-dark bg-dars-ink min-h-screen">
      <div className="px-5 py-5 border-b border-dars-rule-dark">
        <a href="/" className="no-underline block overflow-visible">
          <Logo size="sm" variant="light" />
        </a>
      </div>

      <nav className="flex-1 px-3 py-4">
        <div className="space-y-0.5">
          {mainNavItems.map((item) => (
            <NavEntry key={item.label} {...item} pathname={pathname} />
          ))}
        </div>

        {admin && adminNavItems.length > 0 && (
          <div className="mt-4">
            <p className="px-3 py-1.5 text-[10px] font-semibold tracking-widest uppercase text-dars-muted-light/50">
              Admin
            </p>
            <div className="space-y-0.5">
              {adminNavItems.map((item) => (
                <NavEntry key={item.label} {...item} pathname={pathname} />
              ))}
            </div>
          </div>
        )}

        {isBeta && betaNavItems.length > 0 && (
          <div className="mt-4">
            <p className="px-3 py-1.5 text-[10px] font-semibold tracking-widest uppercase text-dars-muted-light/50">
              Beta
            </p>
            <div className="space-y-0.5">
              {betaNavItems.map((item) => (
                <NavEntry key={item.label} {...item} pathname={pathname} />
              ))}
            </div>
          </div>
        )}
      </nav>

      <div className="px-3 py-4 border-t border-dars-rule-dark space-y-0.5">
        <NavEntry label="Settings" href="/dashboard/settings" icon={IconSettings} pathname={pathname} />
        <button
          onClick={handleSignOut}
          className="w-full text-left px-3 py-2 text-xs text-dars-muted-light hover:text-dars-parchment transition-colors rounded-md hover:bg-white/10 cursor-pointer bg-transparent border-none flex items-center gap-2.5"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          Sign out
        </button>
      </div>
    </aside>
  );
}
