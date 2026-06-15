/**
 * F4.3 — Teacher app layout.
 *
 * Per webapp/CLAUDE.md: layout owns the shell + auth gate; pages own
 * their own data fetching. Auth here is a thin localStorage check —
 * the real auth flows server-side via the X-API-Key header on every
 * API request (handled by lib/dars-api.ts).
 *
 * Auto-login: a user who is already authenticated for the org — either an
 * org API key (dars_org_api_key, set on dashboard login/signup) OR an active
 * dashboard admin session (dars_admin_session) — walks straight in. The API
 * layer sends X-API-Key when a key is present and falls back to
 * X-Admin-Session otherwise, so either credential authenticates every call.
 *
 * Only a user with NEITHER credential is sent to /teacher-app/setup. The setup
 * page is a child of this layout but renders without the check (else we'd
 * loop).
 */
"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";

import { TeacherAppShell } from "@/components/templates/teacher-app-shell";
import { getAdminSession, getApiKey } from "@/lib/dars-api";

/**
 * Read "is the user authed for the org" from localStorage in a
 * hydration-safe way. useSyncExternalStore returns the server snapshot
 * (false) during SSR + first client render, then the real client value,
 * with no setState-in-effect. We don't subscribe to storage events — auth
 * doesn't change under a mounted layout — so the subscribe is a no-op.
 */
const noopSubscribe = () => () => {};
function useAuthed(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => getApiKey() !== "" || getAdminSession() !== "", // client
    () => false, // server / first paint
  );
}

export default function TeacherAppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const isSetup = pathname === "/teacher-app/setup";
  // Either credential is enough — an org key OR a live admin session.
  // False on the server + first paint, then the real localStorage value.
  const authed = useAuthed();

  // A user with neither credential is sent to setup (side effect → effect).
  useEffect(() => {
    if (!isSetup && !authed) {
      router.replace("/teacher-app/setup");
    }
  }, [isSetup, authed, router]);

  // Setup page renders bare (no shell) so the API-key prompt is the
  // first thing the user sees.
  if (isSetup) {
    return <>{children}</>;
  }

  if (!authed) {
    return (
      <div className="min-h-screen bg-dars-parchment flex items-center justify-center">
        <span className="text-sm text-dars-muted">Loading…</span>
      </div>
    );
  }

  return <TeacherAppShell activeHref={pathname}>{children}</TeacherAppShell>;
}
