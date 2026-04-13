"use client";

import { usePathname } from "next/navigation";
import { Logo } from "@/components/atoms/logo";

const navItems = [
  {
    label: "Lesson Plans",
    href: "/dashboard/lesson-plans",
    disabled: false,
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
  {
    label: "Analytics",
    href: "/dashboard/analytics",
    disabled: false,
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    ),
  },
  {
    label: "Teachers",
    href: "/dashboard/teachers",
    disabled: false,
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
  {
    label: "Exam Generator",
    href: null,
    disabled: true,
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
];

export function Sidebar() {
  const pathname = usePathname();

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
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map((item) => {
          if (item.disabled) {
            return (
              <div
                key={item.label}
                className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium text-dars-muted/50 cursor-not-allowed select-none"
              >
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
              key={item.href}
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
        })}
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
