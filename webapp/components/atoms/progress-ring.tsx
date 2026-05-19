/**
 * ProgressRing — circular SVG progress indicator.
 *
 * A pure SVG dial with two concentric strokes (track + fill). The fill
 * stroke is animated via stroke-dashoffset so the ring "draws" itself on
 * mount and whenever `value` changes — same idea as the PenLoader stroke,
 * but tied to data instead of a keyframe.
 *
 * Tone:
 *   - 100%               → emerald (taught — celebratory)
 *   - >0% and <100%      → dars-terra (in progress — brand)
 *   - 0% (no data yet)   → dars-muted-light (cold)
 *
 * The percentage and an optional `taught/total` hint are rendered in the
 * centre using foreignObject so they participate in the page font stack.
 */

interface ProgressRingProps {
  /** Coverage fraction 0..100 (clamped). */
  value: number;
  /** Outer diameter in px. Defaults to 64. */
  size?: number;
  /** Stroke width for both track and fill. Defaults to 6. */
  strokeWidth?: number;
  /** Optional caption shown below the % (e.g. "3/5"). */
  caption?: string;
  /** Accessible label; defaults to "{value}% complete". */
  label?: string;
  /** Extra classes on the wrapper. */
  className?: string;
}

export function ProgressRing({
  value,
  size = 64,
  strokeWidth = 6,
  caption,
  label,
  className = "",
}: ProgressRingProps) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  // stroke-dasharray draws the visible portion; dashoffset hides the rest.
  const offset = circumference * (1 - pct / 100);
  const cx = size / 2;
  const cy = size / 2;

  // Colour — pick a token via inline style so the SVG stroke gets the
  // resolved CSS variable instead of a Tailwind class on the path.
  const fillColor =
    pct >= 100
      ? "var(--color-emerald-600, #059669)"
      : pct > 0
        ? "var(--color-dars-terra)"
        : "var(--color-dars-muted-light)";

  const a11yLabel = label ?? `${pct} percent complete`;

  return (
    <div
      role="img"
      aria-label={a11yLabel}
      className={`relative inline-flex shrink-0 items-center justify-center ${className}`}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-hidden="true"
        className="-rotate-90"
      >
        {/* Track */}
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="var(--color-dars-parchment-deep)"
          strokeWidth={strokeWidth}
        />
        {/* Fill — animated via stroke-dashoffset transition */}
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke={fillColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            transition:
              "stroke-dashoffset 900ms cubic-bezier(0.4, 0, 0.2, 1), stroke 250ms ease-out",
          }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none leading-none">
        <span
          className="font-serif font-bold text-dars-ink tabular-nums"
          style={{ fontSize: Math.max(11, size * 0.26) }}
        >
          {pct}
          <span
            className="text-dars-muted-light font-normal"
            style={{ fontSize: Math.max(8, size * 0.16) }}
          >
            %
          </span>
        </span>
        {caption ? (
          <span
            className="mt-0.5 font-mono text-dars-muted tabular-nums"
            style={{ fontSize: Math.max(8, size * 0.14) }}
          >
            {caption}
          </span>
        ) : null}
      </div>
    </div>
  );
}
