/**
 * F4.3 — API key setup page.
 *
 * Owns the localStorage write + redirect. Template handles UI.
 */
"use client";

import { useRouter } from "next/navigation";

import { TeacherAppSetupTemplate } from "@/components/templates/teacher-app-setup-template";
import { setApiKey } from "@/lib/dars-api";

export default function SetupPage() {
  const router = useRouter();

  async function handleSubmit(apiKey: string) {
    if (!apiKey) throw new Error("API key is required");
    setApiKey(apiKey);
    router.replace("/teacher-app/today");
  }

  return <TeacherAppSetupTemplate onSubmit={handleSubmit} />;
}
