"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/molecules/dashboard/sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Allow the login page through without a session check
    if (pathname === "/dashboard/login") return;

    const raw = localStorage.getItem("dars_pef_session");
    if (!raw) {
      router.replace("/dashboard/login");
    }
  }, [pathname, router]);

  // Render the login page without the sidebar shell
  if (pathname === "/dashboard/login") {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
