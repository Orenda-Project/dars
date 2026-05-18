/**
 * F4.9 — Book tab template.
 *
 * Sidebar of chapters; main area shows the selected chapter's topics
 * with coverage markers. chapter_text rendering is deferred — it's a
 * structured list[dict] OCR slice and rendering it well needs design
 * work beyond what F4.9 specifies. We surface chapter + topic titles +
 * sub-SLO coverage state, which is the v1 acceptance bar.
 */
"use client";

import type { BookChapter, Topic } from "@/lib/dars-api";

export interface BookTabChapter {
  chapter: BookChapter;
  topics: BookTabTopic[];
}

export interface BookTabTopic {
  topic: Topic;
  /** % of sub-SLOs marked taught — null when no sub-SLOs are linked. */
  coverage: number | null;
}

interface BookTabProps {
  chapters: BookTabChapter[];
  selectedChapterId: string | null;
  onSelectChapter: (chapter_id: string) => void;
}

export function ClassBookTab({ chapters, selectedChapterId, onSelectChapter }: BookTabProps) {
  if (chapters.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
        <p className="text-sm font-medium text-dars-ink">No book linked</p>
        <p className="text-xs text-dars-muted mt-1">
          A book hasn’t been wired to this class’s breakdown yet.
        </p>
      </div>
    );
  }

  const selected =
    chapters.find((c) => c.chapter.id === selectedChapterId) ?? chapters[0];

  return (
    <div className="grid sm:grid-cols-[180px_1fr] gap-4">
      <aside className="space-y-1">
        {chapters.map((c) => (
          <button
            key={c.chapter.id}
            type="button"
            onClick={() => onSelectChapter(c.chapter.id)}
            className={
              "w-full text-left px-3 py-2 rounded text-xs font-medium border transition-colors " +
              (selected.chapter.id === c.chapter.id
                ? "bg-dars-terra/10 border-dars-terra/40 text-dars-ink"
                : "bg-dars-parchment-mid border-dars-rule-light text-dars-ink-soft hover:bg-dars-parchment-deep")
            }
          >
            <span className="font-mono text-dars-muted mr-2">{c.chapter.chapter_number}</span>
            {c.chapter.title}
          </button>
        ))}
      </aside>

      <section>
        <h3 className="font-[var(--font-cormorant)] text-2xl font-bold text-dars-ink mb-3">
          {selected.chapter.title}
        </h3>
        <ul className="space-y-2">
          {selected.topics.length === 0 ? (
            <li className="text-xs text-dars-muted">No topics in this chapter.</li>
          ) : (
            selected.topics.map((t) => <TopicRow key={t.topic.id} entry={t} />)
          )}
        </ul>
      </section>
    </div>
  );
}

function TopicRow({ entry }: { entry: BookTabTopic }) {
  return (
    <li className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3">
      <div className="flex items-center gap-2 mb-1">
        <span className="font-mono text-xs text-dars-muted">
          {entry.topic.topic_number}
        </span>
        <span className="text-sm text-dars-ink">{entry.topic.title}</span>
        <CoveragePill coverage={entry.coverage} />
      </div>
      {entry.topic.topic_text ? (
        <p className="text-xs text-dars-muted-light line-clamp-2 whitespace-pre-line">
          {entry.topic.topic_text}
        </p>
      ) : null}
    </li>
  );
}

function CoveragePill({ coverage }: { coverage: number | null }) {
  if (coverage === null) {
    return (
      <span className="ml-auto text-[10px] text-dars-muted-light">
        No sub-SLOs linked
      </span>
    );
  }
  const pct = Math.round(coverage);
  let cls = "bg-dars-parchment-deep text-dars-muted";
  if (pct >= 80) cls = "bg-emerald-100 text-emerald-800";
  else if (pct > 0) cls = "bg-amber-100 text-amber-800";
  return (
    <span
      className={
        "ml-auto px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide " + cls
      }
    >
      {pct}% taught
    </span>
  );
}
