"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/molecules/dashboard/sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    if (pathname === "/dashboard/login") {
      setAuthChecked(true);
      return;
    }

    const raw = localStorage.getItem("dars_pef_session");
    if (!raw) {
      router.replace("/dashboard/login");
    } else {
      setAuthChecked(true);
    }
  }, [pathname, router]);

  if (pathname === "/dashboard/login") {
    return <>{children}</>;
  }

  if (!authChecked) return null;

  return (
    <div className="flex min-h-screen bg-dars-parchment">
      <Sidebar />
      <main className="flex-1 overflow-auto relative">
        {/* Subtle paper grain */}
        <svg className="pointer-events-none fixed inset-0 w-full h-full opacity-[0.035] z-0" xmlns="http://www.w3.org/2000/svg">
          <filter id="grain">
            <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch" />
            <feColorMatrix type="saturate" values="0" />
          </filter>
          <rect width="100%" height="100%" filter="url(#grain)" />
        </svg>
        {/* Warm radial glow from top-right */}
        <div
          className="pointer-events-none fixed top-0 right-0 w-[600px] h-[500px] z-0"
          style={{ background: "radial-gradient(ellipse at top right, rgba(191,78,48,0.06) 0%, transparent 70%)" }}
        />
        <div className="relative z-10">{children}</div>
      </main>
    </div>
  );
}
