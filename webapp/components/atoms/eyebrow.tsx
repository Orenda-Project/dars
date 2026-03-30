import type { ReactNode } from "react";

interface EyebrowProps {
  children: ReactNode;
  className?: string;
}

export function Eyebrow({ children, className = "" }: EyebrowProps) {
  return (
    <div className={`flex items-center justify-center gap-2.5 text-[11px] font-bold tracking-[2px] text-dars-terra uppercase ${className}`}>
      <span className="inline-block w-8 h-px bg-dars-terra opacity-60" />
      {children}
      <span className="inline-block w-8 h-px bg-dars-terra opacity-60" />
    </div>
  );
}
