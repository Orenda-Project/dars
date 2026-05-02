"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { getApiKey, isAdmin } from "@/lib/session";
import { toast } from "sonner";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

const SCHEMAS = [
  { value: "fde_staging", label: "fde_staging — ICT (Federal)" },
  { value: "balochistan_staging", label: "balochistan_staging — Punjab" },
] as const;

type Schema = (typeof SCHEMAS)[number]["value"];

const CURRICULUM_BY_SCHEMA: Record<Schema, string> = {
  fde_staging: "ICT",
  balochistan_staging: "Punjab",
};

interface ChapterPreview {
  id: number;
  title: string;
  chapter_number: number;
  start_page: number | null;
  end_page: number | null;
}

interface BookPreview {
  core_id: number;
  schema: string;
  title: string;
  publisher: string | null;
  edition: string | null;
  published_year: number | null;
  total_chapters: number | null;
  pdf_url: string | null;
  series: string | null;
  has_ocr: boolean;
  chapters: ChapterPreview[];
}

function Spinner() {
  return (
    <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

export default function ImportBookPage() {
  const router = useRouter();
  const [coreId, setCoreId] = useState("");
  const [schema, setSchema] = useState<Schema>("fde_staging");
  const [grade, setGrade] = useState("");
  const [subject, setSubject] = useState("Eng");

  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<BookPreview | null>(null);

  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ status: string; chapters: number } | null>(null);

  useEffect(() => {
    if (!isAdmin()) router.replace("/dashboard/lesson-plans");
  }, [router]);

  async function handlePreview() {
    const id = parseInt(coreId, 10);
    if (!id || id <= 0) { toast.error("Enter a valid book ID."); return; }
    setPreviewing(true);
    setPreview(null);
    setImportResult(null);
    try {
      const r = await fetch(`${API_URL}/admin/preview-book?core_id=${id}&schema=${schema}`, {
        headers: { "X-API-Key": getApiKey() },
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${r.status}`);
      }
      setPreview(await r.json());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Preview failed.");
    } finally {
      setPreviewing(false);
    }
  }

  async function handleImport() {
    if (!preview) return;
    const gradeNum = parseInt(grade, 10);
    if (!gradeNum || gradeNum < 1 || gradeNum > 12) { toast.error("Enter a valid grade (1–12)."); return; }
    setImporting(true);
    setImportResult(null);
    try {
      const r = await fetch(`${API_URL}/admin/import-book`, {
        method: "POST",
        headers: { "X-API-Key": getApiKey(), "Content-Type": "application/json" },
        body: JSON.stringify({
          core_id: preview.core_id,
          schema: preview.schema,
          curriculum: CURRICULUM_BY_SCHEMA[preview.schema as Schema],
          grade: gradeNum,
          subject,
        }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${r.status}`);
      }
      setImportResult(await r.json());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="font-serif text-2xl font-bold text-dars-ink mb-2">Import Book</h1>
      <p className="text-sm text-dars-muted mb-8">
        Enter a core book ID and schema. Preview fetches the book from taleemabad-core without saving anything.
        Confirm to import it fully into Dars — including OCR text.
      </p>

      {/* Input form */}
      <div className="flex flex-col gap-4 mb-6">
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="block text-xs font-semibold text-dars-muted uppercase tracking-wide mb-1.5">
              Book ID
            </label>
            <input
              type="number"
              min="1"
              value={coreId}
              onChange={(e) => { setCoreId(e.target.value); setPreview(null); setImportResult(null); }}
              placeholder="e.g. 1171"
              className="w-full border border-dars-rule-light rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra placeholder:text-dars-muted/50"
            />
          </div>

          <div className="flex-1">
            <label className="block text-xs font-semibold text-dars-muted uppercase tracking-wide mb-1.5">
              Schema
            </label>
            <select
              value={schema}
              onChange={(e) => { setSchema(e.target.value as Schema); setPreview(null); setImportResult(null); }}
              className="w-full border border-dars-rule-light rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
            >
              {SCHEMAS.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        <button
          type="button"
          onClick={handlePreview}
          disabled={previewing || !coreId}
          className="self-start flex items-center gap-2 px-5 py-2 rounded-md border border-dars-terra text-dars-terra text-sm font-semibold hover:bg-dars-terra/5 disabled:opacity-50 cursor-pointer transition-colors"
        >
          {previewing ? <><Spinner /> Looking up…</> : "Preview book"}
        </button>

      </div>

      {/* Preview card */}
      {preview && (
        <div className="border border-dars-rule-light rounded-lg overflow-hidden mb-6">
          <div className="px-5 py-4 bg-dars-parchment border-b border-dars-rule-light">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-serif text-lg font-bold text-dars-ink leading-snug">{preview.title}</h2>
                {preview.series && <p className="text-xs text-dars-muted mt-0.5">{preview.series}</p>}
              </div>
              <span
                className={`shrink-0 mt-1 px-2 py-0.5 rounded text-xs font-semibold ${
                  preview.has_ocr
                    ? "bg-green-100 text-green-700"
                    : "bg-amber-100 text-amber-700"
                }`}
              >
                {preview.has_ocr ? "OCR available" : "No OCR"}
              </span>
            </div>

            <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
              <div><span className="text-dars-muted">Publisher</span> <span className="text-dars-ink ml-2">{preview.publisher ?? "—"}</span></div>
              <div><span className="text-dars-muted">Edition</span> <span className="text-dars-ink ml-2">{preview.edition ?? "—"}</span></div>
              <div><span className="text-dars-muted">Year</span> <span className="text-dars-ink ml-2">{preview.published_year ?? "—"}</span></div>
              <div><span className="text-dars-muted">Chapters</span> <span className="text-dars-ink ml-2">{preview.chapters.length} ({preview.total_chapters} declared)</span></div>
              <div className="col-span-2"><span className="text-dars-muted">Schema</span> <span className="text-dars-ink ml-2 font-mono text-xs">{preview.schema}</span></div>
            </div>
          </div>

          {/* Chapters list */}
          <div className="divide-y divide-dars-rule-light max-h-48 overflow-y-auto">
            {preview.chapters.map((ch) => (
              <div key={ch.id} className="flex items-center gap-3 px-5 py-2 text-sm">
                <span className="w-5 text-right text-dars-muted text-xs shrink-0">{ch.chapter_number}</span>
                <span className="flex-1 text-dars-ink">{ch.title}</span>
                {(ch.start_page || ch.end_page) && (
                  <span className="text-xs text-dars-muted">pp. {ch.start_page}–{ch.end_page}</span>
                )}
              </div>
            ))}
          </div>

          {/* Import controls */}
          <div className="px-5 py-4 bg-dars-parchment border-t border-dars-rule-light">
            {importResult ? (
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold text-green-700">
                  {importResult.status === "imported" ? "Imported" : "Updated"} — {importResult.chapters} chapters saved.
                </span>
                <button
                  type="button"
                  onClick={() => { setPreview(null); setCoreId(""); setImportResult(null); }}
                  className="text-xs text-dars-muted underline cursor-pointer"
                >
                  Import another
                </button>
              </div>
            ) : (
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="block text-xs font-semibold text-dars-muted uppercase tracking-wide mb-1.5">
                    Grade
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="12"
                    value={grade}
                    onChange={(e) => setGrade(e.target.value)}
                    placeholder="e.g. 3"
                    className="w-24 border border-dars-rule-light rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra placeholder:text-dars-muted/50"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-dars-muted uppercase tracking-wide mb-1.5">
                    Subject
                  </label>
                  <select
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    className="border border-dars-rule-light rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  >
                    <option value="Eng">English</option>
                    <option value="Maths">Maths</option>
                    <option value="Urdu">Urdu</option>
                    <option value="Science">Science</option>
                    <option value="SST">Social Studies</option>
                  </select>
                </div>
                <button
                  type="button"
                  onClick={handleImport}
                  disabled={importing}
                  className="flex items-center gap-2 px-5 py-2 rounded-md bg-dars-terra text-white text-sm font-semibold hover:bg-dars-terra/90 disabled:opacity-50 cursor-pointer transition-colors"
                >
                  {importing ? <><Spinner /> Importing…</> : "Confirm import"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
