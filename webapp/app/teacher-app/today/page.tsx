"use client";

import { useState, useEffect } from "react";
import {
  getToday,
  markTaught,
  type TodaySlotEntry,
  type ClassLessonSlotRead,
} from "@/lib/school-api";
import { getMockLP } from "@/lib/teacher-app-mocks";

// ---------------------------------------------------------------------------
// LP slide-over
// ---------------------------------------------------------------------------

function LPSlideOver({
  lpId,
  subject,
  onClose,
}: {
  lpId: string;
  subject: string;
  onClose: () => void;
}) {
  const lp = getMockLP(lpId, subject);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white h-full shadow-xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900 text-sm">Lesson Plan</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors bg-transparent border-none cursor-pointer p-1"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          {lp.content && (
            <div
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: lp.content }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Slot card
// ---------------------------------------------------------------------------

function SlotBadge({ slot }: { slot: ClassLessonSlotRead }) {
  return (
    <div className="text-xs text-gray-500">
      <span className="font-medium">Day {slot.day_number}</span>
      {" · "}
      <span>{slot.lp_type}</span>
      {" · "}
      <span className="truncate">{slot.title}</span>
    </div>
  );
}

function TodayCard({ entry, onTaught }: { entry: TodaySlotEntry; onTaught: (slotId: string) => void }) {
  const [marking, setMarking] = useState(false);
  const [viewLpId, setViewLpId] = useState<string | null>(null);
  const slot = entry.next_planned_slot;

  async function handleMarkTaught() {
    if (!slot) return;
    setMarking(true);
    try {
      await markTaught(slot.id);
      onTaught(slot.id);
    } catch {
      // silent
    } finally {
      setMarking(false);
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Class header */}
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900 text-sm">{entry.class_name}</h3>
          <p className="text-xs text-gray-500 mt-0.5">{entry.subject}</p>
        </div>
        {entry.teacher_name && (
          <span className="text-xs text-gray-400">{entry.teacher_name}</span>
        )}
      </div>

      <div className="px-5 py-4 space-y-3">
        {/* Previous slot */}
        {entry.previous_taught_slot ? (
          <div className="opacity-50">
            <p className="text-[10px] uppercase tracking-widest text-gray-400 mb-1">Previously taught</p>
            <SlotBadge slot={entry.previous_taught_slot} />
          </div>
        ) : (
          <p className="text-xs text-gray-300 italic">No previous lessons</p>
        )}

        {/* Current/next slot */}
        {slot ? (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <p className="text-[10px] uppercase tracking-widest text-amber-600 mb-2 font-semibold">Up next</p>
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{slot.title}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded font-medium">{slot.lp_type}</span>
                  <span className="text-xs text-gray-400">Day {slot.day_number}</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-3">
              {slot.lesson_plan_id && (
                <button
                  onClick={() => setViewLpId(slot.lesson_plan_id)}
                  className="text-xs px-3 py-1.5 border border-amber-300 text-amber-700 rounded-md hover:bg-amber-100 transition-colors bg-transparent cursor-pointer font-medium"
                >
                  View LP
                </button>
              )}
              <button
                onClick={handleMarkTaught}
                disabled={marking}
                className="text-xs px-3 py-1.5 bg-amber-600 text-white rounded-md hover:bg-amber-700 transition-colors cursor-pointer font-medium border-none disabled:opacity-50"
              >
                {marking ? "Marking…" : "Mark as Taught"}
              </button>
            </div>
          </div>
        ) : (
          <div className="text-center py-4">
            <p className="text-xs text-gray-400">No planned lessons remaining</p>
          </div>
        )}
      </div>

      {viewLpId && (
        <LPSlideOver lpId={viewLpId} subject={entry.subject} onClose={() => setViewLpId(null)} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TodayPage() {
  const [entries, setEntries] = useState<TodaySlotEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getToday()
      .then(setEntries)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  function handleTaught(slotId: string) {
    // Refetch today's schedule after marking taught
    getToday()
      .then(setEntries)
      .catch(() => {
        // If refetch fails, optimistically remove the slot
        setEntries((prev) =>
          prev.map((e) =>
            e.next_planned_slot?.id === slotId
              ? { ...e, previous_taught_slot: e.next_planned_slot, next_planned_slot: null }
              : e
          )
        );
      });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-sm text-gray-400 animate-pulse">Loading today&apos;s schedule…</p>
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

  if (entries.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="text-4xl mb-3">📅</div>
        <p className="text-gray-500 font-medium">No classes scheduled for today.</p>
        <p className="text-sm text-gray-400 mt-1">Set up your timetable in the dashboard.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Today&apos;s Classes</h1>
        <p className="text-sm text-gray-500 mt-1">
          {new Date().toLocaleDateString("en-PK", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        </p>
      </div>
      <div className="space-y-4">
        {entries.map((entry) => (
          <TodayCard key={entry.cst_id} entry={entry} onTaught={handleTaught} />
        ))}
      </div>
    </div>
  );
}
