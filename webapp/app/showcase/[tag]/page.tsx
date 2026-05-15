import { promises as fs } from "fs";
import path from "path";

import {
  ShowcaseTemplate,
  type ShowcaseEntry,
  type ReviewPayload,
} from "@/components/templates/showcase-template";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ tag: string }>;
  searchParams: Promise<{ lp?: string | string[] }>;
};

type LoadResult = {
  entries: ShowcaseEntry[];
  generatedAt: string | null;
};

async function loadReview(
  dir: string,
  reviewFile: string | undefined,
): Promise<ReviewPayload | null> {
  if (!reviewFile) return null;
  const reviewPath = path.join(dir, reviewFile);
  try {
    const raw = await fs.readFile(reviewPath, "utf-8");
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      return parsed as ReviewPayload;
    }
    return null;
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === "ENOENT") return null;
    return null;
  }
}

async function loadShowcase(tag: string): Promise<LoadResult | null> {
  const dir = path.join(process.cwd(), "public", "showcase", tag);
  const indexPath = path.join(dir, "index.json");
  // Reviews are gated behind an env flag so we can dark-launch the feature without
  // touching the on-disk JSONs. When off, force every entry to MISSING so the
  // drawer's existing null-render path takes over and no "AI Review" UI is emitted.
  const reviewsEnabled = process.env.NEXT_PUBLIC_SHOWCASE_REVIEWS === "true";
  try {
    const [raw, stat] = await Promise.all([
      fs.readFile(indexPath, "utf-8"),
      fs.stat(indexPath),
    ]);
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;

    const entries = await Promise.all(
      (parsed as ShowcaseEntry[]).map(async (e) => {
        if (!reviewsEnabled) {
          return { ...e, review_status: "MISSING" as const, review: null };
        }
        const review =
          e.review_status === "OK"
            ? await loadReview(dir, e.review_file)
            : null;
        return { ...e, review };
      }),
    );

    const generatedAt = stat.mtime.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
    return { entries, generatedAt };
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === "ENOENT") return null;
    throw err;
  }
}

function parseLpId(raw: string | string[] | undefined): number | null {
  if (raw === undefined) return null;
  const v = Array.isArray(raw) ? raw[0] : raw;
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) ? n : null;
}

export default async function ShowcasePage({ params, searchParams }: PageProps) {
  const { tag } = await params;
  const { lp } = await searchParams;
  const loaded = await loadShowcase(tag);

  if (loaded === null) {
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

  return (
    <ShowcaseTemplate
      tag={tag}
      entries={loaded.entries}
      generatedAt={loaded.generatedAt}
      initialLpId={parseLpId(lp)}
    />
  );
}
