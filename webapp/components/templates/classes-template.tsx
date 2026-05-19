/**
 * F4.5 — /teacher-app/classes template.
 *
 * Pure layout. The page resolves CST → label (school class name, grade,
 * subject) and passes a flat list of items.
 */
"use client";

import Link from "next/link";

export interface ClassListItem {
  cst_id: string;
  className: string;       // "Grade 1 — A"
  subjectCode: string;     // "Eng"
  gradeCode: string;       // "G1"
  schoolName: string;
}

interface ClassesTemplateProps {
  items: ClassListItem[];
  loading: boolean;
  error: string | null;
}

export function ClassesTemplate({ items, loading, error }: ClassesTemplateProps) {
  if (loading && items.length === 0) {
    return <div className="text-sm text-dars-muted">Loading classes…</div>;
  }
  if (error) {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4">
        <p className="text-sm font-semibold text-dars-ink">Couldn’t load classes.</p>
        <p className="text-xs text-dars-muted mt-1">{error}</p>
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
        <p className="text-sm font-medium text-dars-ink">No classes assigned</p>
        <p className="text-xs text-dars-muted mt-1">
          Add a class above, or reach out to your administrator.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-5">
        My classes
      </h1>
      <ul className="grid gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <li key={item.cst_id}>
            <ClassCard item={item} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function ClassCard({ item }: { item: ClassListItem }) {
  return (
    <Link
      href={`/teacher-app/classes/${item.cst_id}`}
      className="block rounded-lg border border-dars-rule-light bg-dars-parchment-mid hover:bg-dars-parchment-deep transition-colors p-4"
    >
      <p className="text-xs uppercase tracking-wide text-dars-muted font-semibold">
        {item.schoolName}
      </p>
      <p className="font-[var(--font-cormorant)] text-2xl font-bold text-dars-ink mt-1">
        {item.className}
      </p>
      <p className="text-sm text-dars-ink-soft mt-1">
        {item.subjectCode} · Grade {item.gradeCode.replace(/^G/, "")}
      </p>
      <p className="text-xs text-dars-terra font-medium mt-3">
        Open class →
      </p>
    </Link>
  );
}
