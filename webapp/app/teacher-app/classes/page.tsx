"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { getMyClasses, type MyClassEntry } from "@/lib/school-api";

function ProgressBar({ taught, total }: { taught: number; total: number }) {
  const pct = total > 0 ? Math.round((taught / total) * 100) : 0;
  return (
    <div className="mt-2">
      <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
        <span>{taught} lessons taught</span>
        <span>{total} total slots</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-1.5">
        <div
          className="bg-amber-500 h-1.5 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function ClassCard({ entry }: { entry: MyClassEntry }) {
  // Approximate total: chapter_count is total chapter plans, taught_count is actual taught slots
  // Use taught_count + remaining from next_slot as rough progress indicator
  const totalSlots = entry.taught_count + (entry.next_slot ? 1 : 0);

  return (
    <Link
      href={`/teacher-app/classes/${entry.cst_id}`}
      className="block bg-white border border-gray-200 rounded-xl shadow-sm p-5 hover:border-amber-300 hover:shadow-md transition-all no-underline group"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
              Grade {entry.grade}
            </span>
          </div>
          <h3 className="font-semibold text-gray-900 text-sm group-hover:text-amber-700 transition-colors">
            {entry.class_name}
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">{entry.subject}</p>
          {entry.book_title && (
            <p className="text-xs text-gray-400 mt-0.5 italic truncate">{entry.book_title}</p>
          )}
        </div>
        <div className="shrink-0">
          <span className="text-xs bg-gray-100 text-gray-600 px-2.5 py-1 rounded-full font-medium">
            {entry.chapter_count} chapter{entry.chapter_count !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      <ProgressBar taught={entry.taught_count} total={totalSlots > 0 ? totalSlots : entry.chapter_count} />

      {entry.next_slot && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p className="text-[10px] uppercase tracking-widest text-gray-400 mb-1">Next lesson</p>
          <p className="text-xs text-gray-700 truncate font-medium">{entry.next_slot.title}</p>
          <p className="text-xs text-gray-400">{entry.next_slot.lp_type} · Day {entry.next_slot.day_number}</p>
        </div>
      )}

      <div className="mt-3 flex items-center gap-1 text-xs text-amber-600 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
        View details
        <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="5" y1="12" x2="19" y2="12" />
          <polyline points="12 5 19 12 12 19" />
        </svg>
      </div>
    </Link>
  );
}

export default function MyClassesPage() {
  const [classes, setClasses] = useState<MyClassEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMyClasses()
      .then((data) => setClasses(data.items))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-sm text-gray-400 animate-pulse">Loading your classes…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (classes.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="text-4xl mb-3">🏫</div>
        <p className="text-gray-500 font-medium">No classes assigned.</p>
        <p className="text-sm text-gray-400 mt-1">
          Set up your school structure in the{" "}
          <Link href="/dashboard/curriculum-demo" className="text-amber-600 underline">
            dashboard
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">My Classes</h1>
        <p className="text-sm text-gray-500 mt-1">{classes.length} class{classes.length !== 1 ? "es" : ""} assigned</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {classes.map((c) => (
          <ClassCard key={c.cst_id} entry={c} />
        ))}
      </div>
    </div>
  );
}
