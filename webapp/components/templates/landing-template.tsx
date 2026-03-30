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
  { num: "i.", chapterLabel: "ch. i", title: "AI Generation", desc: "One API call returns a complete, structured lesson plan — objectives, activities, assessment. Specify grade, subject, topic, duration.", annotation: "See also: structured output →", Illus: IllusQuill },
  { num: "ii.", chapterLabel: "ch. ii", title: "Versioned Storage", desc: "Every plan is stored, versioned, and retrievable — like a library catalogue. Build edit flows, approvals, or history views on top.", annotation: "cf. library card catalogue", Illus: IllusBooks },
  { num: "iii.", chapterLabel: "ch. iii", title: "Structured Output", desc: "Plans return as clean JSON or pre-rendered HTML — like a typeset document, ready to publish. No prompt engineering required.", annotation: "render-ready, always", Illus: IllusOpenBook },
  { num: "iv.", chapterLabel: "ch. iv", title: "API Key Auth", desc: "Per-client keys with scoped access and usage tracking. Like a library card — each institution gets their own, with their own catalogue.", annotation: "hashed, shown once on creation", Illus: IllusKey },
  { num: "v.", chapterLabel: "ch. v", title: "Curriculum Alignment", desc: "Pass your curriculum spec and Dars maps plans to your learning standards — not generic internet content.", annotation: "Punjab Board, AKU, custom specs", Illus: IllusCompass },
  { num: "vi.", chapterLabel: "ch. vi", title: "React Components", desc: "Drop-in @dars/react components for rendering and editing plans in your UI.", annotation: "npm install @dars/react", Illus: IllusComponents },
] as const;

const STEPS = [
  { num: "i.", title: "Connect your product", desc: "Get an API key from the dashboard. Point your backend at the Dars endpoint. Works with any language or framework over REST.", code: `POST /api/v1/lesson-plans\nX-API-Key: drs_live_••••••••` },
  { num: "ii.", title: "Request a lesson plan", desc: "Pass grade, subject, topic, duration, and any curriculum constraints. Dars generates a structured, aligned plan in seconds.", code: `{\n  "grade": "4",\n  "subject": "Science",\n  "topic": "The Water Cycle",\n  "duration_minutes": 45\n}` },
  { num: "iii.", title: "Render it your way", desc: "Get back structured JSON or pre-rendered HTML. Use the Dars React components, or build your own UI on top of the clean data model.", code: null },
] as const;

export function LandingTemplate() {
  return (
    <main className="bg-dars-parchment text-dars-ink">

      <NavBar />

      {/* Hero */}
      <section className="bg-dars-ink min-h-[92vh] flex flex-col items-center justify-center text-center px-14 py-20 relative overflow-hidden border-b border-dars-rule-dark sm:px-6 sm:py-16">
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

        <Eyebrow className="mb-7 relative z-10">Lesson plan infrastructure</Eyebrow>

        <h1 className="font-serif text-[68px] sm:text-[40px] font-bold leading-[1.05] tracking-[-2px] sm:tracking-[-1px] text-dars-parchment mb-7 relative z-10 max-w-[820px]">
          The platform behind{" "}
          <em className="italic text-dars-terra">great teaching.</em>
        </h1>

        <p className="text-lg sm:text-base text-dars-muted-light leading-[1.7] max-w-[480px] mx-auto mb-11 relative z-10">
          Dars gives edtech teams a complete API for generating, storing, and rendering curriculum-aligned lesson plans — powered by AI, built to scale.
        </p>

        <div className="flex gap-3.5 items-center justify-center relative z-10 flex-wrap">
          <a
            href="/docs"
            className="bg-dars-terra text-dars-parchment px-7 py-3.5 rounded-md text-sm font-semibold no-underline hover:opacity-90 transition-opacity"
          >
            Read the docs →
          </a>
          <a
            href="#how"
            className="text-dars-muted-light text-[13px] no-underline border-b border-dars-rule-dark pb-0.5 hover:text-dars-parchment transition-colors"
          >
            See how it works
          </a>
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
      <section className="bg-dars-ink px-14 pb-20 flex justify-center border-b border-dars-rule-dark sm:px-6 sm:pb-12">
        <PlanWindow />
      </section>

      {/* Features */}
      <section className="bg-dars-parchment px-14 py-24 border-b border-dars-rule-light sm:px-6 sm:py-16">
        <div className="flex items-baseline gap-4 mb-13">
          <span className="font-serif text-[13px] text-dars-terra italic">I.</span>
          <h2 className="font-serif text-[30px] sm:text-2xl font-bold text-dars-ink tracking-[-0.5px]">
            Everything a curriculum product needs.
          </h2>
        </div>
        <div className="grid grid-cols-2 gap-x-14 max-[480px]:grid-cols-1 max-[480px]:gap-x-0">
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
      </section>

      {/* How it works */}
      <section
        id="how"
        className="bg-dars-parchment-mid px-14 py-24 border-b border-dars-rule-light grid grid-cols-[1fr_2fr] gap-20 items-start sm:px-6 sm:py-16 sm:grid-cols-1 sm:gap-10"
      >
        <div className="sticky top-[100px] sm:static">
          <span className="block font-serif text-[13px] text-dars-terra italic mb-2">II.</span>
          <h2 className="font-serif text-[30px] sm:text-2xl font-bold text-dars-ink tracking-[-0.5px]">
            From request to classroom.
          </h2>
          <p className="text-sm text-dars-muted mt-3 leading-[1.7]">
            Three steps. No infrastructure to manage, no prompts to maintain.
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
      </section>

      {/* Quote */}
      <blockquote className="bg-dars-ink-soft px-14 py-20 border-b border-dars-rule-dark flex gap-10 items-center sm:px-6 sm:py-14 sm:gap-6 sm:flex-col sm:items-start">
        <span
          className="font-serif text-[120px] sm:text-[80px] text-dars-terra flex-shrink-0 leading-none -mt-2.5"
          style={{ opacity: 0.25 }}
          aria-hidden="true"
        >
          &ldquo;
        </span>
        <div>
          <p className="font-serif text-2xl sm:text-xl italic text-dars-parchment leading-[1.55] tracking-[-0.3px]">
            A good lesson plan is not a script.<br />
            It is a{" "}
            <em className="text-dars-terra not-italic">map</em>
            {" "}— and every student takes a different path.
          </p>
          <p className="text-xs text-dars-muted mt-4 tracking-[0.5px] uppercase">
            — Principle behind Dars
          </p>
        </div>
      </blockquote>

      {/* CTA */}
      <section className="bg-dars-parchment px-14 py-24 text-center relative overflow-hidden sm:px-6 sm:py-16">
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
        <h2 className="font-serif text-[44px] sm:text-[32px] font-bold text-dars-ink tracking-[-1px] leading-[1.1] mb-4 relative">
          Build the lesson plan layer for{" "}
          <em className="text-dars-terra italic">your product.</em>
        </h2>
        <p className="text-base text-dars-muted max-w-[380px] mx-auto mb-9 leading-[1.65] relative">
          Get API access and ship curriculum features in days, not months.
        </p>
        <a
          href="/login"
          className="bg-dars-terra text-dars-parchment px-8 py-3.5 rounded-md text-[15px] font-semibold no-underline relative inline-block hover:opacity-90 transition-opacity"
        >
          Get API access →
        </a>
      </section>

      {/* Footer */}
      <footer className="border-t border-dars-rule-light px-14 py-7 flex justify-between items-center text-xs text-dars-muted bg-dars-parchment-mid sm:px-6 sm:flex-col sm:gap-4 sm:text-center">
        <Logo size="sm" />
        <div className="flex gap-6">
          {[["Docs", "/docs"], ["Privacy", "#"], ["Contact", "#"]].map(([label, href]) => (
            <a key={label} href={href} className="text-dars-muted no-underline hover:text-dars-ink transition-colors">
              {label}
            </a>
          ))}
        </div>
        <div>© 2026 Taleemabad</div>
      </footer>

    </main>
  );
}
