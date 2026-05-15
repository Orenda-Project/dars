"use client";

import { useState } from "react";

export type ShowcaseEntry = {
  id: number;
  grade: number;
  skill: string;
  page: string;
  topic: string;
  status: "OK" | "ERROR";
  html_file: string;
  error?: string;
};

type Props = {
  tag: string;
  entries: ShowcaseEntry[];
};

export function ShowcaseTemplate({ tag, entries }: Props) {
  const firstOk = entries.find((e) => e.status === "OK") ?? entries[0];
  const [selectedId, setSelectedId] = useState<number | null>(firstOk?.id ?? null);

  if (!entries.length) {
    return (
      <main className="min-h-screen bg-dars-parchment text-dars-ink flex items-center justify-center p-10">
        <div className="max-w-md text-center">
          <p className="font-serif text-2xl mb-3">Showcase is empty</p>
          <p className="text-sm text-dars-muted">
            No lesson plans have been generated yet for{" "}
            <code className="text-dars-terra">{tag}</code>.
          </p>
        </div>
      </main>
    );
  }

  const selected = entries.find((e) => e.id === selectedId) ?? entries[0];

  return (
    <main className="min-h-screen bg-dars-parchment text-dars-ink flex flex-col">
      <header className="border-b border-dars-rule-light px-6 py-4 bg-dars-parchment-mid">
        <div className="max-w-7xl mx-auto flex items-baseline justify-between gap-4 flex-wrap">
          <div>
            <span className="block text-[11px] font-bold tracking-[2px] uppercase text-dars-terra">
              Lesson Plan Showcase
            </span>
            <h1 className="font-serif text-2xl mt-1 tracking-[-0.3px]">
              10 sample lesson plans
            </h1>
          </div>
          <span className="text-xs text-dars-muted">
            tag: <code>{tag}</code>
          </span>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-0 max-w-7xl mx-auto w-full">
        <aside className="border-r border-dars-rule-light bg-dars-parchment-mid">
          <ul className="divide-y divide-dars-rule-light">
            {entries.map((e) => {
              const active = e.id === selected.id;
              return (
                <li key={e.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(e.id)}
                    className={
                      "w-full text-left px-5 py-4 transition-colors " +
                      (active
                        ? "bg-dars-parchment border-l-2 border-dars-terra"
                        : "hover:bg-dars-parchment border-l-2 border-transparent")
                    }
                  >
                    <div className="flex items-baseline justify-between gap-2 mb-1">
                      <span className="font-serif text-xs text-dars-terra italic">
                        {String(e.id).padStart(2, "0")}.
                      </span>
                      <StatusBadge status={e.status} />
                    </div>
                    <div className="text-sm font-semibold tracking-[-0.2px]">
                      Grade {e.grade} — {e.skill}
                    </div>
                    <div className="text-xs text-dars-muted mt-0.5">
                      Page {e.page}
                      {e.topic ? ` · ${e.topic}` : ""}
                    </div>
                    {e.status === "ERROR" && e.error ? (
                      <div className="text-[11px] text-dars-terra mt-1 line-clamp-2">
                        {e.error}
                      </div>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>

        <section className="bg-dars-parchment flex flex-col">
          <div className="px-6 py-3 border-b border-dars-rule-light flex items-baseline justify-between gap-4">
            <div>
              <div className="text-[11px] font-bold tracking-[2px] uppercase text-dars-muted">
                Grade {selected.grade} · {selected.skill}
              </div>
              <div className="font-serif text-lg tracking-[-0.2px]">
                Page {selected.page}
                {selected.topic ? ` — ${selected.topic}` : ""}
              </div>
            </div>
            <StatusBadge status={selected.status} />
          </div>
          <div className="flex-1 min-h-[70vh]">
            {selected.status === "OK" ? (
              <iframe
                key={selected.id}
                src={`/showcase/${tag}/${selected.html_file}`}
                title={`Lesson plan ${selected.id}`}
                className="w-full h-full min-h-[70vh] border-0 bg-white"
              />
            ) : (
              <div className="p-10">
                <p className="font-serif text-xl mb-2">This lesson plan failed to generate</p>
                <p className="text-sm text-dars-muted mb-4">
                  Grade {selected.grade}, {selected.skill}, page {selected.page}.
                </p>
                <pre className="bg-dars-parchment-mid border border-dars-rule-light rounded-md p-4 text-xs text-dars-ink whitespace-pre-wrap break-words max-w-2xl">
                  {selected.error ?? "Unknown error"}
                </pre>
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function StatusBadge({ status }: { status: "OK" | "ERROR" }) {
  if (status === "OK") {
    return (
      <span className="text-[10px] font-bold tracking-[1.5px] uppercase text-dars-terra">
        Ready
      </span>
    );
  }
  return (
    <span className="text-[10px] font-bold tracking-[1.5px] uppercase text-dars-terra bg-dars-terra/10 px-2 py-0.5 rounded">
      Error
    </span>
  );
}
