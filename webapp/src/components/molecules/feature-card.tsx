import type { ComponentType } from "react";

const ruledBg = {
  backgroundImage:
    "repeating-linear-gradient(to bottom, transparent, transparent 19px, rgba(208,195,180,0.45) 19px, rgba(208,195,180,0.45) 20px)",
  backgroundSize: "100% 20px",
} as const;

interface FeatureCardProps {
  num: string;
  chapterLabel: string;
  title: string;
  desc: string;
  annotation: string;
  Illus: ComponentType<{ size?: number }>;
  hasBorderBottom?: boolean;
}

export function FeatureCard({
  num,
  chapterLabel,
  title,
  desc,
  annotation,
  Illus,
  hasBorderBottom = true,
}: FeatureCardProps) {
  return (
    <div
      className={`grid grid-cols-[52px_1fr] gap-5 py-7 ${hasBorderBottom ? "border-b border-dars-rule-light" : ""}`}
    >
      <div className="flex flex-col items-center gap-2.5 pt-0.5">
        <span className="font-serif text-xl font-bold text-dars-terra italic leading-none">
          {num}
        </span>
        <Illus size={28} />
      </div>
      <div>
        <div
          className="relative px-0 pr-0 pb-1.5 mb-2.5 rounded-sm"
          style={ruledBg}
        >
          <span className="absolute top-0.5 right-0 font-serif text-[9px] italic text-dars-terra leading-none tracking-[0.5px]" style={{ opacity: 0.45 }}>
            {chapterLabel}
          </span>
          <h3 className="font-serif text-base font-bold text-dars-ink leading-snug relative z-10">
            {title}
          </h3>
        </div>
        <p className="text-[13px] text-dars-muted leading-relaxed">{desc}</p>
        <span
          className="inline-block mt-2 font-serif text-[11px] italic text-dars-terra pb-px border-b border-dashed border-dars-terra/35"
          style={{ opacity: 0.65 }}
        >
          {annotation}
        </span>
      </div>
    </div>
  );
}
