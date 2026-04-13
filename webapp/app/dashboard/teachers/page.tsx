"use client";

import { useEffect, useRef, useState } from "react";

interface Session {
  api_key: string;
  client_id: string;
  name: string;
  email: string;
}

interface Teacher {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  school: string | null;
  created_at: string;
}

interface TeacherListResponse {
  items: Teacher[];
  total: number;
  limit: number;
  offset: number;
}

interface RegisterForm {
  name: string;
  email: string;
  phone: string;
  school: string;
}

const DEFAULT_FORM: RegisterForm = {
  name: "",
  email: "",
  phone: "",
  school: "",
};

const LIMIT = 10;

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-PK", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function TeachersPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const [session, setSession] = useState<Session | null>(null);

  // --- Register form state ---
  const [form, setForm] = useState<RegisterForm>(DEFAULT_FORM);
  const [registering, setRegistering] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);
  const [registerSuccess, setRegisterSuccess] = useState<string | null>(null);

  // --- Teacher list state ---
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  // --- Search state ---
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --- Copy-to-clipboard state ---
  const [copiedId, setCopiedId] = useState<string | null>(null);

  function handleCopyId(id: string) {
    navigator.clipboard.writeText(id).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1500);
    });
  }

  // --- Auth ---
  useEffect(() => {
    const raw = localStorage.getItem("dars_session");
    if (!raw) {
      window.location.href = "/login";
      return;
    }
    setSession(JSON.parse(raw) as Session);
  }, []);

  // --- Fetch teachers ---
  function fetchTeachers(newOffset: number, apiKey: string, query: string) {
    setListLoading(true);
    setListError(null);
    const params = new URLSearchParams({
      limit: String(LIMIT),
      offset: String(newOffset),
    });
    if (query) params.set("search", query);

    fetch(`${apiBase}/api/v1/teachers?${params.toString()}`, {
      headers: { "X-API-Key": apiKey },
    })
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 401) {
            localStorage.removeItem("dars_session");
            window.location.href = "/login";
            return;
          }
          throw new Error("Failed to fetch teachers.");
        }
        const data = (await res.json()) as TeacherListResponse;
        setTeachers(data.items);
        setTotal(data.total);
        setListLoading(false);
      })
      .catch((err: unknown) => {
        setListError(err instanceof Error ? err.message : "An unexpected error occurred.");
        setListLoading(false);
      });
  }

  useEffect(() => {
    if (!session) return;
    fetchTeachers(offset, session.api_key, searchQuery);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, offset, searchQuery]);

  // --- Debounced search ---
  function handleSearchChange(value: string) {
    setSearchInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setOffset(0);
      setSearchQuery(value.trim());
    }, 400);
  }

  // --- Register teacher ---
  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (!session) return;
    setRegistering(true);
    setRegisterError(null);
    setRegisterSuccess(null);

    const body: Record<string, string> = { name: form.name };
    if (form.email) body.email = form.email;
    if (form.phone) body.phone = form.phone;
    if (form.school) body.school = form.school;

    try {
      const res = await fetch(`${apiBase}/api/v1/teachers`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": session.api_key,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        if (res.status === 401) {
          localStorage.removeItem("dars_session");
          window.location.href = "/login";
          return;
        }
        const errData = await res.json().catch(() => ({}));
        throw new Error(
          (errData as { detail?: string }).detail ?? "Failed to register teacher.",
        );
      }

      const created = (await res.json()) as Teacher;
      setRegisterSuccess(`Teacher "${created.name}" registered successfully.`);
      setForm(DEFAULT_FORM);
      setOffset(0);
      setSearchQuery("");
      setSearchInput("");
      fetchTeachers(0, session.api_key, "");
    } catch (err: unknown) {
      setRegisterError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setRegistering(false);
    }
  }

  const totalPages = Math.ceil(total / LIMIT);
  const currentPage = Math.floor(offset / LIMIT) + 1;

  return (
    <div className="p-8 max-w-5xl">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-serif font-bold text-dars-ink">Teachers</h1>
        {session && (
          <p className="text-sm text-dars-muted mt-1">
            {session.name} &middot; {session.email}
          </p>
        )}
      </div>

      {/* Section A: Register form */}
      <section className="mb-12">
        <h2 className="text-lg font-serif font-semibold text-dars-ink mb-4">
          Register a Teacher
        </h2>
        <form
          onSubmit={handleRegister}
          className="border border-dars-rule-light rounded-lg bg-dars-parchment p-6 space-y-5"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Name */}
            <div>
              <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                Name <span className="text-dars-terra">*</span>
              </label>
              <input
                type="text"
                required
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                placeholder="e.g. Ayesha Khan"
              />
            </div>

            {/* Email */}
            <div>
              <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                Email
              </label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                placeholder="e.g. ayesha@school.edu.pk"
              />
            </div>

            {/* Phone */}
            <div>
              <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                Phone
              </label>
              <input
                type="text"
                value={form.phone}
                onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                placeholder="Optional"
              />
            </div>

            {/* School */}
            <div>
              <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                School
              </label>
              <input
                type="text"
                value={form.school}
                onChange={(e) => setForm((f) => ({ ...f, school: e.target.value }))}
                className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                placeholder="Optional"
              />
            </div>
          </div>

          {registerError && (
            <p className="text-sm text-red-600 border border-red-200 rounded-md px-3 py-2 bg-red-50">
              {registerError}
            </p>
          )}

          {registerSuccess && (
            <p className="text-sm text-green-700 border border-green-200 rounded-md px-3 py-2 bg-green-50">
              {registerSuccess}
            </p>
          )}

          <button
            type="submit"
            disabled={registering}
            className="px-5 py-2.5 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {registering ? "Registering..." : "Register Teacher"}
          </button>
        </form>
      </section>

      {/* Section B: Teacher table */}
      <section>
        <div className="flex items-center justify-between gap-4 mb-4">
          <h2 className="text-lg font-serif font-semibold text-dars-ink">
            Registered Teachers
          </h2>
          {/* Search */}
          <input
            type="search"
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search by name or email..."
            className="w-64 border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
          />
        </div>

        {listError && (
          <p className="text-sm text-red-600 border border-red-200 rounded-md px-3 py-2 bg-red-50 mb-4">
            {listError}
          </p>
        )}

        {/* Table */}
        <div className="border border-dars-rule-light rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-dars-parchment border-b border-dars-rule-light">
                <th className="text-left px-4 py-3 text-xs font-semibold text-dars-muted uppercase tracking-wide">
                  Name
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-dars-muted uppercase tracking-wide">
                  Email
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-dars-muted uppercase tracking-wide hidden sm:table-cell">
                  Phone
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-dars-muted uppercase tracking-wide hidden md:table-cell">
                  School
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-dars-muted uppercase tracking-wide whitespace-nowrap hidden lg:table-cell">
                  Teacher ID
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-dars-muted uppercase tracking-wide whitespace-nowrap">
                  Registered
                </th>
              </tr>
            </thead>
            <tbody>
              {listLoading && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-dars-muted animate-pulse">
                    Loading teachers...
                  </td>
                </tr>
              )}

              {!listLoading && !listError && teachers.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-dars-muted">
                    {searchQuery
                      ? `No teachers found matching "${searchQuery}".`
                      : "No teachers registered yet. Add the first one above."}
                  </td>
                </tr>
              )}

              {!listLoading &&
                teachers.map((teacher, idx) => (
                  <tr
                    key={teacher.id}
                    className={
                      idx % 2 === 0
                        ? "bg-white border-b border-dars-rule-light last:border-b-0"
                        : "bg-dars-parchment border-b border-dars-rule-light last:border-b-0"
                    }
                  >
                    <td className="px-4 py-3 font-medium text-dars-ink">
                      {teacher.name}
                    </td>
                    <td className="px-4 py-3 text-dars-muted">
                      {teacher.email ?? <span className="text-dars-rule-dark">—</span>}
                    </td>
                    <td className="px-4 py-3 text-dars-muted hidden sm:table-cell">
                      {teacher.phone ?? <span className="text-dars-rule-dark">—</span>}
                    </td>
                    <td className="px-4 py-3 text-dars-muted hidden md:table-cell">
                      {teacher.school ?? <span className="text-dars-rule-dark">—</span>}
                    </td>
                    <td className="px-4 py-3 text-dars-muted hidden lg:table-cell">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="font-mono text-xs">
                          {teacher.id.slice(0, 8)}&hellip;
                        </span>
                        <button
                          type="button"
                          onClick={() => handleCopyId(teacher.id)}
                          title="Copy full Teacher ID"
                          className="text-dars-muted hover:text-dars-ink transition-colors cursor-pointer"
                        >
                          {copiedId === teacher.id ? (
                            <span className="text-xs font-medium text-green-600">Copied!</span>
                          ) : (
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="13"
                              height="13"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              aria-hidden="true"
                            >
                              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                            </svg>
                          )}
                        </button>
                      </span>
                    </td>
                    <td className="px-4 py-3 text-dars-muted whitespace-nowrap">
                      {formatDate(teacher.created_at)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > LIMIT && (
          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              onClick={() => {
                if (session) setOffset(Math.max(0, offset - LIMIT));
              }}
              disabled={offset === 0 || listLoading}
              className="px-4 py-2 text-sm font-medium border border-dars-rule-dark rounded-md text-dars-ink hover:bg-dars-parchment-mid transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer bg-white"
            >
              Previous
            </button>
            <span className="text-sm text-dars-muted">
              Page {currentPage} of {totalPages}
            </span>
            <button
              type="button"
              onClick={() => {
                if (session) setOffset(offset + LIMIT);
              }}
              disabled={offset + LIMIT >= total || listLoading}
              className="px-4 py-2 text-sm font-medium border border-dars-rule-dark rounded-md text-dars-ink hover:bg-dars-parchment-mid transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer bg-white"
            >
              Next
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
