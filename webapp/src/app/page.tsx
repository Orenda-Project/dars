// src/app/page.tsx
import { PlanWindow } from "@/components/landing/plan-window";
import {
  IllusQuill,
  IllusBooks,
  IllusOpenBook,
  IllusKey,
  IllusCompass,
  IllusComponents,
} from "@/components/landing/illustrations";

const C = {
  ink: "#1c1410",
  inkSoft: "#2c2420",
  parchment: "#faf7f2",
  parchmentMid: "#f0ebe3",
  parchmentDeep: "#e8dfd3",
  terra: "#bf4e30",
  terraLight: "#e8a07a",
  muted: "#7a6b62",
  mutedLight: "#a89890",
  ruleDark: "#2e2420",
  ruleLight: "#e0d5c8",
} as const;

const FEATURES = [
  { num: "i.", chapterLabel: "ch. i", title: "AI Generation", desc: "One API call returns a complete, structured lesson plan — objectives, activities, assessment. Specify grade, subject, topic, duration.", annotation: "See also: structured output →", Illus: IllusQuill },
  { num: "ii.", chapterLabel: "ch. ii", title: "Versioned Storage", desc: "Every plan is stored, versioned, and retrievable — like a library catalogue. Build edit flows, approvals, or history views on top.", annotation: "cf. library card catalogue", Illus: IllusBooks },
  { num: "iii.", chapterLabel: "ch. iii", title: "Structured Output", desc: "Plans return as clean JSON or pre-rendered HTML — like a typeset document, ready to publish. No prompt engineering required.", annotation: "render-ready, always", Illus: IllusOpenBook },
  { num: "iv.", chapterLabel: "ch. iv", title: "API Key Auth", desc: "Per-client keys with scoped access and usage tracking. Like a library card — each institution gets their own, with their own catalogue.", annotation: "hashed, shown once on creation", Illus: IllusKey },
  { num: "v.", chapterLabel: "ch. v", title: "Curriculum Alignment", desc: "Pass your curriculum spec and Dars maps plans to your learning standards — not generic internet content.", annotation: "Punjab Board, AKU, custom specs", Illus: IllusCompass },
  { num: "vi.", chapterLabel: "ch. vi", title: "React Components", desc: "Drop-in @dars/react components for rendering and editing plans in your UI.", annotation: "npm install @dars/react", Illus: IllusComponents },
];

const STEPS = [
  { num: "i.", title: "Connect your product", desc: "Get an API key from the dashboard. Point your backend at the Dars endpoint. Works with any language or framework over REST.", code: `POST /api/v1/lesson-plans\nX-API-Key: drs_live_••••••••` },
  { num: "ii.", title: "Request a lesson plan", desc: "Pass grade, subject, topic, duration, and any curriculum constraints. Dars generates a structured, aligned plan in seconds.", code: `{\n  "grade": "4",\n  "subject": "Science",\n  "topic": "The Water Cycle",\n  "duration_minutes": 45\n}` },
  { num: "iii.", title: "Render it your way", desc: "Get back structured JSON or pre-rendered HTML. Use the Dars React components, or build your own UI on top of the clean data model.", code: null },
];

const ruledBg = {
  backgroundImage: "repeating-linear-gradient(to bottom, transparent, transparent 19px, rgba(208,195,180,0.45) 19px, rgba(208,195,180,0.45) 20px)",
  backgroundSize: "100% 20px",
} as const;

export default function Home() {
  return (
    <main style={{ background: C.parchment, color: C.ink }}>

      <nav style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "22px 56px", borderBottom: `1px solid ${C.ruleDark}`, position: "sticky", top: 0, background: "rgba(28,20,16,0.96)", backdropFilter: "blur(8px)", zIndex: 100 }}>
        <div style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 19, fontWeight: 700, color: C.parchment, display: "flex", alignItems: "baseline", gap: 9 }}>
          Dars <span style={{ color: C.terra, fontWeight: 400, fontSize: 15 }}>درس</span>
        </div>
        <div style={{ display: "flex", gap: 32, alignItems: "center", fontSize: 13, color: C.mutedLight }}>
          <a href="/docs" style={{ color: "inherit", textDecoration: "none" }}>Docs</a>
          <a href="/docs" style={{ color: "inherit", textDecoration: "none" }}>API</a>
          <a href="#" style={{ color: "inherit", textDecoration: "none" }}>Pricing</a>
          <a href="/login" style={{ background: C.terra, color: C.parchment, padding: "8px 18px", borderRadius: 5, fontSize: 13, fontWeight: 600, textDecoration: "none" }}>Get access</a>
        </div>
      </nav>

      <section style={{ background: C.ink, minHeight: "92vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "80px 56px", position: "relative", overflow: "hidden", borderBottom: `1px solid ${C.ruleDark}` }}>
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", display: "flex", alignItems: "center", justifyContent: "center" }}>
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
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", display: "flex", alignItems: "center", justifyContent: "center" }}>
          {[320, 520, 740, 980].map((size, i) => (
            <div key={size} style={{ position: "absolute", borderRadius: "50%", width: size, height: size, border: `1px solid rgba(191,78,48,${[0.12, 0.07, 0.04, 0.025][i]})` }} />
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, fontSize: 11, fontWeight: 700, letterSpacing: "2px", color: C.terra, textTransform: "uppercase", marginBottom: 28, position: "relative", zIndex: 2 }}>
          <span style={{ display: "inline-block", width: 32, height: 1, background: C.terra, opacity: 0.6 }} />
          Lesson plan infrastructure
          <span style={{ display: "inline-block", width: 32, height: 1, background: C.terra, opacity: 0.6 }} />
        </div>
        <h1 style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 68, fontWeight: 700, lineHeight: 1.05, letterSpacing: "-2px", color: C.parchment, marginBottom: 28, position: "relative", zIndex: 2, maxWidth: 820 }}>
          The platform behind{" "}<em style={{ fontStyle: "italic", color: C.terra }}>great teaching.</em>
        </h1>
        <p style={{ fontSize: 18, color: C.mutedLight, lineHeight: 1.7, maxWidth: 480, margin: "0 auto 44px", position: "relative", zIndex: 2 }}>
          Dars gives edtech teams a complete API for generating, storing, and rendering curriculum-aligned lesson plans — powered by AI, built to scale.
        </p>
        <div style={{ display: "flex", gap: 14, alignItems: "center", justifyContent: "center", position: "relative", zIndex: 2 }}>
          <a href="/docs" style={{ background: C.terra, color: C.parchment, padding: "13px 28px", borderRadius: 6, fontSize: 14, fontWeight: 600, textDecoration: "none" }}>Read the docs →</a>
          <a href="#how" style={{ color: C.mutedLight, fontSize: 13, textDecoration: "none", borderBottom: `1px solid ${C.ruleDark}`, paddingBottom: 2 }}>See how it works</a>
        </div>
        <div style={{ position: "absolute", bottom: 32, left: "50%", transform: "translateX(-50%)", zIndex: 2 }}>
          <div style={{ width: 1, height: 40, background: "linear-gradient(to bottom, rgba(122,107,98,0.5), transparent)", margin: "0 auto" }} />
        </div>
      </section>

      <section style={{ background: C.ink, padding: "0 56px 80px", display: "flex", justifyContent: "center", borderBottom: `1px solid ${C.ruleDark}` }}>
        <PlanWindow />
      </section>

      <section style={{ background: C.parchment, padding: "96px 56px", borderBottom: `1px solid ${C.ruleLight}` }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 52 }}>
          <span style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 13, color: C.terra, fontStyle: "italic" }}>I.</span>
          <h2 style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 30, fontWeight: 700, color: C.ink, letterSpacing: "-0.5px" }}>Everything a curriculum product needs.</h2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 56px" }}>
          {FEATURES.map(({ num, chapterLabel, title, desc, annotation, Illus }, idx) => (
            <div key={num} style={{ display: "grid", gridTemplateColumns: "52px 1fr", gap: 20, padding: "28px 0", borderBottom: idx < 4 ? `1px solid ${C.ruleLight}` : "none" }}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, paddingTop: 2 }}>
                <span style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 20, fontWeight: 700, color: C.terra, fontStyle: "italic", lineHeight: 1 }}>{num}</span>
                <Illus size={28} />
              </div>
              <div>
                <div style={{ position: "relative", padding: "6px 10px 6px 0", marginBottom: 10, borderRadius: 2, ...ruledBg }}>
                  <span style={{ position: "absolute", top: 2, right: 0, fontFamily: "var(--font-lora), Georgia, serif", fontSize: 9, fontStyle: "italic", color: C.terra, opacity: 0.45, letterSpacing: "0.5px" }}>{chapterLabel}</span>
                  <h3 style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 16, fontWeight: 700, color: C.ink, lineHeight: 1.4, position: "relative", zIndex: 1 }}>{title}</h3>
                </div>
                <p style={{ fontSize: 13, color: C.muted, lineHeight: 1.75 }}>{desc}</p>
                <span style={{ display: "inline-block", marginTop: 9, fontFamily: "var(--font-lora), Georgia, serif", fontSize: 11, fontStyle: "italic", color: C.terra, opacity: 0.65, borderBottom: `1px dashed rgba(191,78,48,0.35)`, paddingBottom: 1 }}>{annotation}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section id="how" style={{ background: C.parchmentMid, padding: "96px 56px", borderBottom: `1px solid ${C.ruleLight}`, display: "grid", gridTemplateColumns: "1fr 2fr", gap: 80, alignItems: "start" }}>
        <div style={{ position: "sticky", top: 100 }}>
          <span style={{ display: "block", fontFamily: "var(--font-lora), Georgia, serif", fontSize: 13, color: C.terra, fontStyle: "italic", marginBottom: 8 }}>II.</span>
          <h2 style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 30, fontWeight: 700, color: C.ink, letterSpacing: "-0.5px" }}>From request to classroom.</h2>
          <p style={{ fontSize: 14, color: C.muted, marginTop: 12, lineHeight: 1.7 }}>Three steps. No infrastructure to manage, no prompts to maintain.</p>
        </div>
        <div>
          {STEPS.map(({ num, title, desc, code }, i) => (
            <div key={num} style={{ display: "grid", gridTemplateColumns: "40px 1fr", gap: 20, padding: "32px 0", borderTop: i === 0 ? `1px solid ${C.ruleLight}` : undefined, borderBottom: `1px solid ${C.ruleLight}`, alignItems: "start" }}>
              <span style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 24, fontWeight: 700, color: C.terra, fontStyle: "italic", marginTop: 2 }}>{num}</span>
              <div>
                <h3 style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 18, fontWeight: 700, color: C.ink, marginBottom: 8 }}>{title}</h3>
                <p style={{ fontSize: 13, color: C.muted, lineHeight: 1.7 }}>{desc}</p>
                {code && (
                  <pre style={{ marginTop: 14, background: C.ink, border: `1px solid ${C.ruleDark}`, borderRadius: 6, padding: "14px 16px", fontFamily: "var(--font-geist-mono), monospace", fontSize: 11, color: C.mutedLight, lineHeight: 1.6, whiteSpace: "pre" }}>{code}</pre>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      <blockquote style={{ background: C.inkSoft, padding: "80px 56px", borderBottom: `1px solid ${C.ruleDark}`, display: "flex", gap: 40, alignItems: "center" }}>
        <span style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 120, color: C.terra, opacity: 0.25, lineHeight: 0.8, flexShrink: 0, marginTop: -10 }} aria-hidden="true">&ldquo;</span>
        <div>
          <p style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 24, fontStyle: "italic", color: C.parchment, lineHeight: 1.55, letterSpacing: "-0.3px" }}>
            A good lesson plan is not a script.<br />It is a{" "}<em style={{ color: C.terra, fontStyle: "normal" }}>map</em>{" "}— and every student takes a different path.
          </p>
          <p style={{ fontSize: 12, color: C.muted, marginTop: 16, letterSpacing: "0.5px", textTransform: "uppercase" }}>— Principle behind Dars</p>
        </div>
      </blockquote>

      <section style={{ background: C.parchment, padding: "96px 56px", textAlign: "center", position: "relative", overflow: "hidden" }}>
        {[{ size: 600, bottom: -200, border: C.ruleLight }, { size: 800, bottom: -280, border: C.parchmentDeep }].map(({ size, bottom, border }) => (
          <div key={size} style={{ position: "absolute", bottom, left: "50%", transform: "translateX(-50%)", width: size, height: size, borderRadius: "50%", border: `1px solid ${border}`, pointerEvents: "none" }} />
        ))}
        <h2 style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 44, fontWeight: 700, color: C.ink, letterSpacing: "-1px", lineHeight: 1.1, marginBottom: 16, position: "relative" }}>
          Build the lesson plan layer for{" "}<em style={{ color: C.terra, fontStyle: "italic" }}>your product.</em>
        </h2>
        <p style={{ fontSize: 16, color: C.muted, maxWidth: 380, margin: "0 auto 36px", lineHeight: 1.65, position: "relative" }}>Get API access and ship curriculum features in days, not months.</p>
        <a href="/login" style={{ background: C.terra, color: C.parchment, padding: "14px 30px", borderRadius: 6, fontSize: 15, fontWeight: 600, textDecoration: "none", position: "relative", display: "inline-block" }}>Get API access →</a>
      </section>

      <footer style={{ borderTop: `1px solid ${C.ruleLight}`, padding: "28px 56px", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, color: C.muted, background: C.parchmentMid }}>
        <div style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 16, fontWeight: 700, color: C.ink, display: "flex", alignItems: "baseline", gap: 9 }}>
          Dars <span style={{ color: C.terra, fontWeight: 400, fontSize: 13 }}>درس</span>
        </div>
        <div style={{ display: "flex", gap: 24 }}>
          {[["Docs", "/docs"], ["Privacy", "#"], ["Contact", "#"]].map(([label, href]) => (
            <a key={label} href={href} style={{ color: C.muted, textDecoration: "none" }}>{label}</a>
          ))}
        </div>
        <div>© 2025 Taleemabad</div>
      </footer>

    </main>
  );
}
