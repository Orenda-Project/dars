/**
 * F5.1 — Dashboard shell.
 *
 * Desktop-first layout: left sidebar nav, top bar with org/admin name +
 * logout, main content area. Auth gate lives in the layout file; this
 * template just renders.
 */
"use client";

import Link from "next/link";

import { Logo } from "@/components/atoms";

export interface DashboardNavItem {
  href: string;
  label: string;
  group?: string;
}

interface DashboardShellProps {
  activeHref: string;
  orgName: string;
  adminName: string;
  onLogout: () => void;
  children: React.ReactNode;
}

const NAV: DashboardNavItem[] = [
  { href: "/dashboard/overview", label: "Overview" },
  { href: "/dashboard/schools", label: "Schools", group: "Tenancy" },
  { href: "/dashboard/curriculum", label: "Curriculum", group: "Content" },
  { href: "/dashboard/breakdowns", label: "Syllabus Breakdowns", group: "Content" },
  { href: "/dashboard/generations", label: "Generations", group: "Operations" },
  { href: "/dashboard/generations/failures", label: "Failures", group: "Operations" },
  { href: "/dashboard/reports/slo-coverage", label: "SLO coverage", group: "Reports" },
  { href: "/dashboard/reports/usage", label: "Usage", group: "Reports" },
  { href: "/dashboard/settings/org", label: "Org settings", group: "Settings" },
  { href: "/dashboard/settings/holidays", label: "Holidays", group: "Settings" },
];

export function DashboardShell({
  activeHref,
  orgName,
  adminName,
  onLogout,
  children,
}: DashboardShellProps) {
  // Group nav items by group label for visual hierarchy
  const grouped = NAV.reduce<Record<string, DashboardNavItem[]>>((acc, item) => {
    const g = item.group ?? "";
    acc[g] ??= [];
    acc[g].push(item);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-dars-parchment flex">
      <aside className="w-60 border-r border-dars-rule-light bg-dars-parchment-mid p-4 hidden md:block">
        <Link href="/dashboard/overview" className="block mb-6">
          <Logo size="md" variant="dark" />
        </Link>
        <nav className="space-y-4 text-sm">
          {Object.entries(grouped).map(([group, items]) => (
            <div key={group}>
              {group ? (
                <p className="text-[10px] uppercase tracking-wider text-dars-muted font-semibold mb-1 px-2">
                  {group}
                </p>
              ) : null}
              <ul className="space-y-0.5">
                {items.map((item) => (
                  <li key={item.href}>
                    <NavLink
                      href={item.href}
                      label={item.label}
                      active={
                        activeHref === item.href ||
                        activeHref.startsWith(item.href + "/")
                      }
                    />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="border-b border-dars-rule-light bg-dars-parchment px-5 py-3 flex items-center justify-between gap-3">
          <div className="text-sm text-dars-ink-soft truncate">
            <span className="font-semibold text-dars-ink">{orgName}</span>
            <span className="text-dars-muted-light mx-2">·</span>
            <span className="text-dars-muted">{adminName}</span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/teacher-app/today"
              className="text-xs text-dars-muted hover:text-dars-terra px-2 py-1 rounded hover:bg-dars-parchment-deep"
            >
              Teacher app demo →
            </Link>
            <button
              type="button"
              onClick={onLogout}
              className="text-xs text-dars-muted hover:text-dars-terra px-2 py-1 rounded hover:bg-dars-parchment-deep"
            >
              Log out
            </button>
          </div>
        </header>

        <main className="flex-1 p-6 overflow-x-auto">{children}</main>
      </div>
    </div>
  );
}

function NavLink({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={
        "block px-2 py-1.5 rounded text-sm " +
        (active
          ? "bg-dars-terra/15 text-dars-terra font-semibold"
          : "text-dars-ink-soft hover:bg-dars-parchment-deep")
      }
    >
      {label}
    </Link>
  );
}
