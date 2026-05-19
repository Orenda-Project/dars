/**
 * F4.5 — /teacher-app/classes
 *
 * Resolves the teacher (`org.default_teacher_id`), pulls their CSTs,
 * and enriches each row with school + grade + subject labels.
 *
 * Teachers can self-serve a new class via the "+ Add class" panel.
 * Backend POST /classes and POST /csts both accept X-API-Key
 * (get_current_org), so no admin involvement is required.
 */
"use client";

import { useCallback, useEffect, useState } from "react";

import { ClassesTemplate, type ClassListItem } from "@/components/templates/classes-template";
import {
  DarsApiError,
  admin,
  books as booksApi,
  curriculum as curriculumApi,
  tenancy as tenancyApi,
  type AcademicYear,
  type Book,
  type CST,
  type Grade,
  type SchoolClass,
  type School,
  type Subject,
} from "@/lib/dars-api";

interface RefData {
  schools: School[];
  academicYears: AcademicYear[];
  classes: SchoolClass[];
  grades: Grade[];
  subjects: Subject[];
  books: Book[];
  teacherId: string;
  curriculumId: string;
}

export default function ClassesPage() {
  const [items, setItems] = useState<ClassListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refData, setRefData] = useState<RefData | null>(null);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const org = await tenancyApi.getMyOrg();
      const teacherId = org.default_teacher_id;
      if (!teacherId) {
        setError("No default teacher is set up yet. Reach out to your administrator.");
        setItems([]);
        return;
      }
      const [
        { items: csts },
        { items: grades },
        { items: subjects },
        { items: classes },
        { items: schools },
        { items: ays },
        { items: bks },
      ] = await Promise.all([
        tenancyApi.getCSTs({ teacher_id: teacherId }),
        curriculumApi.getGrades(),
        curriculumApi.getSubjects(),
        tenancyApi.getClasses(),
        tenancyApi.getSchools(),
        tenancyApi.getAcademicYears(),
        booksApi.getBooks({ curriculum_id: org.curriculum_id }),
      ]);

      const gradeById = new Map<string, Grade>(grades.map((g) => [g.id, g]));
      const subjectById = new Map<string, Subject>(subjects.map((s) => [s.id, s]));
      const classById = new Map<string, SchoolClass>(classes.map((c) => [c.id, c]));
      const schoolById = new Map(schools.map((s) => [s.id, s]));

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

      setRefData({
        schools,
        academicYears: ays,
        classes,
        grades,
        subjects,
        books: bks,
        teacherId,
        curriculumId: org.curriculum_id,
      });
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

  return (
    <div className="space-y-4">
      {refData ? (
        <div className="flex justify-end">
          {showForm ? null : (
            <button
              type="button"
              onClick={() => setShowForm(true)}
              className="px-3 py-1.5 rounded-md bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90"
            >
              + Add class
            </button>
          )}
        </div>
      ) : null}

      {showForm && refData ? (
        <CreateClassForm
          refData={refData}
          onCancel={() => setShowForm(false)}
          onCreated={async () => {
            setShowForm(false);
            await load();
          }}
        />
      ) : null}

      <ClassesTemplate items={items} loading={loading} error={error} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// CreateClassForm
// ---------------------------------------------------------------------------

function CreateClassForm({
  refData,
  onCancel,
  onCreated,
}: {
  refData: RefData;
  onCancel: () => void;
  onCreated: () => Promise<void>;
}) {
  // School defaults to the first one with an AY.
  const initialSchoolId = refData.schools[0]?.id ?? "";
  const [schoolId, setSchoolId] = useState(initialSchoolId);
  const aysForSchool = refData.academicYears.filter((a) => a.school_id === schoolId);
  const [academicYearId, setAcademicYearId] = useState(aysForSchool[0]?.id ?? "");
  const [gradeId, setGradeId] = useState(refData.grades[0]?.id ?? "");
  const [section, setSection] = useState("A");
  const [subjectId, setSubjectId] = useState(refData.subjects[0]?.id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-pin AY when school changes.
  useEffect(() => {
    const validAYs = refData.academicYears.filter((a) => a.school_id === schoolId);
    if (validAYs.length > 0 && !validAYs.some((a) => a.id === academicYearId)) {
      setAcademicYearId(validAYs[0].id);
    } else if (validAYs.length === 0) {
      setAcademicYearId("");
    }
  }, [schoolId, refData.academicYears, academicYearId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!schoolId || !academicYearId || !gradeId || !subjectId || !section.trim()) {
      setError("Pick a school, academic year, grade, subject, and section.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      // 1. Find or create the school_class. If a class for this (school, AY,
      //    grade, section) already exists, reuse it so the teacher doesn't
      //    accidentally fork an extra class row.
      const existing = refData.classes.find(
        (c) =>
          c.school_id === schoolId &&
          c.academic_year_id === academicYearId &&
          c.grade_id === gradeId &&
          c.section.toUpperCase() === section.trim().toUpperCase(),
      );
      let schoolClassId: string;
      if (existing) {
        schoolClassId = existing.id;
      } else {
        const klass = await admin.createClass({
          school_id: schoolId,
          academic_year_id: academicYearId,
          grade_id: gradeId,
          section: section.trim(),
        });
        schoolClassId = klass.id;
      }

      // 2. Pick a book for this curriculum × grade × subject (if seeded).
      const book = refData.books.find(
        (b) =>
          b.curriculum_id === refData.curriculumId &&
          b.grade_id === gradeId &&
          b.subject_id === subjectId,
      );

      // 3. Create the CST linking the class + subject + this teacher.
      await admin.createCST({
        school_class_id: schoolClassId,
        subject_id: subjectId,
        teacher_id: refData.teacherId,
        book_id: book?.id,
      });

      await onCreated();
    } catch (err) {
      setError(
        err instanceof DarsApiError
          ? `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`
          : err instanceof Error
          ? err.message
          : "Failed to create class",
      );
    } finally {
      setBusy(false);
    }
  }

  if (refData.schools.length === 0) {
    return (
      <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-ink-soft">
        Your org has no schools set up yet. Ask an admin to add one.
      </div>
    );
  }

  if (aysForSchool.length === 0) {
    return (
      <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4">
        <p className="text-sm text-dars-ink">
          No academic year on this school yet. Ask an admin to add one.
        </p>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs text-dars-muted hover:text-dars-terra mt-2"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 space-y-3"
    >
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-dars-ink">New class</p>
        <button
          type="button"
          onClick={onCancel}
          className="text-xs text-dars-muted hover:text-dars-terra"
        >
          Cancel
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <Field label="School">
          <select
            value={schoolId}
            onChange={(e) => setSchoolId(e.target.value)}
            className="select"
          >
            {refData.schools.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Academic year">
          <select
            value={academicYearId}
            onChange={(e) => setAcademicYearId(e.target.value)}
            className="select"
          >
            {aysForSchool.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Subject">
          <select
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
            className="select"
          >
            {refData.subjects.map((s) => (
              <option key={s.id} value={s.id}>{s.code} — {s.display_name}</option>
            ))}
          </select>
        </Field>
        <Field label="Grade">
          <select
            value={gradeId}
            onChange={(e) => setGradeId(e.target.value)}
            className="select"
          >
            {refData.grades.map((g) => (
              <option key={g.id} value={g.id}>{g.display_name}</option>
            ))}
          </select>
        </Field>
        <Field label="Section">
          <input
            type="text"
            value={section}
            onChange={(e) => setSection(e.target.value)}
            placeholder="A"
            maxLength={4}
            className="w-full px-2 py-1.5 rounded border border-dars-rule-light bg-white text-sm"
          />
        </Field>
      </div>

      {error ? (
        <p className="text-sm text-dars-terra" role="alert">{error}</p>
      ) : null}

      <div className="flex justify-end gap-2">
        <button
          type="submit"
          disabled={busy}
          className="px-3 py-1.5 rounded-md bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Creating…" : "Create class"}
        </button>
      </div>

      <style jsx>{`
        .select {
          padding: 0.5rem 0.75rem;
          border-radius: 0.375rem;
          border: 1px solid var(--color-dars-rule-light);
          background: white;
          font-size: 0.875rem;
          color: var(--color-dars-ink);
          width: 100%;
        }
      `}</style>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col">
      <span className="text-xs font-medium text-dars-ink-soft mb-1">{label}</span>
      {children}
    </label>
  );
}
