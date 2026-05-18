/**
 * F5.1 — Dashboard layout.
 *
 * Auth gate: redirects to /dashboard/login if no admin session. The
 * login + signup pages render outside the shell.
 */
"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/templates/dashboard-shell";
import {
  admin,
  clearAdminSession,
  clearApiKey,
  DarsApiError,
  getAdminSession,
  type AdminMeResponse,
} from "@/lib/dars-api";

const UNAUTHED_PATHS = new Set(["/dashboard/login", "/dashboard/signup"]);

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<AdminMeResponse | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (UNAUTHED_PATHS.has(pathname)) {
      setChecked(true);
      return;
    }
    if (!getAdminSession()) {
      router.replace("/dashboard/login");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const m = await admin.me();
        if (!cancelled) {
          setMe(m);
          setChecked(true);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof DarsApiError && err.status === 401) {
          clearAdminSession();
          clearApiKey();
          router.replace("/dashboard/login");
          return;
        }
        // Other errors: still mark checked so we can show an inline error.
        setChecked(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  if (UNAUTHED_PATHS.has(pathname)) {
    return <>{children}</>;
  }

  if (!checked) {
    return (
      <div className="min-h-screen bg-dars-parchment flex items-center justify-center">
        <span className="text-sm text-dars-muted">Loading…</span>
      </div>
    );
  }

  if (!me) {
    return (
      <div className="min-h-screen bg-dars-parchment flex items-center justify-center">
        <span className="text-sm text-dars-terra">
          Couldn’t load your session. <a className="underline" href="/dashboard/login">Log in again</a>.
        </span>
      </div>
    );
  }

  async function handleLogout() {
    try {
      await admin.logout();
    } catch {
      // ignore — token may already be invalid
    }
    clearAdminSession();
    clearApiKey();
    router.replace("/dashboard/login");
  }

  return (
    <DashboardShell
      activeHref={pathname}
      orgName={me.org_name}
      adminName={me.name}
      onLogout={handleLogout}
    >
      {children}
    </DashboardShell>
  );
}
