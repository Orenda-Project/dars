# Dars Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved Dars landing page design in Next.js, replacing the current placeholder homepage with the full multi-section layout.

**Architecture:** Single `page.tsx` for the landing route, a `globals.css` update to register Dars design tokens and import Georgia via `next/font`, and small focused components for the SVG illustrations and product window. No client-side JS needed — fully server-rendered.

**Tech Stack:** Next.js 16 (App Router), TypeScript, Tailwind CSS v4, `next/font/google` for serif font loading.

**Design reference:** `docs/superpowers/specs/2026-03-27-dars-landing-design.md`
**Approved HTML mockup:** `.superpowers/brainstorm/107634-1774623549/content/landing-v5.html`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `src/app/globals.css` | Modify | Add Dars CSS custom properties (colors, rule tokens) |
| `src/app/layout.tsx` | Modify | Load Georgia-equivalent serif via next/font, update metadata |
| `src/app/page.tsx` | Replace | Full landing page — all sections |
| `src/components/landing/illustrations.tsx` | Create | SVG illustration components for the 6 features |
| `src/components/landing/plan-window.tsx` | Create | The browser-chrome product mockup component |

---

## Task 1: Design tokens in globals.css

**Files:**
- Modify: `src/app/globals.css`

- [ ] **Step 1: Add Dars CSS custom properties to `:root`**

Open `src/app/globals.css`. After the existing `:root { ... }` block, append a new block (do not remove existing shadcn variables — they may be needed later):

```css
/* ── Dars design tokens ── */
:root {
  --dars-ink: #1c1410;
  --dars-ink-soft: #2c2420;
  --dars-parchment: #faf7f2;
  --dars-parchment-mid: #f0ebe3;
  --dars-parchment-deep: #e8dfd3;
  --dars-terra: #bf4e30;
  --dars-terra-light: #e8a07a;
  --dars-muted: #7a6b62;
  --dars-muted-light: #a89890;
  --dars-rule-dark: #2e2420;
  --dars-rule-light: #e0d5c8;
}
```

- [ ] **Step 2: Verify build still passes**

```bash
cd webapp && npm run build
```
Expected: exits 0, no type errors.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/app/globals.css
git commit -m "feat(webapp): add Dars design tokens to globals.css"
```

---

## Task 2: Layout — serif font + metadata

**Files:**
- Modify: `src/app/layout.tsx`

- [ ] **Step 1: Add Lora (Georgia-equivalent serif) via next/font and update metadata**

Replace the entire content of `src/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { Geist_Mono } from "next/font/google";
import { Lora } from "next/font/google";
import "./globals.css";

const lora = Lora({
  variable: "--font-lora",
  subsets: ["latin"],
  style: ["normal", "italic"],
  weight: ["400", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Dars — Lesson plan infrastructure",
  description:
    "Dars gives edtech teams a complete API for generating, storing, and rendering curriculum-aligned lesson plans — powered by AI, built to scale.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${lora.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
```

- [ ] **Step 2: Register the serif font variable in globals.css**

In `src/app/globals.css`, inside the `@theme inline { ... }` block, find:
```css
  --font-heading: var(--font-sans);
```
Replace with:
```css
  --font-heading: var(--font-lora);
  --font-serif: var(--font-lora);
  --font-mono: var(--font-geist-mono);
```

- [ ] **Step 3: Verify build passes**

```bash
cd webapp && npm run build
```
Expected: exits 0.

- [ ] **Step 4: Commit**

```bash
git add webapp/src/app/layout.tsx webapp/src/app/globals.css
git commit -m "feat(webapp): load Lora serif font, update page metadata"
```

---

## Task 3: Feature illustrations component

**Files:**
- Create: `src/components/landing/illustrations.tsx`

Each illustration is a small inline SVG. They all use ink stroke `#2c2420` and a single terracotta accent `#bf4e30`. `size` prop defaults to 28.

- [ ] **Step 1: Create the file**

```tsx
// src/components/landing/illustrations.tsx

interface IllusProps {
  size?: number;
}

export function IllusQuill({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
      <path
        d="M21 4C21 4 25 8 22 14L11 23L7 24L8 20L19 11C20 8 21 4 21 4Z"
        stroke="#2c2420"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <path d="M19 11L21 13" stroke="#2c2420" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="7" y1="24" x2="11" y2="24" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M17 7C19 6 21 5 22 5" stroke="#2c2420" strokeWidth="0.9" strokeLinecap="round" opacity="0.35" />
    </svg>
  );
}

export function IllusBooks({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
      <rect x="4" y="18" width="20" height="6" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="5" y="13" width="18" height="5" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="7" y="9" width="14" height="4" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <line x1="8" y1="18" x2="8" y2="24" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="11" y1="13" x2="11" y2="18" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" opacity="0.5" />
      <line x1="14" y1="9" x2="14" y2="13" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" opacity="0.28" />
    </svg>
  );
}

export function IllusOpenBook({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
      <path
        d="M14 4C11 4 6 6 5 9L5 24C6 22 11 21 14 21C17 21 22 22 23 24L23 9C22 6 17 4 14 4Z"
        stroke="#2c2420"
        strokeWidth="1.3"
      />
      <line x1="14" y1="4" x2="14" y2="21" stroke="#2c2420" strokeWidth="1.3" />
      <line x1="7" y1="12" x2="13" y2="13" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.45" />
      <line x1="7" y1="15" x2="13" y2="16" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.45" />
      <line x1="15" y1="13" x2="21" y2="12" stroke="#bf4e30" strokeWidth="1" strokeLinecap="round" opacity="0.7" />
      <line x1="15" y1="16" x2="21" y2="15" stroke="#bf4e30" strokeWidth="1" strokeLinecap="round" opacity="0.7" />
    </svg>
  );
}

export function IllusKey({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
      <circle cx="11" cy="12" r="6" stroke="#2c2420" strokeWidth="1.3" />
      <circle cx="11" cy="12" r="2.5" stroke="#bf4e30" strokeWidth="1.3" />
      <path d="M16 17L24 25" stroke="#2c2420" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="21" y1="22" x2="24" y2="19" stroke="#2c2420" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

export function IllusCompass({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
      <circle cx="14" cy="14" r="8" stroke="#2c2420" strokeWidth="1.3" strokeDasharray="2 2" />
      <path d="M12 17L14 11L16 17" stroke="#bf4e30" strokeWidth="1.3" fill="none" />
      <line x1="12.5" y1="15.5" x2="15.5" y2="15.5" stroke="#bf4e30" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="6" y1="24" x2="22" y2="6" stroke="#2c2420" strokeWidth="1.1" strokeLinecap="round" opacity="0.25" />
      <circle cx="14" cy="14" r="1.5" fill="#2c2420" />
    </svg>
  );
}

export function IllusComponents({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
      <rect x="2" y="16" width="10" height="9" rx="1.5" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="16" y="16" width="10" height="9" rx="1.5" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="9" y="4" width="10" height="9" rx="1.5" stroke="#bf4e30" strokeWidth="1.3" />
      <line x1="7" y1="16" x2="14" y2="13" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.4" />
      <line x1="21" y1="16" x2="14" y2="13" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.4" />
    </svg>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd webapp && npm run build
```
Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/landing/illustrations.tsx
git commit -m "feat(webapp): add landing page SVG illustration components"
```

---

## Task 4: Plan window component

**Files:**
- Create: `src/components/landing/plan-window.tsx`

This is the browser-chrome mockup shown below the hero.

- [ ] **Step 1: Create the file**

```tsx
// src/components/landing/plan-window.tsx

export function PlanWindow() {
  return (
    <div
      style={{
        width: "100%",
        maxWidth: 700,
        background: "#231c18",
        border: "1px solid #3a2e28",
        borderRadius: 10,
        overflow: "hidden",
        boxShadow: "0 40px 100px rgba(0,0,0,0.6)",
        transform: "translateY(-48px)",
      }}
    >
      {/* Window chrome */}
      <div
        style={{
          background: "#17110e",
          padding: "10px 16px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          borderBottom: "1px solid #2e2420",
        }}
      >
        <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#bf4e30", opacity: 0.6 }} />
        <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#c47a3a", opacity: 0.6 }} />
        <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#4a7c59", opacity: 0.6 }} />
        <div
          style={{
            flex: 1,
            background: "#2e2420",
            borderRadius: 4,
            padding: "4px 12px",
            fontSize: 11,
            color: "#5a4a42",
            fontFamily: "monospace",
            margin: "0 8px",
          }}
        >
          dars.taleemabad.com/dashboard
        </div>
      </div>

      {/* Window body */}
      <div style={{ display: "grid", gridTemplateColumns: "200px 1fr" }}>
        {/* Sidebar */}
        <div style={{ background: "#1a1410", borderRight: "1px solid #2e2420", padding: "20px 16px" }}>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "1.5px", textTransform: "uppercase", color: "#4a3830", marginBottom: 12 }}>
            My Plans
          </div>
          {[
            { label: "The Water Cycle", active: true },
            { label: "Fractions — Grade 5", active: false },
            { label: "Urdu Comprehension", active: false },
            { label: "Forces & Motion", active: false },
            { label: "Poetry Analysis", active: false },
          ].map(({ label, active }) => (
            <div
              key={label}
              style={{
                padding: "7px 10px",
                borderRadius: 5,
                fontSize: 12,
                color: active ? "#e8a07a" : "#6a5a52",
                fontWeight: active ? 600 : 400,
                marginBottom: 2,
                background: active ? "rgba(191,78,48,0.15)" : "transparent",
              }}
            >
              {active ? "▸ " : ""}{label}
            </div>
          ))}
        </div>

        {/* Main */}
        <div style={{ padding: "24px 28px" }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20, paddingBottom: 16, borderBottom: "1px solid #2e2420" }}>
            <div>
              <div style={{ fontFamily: "Georgia, serif", fontSize: 16, fontWeight: 700, color: "#faf7f2", marginBottom: 4 }}>
                The Water Cycle
              </div>
              <div style={{ fontSize: 11, color: "#6a5a52" }}>Grade 4 · Science · 45 min · Punjab Board</div>
            </div>
            <div style={{ fontSize: 10, fontWeight: 600, padding: "3px 9px", borderRadius: 20, background: "rgba(191,78,48,0.15)", color: "#e8a07a", whiteSpace: "nowrap" }}>
              AI Generated
            </div>
          </div>

          <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "1.5px", textTransform: "uppercase", color: "#e8a07a", marginBottom: 8 }}>
            Learning Objectives
          </div>
          {[
            "Identify and describe the stages of the water cycle",
            "Explain evaporation and condensation using examples",
            "Describe how precipitation forms and its effects",
          ].map((obj) => (
            <div key={obj} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#8a7a72", marginBottom: 5 }}>
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#bf4e30", opacity: 0.6, flexShrink: 0 }} />
              {obj}
            </div>
          ))}

          <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "1.5px", textTransform: "uppercase", color: "#e8a07a", marginBottom: 8, marginTop: 16 }}>
            Activities
          </div>
          {[
            { num: "i.", text: "Warm-up discussion — \"Where does rain come from?\"", dur: "5 min" },
            { num: "ii.", text: "Diagram labelling exercise", dur: "10 min" },
            { num: "iii.", text: "Group experiment — evaporation in a bag", dur: "20 min" },
            { num: "iv.", text: "Exit ticket — 3 facts learned today", dur: "5 min" },
          ].map(({ num, text, dur }) => (
            <div key={num} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", background: "#1a1410", borderRadius: 5, marginBottom: 4 }}>
              <span style={{ fontFamily: "Georgia, serif", fontSize: 12, color: "#bf4e30", fontStyle: "italic", minWidth: 20 }}>{num}</span>
              <span style={{ fontSize: 12, color: "#7a6a62" }}>{text}</span>
              <span style={{ fontSize: 10, color: "#4a3830", marginLeft: "auto" }}>{dur}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd webapp && npm run build
```
Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
git add webapp/src/components/landing/plan-window.tsx
git commit -m "feat(webapp): add PlanWindow product mockup component"
```

---

## Task 5: Main landing page

**Files:**
- Replace: `src/app/page.tsx`

This is the full page. It assembles all sections using the components from Tasks 3 and 4. We use inline `style` props for the design-token values (Tailwind v4 arbitrary values would work too, but inline styles are simpler for the one-off pixel-exact values from the design spec).

- [ ] **Step 1: Replace page.tsx**

```tsx
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

// ── Shared style constants ────────────────────────────────────────────────
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

// ── Feature data ──────────────────────────────────────────────────────────
const FEATURES = [
  {
    num: "i.",
    chapterLabel: "ch. i",
    title: "AI Generation",
    desc: "One API call returns a complete, structured lesson plan — objectives, activities, assessment. Specify grade, subject, topic, duration.",
    annotation: "See also: structured output →",
    Illus: IllusQuill,
  },
  {
    num: "ii.",
    chapterLabel: "ch. ii",
    title: "Versioned Storage",
    desc: "Every plan is stored, versioned, and retrievable — like a library catalogue. Build edit flows, approvals, or history views on top.",
    annotation: "cf. library card catalogue",
    Illus: IllusBooks,
  },
  {
    num: "iii.",
    chapterLabel: "ch. iii",
    title: "Structured Output",
    desc: "Plans return as clean JSON or pre-rendered HTML — like a typeset document, ready to publish. No prompt engineering required.",
    annotation: "render-ready, always",
    Illus: IllusOpenBook,
  },
  {
    num: "iv.",
    chapterLabel: "ch. iv",
    title: "API Key Auth",
    desc: "Per-client keys with scoped access and usage tracking. Like a library card — each institution gets their own, with their own catalogue.",
    annotation: "hashed, shown once on creation",
    Illus: IllusKey,
  },
  {
    num: "v.",
    chapterLabel: "ch. v",
    title: "Curriculum Alignment",
    desc: "Pass your curriculum spec and Dars maps plans to your learning standards — not generic internet content.",
    annotation: "Punjab Board, AKU, custom specs",
    Illus: IllusCompass,
  },
  {
    num: "vi.",
    chapterLabel: "ch. vi",
    title: "React Components",
    desc: "Drop-in @dars/react components for rendering and editing plans in your UI.",
    annotation: "npm install @dars/react",
    Illus: IllusComponents,
  },
];

// ── Steps data ────────────────────────────────────────────────────────────
const STEPS = [
  {
    num: "i.",
    title: "Connect your product",
    desc: "Get an API key from the dashboard. Point your backend at the Dars endpoint. Works with any language or framework over REST.",
    code: `POST /api/v1/lesson-plans\nX-API-Key: drs_live_••••••••`,
  },
  {
    num: "ii.",
    title: "Request a lesson plan",
    desc: "Pass grade, subject, topic, duration, and any curriculum constraints. Dars generates a structured, aligned plan in seconds.",
    code: `{\n  "grade": "4",\n  "subject": "Science",\n  "topic": "The Water Cycle",\n  "duration_minutes": 45\n}`,
  },
  {
    num: "iii.",
    title: "Render it your way",
    desc: "Get back structured JSON or pre-rendered HTML. Use the Dars React components, or build your own UI on top of the clean data model.",
    code: null,
  },
];

// ── Ruled heading background (notebook paper lines) ───────────────────────
const ruledBg = {
  backgroundImage:
    "repeating-linear-gradient(to bottom, transparent, transparent 19px, rgba(208,195,180,0.45) 19px, rgba(208,195,180,0.45) 20px)",
  backgroundSize: "100% 20px",
} as const;

// ── Page ──────────────────────────────────────────────────────────────────
export default function Home() {
  return (
    <main style={{ background: C.parchment, color: C.ink }}>

      {/* ── NAV ── */}
      <nav style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "22px 56px", borderBottom: `1px solid ${C.ruleDark}`,
        position: "sticky", top: 0,
        background: "rgba(28,20,16,0.96)", backdropFilter: "blur(8px)",
        zIndex: 100,
      }}>
        <div style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 19, fontWeight: 700, color: C.parchment, display: "flex", alignItems: "baseline", gap: 9 }}>
          Dars <span style={{ color: C.terra, fontWeight: 400, fontSize: 15 }}>درس</span>
        </div>
        <div style={{ display: "flex", gap: 32, alignItems: "center", fontSize: 13, color: C.mutedLight }}>
          <a href="/docs" style={{ color: "inherit", textDecoration: "none" }}>Docs</a>
          <a href="/docs" style={{ color: "inherit", textDecoration: "none" }}>API</a>
          <a href="#" style={{ color: "inherit", textDecoration: "none" }}>Pricing</a>
          <a href="/login" style={{ background: C.terra, color: C.parchment, padding: "8px 18px", borderRadius: 5, fontSize: 13, fontWeight: 600, textDecoration: "none" }}>
            Get access
          </a>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section style={{
        background: C.ink, minHeight: "92vh",
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        textAlign: "center", padding: "80px 56px",
        position: "relative", overflow: "hidden",
        borderBottom: `1px solid ${C.ruleDark}`,
      }}>
        {/* Open book watermark */}
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <svg width={720} height={720} viewBox="0 0 200 200" fill="none" style={{ opacity: 0.045 }}>
            <path d="M100 30 C70 30 30 40 20 60 L20 170 C30 150 70 140 100 140 C130 140 170 150 180 170 L180 60 C170 40 130 30 100 30Z" stroke="white" strokeWidth="1.5" />
            <line x1="100" y1="30" x2="100" y2="140" stroke="white" strokeWidth="1.5" />
            {[75,90,105,120].map((y, i) => (
              <>
                <line key={`l${i}`} x1="30" y1={y} x2="95" y2={y+5} stroke="white" strokeWidth="1" />
                <line key={`r${i}`} x1="105" y1={y+5} x2="170" y2={y} stroke="white" strokeWidth="1" />
              </>
            ))}
          </svg>
        </div>
        {/* Concentric rings */}
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", display: "flex", alignItems: "center", justifyContent: "center" }}>
          {[320, 520, 740, 980].map((size, i) => (
            <div key={size} style={{
              position: "absolute", borderRadius: "50%",
              width: size, height: size,
              border: `1px solid rgba(191,78,48,${[0.12,0.07,0.04,0.025][i]})`,
            }} />
          ))}
        </div>

        {/* Eyebrow */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
          fontSize: 11, fontWeight: 700, letterSpacing: "2px", color: C.terra,
          textTransform: "uppercase", marginBottom: 28, position: "relative", zIndex: 2,
        }}>
          <span style={{ display: "inline-block", width: 32, height: 1, background: C.terra, opacity: 0.6 }} />
          Lesson plan infrastructure
          <span style={{ display: "inline-block", width: 32, height: 1, background: C.terra, opacity: 0.6 }} />
        </div>

        <h1 style={{
          fontFamily: "var(--font-lora), Georgia, serif",
          fontSize: 68, fontWeight: 700, lineHeight: 1.05,
          letterSpacing: "-2px", color: C.parchment,
          marginBottom: 28, position: "relative", zIndex: 2, maxWidth: 820,
        }}>
          The platform behind{" "}
          <em style={{ fontStyle: "italic", color: C.terra }}>great teaching.</em>
        </h1>

        <p style={{
          fontSize: 18, color: C.mutedLight, lineHeight: 1.7,
          maxWidth: 480, margin: "0 auto 44px", position: "relative", zIndex: 2,
        }}>
          Dars gives edtech teams a complete API for generating, storing, and rendering
          curriculum-aligned lesson plans — powered by AI, built to scale.
        </p>

        <div style={{ display: "flex", gap: 14, alignItems: "center", justifyContent: "center", position: "relative", zIndex: 2 }}>
          <a href="/docs" style={{ background: C.terra, color: C.parchment, padding: "13px 28px", borderRadius: 6, fontSize: 14, fontWeight: 600, textDecoration: "none" }}>
            Read the docs →
          </a>
          <a href="#how" style={{ color: C.mutedLight, fontSize: 13, textDecoration: "none", borderBottom: `1px solid ${C.ruleDark}`, paddingBottom: 2 }}>
            See how it works
          </a>
        </div>

        {/* Scroll hint */}
        <div style={{ position: "absolute", bottom: 32, left: "50%", transform: "translateX(-50%)", zIndex: 2 }}>
          <div style={{ width: 1, height: 40, background: "linear-gradient(to bottom, rgba(122,107,98,0.5), transparent)", margin: "0 auto" }} />
        </div>
      </section>

      {/* ── PLAN PREVIEW ── */}
      <section style={{ background: C.ink, padding: "0 56px 80px", display: "flex", justifyContent: "center", borderBottom: `1px solid ${C.ruleDark}` }}>
        <PlanWindow />
      </section>

      {/* ── FEATURES ── */}
      <section style={{ background: C.parchment, padding: "96px 56px", borderBottom: `1px solid ${C.ruleLight}` }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 52 }}>
          <span style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 13, color: C.terra, fontStyle: "italic" }}>I.</span>
          <h2 style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 30, fontWeight: 700, color: C.ink, letterSpacing: "-0.5px" }}>
            Everything a curriculum product needs.
          </h2>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 56px" }}>
          {FEATURES.map(({ num, chapterLabel, title, desc, annotation, Illus }) => (
            <div key={num} style={{
              display: "grid", gridTemplateColumns: "52px 1fr", gap: 20,
              padding: "28px 0", borderBottom: `1px solid ${C.ruleLight}`,
            }}>
              {/* Margin */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, paddingTop: 2 }}>
                <span style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 20, fontWeight: 700, color: C.terra, fontStyle: "italic", lineHeight: 1 }}>
                  {num}
                </span>
                <Illus size={28} />
              </div>
              {/* Content */}
              <div>
                <div style={{ position: "relative", padding: "6px 10px 6px 0", marginBottom: 10, borderRadius: 2, ...ruledBg }}>
                  <span style={{
                    position: "absolute", top: 2, right: 0,
                    fontFamily: "var(--font-lora), Georgia, serif", fontSize: 9,
                    fontStyle: "italic", color: C.terra, opacity: 0.45, letterSpacing: "0.5px",
                  }}>
                    {chapterLabel}
                  </span>
                  <h3 style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 16, fontWeight: 700, color: C.ink, lineHeight: 1.4, position: "relative", zIndex: 1 }}>
                    {title}
                  </h3>
                </div>
                <p style={{ fontSize: 13, color: C.muted, lineHeight: 1.75 }}>{desc}</p>
                <span style={{
                  display: "inline-block", marginTop: 9,
                  fontFamily: "var(--font-lora), Georgia, serif", fontSize: 11,
                  fontStyle: "italic", color: C.terra, opacity: 0.65,
                  borderBottom: `1px dashed rgba(191,78,48,0.35)`, paddingBottom: 1,
                }}>
                  {annotation}
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section id="how" style={{ background: C.parchmentMid, padding: "96px 56px", borderBottom: `1px solid ${C.ruleLight}`, display: "grid", gridTemplateColumns: "1fr 2fr", gap: 80, alignItems: "start" }}>
        <div style={{ position: "sticky", top: 100 }}>
          <span style={{ display: "block", fontFamily: "var(--font-lora), Georgia, serif", fontSize: 13, color: C.terra, fontStyle: "italic", marginBottom: 8 }}>II.</span>
          <h2 style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 30, fontWeight: 700, color: C.ink, letterSpacing: "-0.5px" }}>
            From request to classroom.
          </h2>
          <p style={{ fontSize: 14, color: C.muted, marginTop: 12, lineHeight: 1.7 }}>
            Three steps. No infrastructure to manage, no prompts to maintain.
          </p>
        </div>

        <div>
          {STEPS.map(({ num, title, desc, code }, i) => (
            <div key={num} style={{
              display: "grid", gridTemplateColumns: "40px 1fr", gap: 20,
              padding: "32px 0",
              borderTop: i === 0 ? `1px solid ${C.ruleLight}` : undefined,
              borderBottom: `1px solid ${C.ruleLight}`,
              alignItems: "start",
            }}>
              <span style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 24, fontWeight: 700, color: C.terra, fontStyle: "italic", marginTop: 2 }}>
                {num}
              </span>
              <div>
                <h3 style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 18, fontWeight: 700, color: C.ink, marginBottom: 8 }}>{title}</h3>
                <p style={{ fontSize: 13, color: C.muted, lineHeight: 1.7 }}>{desc}</p>
                {code && (
                  <pre style={{
                    marginTop: 14, background: C.ink, border: `1px solid ${C.ruleDark}`,
                    borderRadius: 6, padding: "14px 16px",
                    fontFamily: "var(--font-geist-mono), monospace", fontSize: 11,
                    color: C.mutedLight, lineHeight: 1.6, whiteSpace: "pre",
                  }}>
                    {code}
                  </pre>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── QUOTE ── */}
      <div style={{
        background: C.inkSoft, padding: "80px 56px",
        borderBottom: `1px solid ${C.ruleDark}`,
        display: "flex", gap: 40, alignItems: "center",
      }}>
        <span style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 120, color: C.terra, opacity: 0.25, lineHeight: 0.8, flexShrink: 0, marginTop: -10 }}>
          &ldquo;
        </span>
        <div>
          <p style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 24, fontStyle: "italic", color: C.parchment, lineHeight: 1.55, letterSpacing: "-0.3px" }}>
            A good lesson plan is not a script.<br />
            It is a{" "}
            <em style={{ color: C.terra, fontStyle: "normal" }}>map</em>
            {" "}— and every student takes a different path.
          </p>
          <p style={{ fontSize: 12, color: C.muted, marginTop: 16, letterSpacing: "0.5px", textTransform: "uppercase" }}>
            — Principle behind Dars
          </p>
        </div>
      </div>

      {/* ── CTA ── */}
      <section style={{ background: C.parchment, padding: "96px 56px", textAlign: "center", position: "relative", overflow: "hidden" }}>
        {[600, 800].map((size) => (
          <div key={size} style={{
            position: "absolute", bottom: -200 - (size - 600) * 0.4, left: "50%", transform: "translateX(-50%)",
            width: size, height: size, borderRadius: "50%",
            border: `1px solid ${size === 600 ? C.ruleLight : C.parchmentDeep}`,
            pointerEvents: "none",
          }} />
        ))}
        <h2 style={{ fontFamily: "var(--font-lora), Georgia, serif", fontSize: 44, fontWeight: 700, color: C.ink, letterSpacing: "-1px", lineHeight: 1.1, marginBottom: 16, position: "relative" }}>
          Build the lesson plan layer for{" "}
          <em style={{ color: C.terra, fontStyle: "italic" }}>your product.</em>
        </h2>
        <p style={{ fontSize: 16, color: C.muted, maxWidth: 380, margin: "0 auto 36px", lineHeight: 1.65, position: "relative" }}>
          Get API access and ship curriculum features in days, not months.
        </p>
        <a href="/login" style={{ background: C.terra, color: C.parchment, padding: "14px 30px", borderRadius: 6, fontSize: 15, fontWeight: 600, textDecoration: "none", position: "relative", display: "inline-block" }}>
          Get API access →
        </a>
      </section>

      {/* ── FOOTER ── */}
      <footer style={{
        borderTop: `1px solid ${C.ruleLight}`, padding: "28px 56px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        fontSize: 12, color: C.muted, background: C.parchmentMid,
      }}>
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
```

- [ ] **Step 2: Run build to catch type errors**

```bash
cd webapp && npm run build
```
Expected: exits 0, no TypeScript errors.

- [ ] **Step 3: Run dev server and visually verify**

```bash
make webapp
```

Open `http://localhost:3000`. Check each section:
- Nav is sticky, dark, terracotta "Get access" button
- Hero: centered text, rings visible, book watermark behind
- Plan window floats up from hero
- Features: 2-column, Roman numerals in margin, ruled heading bg, italic annotations
- How it works: sticky left column, dark code blocks, Roman numeral steps
- Quote: large `"` mark, terracotta `map`
- CTA: concentric rings, terracotta button
- Footer: parchment-mid bg

- [ ] **Step 4: Commit**

```bash
git add webapp/src/app/page.tsx
git commit -m "feat(webapp): implement Dars landing page"
```

---

## Self-Review

**Spec coverage:**
- ✅ Color palette — all tokens registered in globals.css (Task 1) and `C` constant (Task 5)
- ✅ Typography — Lora serif loaded (Task 2), applied via `var(--font-lora)` throughout
- ✅ Section rhythm dark/light/dark — implemented in order
- ✅ Illustrations — all 6 SVG components (Task 3)
- ✅ Hero centered with rings and watermark
- ✅ Plan window (Task 4)
- ✅ Manuscript marginalia features with ruled heading bg
- ✅ Roman numerals throughout (i.–vi., I.–II.)
- ✅ How it works sticky left, dark code blocks
- ✅ Quote section
- ✅ CTA with rings
- ✅ Footer

**Placeholder scan:** None found — all steps contain complete code.

**Type consistency:**
- `IllusQuill`, `IllusBooks`, etc. defined in Task 3, imported by name in Task 5 ✅
- `PlanWindow` defined in Task 4, imported in Task 5 ✅
- `C` constant defined once at top of page.tsx, referenced throughout ✅
- `FEATURES[].Illus` typed as component, called as `<Illus size={28} />` ✅
