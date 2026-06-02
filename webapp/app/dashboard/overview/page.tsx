/**
 * F5.1 — Dashboard overview / home.
 *
 * High-level summary so admins land somewhere useful. v1 shows counts
 * (schools / teachers / CSTs / breakdowns) + a "what's next" hint.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  syllabusBreakdowns as syllabusBreakdownsApi,
  curriculum as curriculumApi,
  DarsApiError,
  tenancy as tenancyApi,
  type SyllabusBreakdown,
  type CST,
  type School,
  type Teacher,
} from "@/lib/dars-api";

interface Counts {
  schools: number;
  teachers: number;
  csts: number;
  breakdownsPublished: number;
  breakdownsDraft: number;
}

export default function OverviewPage() {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [{ items: schools }, { items: teachers }, { items: csts }, { items: bds }] =
        await Promise.all([
          tenancyApi.getSchools(),
          tenancyApi.getTeachers(),
          tenancyApi.getCSTs(),
          syllabusBreakdownsApi.getBreakdowns(),
        ]);
      setCounts({
        schools: (schools as School[]).length,
        teachers: (teachers as Teacher[]).length,
        csts: (csts as CST[]).length,
        breakdownsPublished: (bds as SyllabusBreakdown[]).filter((b) => b.status === "published").length,
        breakdownsDraft: (bds as SyllabusBreakdown[]).filter((b) => b.status === "draft").length,
      });
    } catch (err) {
      setError(
        err instanceof DarsApiError
          ? `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`
          : err instanceof Error
          ? err.message
          : "Failed to load overview",
      );
    }
  }, []);

  useEffect(() => {
    load();
    void curriculumApi; // keep import for parity
  }, [load]);

  return (
    <div>
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-6">
        Overview
      </h1>

      {error ? (
        <ErrorBanner message={error} />
      ) : counts === null ? (
        <p className="text-sm text-dars-muted">Loading…</p>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
            <StatCard label="Schools" value={counts.schools} href="/dashboard/schools" />
            <StatCard label="Teachers" value={counts.teachers} />
            <StatCard label="Classes (CSTs)" value={counts.csts} />
            <StatCard
              label="Published syllabus breakdowns"
              value={counts.breakdownsPublished}
              href="/dashboard/syllabus-breakdowns"
            />
            <StatCard
              label="Draft syllabus breakdowns"
              value={counts.breakdownsDraft}
              href="/dashboard/syllabus-breakdowns"
            />
          </div>

          <section className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4">
            <h2 className="text-sm font-semibold text-dars-ink mb-2">Suggested next steps</h2>
            <ul className="text-sm text-dars-ink-soft space-y-1 list-disc list-inside">
              {counts.schools === 0 ? (
                <li>
                  <Link className="underline" href="/dashboard/schools">Add your first school</Link>.
                </li>
              ) : null}
              {counts.teachers === 0 ? (
                <li>
                  Add teachers under <Link className="underline" href="/dashboard/schools">Schools → Teachers</Link>.
                </li>
              ) : null}
              {counts.breakdownsDraft > 0 ? (
                <li>
                  You have {counts.breakdownsDraft} draft syllabus breakdown{counts.breakdownsDraft === 1 ? "" : "s"} —{" "}
                  <Link className="underline" href="/dashboard/syllabus-breakdowns">review and publish</Link>.
                </li>
              ) : null}
              <li>
                <Link className="underline" href="/dashboard/generations">Generation status</Link> —
                see in-flight LP/Exam batches.
              </li>
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, href }: { label: string; value: number; href?: string }) {
  const body = (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4">
      <p className="text-xs uppercase tracking-wide text-dars-muted font-semibold">{label}</p>
      <p className="text-2xl font-bold text-dars-ink mt-1 font-[var(--font-cormorant)]">{value}</p>
    </div>
  );
  return href ? (
    <Link href={href} className="block hover:opacity-90">
      {body}
    </Link>
  ) : body;
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4 mb-4">
      <p className="text-sm font-semibold text-dars-ink">Couldn’t load overview.</p>
      <p className="text-xs text-dars-muted mt-1">{message}</p>
    </div>
  );
}
