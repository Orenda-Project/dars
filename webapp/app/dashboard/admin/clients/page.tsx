"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getApiKey, isAdmin } from "@/lib/session";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface ClientRow {
  id: string;
  name: string;
  email: string | null;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export default function AdminClientsPage() {
  const router = useRouter();
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAdmin()) { router.replace("/dashboard/lesson-plans"); return; }
    fetch(`${API_URL}/admin/clients`, { headers: { "X-API-Key": getApiKey() } })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: { items: ClientRow[] }) => setClients(data.items ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [router]);

  return (
    <div className="p-8 max-w-4xl">
      <h1 className="font-serif text-2xl font-bold text-dars-ink mb-6">Clients</h1>
      {loading ? (
        <p className="text-sm text-dars-muted">Loading…</p>
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-dars-rule-light">
              <th className="text-left py-2 px-3 text-xs font-semibold text-dars-muted uppercase tracking-wide">Name</th>
              <th className="text-left py-2 px-3 text-xs font-semibold text-dars-muted uppercase tracking-wide">Email</th>
              <th className="text-left py-2 px-3 text-xs font-semibold text-dars-muted uppercase tracking-wide">Active</th>
              <th className="text-left py-2 px-3 text-xs font-semibold text-dars-muted uppercase tracking-wide">Admin</th>
              <th className="text-left py-2 px-3 text-xs font-semibold text-dars-muted uppercase tracking-wide">Created</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((c) => (
              <tr key={c.id} className="border-b border-dars-rule-light hover:bg-dars-parchment">
                <td className="py-2.5 px-3 text-dars-ink font-medium">{c.name}</td>
                <td className="py-2.5 px-3 text-dars-muted">{c.email ?? "—"}</td>
                <td className="py-2.5 px-3">{c.is_active ? <span className="text-green-600 font-semibold">Yes</span> : <span className="text-red-500">No</span>}</td>
                <td className="py-2.5 px-3">{c.is_admin ? <span className="text-dars-terra font-semibold">Yes</span> : <span className="text-dars-muted">No</span>}</td>
                <td className="py-2.5 px-3 text-dars-muted">{new Date(c.created_at).toLocaleDateString("en-PK", { day: "numeric", month: "short", year: "numeric" })}</td>
              </tr>
            ))}
            {clients.length === 0 && (
              <tr><td colSpan={5} className="py-8 text-center text-dars-muted">No clients yet.</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
