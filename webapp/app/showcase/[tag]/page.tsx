import { promises as fs } from "fs";
import path from "path";

import {
  ShowcaseTemplate,
  type ShowcaseEntry,
} from "@/components/templates/showcase-template";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ tag: string }>;
};

async function loadEntries(tag: string): Promise<ShowcaseEntry[] | null> {
  const indexPath = path.join(
    process.cwd(),
    "public",
    "showcase",
    tag,
    "index.json",
  );
  try {
    const raw = await fs.readFile(indexPath, "utf-8");
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    return parsed as ShowcaseEntry[];
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === "ENOENT") return null;
    throw err;
  }
}

export default async function ShowcasePage({ params }: PageProps) {
  const { tag } = await params;
  const entries = await loadEntries(tag);

  if (entries === null) {
    return (
      <main className="min-h-screen bg-dars-parchment text-dars-ink flex items-center justify-center p-10">
        <div className="max-w-md text-center">
          <span className="block text-[11px] font-bold tracking-[2px] uppercase text-dars-terra mb-3">
            Not Found
          </span>
          <p className="font-serif text-2xl mb-3">Showcase not found</p>
          <p className="text-sm text-dars-muted">
            No showcase has been generated for{" "}
            <code className="text-dars-terra">{tag}</code> yet. Run{" "}
            <code className="text-dars-terra">
              python3 useful-scripts/generate_showcase_lps.py --tag {tag}
            </code>{" "}
            to populate it.
          </p>
        </div>
      </main>
    );
  }

  return <ShowcaseTemplate tag={tag} entries={entries} />;
}
