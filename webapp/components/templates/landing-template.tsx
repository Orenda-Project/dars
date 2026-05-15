import { Eyebrow } from "@/components/atoms/eyebrow";
import { Logo } from "@/components/atoms/logo";
import { NavBar } from "@/components/molecules/nav-bar";
import { PlanWindow } from "@/components/molecules/plan-window";
import { FeatureCard } from "@/components/molecules/feature-card";
import { StepItem } from "@/components/molecules/step-item";
import {
  IllusQuill,
  IllusBooks,
  IllusOpenBook,
  IllusKey,
  IllusCompass,
  IllusComponents,
} from "@/components/atoms/illustrations";

const FEATURES = [
  { num: "i.", chapterLabel: "ch. i", title: "Lesson Plan Generation", desc: "One API call returns a complete, structured lesson plan — objectives, activities, assessment questions. Pass grade, subject, page number. No prompts to write, no model to host.", annotation: "bilingual output available →", Illus: IllusQuill },
  { num: "ii.", chapterLabel: "ch. ii", title: "Full Curriculum Tree", desc: "Dars holds structured Pakistani textbooks — chapters, topics, and pre-generated lesson plans for each. Browse the whole tree for a grade and subject, collect IDs, fetch content. Your product is one GET request away from a full term.", annotation: "ICT · Punjab", Illus: IllusBooks },
  { num: "iii.", chapterLabel: "ch. iii", title: "Exam Generation", desc: "Generate curriculum-aligned exams and class assessments from any page range. Control question types, seen/unseen split, counts, answer key, and AI review — or let the defaults handle it.", annotation: "seen · unseen · objective · subjective", Illus: IllusOpenBook },
  { num: "iv.", chapterLabel: "ch. iv", title: "Per-client API Keys", desc: "Register, set your curriculum, get a key. Each client is fully isolated — their own generation history, their own analytics. Keys are hashed at rest and shown once on creation.", annotation: "hashed, shown once on creation", Illus: IllusKey },
  { num: "v.", chapterLabel: "ch. v", title: "Async by Default", desc: "Every generation request returns immediately with a job ID. Poll for status or build on top of it. Generation typically completes in under two minutes.", annotation: "202 → PENDING → READY", Illus: IllusCompass },
  { num: "vi.", chapterLabel: "ch. vi", title: "Built for Integration", desc: "REST API with predictable JSON responses. An MCP server and client SDK are on the roadmap — so your coding agent or frontend can integrate Dars with minimal boilerplate.", annotation: "API · SDK · MCP — coming", Illus: IllusComponents },
] as const;

const STEPS = [
  { num: "i.", title: "Register and set your curriculum", desc: "Sign up on the Dars dashboard, select your curriculum — ICT or Punjab — and copy your API key. That's the entire setup. Your curriculum determines which grades, subjects, and textbooks are available to you.", code: `// Your key, shown once on registration\nX-API-Key: dars_••••••••\n\n// Curriculum set in Settings:\n// ICT or Punjab` },
  { num: "ii.", title: "Browse the curriculum tree", desc: "Fetch the full breakdown for any grade and subject — chapters, topics, and pre-generated lesson plans with their IDs. Use this to build your navigation, resolve IDs, or let a teacher browse to their lesson.", code: `GET /api/v1/curriculum?grade=3&subject=Eng\n\n→ chapters\n  → topics\n    → lessons\n        lesson_plan_id\n        assessment_id` },
  { num: "iii.", title: "Fetch plans and assessments", desc: "Once you have an ID from the tree, fetch the full lesson plan or assessment content. Lesson plans come back as HTML, ready to render. Assessments include structured question JSON with an answer key.", code: `GET /api/v1/lesson-plans/{id}\n→ content (HTML, bilingual optional)\n\nGET /api/v1/assessments/{id}\n→ content_json  (structured questions)\n→ answers_json  (answer key)` },
  { num: "iv.", title: "Generate custom lesson plans and exams", desc: "Need a plan outside the pre-built tree? Generate one on demand — pass a page number and optional topic. For exams, control every dimension: question types, seen/unseen split, counts per type, answer key, image generation, AI review.", code: `POST /api/v1/custom-lesson-plans\n{\n  "grade": 3, "subject": "Maths",\n  "page_number": "42"\n}\n→ 202 PENDING → poll → READY` },
  { num: "v.", title: "Tag generations with your own IDs", desc: "Every generation accepts an optional external_id — a teacher ID, student ID, or any string from your system. Filter listings by it, track who generated what, and pipe results back to the right person without Dars needing to know your data model.", code: `POST /api/v1/custom-exam-generations\n{\n  "grade": 4, "subject": "Eng",\n  "page_ranges": "10-20",\n  "external_id": "teacher-007"\n}\n\nGET /api/v1/custom-exam-generations\n  ?external_id=teacher-007` },
] as const;

export function LandingTemplate() {
  return (
    <main className="bg-dars-parchment text-dars-ink">

      <NavBar />

      {/* Hero */}
      <section className="bg-dars-ink min-h-[92vh] flex flex-col items-center justify-center text-center py-20 relative overflow-hidden border-b border-dars-rule-dark sm:py-16">
        {/* Book watermark */}
        <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
          <svg width={720} height={720} viewBox="0 0 200 200" fill="none" style={{ opacity: 0.045 }} aria-hidden="true">
            <path d="M100 30 C70 30 30 40 20 60 L20 170 C30 150 70 140 100 140 C130 140 170 150 180 170 L180 60 C170 40 130 30 100 30Z" stroke="white" strokeWidth="1.5" />
            <line x1="100" y1="30" x2="100" y2="140" stroke="white" strokeWidth="1.5" />
            <line x1="30" y1="75" x2="95" y2="80" stroke="white" strokeWidth="1" />
            <line x1="32" y1="90" x2="95" y2="94" stroke="white" strokeWidth="1" />
            <line x1="34" y1="105" x2="95" y2="108" stroke="white" strokeWidth="1" />
            <line x1="34" y1="120" x2="95" y2="122" stroke="white" strokeWidth="1" />
            <line x1="105" y1="80" x2="170" y2="75" stroke="white" strokeWidth="1" />
            <line x1="105" y1="94" x2="168" y2="90" stroke="white" strokeWidth="1" />
            <line x1="105" y1="108" x2="166" y2="105" stroke="white" strokeWidth="1" />
            <line x1="105" y1="122" x2="166" y2="120" stroke="white" strokeWidth="1" />
          </svg>
        </div>
        {/* Concentric rings */}
        <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
          {[320, 520, 740, 980].map((size, i) => (
            <div
              key={size}
              className="absolute rounded-full"
              style={{
                width: size,
                height: size,
                border: `1px solid rgba(191,78,48,${[0.12, 0.07, 0.04, 0.025][i]})`,
              }}
            />
          ))}
        </div>

        <div className="w-full max-w-7xl mx-auto px-14 sm:px-6 flex flex-col items-center">
          <Eyebrow className="mb-7 relative z-10">Lesson plans, in seconds</Eyebrow>

          <h1 className="font-serif text-[68px] sm:text-[40px] font-bold leading-[1.05] tracking-[-2px] sm:tracking-[-1px] text-dars-parchment mb-7 relative z-10 max-w-[820px]">
            Every teacher deserves a{" "}
            <em className="italic text-dars-terra">great lesson plan.</em>
          </h1>

          <p className="text-lg sm:text-base text-dars-muted-light leading-[1.7] max-w-[480px] mx-auto mb-11 relative z-10">
            Dars turns textbooks into full-term lesson plans — structured, bilingual, and aligned to NCP and provincial curricula. Your teachers ask, Dars delivers.
          </p>

          <div className="flex gap-3.5 items-center justify-center relative z-10 flex-wrap">
            <a
              href="/dashboard/login"
              className="bg-dars-terra text-dars-parchment px-7 py-3.5 rounded-md text-sm font-semibold no-underline hover:opacity-90 transition-opacity"
            >
              Log in →
            </a>
            <a
              href="/showcase/ali-sipra-2026-05-15"
              className="text-dars-parchment text-sm font-medium no-underline border border-dars-rule-dark px-6 py-3 rounded-md hover:border-dars-parchment transition-colors"
            >
              View sample lesson plans →
            </a>
            <a
              href="#how"
              className="text-dars-muted-light text-[13px] no-underline border-b border-dars-rule-dark pb-0.5 hover:text-dars-parchment transition-colors"
            >
              How it works ↓
            </a>
          </div>
        </div>

        {/* Scroll hint */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10">
          <div
            className="w-px h-10 mx-auto"
            style={{ background: "linear-gradient(to bottom, rgba(122,107,98,0.5), transparent)" }}
          />
        </div>
      </section>

      {/* Plan window */}
      <section className="bg-dars-ink pb-20 border-b border-dars-rule-dark sm:pb-12">
        <div className="w-full max-w-7xl mx-auto px-14 sm:px-6 flex justify-center">
          <PlanWindow />
        </div>
      </section>

      {/* Features */}
      <section className="bg-dars-parchment py-24 border-b border-dars-rule-light sm:py-16">
        <div className="w-full max-w-7xl mx-auto px-14 sm:px-6">
          <div className="flex items-baseline gap-4 mb-13">
            <span className="font-serif text-[13px] text-dars-terra italic">I.</span>
            <h2 className="font-serif text-[30px] sm:text-2xl font-bold text-dars-ink tracking-[-0.5px]">
              Everything a curriculum product needs.
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 md:gap-x-14">
            {FEATURES.map(({ num, chapterLabel, title, desc, annotation, Illus }, idx) => (
              <FeatureCard
                key={num}
                num={num}
                chapterLabel={chapterLabel}
                title={title}
                desc={desc}
                annotation={annotation}
                Illus={Illus}
                hasBorderBottom={idx < 5}
              />
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section
        id="how"
        className="bg-dars-parchment-mid py-16 border-b border-dars-rule-light sm:py-16"
      >
        <div className="w-full max-w-7xl mx-auto px-14 sm:px-6 grid grid-cols-1 gap-10 items-start lg:py-24 lg:grid-cols-[1fr_2fr] lg:gap-20">
          <div className="lg:sticky lg:top-[100px]">
            <span className="block font-serif text-[13px] text-dars-terra italic mb-2">II.</span>
            <h2 className="font-serif text-2xl lg:text-[30px] font-bold text-dars-ink tracking-[-0.5px]">
              Don&apos;t build it. Borrow it.
            </h2>
            <p className="text-sm text-dars-muted mt-3 leading-[1.7]">
              LP generation, curriculum data, SLO mapping — it&apos;s all here. Connect via MCP and your agent can pull it straight into your app. Or wire up the API yourself.
            </p>
          </div>
          <div>
            {STEPS.map(({ num, title, desc, code }, i) => (
              <StepItem
                key={num}
                num={num}
                title={title}
                desc={desc}
                code={code}
                isFirst={i === 0}
              />
            ))}
          </div>
        </div>
      </section>

      {/* Quote */}
      <blockquote className="bg-dars-ink-soft py-14 border-b border-dars-rule-dark md:py-20">
        <div className="w-full max-w-7xl mx-auto px-14 sm:px-6 flex flex-col items-start gap-6 md:flex-row md:items-center md:gap-10">
          <span
            className="font-serif text-[80px] md:text-[120px] text-dars-terra flex-shrink-0 leading-none -mt-2.5"
            style={{ opacity: 0.25 }}
            aria-hidden="true"
          >
            &ldquo;
          </span>
          <div>
            <p className="font-serif text-xl md:text-2xl italic text-dars-parchment leading-[1.55] tracking-[-0.3px]">
              A lesson plan is not a script. It is a{" "}
              <em className="text-dars-terra not-italic">map</em>
              {" "}— one that every teacher draws for their students.
            </p>
            <p className="text-xs text-dars-muted mt-4 tracking-[0.5px] uppercase">
              — Principle behind Dars
            </p>
          </div>
        </div>
      </blockquote>

      {/* CTA */}
      <section className="bg-dars-parchment py-24 relative overflow-hidden sm:py-16">
        {[
          { size: 600, bottom: -200, border: "border-dars-rule-light" },
          { size: 800, bottom: -280, border: "border-dars-parchment-deep" },
        ].map(({ size, bottom, border }) => (
          <div
            key={size}
            className={`absolute left-1/2 -translate-x-1/2 rounded-full border ${border} pointer-events-none`}
            style={{ width: size, height: size, bottom }}
          />
        ))}
        <div className="w-full max-w-7xl mx-auto px-14 sm:px-6 text-center">
          <h2 className="font-serif text-[44px] sm:text-[32px] font-bold text-dars-ink tracking-[-1px] leading-[1.1] mb-4 relative">
            Ready to give your teachers a{" "}
            <em className="text-dars-terra italic">better plan?</em>
          </h2>
          <p className="text-base text-dars-muted max-w-[380px] mx-auto mb-9 leading-[1.65] relative">
            Log in to your dashboard and start generating curriculum-aligned lesson plans today.
          </p>
          <a
            href="/dashboard/login"
            className="bg-dars-terra text-dars-parchment px-8 py-3.5 rounded-md text-[15px] font-semibold no-underline relative inline-block hover:opacity-90 transition-opacity"
          >
            Log in →
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-dars-rule-light py-7 bg-dars-parchment-mid">
        <div className="w-full max-w-7xl mx-auto px-14 sm:px-6 flex justify-between items-center text-xs text-dars-muted sm:flex-col sm:gap-4 sm:text-center">
          <Logo size="sm" />
          <div>© 2026 Taleemabad</div>
        </div>
      </footer>

    </main>
  );
}
