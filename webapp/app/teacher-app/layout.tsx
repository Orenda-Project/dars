/**
 * F4.3 — Teacher app layout.
 *
 * Per webapp/CLAUDE.md: layout owns the shell + auth gate; pages own
 * their own data fetching. Auth here is a thin localStorage check —
 * the real auth flows server-side via the X-API-Key header on every
 * API request (handled by lib/dars-api.ts).
 *
 * Missing key → redirect to /teacher-app/setup. The setup page is
 * itself a child of this layout but we let it render without checking
 * for a key (otherwise we'd loop).
 */
"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { TeacherAppShell } from "@/components/templates/teacher-app-shell";
import { getApiKey } from "@/lib/dars-api";

export default function TeacherAppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (pathname === "/teacher-app/setup") {
      setChecked(true);
      return;
    }
    if (!getApiKey()) {
      router.replace("/teacher-app/setup");
      return;
    }
    setChecked(true);
  }, [pathname, router]);

  // Setup page renders bare (no shell) so the API-key prompt is the
  // first thing the user sees.
  if (pathname === "/teacher-app/setup") {
    return <>{children}</>;
  }

  if (!checked) {
    return (
      <div className="min-h-screen bg-dars-parchment flex items-center justify-center">
        <span className="text-sm text-dars-muted">Loading…</span>
      </div>
    );
  }

  return <TeacherAppShell activeHref={pathname}>{children}</TeacherAppShell>;
}
