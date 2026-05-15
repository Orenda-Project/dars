"use client";

import { isMockExamPaper, type MockExamPaper, type MockExamQuestion } from "@/lib/teacher-app-mocks";

function QuestionRow({ q, index }: { q: MockExamQuestion; index: number }) {
  return (
    <div className="mb-4">
      <p
        className="text-sm text-gray-900"
        style={{ fontFamily: "Georgia, serif", lineHeight: 1.6 }}
      >
        <span className="font-semibold mr-1">Q{index}.</span>
        {q.text}
        <span className="text-xs text-gray-400 ml-2">({q.marks} mark{q.marks === 1 ? "" : "s"})</span>
      </p>
      {q.type === "MCQ" && q.options && (
        <ol
          className="mt-2 ml-6 text-sm text-gray-700 space-y-1"
          style={{ fontFamily: "Georgia, serif", listStyleType: "upper-alpha" }}
        >
          {q.options.map((opt, i) => (
            <li key={i}>{opt}</li>
          ))}
        </ol>
      )}
      {q.type === "SHORT" && (
        <div className="mt-2 space-y-2 ml-6">
          <div className="border-b border-dashed border-gray-300 h-5" />
          <div className="border-b border-dashed border-gray-300 h-5" />
        </div>
      )}
      {q.type === "LONG" && (
        <div className="mt-2 space-y-2 ml-6">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="border-b border-dashed border-gray-300 h-5" />
          ))}
        </div>
      )}
    </div>
  );
}

export function ExamPaperView({ result }: { result: unknown }) {
  if (!isMockExamPaper(result)) {
    return (
      <pre className="text-xs bg-gray-50 p-4 rounded overflow-auto whitespace-pre-wrap">
        {JSON.stringify(result, null, 2)}
      </pre>
    );
  }
  const paper = result as MockExamPaper;
  let qIndex = 0;

  return (
    <div style={{ fontFamily: "Georgia, serif", color: "#1c1410" }}>
      {/* Header */}
      <div className="text-center border-b-2 border-gray-300 pb-4 mb-5">
        <h2 className="text-lg font-bold mb-1">{paper.title}</h2>
        <p className="text-sm text-gray-600">
          {paper.subject} · Grade {paper.grade}
        </p>
        <div className="flex justify-center gap-6 mt-3 text-xs text-gray-500">
          <span>
            <strong className="text-gray-700">Total Marks:</strong> {paper.metadata.total_marks}
          </span>
          <span>
            <strong className="text-gray-700">Time:</strong> {paper.metadata.duration_minutes} min
          </span>
          <span>
            <strong className="text-gray-700">Questions:</strong> {paper.metadata.question_count}
          </span>
        </div>
      </div>

      {/* Sections */}
      {paper.sections.map((section, si) => (
        <div key={si} className="mb-6">
          <h3
            className="text-sm font-bold uppercase tracking-wider text-gray-600 mb-3 pb-1 border-b border-gray-200"
            style={{ letterSpacing: "0.05em" }}
          >
            {section.title}
          </h3>
          {section.questions.map((q) => {
            qIndex += 1;
            return <QuestionRow key={q.id} q={q} index={qIndex} />;
          })}
        </div>
      ))}
    </div>
  );
}
