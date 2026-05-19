/**
 * F4.9 — Book tab template.
 *
 * Sidebar of chapters; main area shows the selected chapter's topics
 * with coverage markers and per-topic sub-SLO chips. chapter_text
 * rendering is deferred — it's a structured list[dict] OCR slice and
 * rendering it well needs design work beyond what F4.9 specifies.
 *
 * Per-topic sub-SLOs are lazy: the parent page fetches `getTopicSubSLOs`
 * only when a topic row is expanded, caching results by topic_id so a
 * second expansion is instant. Avoids an N+1 storm on tab mount when a
 * chapter has ~30 topics.
 */
"use client";

import type { BookChapter, SubSLO, Topic } from "@/lib/dars-api";

export interface BookTabChapter {
  chapter: BookChapter;
  topics: BookTabTopic[];
}

export interface BookTabTopic {
  topic: Topic;
  /** % of sub-SLOs marked taught — null when no sub-SLOs are linked. */
  coverage: number | null;
}

export type TopicSubSLOState =
  | { state: "loading" }
  | { state: "loaded"; items: SubSLO[] }
  | { state: "error"; error: string };

interface BookTabProps {
  chapters: BookTabChapter[];
  selectedChapterId: string | null;
  onSelectChapter: (chapter_id: string) => void;
  expandedTopicId: string | null;
  onToggleTopic: (topic_id: string) => void;
  /** Cache keyed by topic_id. Missing key = not yet expanded. */
  topicSubSLOs: Record<string, TopicSubSLOState>;
}

export function ClassBookTab({
  chapters,
  selectedChapterId,
  onSelectChapter,
  expandedTopicId,
  onToggleTopic,
  topicSubSLOs,
}: BookTabProps) {
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
            selected.topics.map((t) => (
              <TopicRow
                key={t.topic.id}
                entry={t}
                expanded={expandedTopicId === t.topic.id}
                onToggle={() => onToggleTopic(t.topic.id)}
                subSLOState={topicSubSLOs[t.topic.id]}
              />
            ))
          )}
        </ul>
      </section>
    </div>
  );
}

function TopicRow({
  entry,
  expanded,
  onToggle,
  subSLOState,
}: {
  entry: BookTabTopic;
  expanded: boolean;
  onToggle: () => void;
  subSLOState: TopicSubSLOState | undefined;
}) {
  return (
    <li className="rounded-md border border-dars-rule-light bg-dars-parchment-mid overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="w-full text-left p-3 hover:bg-dars-parchment-deep/40 transition-colors flex items-center gap-2"
      >
        <span className="font-mono text-xs text-dars-muted">
          {entry.topic.topic_number}
        </span>
        <span className="text-sm text-dars-ink">{entry.topic.title}</span>
        <CoveragePill coverage={entry.coverage} />
        <span className="text-dars-muted text-xs ml-1" aria-hidden>
          {expanded ? "▾" : "▸"}
        </span>
      </button>
      {entry.topic.topic_text ? (
        <p className="px-3 pb-2 text-xs text-dars-muted-light line-clamp-2 whitespace-pre-line">
          {entry.topic.topic_text}
        </p>
      ) : null}
      {expanded ? (
        <div className="border-t border-dars-rule-light bg-dars-parchment p-3">
          <SubSLOSection state={subSLOState} />
        </div>
      ) : null}
    </li>
  );
}

function SubSLOSection({ state }: { state: TopicSubSLOState | undefined }) {
  if (!state || state.state === "loading") {
    return <p className="text-xs text-dars-muted italic">Loading sub-SLOs…</p>;
  }
  if (state.state === "error") {
    return (
      <p className="text-xs text-dars-muted-light">
        Couldn’t load sub-SLOs ({state.error}).
      </p>
    );
  }
  if (state.items.length === 0) {
    return (
      <p className="text-xs text-dars-muted-light italic">
        No sub-SLOs mapped to this topic.
      </p>
    );
  }
  return <SubSLOChipList items={state.items} />;
}

function SubSLOChipList({ items }: { items: SubSLO[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((s) => (
        <SubSLOChip key={s.id} subSlo={s} />
      ))}
    </ul>
  );
}

function SubSLOChip({ subSlo }: { subSlo: SubSLO }) {
  // Native <details> keeps this leaf widget state-free; group-open:*
  // variants swap the truncated chip text for the full statement.
  return (
    <li>
      <details className="group">
        <summary
          className="cursor-pointer list-none flex items-start gap-2 text-xs px-2 py-1 rounded bg-dars-parchment-mid border border-dars-rule-light hover:bg-dars-parchment-deep transition-colors"
          aria-label={`Sub-SLO ${subSlo.code}`}
        >
          <span className="font-mono text-dars-ink font-semibold whitespace-nowrap">
            {subSlo.code}
          </span>
          <span className="text-dars-ink-soft flex-1 line-clamp-1 group-open:line-clamp-none group-open:whitespace-pre-line">
            {subSlo.statement}
          </span>
          <span className="text-dars-muted pl-1 shrink-0" aria-hidden>
            <span className="group-open:hidden">▸</span>
            <span className="hidden group-open:inline">▾</span>
          </span>
        </summary>
      </details>
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
