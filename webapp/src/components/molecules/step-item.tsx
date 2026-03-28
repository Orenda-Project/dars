interface StepItemProps {
  num: string;
  title: string;
  desc: string;
  code?: string | null;
  isFirst?: boolean;
}

export function StepItem({ num, title, desc, code, isFirst = false }: StepItemProps) {
  return (
    <div
      className={`grid gap-5 py-8 border-b border-dars-rule-light ${isFirst ? "border-t border-dars-rule-light" : ""} items-start`}
      style={{ gridTemplateColumns: "40px 1fr" }}
    >
      <span className="font-serif text-2xl font-bold text-dars-terra italic mt-0.5">
        {num}
      </span>
      <div>
        <h3 className="font-serif text-lg font-bold text-dars-ink mb-2">{title}</h3>
        <p className="text-[13px] text-dars-muted leading-relaxed">{desc}</p>
        {code && (
          <pre className="mt-3.5 bg-dars-ink border border-dars-rule-dark rounded-md px-4 py-3.5 font-mono text-[11px] text-dars-muted-light leading-relaxed overflow-x-auto whitespace-pre">
            {code}
          </pre>
        )}
      </div>
    </div>
  );
}
