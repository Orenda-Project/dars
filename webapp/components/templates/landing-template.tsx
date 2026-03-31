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
  { num: "i.", chapterLabel: "ch. i", title: "AI Generation", desc: "One API call returns a complete, structured lesson plan — objectives, activities, assessment. Pass grade, subject, page number, curriculum. No prompts to write.", annotation: "See also: structured output →", Illus: IllusQuill },
  { num: "ii.", chapterLabel: "ch. ii", title: "Versioned Storage", desc: "Every plan is stored per client, versioned, and retrievable. Build edit flows, approvals, or history views on top of a clean data model.", annotation: "cf. library card catalogue", Illus: IllusBooks },
  { num: "iii.", chapterLabel: "ch. iii", title: "Structured Output", desc: "Plans return as clean JSON or pre-rendered HTML — ready to publish. Pipe to your UI, your WhatsApp channel, or anywhere you need it.", annotation: "render-ready, always", Illus: IllusOpenBook },
  { num: "iv.", chapterLabel: "ch. iv", title: "API Key Auth", desc: "Per-client keys with scoped access. Each institution gets their own key, their own plan catalogue — fully isolated.", annotation: "hashed, shown once on creation", Illus: IllusKey },
  { num: "v.", chapterLabel: "ch. v", title: "Curriculum Alignment", desc: "Pass your curriculum spec and Dars maps plans to your learning standards. Punjab Board, Sindh Board, AKU-EB, ICT — and more.", annotation: "Punjab Board, AKU, custom specs", Illus: IllusCompass },
  { num: "vi.", chapterLabel: "ch. vi", title: "React Components", desc: "Drop-in @dars/react components for rendering and generating plans in your UI. Works alongside @dars/node middleware — API key stays server-side.", annotation: "npm install @dars/react", Illus: IllusComponents },
] as const;

const STEPS = [
  { num: "i.", title: "Connect your product", desc: "Get an API key from the dashboard. One header, any language or framework.", code: `POST /api/v1/lesson-plans\nX-API-Key: dars_••••••••` },
  { num: "ii.", title: "Request a lesson plan", desc: "Pass grade, subject, page number, and curriculum. Dars generates, aligns, and stores the plan.", code: `{\n  "grade": "4",\n  "subject": "Science",\n  "page_number": "38",\n  "curriculum": "Punjab"\n}` },
  { num: "iii.", title: "Deliver it your way", desc: "Get back structured JSON or pre-rendered HTML. Use the Dars React components, pipe to WhatsApp, or build your own UI entirely.", code: null },
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
            Dars generates structured, curriculum-aligned lesson plans in seconds — for any subject, any grade, any board. Your teachers ask, Dars delivers.
          </p>

          <div className="flex gap-3.5 items-center justify-center relative z-10 flex-wrap">
            <a
              href="/docs"
              className="bg-dars-terra text-dars-parchment px-7 py-3.5 rounded-md text-sm font-semibold no-underline hover:opacity-90 transition-opacity"
            >
              Start generating plans →
            </a>
            <a
              href="#how"
              className="text-dars-muted-light text-[13px] no-underline border-b border-dars-rule-dark pb-0.5 hover:text-dars-parchment transition-colors"
            >
              For edtech teams ↓
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
            Get API access and ship curriculum features in days, not months.
          </p>
          <a
            href="/login"
            className="bg-dars-terra text-dars-parchment px-8 py-3.5 rounded-md text-[15px] font-semibold no-underline relative inline-block hover:opacity-90 transition-opacity"
          >
            Get API access →
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-dars-rule-light py-7 bg-dars-parchment-mid">
        <div className="w-full max-w-7xl mx-auto px-14 sm:px-6 flex justify-between items-center text-xs text-dars-muted sm:flex-col sm:gap-4 sm:text-center">
          <Logo size="sm" />
          <div className="flex gap-6">
            {[["Docs", "/docs"], ["For Teams", "#"], ["Privacy", "#"], ["Contact", "#"]].map(([label, href]) => (
              <a key={label} href={href} className="text-dars-muted no-underline hover:text-dars-ink transition-colors">
                {label}
              </a>
            ))}
          </div>
          <div>© 2026 Taleemabad | LP Team</div>
        </div>
      </footer>

    </main>
  );
}
