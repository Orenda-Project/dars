/**
 * F4.4 — Slide-over panel.
 *
 * Right-side panel anchored over the page. Used to render LP/exam HTML
 * without taking the user away from the today/class view.
 *
 * No internal state — parent controls `open`. Closes on backdrop click
 * or Escape.
 */
"use client";

import { useEffect } from "react";

interface SlideOverProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export function SlideOver({ open, onClose, title, subtitle, children }: SlideOverProps) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <div
      className={
        "fixed inset-0 z-40 transition-opacity " +
        (open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0")
      }
      aria-hidden={!open}
    >
      {/* backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />

      {/* panel */}
      <aside
        className={
          "absolute top-0 right-0 h-full w-full sm:w-[640px] bg-dars-parchment shadow-2xl flex flex-col transition-transform " +
          (open ? "translate-x-0" : "translate-x-full")
        }
        role="dialog"
        aria-modal="true"
      >
        <header className="flex items-start justify-between gap-4 border-b border-dars-rule-light px-5 py-4">
          <div>
            <h2 className="font-[var(--font-cormorant)] text-2xl font-bold text-dars-ink">
              {title}
            </h2>
            {subtitle ? (
              <p className="text-xs text-dars-muted mt-0.5">{subtitle}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-dars-muted hover:text-dars-ink text-sm px-2 py-1 rounded hover:bg-dars-parchment-deep transition-colors"
            aria-label="Close"
          >
            ✕
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </aside>
    </div>
  );
}
