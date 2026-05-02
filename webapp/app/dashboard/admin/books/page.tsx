"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getApiKey, isAdmin } from "@/lib/session";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface Book {
  id: string;
  core_id: number;
  curriculum: string;
  grade: number;
  subject: string;
  title: string;
  publisher: string | null;
  total_chapters: number | null;
  series: string | null;
  created_at: string;
}

const SUBJECTS = ["Eng", "Maths", "Urdu", "Science", "SST"];
const SUBJECT_LABELS: Record<string, string> = {
  Eng: "English",
  Maths: "Maths",
  Urdu: "Urdu",
  Science: "Science",
  SST: "Social Studies",
};

export default function AdminBooksPage() {
  const router = useRouter();
  const [books, setBooks] = useState<Book[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [curriculum, setCurriculum] = useState("");
  const [grade, setGrade] = useState("");
  const [subject, setSubject] = useState("");

  useEffect(() => {
    if (!isAdmin()) { router.replace("/dashboard/lesson-plans"); return; }
  }, [router]);

  useEffect(() => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (curriculum) params.set("curriculum", curriculum);
    if (grade) params.set("grade", grade);
    if (subject) params.set("subject", subject);
    const qs = params.toString();
    fetch(`${API_URL}/api/v1/books${qs ? `?${qs}` : ""}`, {
      headers: { "X-API-Key": getApiKey() },
    })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: { items: Book[]; total: number }) => {
        setBooks(data.items ?? []);
        setTotal(data.total ?? 0);
      })
      .catch(() => setError("Failed to load books."))
      .finally(() => setLoading(false));
  }, [curriculum, grade, subject]);

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="font-serif text-2xl font-bold text-dars-ink mb-1">Books</h1>
          <p className="text-sm text-dars-muted">
            {loading ? "Loading…" : `${total} book${total !== 1 ? "s" : ""} imported`}
          </p>
        </div>
        <a
          href="/dashboard/admin/import"
          className="px-4 py-2 rounded-md bg-dars-terra text-white text-sm font-semibold hover:bg-dars-terra/90 transition-colors no-underline"
        >
          Import book
        </a>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-5">
        <select
          value={curriculum}
          onChange={(e) => setCurriculum(e.target.value)}
          className="border border-dars-rule-light rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
        >
          <option value="">All curricula</option>
          <option value="ICT">ICT</option>
          <option value="Punjab">Punjab</option>
        </select>

        <select
          value={grade}
          onChange={(e) => setGrade(e.target.value)}
          className="border border-dars-rule-light rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
        >
          <option value="">All grades</option>
          {[1, 2, 3, 4, 5, 6, 7, 8].map((g) => (
            <option key={g} value={g}>Grade {g}</option>
          ))}
        </select>

        <select
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className="border border-dars-rule-light rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
        >
          <option value="">All subjects</option>
          {SUBJECTS.map((s) => (
            <option key={s} value={s}>{SUBJECT_LABELS[s]}</option>
          ))}
        </select>

        {(curriculum || grade || subject) && (
          <button
            type="button"
            onClick={() => { setCurriculum(""); setGrade(""); setSubject(""); }}
            className="text-sm text-dars-muted hover:text-dars-ink transition-colors cursor-pointer"
          >
            Clear
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      {loading ? (
        <p className="text-sm text-dars-muted">Loading…</p>
      ) : books.length === 0 ? (
        <div className="border border-dars-rule-light rounded-lg px-6 py-12 text-center">
          <p className="text-sm text-dars-muted">No books found.</p>
          <a href="/dashboard/admin/import" className="mt-3 inline-block text-sm text-dars-terra underline">
            Import one
          </a>
        </div>
      ) : (
        <div className="border border-dars-rule-light rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-dars-rule-light bg-dars-parchment">
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-dars-muted uppercase tracking-wide">Title</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-dars-muted uppercase tracking-wide">Curriculum</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-dars-muted uppercase tracking-wide">Grade</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-dars-muted uppercase tracking-wide">Subject</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-dars-muted uppercase tracking-wide">Chapters</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-dars-muted uppercase tracking-wide">Core ID</th>
              </tr>
            </thead>
            <tbody>
              {books.map((book) => (
                <tr
                  key={book.id}
                  className="border-b border-dars-rule-light last:border-0 hover:bg-dars-parchment transition-colors"
                >
                  <td className="px-4 py-3">
                    <a
                      href={`/dashboard/curriculum?book_id=${book.id}`}
                      className="text-dars-ink font-medium hover:text-dars-terra transition-colors no-underline"
                    >
                      {book.title}
                    </a>
                    {book.series && (
                      <p className="text-xs text-dars-muted mt-0.5">{book.series}</p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-dars-ink">{book.curriculum}</td>
                  <td className="px-4 py-3 text-dars-ink">{book.grade}</td>
                  <td className="px-4 py-3 text-dars-ink">{SUBJECT_LABELS[book.subject] ?? book.subject}</td>
                  <td className="px-4 py-3 text-dars-muted">{book.total_chapters ?? "—"}</td>
                  <td className="px-4 py-3 text-dars-muted font-mono text-xs">{book.core_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
