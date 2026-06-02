/**
 * F4.6..F4.10 — Class detail shell.
 *
 * Top-level layout: class header + tab bar. Tab content is a slot the
 * page fills with the right tab template based on the URL ?tab= param.
 */
"use client";

import Link from "next/link";

export type ClassDetailTab =
  | "today"
  | "syllabus"
  | "timeline"
  | "timetable"
  | "book"
  | "slos";

interface ClassDetailHeaderProps {
  className: string;
  subjectCode: string;
  gradeCode: string;
  schoolName: string;
}

interface ClassDetailTemplateProps extends ClassDetailHeaderProps {
  cstId: string;
  activeTab: ClassDetailTab;
  children: React.ReactNode;
}

const TABS: { key: ClassDetailTab; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "syllabus", label: "Syllabus" },
  { key: "timeline", label: "Timeline" },
  { key: "timetable", label: "Timetable" },
  { key: "book", label: "Book" },
  { key: "slos", label: "SLO Progress" },
];

export function ClassDetailTemplate(props: ClassDetailTemplateProps) {
  const { cstId, activeTab, className, subjectCode, gradeCode, schoolName, children } = props;
  return (
    <div>
      <div className="mb-2 text-xs text-dars-muted">
        <Link href="/teacher-app/classes" className="hover:text-dars-terra">
          ← All classes
        </Link>
      </div>

      <header className="mb-5">
        <p className="text-xs uppercase tracking-wide text-dars-muted font-semibold">
          {schoolName}
        </p>
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mt-1">
          {className}
        </h1>
        <p className="text-sm text-dars-ink-soft mt-1">
          {subjectCode} · Grade {gradeCode.replace(/^G/, "")}
        </p>
      </header>

      <nav className="border-b border-dars-rule-light mb-5 flex gap-1 overflow-x-auto">
        {TABS.map((tab) => (
          <Link
            key={tab.key}
            href={`/teacher-app/classes/${cstId}?tab=${tab.key}`}
            scroll={false}
            className={
              "px-3 py-2 text-sm border-b-2 -mb-px transition-colors whitespace-nowrap " +
              (activeTab === tab.key
                ? "border-dars-terra text-dars-terra font-semibold"
                : "border-transparent text-dars-muted hover:text-dars-ink")
            }
          >
            {tab.label}
          </Link>
        ))}
      </nav>

      {children}
    </div>
  );
}

interface LoadingProps {
  label?: string;
}
export function TabLoading({ label = "Loading…" }: LoadingProps) {
  return <p className="text-sm text-dars-muted">{label}</p>;
}

export function TabError({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4">
      <p className="text-sm font-semibold text-dars-ink">Something went wrong</p>
      <p className="text-xs text-dars-muted mt-1">{message}</p>
    </div>
  );
}

export function TabEmpty({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
      <p className="text-sm font-medium text-dars-ink">{title}</p>
      <p className="text-xs text-dars-muted mt-1">{body}</p>
    </div>
  );
}
