/**
 * F4.12 — /teacher-app/onboarding/[cst_id]
 *
 * Wizard for setting current_sequence_position. Calls POST
 * /api/v2/csts/{id}/onboard with chapter_position + chapter_day.
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import {
  OnboardingTemplate,
  type OnboardingChapterOption,
} from "@/components/templates/onboarding-template";
import {
  DarsApiError,
  books as booksApi,
  breakdowns as breakdownsApi,
  curriculum as curriculumApi,
  onboarding as onboardingApi,
  tenancy as tenancyApi,
} from "@/lib/dars-api";

export default function OnboardingPage() {
  const params = useParams<{ cst_id: string }>();
  const cstId = params.cst_id;
  const router = useRouter();

  const [className, setClassName] = useState("");
  const [chapters, setChapters] = useState<OnboardingChapterOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const cst = await tenancyApi.getCST(cstId);
      const [{ items: classes }, breakdown] = await Promise.all([
        tenancyApi.getClasses(),
        breakdownsApi.getMyClassBreakdown(cstId),
      ]);
      const klass = classes.find((c) => c.id === cst.school_class_id);
      setClassName(klass?.name ?? `Class ${cst.school_class_id.slice(0, 8)}`);

      if (!breakdown) {
        setChapters([]);
        return;
      }
      const hydrated = await breakdownsApi.getBreakdown(breakdown.id);
      // book_chapter title lookup
      let titleByChapterId = new Map<string, string>();
      if (hydrated.book_id) {
        const { items: bookChapters } = await booksApi.getBookChapters(hydrated.book_id);
        titleByChapterId = new Map(bookChapters.map((bc) => [bc.id, bc.title]));
      }
      void curriculumApi; // (kept import for symmetry with other pages)

      const options: OnboardingChapterOption[] = [...hydrated.chapters]
        .sort((a, b) => a.position - b.position)
        .map((c) => ({
          position: c.position,
          title: titleByChapterId.get(c.book_chapter_id) ?? `Chapter ${c.position}`,
          teaching_days: c.teaching_days,
        }));
      setChapters(options);
    } catch (err) {
      setError(
        err instanceof DarsApiError
          ? `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`
          : err instanceof Error
          ? err.message
          : "Failed to load",
      );
    } finally {
      setLoading(false);
    }
  }, [cstId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSubmit(payload: {
    chapter_position: number;
    chapter_day: number;
  }) {
    await onboardingApi.onboardCST(cstId, payload);
    router.replace("/teacher-app/today");
  }

  return (
    <OnboardingTemplate
      className={className}
      chapters={chapters}
      onSubmit={handleSubmit}
      loading={loading}
      error={error}
    />
  );
}
