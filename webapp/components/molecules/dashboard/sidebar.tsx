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

const isBeta = process.env.NEXT_PUBLIC_BETA === "true";

const mainNavItems = [
  { label: "Lesson Plans", href: "/dashboard/lesson-plans", icon: IconLessonPlan },
  { label: "Exam Generator", href: "/dashboard/exam-generator", icon: IconExam },
];

const adminNavItems = [
  { label: "Curriculum", href: "/dashboard/curriculum", icon: IconBook },
  { label: "Clients", href: "/dashboard/admin/clients", icon: IconUsers },
];

const betaNavItems = [
  { label: "Curriculum Demo", href: "/dashboard/curriculum-demo", icon: IconBook },
];

function NavEntry({ label, href, icon, pathname }: { label: string; href: string; icon: React.ReactNode; pathname: string }) {
  const active = pathname === href || pathname.startsWith(href + "/");

  return (
    <a
      href={href}
      className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-colors no-underline ${
        active
          ? "bg-dars-terra text-white"
          : "text-dars-muted hover:bg-dars-parchment-deep hover:text-dars-ink"
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
    <aside className="w-56 shrink-0 flex flex-col border-r border-dars-rule-light bg-dars-parchment min-h-screen">
      <div className="px-5 py-5 border-b border-dars-rule-light">
        <a href="/" className="no-underline">
          <Logo size="sm" />
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
            <p className="px-3 py-1.5 text-[10px] font-semibold tracking-widest uppercase text-dars-muted/70">
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
            <p className="px-3 py-1.5 text-[10px] font-semibold tracking-widest uppercase text-dars-muted/70">
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
