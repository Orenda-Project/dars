/**
 * F4.5 — /teacher-app/classes
 *
 * Resolves the teacher (`org.default_teacher_id`), pulls their CSTs,
 * and enriches each row with school + grade + subject labels.
 *
 * The class-detail target route (/teacher-app/classes/[cst_id]) ships
 * with F4.6+; the link is wired now so as soon as that page lands the
 * navigation works end-to-end.
 */
"use client";

import { useCallback, useEffect, useState } from "react";

import { ClassesTemplate, type ClassListItem } from "@/components/templates/classes-template";
import {
  DarsApiError,
  curriculum as curriculumApi,
  tenancy as tenancyApi,
  type CST,
  type Grade,
  type SchoolClass,
  type Subject,
} from "@/lib/dars-api";

export default function ClassesPage() {
  const [items, setItems] = useState<ClassListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const org = await tenancyApi.getMyOrg();
      const teacherId = org.default_teacher_id;
      if (!teacherId) {
        setError("This org has no default teacher set — wire one in the dashboard.");
        setItems([]);
        return;
      }
      const [{ items: csts }, { items: grades }, { items: subjects }, { items: classes }, { items: schools }] = await Promise.all([
        tenancyApi.getCSTs({ teacher_id: teacherId }),
        curriculumApi.getGrades(),
        curriculumApi.getSubjects(),
        tenancyApi.getClasses(),
        tenancyApi.getSchools(),
      ]);

      const gradeById = new Map<string, Grade>(grades.map((g) => [g.id, g]));
      const subjectById = new Map<string, Subject>(subjects.map((s) => [s.id, s]));
      const classById = new Map<string, SchoolClass>(classes.map((c) => [c.id, c]));
      const schoolById = new Map(schools.map((s) => [s.id, s]));

      // CST → school_class → (grade, school). CST itself only carries
      // school_class_id + subject_id; everything else is joined.
      setItems(
        csts.map((cst: CST) => {
          const klass = classById.get(cst.school_class_id);
          const grade = klass ? gradeById.get(klass.grade_id) : undefined;
          const school = klass ? schoolById.get(klass.school_id) : undefined;
          const subject = subjectById.get(cst.subject_id);
          return {
            cst_id: cst.id,
            className: klass?.name ?? `Class ${cst.school_class_id.slice(0, 8)}`,
            subjectCode: subject?.code ?? "—",
            gradeCode: grade?.code != null ? String(grade.code) : "—",
            schoolName: school?.name ?? "—",
          } satisfies ClassListItem;
        }),
      );
    } catch (err) {
      setError(
        err instanceof DarsApiError
          ? `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`
          : err instanceof Error
          ? err.message
          : "Failed to load classes",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return <ClassesTemplate items={items} loading={loading} error={error} />;
}
