/**
 * F5.8 — Classes + CST assignment.
 *
 * Per-AY class list. Add class (grade + section); per class, list CSTs
 * (one row per subject) with add/edit.
 */
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  admin,
  books as booksApi,
  curriculum as curriculumApi,
  DarsApiError,
  tenancy as tenancyApi,
  type Book,
  type CST,
  type Grade,
  type SchoolClass,
  type Subject,
  type Teacher,
} from "@/lib/dars-api";

export default function ClassesPage() {
  const params = useParams<{ school_id: string; ay_id: string }>();
  const { school_id: schoolId, ay_id: ayId } = params;

  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [csts, setCsts] = useState<CST[]>([]);
  const [books, setBooks] = useState<Book[]>([]);
  const [showClassForm, setShowClassForm] = useState(false);
  const [newGradeId, setNewGradeId] = useState("");
  const [newSection, setNewSection] = useState("A");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [
        { items: cls },
        { items: gs },
        { items: ss },
        { items: ts },
        { items: cs },
        { items: bs },
      ] = await Promise.all([
        tenancyApi.getClasses({ school_id: schoolId, academic_year_id: ayId }),
        curriculumApi.getGrades(),
        curriculumApi.getSubjects(),
        tenancyApi.getTeachers(schoolId),
        tenancyApi.getCSTs(),
        booksApi.getBooks(),
      ]);
      setClasses(cls);
      setGrades(gs);
      setSubjects(ss);
      setTeachers(ts);
      setCsts(cs);
      setBooks(bs);
      if (!newGradeId && gs[0]) setNewGradeId(gs[0].id);
    } catch (err) {
      setError(formatErr(err));
    }
  }, [schoolId, ayId, newGradeId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAddClass(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await admin.createClass({
        school_id: schoolId,
        academic_year_id: ayId,
        grade_id: newGradeId,
        section: newSection,
      });
      setNewSection("A");
      setShowClassForm(false);
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="text-xs text-dars-muted mb-2">
        <Link href={`/dashboard/schools/${schoolId}/academic-years`} className="hover:text-dars-terra">
          ← Back to academic years
        </Link>
      </div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">Classes</h1>
        <button
          type="button"
          onClick={() => setShowClassForm((s) => !s)}
          className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold"
        >
          {showClassForm ? "Cancel" : "Add class"}
        </button>
      </div>

      {showClassForm ? (
        <form onSubmit={handleAddClass} className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 mb-4 grid grid-cols-3 gap-2 items-end">
          <label>
            <span className="text-xs text-dars-ink-soft">Grade</span>
            <select required value={newGradeId} onChange={(e) => setNewGradeId(e.target.value)} className="input">
              {grades.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="text-xs text-dars-ink-soft">Section</span>
            <input required value={newSection} onChange={(e) => setNewSection(e.target.value)} className="input" />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="px-3 py-1.5 rounded bg-dars-ink text-dars-parchment text-xs font-semibold disabled:opacity-50"
          >
            {busy ? "Saving…" : "Create"}
          </button>
          <style jsx>{`
            .input {
              margin-top: 0.25rem; width: 100%;
              padding: 0.5rem 0.75rem;
              border-radius: 0.375rem;
              border: 1px solid var(--color-dars-rule-light);
              background: white;
              font-size: 0.875rem;
            }
          `}</style>
        </form>
      ) : null}

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      <ul className="space-y-3">
        {classes.length === 0 ? (
          <li className="text-sm text-dars-muted">No classes yet.</li>
        ) : (
          classes.map((c) => (
            <ClassRow
              key={c.id}
              klass={c}
              grades={grades}
              subjects={subjects}
              teachers={teachers}
              books={books}
              csts={csts.filter((x) => x.school_class_id === c.id)}
              onChanged={load}
            />
          ))
        )}
      </ul>
    </div>
  );
}

function ClassRow({
  klass,
  grades,
  subjects,
  teachers,
  books,
  csts,
  onChanged,
}: {
  klass: SchoolClass;
  grades: Grade[];
  subjects: Subject[];
  teachers: Teacher[];
  books: Book[];
  csts: CST[];
  onChanged: () => Promise<void>;
}) {
  const grade = grades.find((g) => g.id === klass.grade_id);
  const [showSubjectForm, setShowSubjectForm] = useState(false);
  const [subjectId, setSubjectId] = useState(subjects[0]?.id ?? "");
  const [teacherId, setTeacherId] = useState(teachers[0]?.id ?? "");
  const [bookId, setBookId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!subjectId && subjects[0]) setSubjectId(subjects[0].id);
    if (!teacherId && teachers[0]) setTeacherId(teachers[0].id);
  }, [subjects, teachers, subjectId, teacherId]);

  async function handleAddCst(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await admin.createCST({
        school_class_id: klass.id,
        subject_id: subjectId,
        teacher_id: teacherId,
        book_id: bookId || undefined,
      });
      setShowSubjectForm(false);
      await onChanged();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  // Filter books by grade — the dropdown should only show appropriate ones.
  const filteredBooks = books.filter((b) => b.grade_id === klass.grade_id);

  return (
    <li className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3">
      <div className="flex items-center justify-between mb-2">
        <p className="font-medium text-dars-ink">
          {klass.name} <span className="text-xs text-dars-muted">({grade?.code})</span>
        </p>
        <button
          type="button"
          onClick={() => setShowSubjectForm((s) => !s)}
          className="text-xs text-dars-terra hover:underline"
        >
          {showSubjectForm ? "Cancel" : "+ Subject"}
        </button>
      </div>

      <ul className="space-y-1">
        {csts.length === 0 ? (
          <li className="text-xs text-dars-muted">No subjects yet.</li>
        ) : (
          csts.map((cst) => {
            const subject = subjects.find((s) => s.id === cst.subject_id);
            const teacher = teachers.find((t) => t.id === cst.teacher_id);
            return (
              <li
                key={cst.id}
                className="text-xs text-dars-ink-soft px-2 py-1 rounded bg-dars-parchment flex items-center justify-between"
              >
                <span>
                  <strong className="font-semibold">{subject?.code ?? "—"}</strong>
                  {" · "}
                  <span className="text-dars-muted">{teacher?.name ?? "—"}</span>
                </span>
                <span className="font-mono text-[10px] text-dars-muted-light">
                  {cst.id.slice(0, 8)}…
                </span>
              </li>
            );
          })
        )}
      </ul>

      {showSubjectForm ? (
        <form onSubmit={handleAddCst} className="grid grid-cols-3 gap-2 mt-2 items-end">
          <label className="text-xs">
            Subject
            <select required value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="input">
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs">
            Teacher
            <select required value={teacherId} onChange={(e) => setTeacherId(e.target.value)} className="input">
              {teachers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs">
            Book (optional)
            <select value={bookId} onChange={(e) => setBookId(e.target.value)} className="input">
              <option value="">— none —</option>
              {filteredBooks.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.title}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={busy}
            className="col-span-3 px-3 py-1.5 rounded bg-dars-ink text-dars-parchment text-xs font-semibold disabled:opacity-50"
          >
            {busy ? "Saving…" : "Add subject"}
          </button>
          {error ? <p className="col-span-3 text-xs text-dars-terra">{error}</p> : null}
          <style jsx>{`
            .input {
              margin-top: 0.25rem;
              width: 100%;
              padding: 0.4rem 0.5rem;
              border-radius: 0.375rem;
              border: 1px solid var(--color-dars-rule-light);
              background: white;
              font-size: 0.75rem;
            }
          `}</style>
        </form>
      ) : null}
    </li>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
