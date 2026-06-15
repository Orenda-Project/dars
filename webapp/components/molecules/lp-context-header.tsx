/**
 * lp-context-header F-2.2 / D-2, D-6 — the one shared way an LP's identity is
 * shown: which chapter, which topic, what kind of lesson.
 *
 * Hierarchy (D-2): topic title is the headline, the chapter is a small eyebrow
 * above it, and the LP type is a colored badge (the part that used to be a
 * "very subtle 'reading'"). The raw `lp_type` is always run through
 * `lpTypeLabel()` (D-3) — never rendered raw.
 *
 * Two layouts (D-6):
 *   - "default"  — stacked; for cards and the LP slide-over.
 *   - "compact"  — one line; for dense timeline / syllabus rows.
 *
 * Presentational only (molecule layer rules): props + atoms/ui, no hooks, no
 * data fetching. Styling via Dars tokens.
 */
import { lpTypeLabel } from "@/lib/lp-type-label";

export interface LpContextHeaderProps {
  chapterNumber?: number | null;
  chapterTitle?: string | null;
  topicTitle?: string | null;
  lpType?: string | null;
  variant?: "default" | "compact";
  className?: string;
}

function LpTypeBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-dars-terra px-2 py-0.5 text-[11px] font-semibold text-dars-parchment whitespace-nowrap">
      {label}
    </span>
  );
}

/** "CH 3 · School Time" — omitted entirely when there's no chapter. */
function chapterEyebrow(
  chapterNumber?: number | null,
  chapterTitle?: string | null,
): string | null {
  const parts: string[] = [];
  if (chapterNumber != null) parts.push(`CH ${chapterNumber}`);
  if (chapterTitle) parts.push(chapterTitle);
  return parts.length ? parts.join(" · ") : null;
}

export function LpContextHeader({
  chapterNumber,
  chapterTitle,
  topicTitle,
  lpType,
  variant = "default",
  className = "",
}: LpContextHeaderProps) {
  const eyebrow = chapterEyebrow(chapterNumber, chapterTitle);
  const typeLabel = lpTypeLabel(lpType);
  // Topic is the anchor; fall back to a neutral word so the headline is never
  // empty (a slot may have no topic yet).
  const topic = topicTitle?.trim() || "Lesson";

  if (variant === "compact") {
    return (
      <div
        className={`flex items-center gap-2 min-w-0 ${className}`.trim()}
      >
        {eyebrow ? (
          <span className="text-[11px] text-dars-muted-light whitespace-nowrap shrink-0">
            {eyebrow}
          </span>
        ) : null}
        {eyebrow ? (
          <span className="text-dars-muted-light shrink-0" aria-hidden>
            ›
          </span>
        ) : null}
        <span className="text-xs font-semibold text-dars-ink truncate min-w-0">
          {topic}
        </span>
        {typeLabel ? <LpTypeBadge label={typeLabel} /> : null}
      </div>
    );
  }

  return (
    <div className={`flex items-start justify-between gap-3 ${className}`.trim()}>
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-[10px] uppercase tracking-wide text-dars-muted font-semibold">
            {eyebrow}
          </p>
        ) : null}
        <p className="text-sm font-semibold text-dars-ink mt-0.5 break-words">
          {topic}
        </p>
      </div>
      {typeLabel ? (
        <div className="shrink-0 pt-0.5">
          <LpTypeBadge label={typeLabel} />
        </div>
      ) : null}
    </div>
  );
}
