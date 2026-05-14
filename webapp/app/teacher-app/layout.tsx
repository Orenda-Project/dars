"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";

const NAV_ITEMS = [
  { label: "Today", href: "/teacher-app/today" },
  { label: "My Classes", href: "/teacher-app/classes" },
  { label: "Calendar", href: "/teacher-app/calendar" },
  { label: "Quick LP", href: "/teacher-app/quick-lp" },
  { label: "Quick Exam", href: "/teacher-app/quick-exam" },
];

function TopNav({ pathname }: { pathname: string }) {
  return (
    <div className="flex gap-1 px-4">
      {NAV_ITEMS.map((item) => {
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors no-underline ${
              active
                ? "border-amber-600 text-amber-700"
                : "border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}

export default function TeacherAppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const raw = localStorage.getItem("dars_pef_session");
    if (!raw) {
      router.replace("/dashboard/login");
    } else {
      setAuthChecked(true);
    }
  }, [router]);

  if (!authChecked) return null;

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Top bar */}
      <header className="border-b border-gray-200 bg-white sticky top-0 z-30">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold tracking-widest uppercase text-gray-400">Dars</span>
            <span className="text-gray-200">|</span>
            <span className="text-sm font-medium text-gray-700">Teacher App</span>
          </div>
          <Link
            href="/dashboard"
            className="text-xs text-gray-500 hover:text-gray-700 transition-colors no-underline flex items-center gap-1"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Back to Dashboard
          </Link>
        </div>

        {/* Amber banner */}
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-center">
          <span className="text-xs text-amber-700 font-medium">
            Sample Integration — this shows what you can build with the Dars API
          </span>
        </div>

        {/* Internal nav */}
        <TopNav pathname={pathname} />
      </header>

      <main className="flex-1 p-6 max-w-4xl mx-auto w-full">
        {children}
      </main>
    </div>
  );
}
