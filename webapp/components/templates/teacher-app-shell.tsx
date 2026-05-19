/**
 * F4.3 — Teacher app shell template.
 *
 * Per webapp/CLAUDE.md: templates render with props only. No hooks, no
 * fetch. The layout file passes children + nav state.
 *
 * The amber banner declares "this is a sample integration" so prospects
 * understand what they're looking at. The nav is mobile-first (most
 * teachers will use phones).
 */
import Link from "next/link";
import { Logo } from "@/components/atoms";

interface NavItem {
  href: string;
  label: string;
}

interface TeacherAppShellProps {
  activeHref: string;
  children: React.ReactNode;
}

const NAV: NavItem[] = [
  { href: "/teacher-app/today", label: "Today" },
  { href: "/teacher-app/classes", label: "My Classes" },
  { href: "/teacher-app/calendar", label: "Calendar" },
  { href: "/teacher-app/quick-lp", label: "Quick LP" },
  { href: "/teacher-app/quick-exam", label: "Quick Exam" },
];

function NavLink({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={
        "px-3 py-2 text-sm rounded-md transition-colors whitespace-nowrap " +
        (active
          ? "bg-dars-terra text-dars-parchment font-semibold"
          : "text-dars-ink-soft hover:bg-dars-parchment-deep")
      }
    >
      {label}
    </Link>
  );
}

export function TeacherAppShell({ activeHref, children }: TeacherAppShellProps) {
  return (
    <div className="min-h-screen bg-dars-parchment text-dars-ink">
      {/* sample-integration banner */}
      <div className="bg-dars-terra-light/40 border-b border-dars-rule-light px-4 py-2 text-center text-xs sm:text-sm text-dars-ink-soft">
        <strong className="font-semibold">Sample integration</strong>
        {" — "}
        this is what a teacher's experience could look like.{" "}
        <a
          href="/"
          className="underline decoration-dars-terra underline-offset-2 hover:text-dars-terra"
        >
          Build your own with Dars
        </a>
        .
      </div>

      {/* top bar */}
      <header className="border-b border-dars-rule-light bg-dars-parchment sticky top-0 z-20">
        <div className="max-w-5xl mx-auto flex items-center gap-3 px-4 py-3">
          <Link href="/teacher-app/today" className="shrink-0">
            <Logo size="sm" variant="dark" />
          </Link>
          <nav className="flex-1 flex items-center gap-1 overflow-x-auto scrollbar-thin">
            {NAV.map((item) => (
              <NavLink
                key={item.href}
                href={item.href}
                label={item.label}
                active={activeHref === item.href || activeHref.startsWith(item.href + "/")}
              />
            ))}
          </nav>
          <Link
            href="/dashboard/overview"
            className="shrink-0 text-xs text-dars-muted hover:text-dars-terra px-2 py-1 rounded hover:bg-dars-parchment-deep whitespace-nowrap"
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
