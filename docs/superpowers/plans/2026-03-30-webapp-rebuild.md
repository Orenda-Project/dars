# Webapp Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken `webapp/` with a clean `create-next-app` scaffold and recreate the Dars landing page with identical sections, copy, and visual design.

**Architecture:** Scaffold with `create-next-app` (TypeScript, Tailwind v4, App Router, no src/ dir), then layer on the Dars design system (CSS tokens in `globals.css`) and rebuild components bottom-up: atoms → molecules → template → page.

**Tech Stack:** Next.js 16, React 19, TypeScript 5, Tailwind CSS v4, `@tailwindcss/postcss`, Lora + Geist Mono (next/font), no shadcn required for this page.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `webapp/` | Create (scaffold) | New standalone Next.js project |
| `webapp/app/globals.css` | Replace | Tailwind import + all Dars CSS tokens |
| `webapp/app/layout.tsx` | Replace | Lora + Geist Mono fonts, metadata |
| `webapp/app/page.tsx` | Replace | Renders `<LandingTemplate />` |
| `webapp/components/atoms/logo.tsx` | Create | Dars wordmark with Urdu subtitle |
| `webapp/components/atoms/eyebrow.tsx` | Create | Section label with flanking dashes |
| `webapp/components/atoms/rule.tsx` | Create | `<hr>` with light/dark variants |
| `webapp/components/atoms/illustrations/illus-quill.tsx` | Create | SVG quill illustration |
| `webapp/components/atoms/illustrations/illus-books.tsx` | Create | SVG books illustration |
| `webapp/components/atoms/illustrations/illus-open-book.tsx` | Create | SVG open book illustration |
| `webapp/components/atoms/illustrations/illus-key.tsx` | Create | SVG key illustration |
| `webapp/components/atoms/illustrations/illus-compass.tsx` | Create | SVG compass illustration |
| `webapp/components/atoms/illustrations/illus-components.tsx` | Create | SVG components illustration |
| `webapp/components/atoms/illustrations/index.ts` | Create | Re-exports all illustrations |
| `webapp/components/atoms/index.ts` | Create | Re-exports all atoms |
| `webapp/components/molecules/nav-bar.tsx` | Create | Sticky dark navbar with logo + CTA |
| `webapp/components/molecules/plan-window.tsx` | Create | Browser chrome mockup |
| `webapp/components/molecules/feature-card.tsx` | Create | Feature card with ruled-paper heading |
| `webapp/components/molecules/step-item.tsx` | Create | Numbered step with optional code block |
| `webapp/components/templates/landing-template.tsx` | Create | Full landing page, all sections |
| `webapp/CLAUDE.md` | Create | Frontend conventions carried over from archive |
| `webapp/.gitignore` | Modify | Ensure `.superpowers/` is ignored |

---

## Task 1: Archive old webapp and scaffold new one

**Files:**
- Rename: `webapp/` → `webapp-archive/`
- Create: `webapp/` (via create-next-app)

- [ ] **Step 1: Rename old webapp to archive**

```bash
cd /home/hataf/taleemabad/dars
mv webapp webapp-archive
```

- [ ] **Step 2: Scaffold new webapp**

Run interactively — answer the prompts exactly as shown:

```bash
cd /home/hataf/taleemabad/dars
npx create-next-app@latest webapp
```

Prompts — answer exactly:
```
Would you like to use TypeScript? › Yes
Would you like to use ESLint? › Yes
Would you like to use Tailwind CSS? › Yes
Would you like your code inside a `src/` directory? › No
Would you like to use App Router? › Yes
Would you like to use Turbopack for `next dev`? › Yes
Would you like to customize the import alias? › No
```

- [ ] **Step 3: Verify dev server starts**

```bash
cd /home/hataf/taleemabad/dars/webapp
npm run dev
```

Expected: server starts at `http://localhost:3000` with no errors. Ctrl+C to stop.

- [ ] **Step 4: Commit**

```bash
cd /home/hataf/taleemabad/dars
git add webapp-archive webapp
git commit -m "chore(webapp): archive old webapp, scaffold fresh create-next-app"
```

---

## Task 2: Install design system — globals.css and layout

**Files:**
- Modify: `webapp/app/globals.css`
- Modify: `webapp/app/layout.tsx`

- [ ] **Step 1: Replace globals.css**

Replace `webapp/app/globals.css` with:

```css
@import "tailwindcss";
@import "tw-animate-css";

@theme {
  --color-dars-ink: #1c1410;
  --color-dars-ink-soft: #2c2420;
  --color-dars-parchment: #faf7f2;
  --color-dars-parchment-mid: #f0ebe3;
  --color-dars-parchment-deep: #e8dfd3;
  --color-dars-terra: #bf4e30;
  --color-dars-terra-light: #e8a07a;
  --color-dars-muted: #7a6b62;
  --color-dars-muted-light: #a89890;
  --color-dars-rule-dark: #2e2420;
  --color-dars-rule-light: #e0d5c8;

  --font-serif: var(--font-lora), Georgia, serif;
  --font-mono: var(--font-geist-mono), ui-monospace, monospace;
}

@layer base {
  * {
    @apply border-border outline-ring/50;
  }
  body {
    @apply bg-background text-foreground;
  }
  html {
    @apply font-sans;
  }
}
```

- [ ] **Step 2: Install tw-animate-css**

```bash
cd /home/hataf/taleemabad/dars/webapp
npm install tw-animate-css
```

- [ ] **Step 3: Replace layout.tsx**

Replace `webapp/app/layout.tsx` with:

```typescript
import type { Metadata } from "next";
import { Geist_Mono, Lora } from "next/font/google";
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

- [ ] **Step 4: Verify dev server still starts with no errors**

```bash
cd /home/hataf/taleemabad/dars/webapp
npm run dev
```

Expected: starts cleanly, no Tailwind resolution errors.

- [ ] **Step 5: Commit**

```bash
cd /home/hataf/taleemabad/dars/webapp
git add app/globals.css app/layout.tsx package.json package-lock.json
git commit -m "feat(webapp): install Dars design tokens and fonts"
```

---

## Task 3: Build atoms

**Files:**
- Create: `webapp/components/atoms/logo.tsx`
- Create: `webapp/components/atoms/eyebrow.tsx`
- Create: `webapp/components/atoms/rule.tsx`
- Create: `webapp/components/atoms/index.ts`

- [ ] **Step 1: Create `components/atoms/logo.tsx`**

```typescript
interface LogoProps {
  variant?: "light" | "dark";
  size?: "sm" | "md";
}

export function Logo({ variant = "dark", size = "md" }: LogoProps) {
  const nameColor = variant === "light" ? "text-dars-parchment" : "text-dars-ink";
  const textSize = size === "sm" ? "text-base" : "text-lg";

  return (
    <div className={`font-serif font-bold flex items-baseline gap-2 ${textSize} ${nameColor}`}>
      Dars{" "}
      <span className="text-dars-terra font-normal text-sm">درس</span>
    </div>
  );
}
```

- [ ] **Step 2: Create `components/atoms/eyebrow.tsx`**

```typescript
import type { ReactNode } from "react";

interface EyebrowProps {
  children: ReactNode;
  className?: string;
}

export function Eyebrow({ children, className = "" }: EyebrowProps) {
  return (
    <div className={`flex items-center justify-center gap-2.5 text-[11px] font-bold tracking-[2px] text-dars-terra uppercase ${className}`}>
      <span className="inline-block w-8 h-px bg-dars-terra opacity-60" />
      {children}
      <span className="inline-block w-8 h-px bg-dars-terra opacity-60" />
    </div>
  );
}
```

- [ ] **Step 3: Create `components/atoms/rule.tsx`**

```typescript
interface RuleProps {
  variant?: "light" | "dark";
  className?: string;
}

export function Rule({ variant = "light", className = "" }: RuleProps) {
  const color = variant === "dark" ? "border-dars-rule-dark" : "border-dars-rule-light";
  return <hr className={`border-t ${color} ${className}`} />;
}
```

- [ ] **Step 4: Create `components/atoms/index.ts`**

```typescript
export { Logo } from "./logo";
export { Eyebrow } from "./eyebrow";
export { Rule } from "./rule";
export * from "./illustrations";
```

- [ ] **Step 5: Commit**

```bash
cd /home/hataf/taleemabad/dars/webapp
git add components/atoms/
git commit -m "feat(webapp): add Logo, Eyebrow, Rule atoms"
```

---

## Task 4: Build illustration atoms

**Files:**
- Create: `webapp/components/atoms/illustrations/illus-quill.tsx`
- Create: `webapp/components/atoms/illustrations/illus-books.tsx`
- Create: `webapp/components/atoms/illustrations/illus-open-book.tsx`
- Create: `webapp/components/atoms/illustrations/illus-key.tsx`
- Create: `webapp/components/atoms/illustrations/illus-compass.tsx`
- Create: `webapp/components/atoms/illustrations/illus-components.tsx`
- Create: `webapp/components/atoms/illustrations/index.ts`

- [ ] **Step 1: Create `illus-quill.tsx`**

```typescript
interface IllusProps {
  size?: number;
}

export function IllusQuill({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
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
```

- [ ] **Step 2: Create `illus-books.tsx`**

```typescript
interface IllusProps {
  size?: number;
}

export function IllusBooks({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <rect x="4" y="18" width="20" height="6" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="5" y="13" width="18" height="5" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="7" y="9" width="14" height="4" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <line x1="8" y1="18" x2="8" y2="24" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="11" y1="13" x2="11" y2="18" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" opacity="0.5" />
      <line x1="14" y1="9" x2="14" y2="13" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" opacity="0.28" />
    </svg>
  );
}
```

- [ ] **Step 3: Create `illus-open-book.tsx`**

```typescript
interface IllusProps {
  size?: number;
}

export function IllusOpenBook({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
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
```

- [ ] **Step 4: Create `illus-key.tsx`**

```typescript
interface IllusProps {
  size?: number;
}

export function IllusKey({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <circle cx="11" cy="12" r="6" stroke="#2c2420" strokeWidth="1.3" />
      <circle cx="11" cy="12" r="2.5" stroke="#bf4e30" strokeWidth="1.3" />
      <path d="M16 17L24 25" stroke="#2c2420" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="21" y1="22" x2="24" y2="19" stroke="#2c2420" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}
```

- [ ] **Step 5: Create `illus-compass.tsx`**

```typescript
interface IllusProps {
  size?: number;
}

export function IllusCompass({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <circle cx="14" cy="14" r="8" stroke="#2c2420" strokeWidth="1.3" strokeDasharray="2 2" />
      <path d="M12 17L14 11L16 17" stroke="#bf4e30" strokeWidth="1.3" fill="none" />
      <line x1="12.5" y1="15.5" x2="15.5" y2="15.5" stroke="#bf4e30" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="6" y1="24" x2="22" y2="6" stroke="#2c2420" strokeWidth="1.1" strokeLinecap="round" opacity="0.25" />
      <circle cx="14" cy="14" r="1.5" fill="#2c2420" />
    </svg>
  );
}
```

- [ ] **Step 6: Create `illus-components.tsx`**

```typescript
interface IllusProps {
  size?: number;
}

export function IllusComponents({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <rect x="2" y="16" width="10" height="9" rx="1.5" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="16" y="16" width="10" height="9" rx="1.5" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="9" y="4" width="10" height="9" rx="1.5" stroke="#bf4e30" strokeWidth="1.3" />
      <line x1="7" y1="16" x2="14" y2="13" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.4" />
      <line x1="21" y1="16" x2="14" y2="13" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.4" />
    </svg>
  );
}
```

- [ ] **Step 7: Create `illustrations/index.ts`**

```typescript
export { IllusQuill } from "./illus-quill";
export { IllusBooks } from "./illus-books";
export { IllusOpenBook } from "./illus-open-book";
export { IllusKey } from "./illus-key";
export { IllusCompass } from "./illus-compass";
export { IllusComponents } from "./illus-components";
```

- [ ] **Step 8: Commit**

```bash
cd /home/hataf/taleemabad/dars/webapp
git add components/atoms/illustrations/
git commit -m "feat(webapp): add six SVG illustration atoms"
```

---

## Task 5: Build molecules

**Files:**
- Create: `webapp/components/molecules/nav-bar.tsx`
- Create: `webapp/components/molecules/plan-window.tsx`
- Create: `webapp/components/molecules/feature-card.tsx`
- Create: `webapp/components/molecules/step-item.tsx`

- [ ] **Step 1: Create `components/molecules/nav-bar.tsx`**

```typescript
import { Logo } from "@/components/atoms/logo";

const NAV_LINKS = [
  { label: "Docs", href: "/docs" },
  { label: "API", href: "/docs" },
  { label: "Pricing", href: "#" },
];

export function NavBar() {
  return (
    <nav className="flex justify-between items-center px-14 py-[22px] border-b border-dars-rule-dark sticky top-0 bg-dars-ink/[0.96] backdrop-blur-sm z-[100] sm:px-6">
      <Logo variant="light" />
      <div className="flex gap-8 items-center text-[13px] text-dars-muted-light sm:gap-4">
        {NAV_LINKS.map(({ label, href }) => (
          <a
            key={label}
            href={href}
            className="text-inherit no-underline hover:text-dars-parchment transition-colors hidden sm:block"
          >
            {label}
          </a>
        ))}
        <a
          href="/login"
          className="bg-dars-terra text-dars-parchment px-[18px] py-2 rounded-md text-[13px] font-semibold no-underline hover:opacity-90 transition-opacity"
        >
          Get access
        </a>
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: Create `components/molecules/plan-window.tsx`**

```typescript
export function PlanWindow() {
  return (
    <div
      className="w-full max-w-[700px] rounded-[10px] overflow-hidden -translate-y-12 sm:-translate-y-6"
      style={{
        background: "#231c18",
        border: "1px solid #3a2e28",
        boxShadow: "0 40px 100px rgba(0,0,0,0.6)",
      }}
    >
      {/* Window chrome */}
      <div
        className="flex items-center gap-2 px-4 py-2.5 border-b"
        style={{ background: "#17110e", borderColor: "#2e2420" }}
      >
        <div className="w-2.5 h-2.5 rounded-full bg-dars-terra opacity-60" />
        <div className="w-2.5 h-2.5 rounded-full opacity-60" style={{ background: "#c47a3a" }} />
        <div className="w-2.5 h-2.5 rounded-full opacity-60" style={{ background: "#4a7c59" }} />
        <div
          className="flex-1 rounded px-3 py-1 text-[11px] font-mono mx-2 hidden sm:block"
          style={{ background: "#2e2420", color: "#5a4a42" }}
        >
          dars.taleemabad.com/dashboard
        </div>
      </div>

      {/* Window body */}
      <div className="grid grid-cols-1 sm:grid-cols-[200px_1fr]">
        {/* Sidebar — hidden on mobile */}
        <div
          className="border-r p-5 hidden sm:block"
          style={{ background: "#1a1410", borderColor: "#2e2420" }}
        >
          <div className="text-[10px] font-bold tracking-[1.5px] uppercase mb-3" style={{ color: "#4a3830" }}>
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
              className="px-2.5 py-[7px] rounded-md text-[12px] mb-0.5"
              style={{
                color: active ? "#e8a07a" : "#6a5a52",
                fontWeight: active ? 600 : 400,
                background: active ? "rgba(191,78,48,0.15)" : "transparent",
              }}
            >
              {active ? "▸ " : ""}{label}
            </div>
          ))}
        </div>

        {/* Main content */}
        <div className="p-6 sm:p-4">
          <div
            className="flex items-start justify-between mb-5 pb-4 border-b"
            style={{ borderColor: "#2e2420" }}
          >
            <div>
              <div className="font-serif text-base font-bold mb-1" style={{ color: "#faf7f2" }}>
                The Water Cycle
              </div>
              <div className="text-[11px]" style={{ color: "#6a5a52" }}>
                Grade 4 · Science · 45 min · Punjab Board
              </div>
            </div>
            <div
              className="text-[10px] font-semibold px-2 py-[3px] rounded-full whitespace-nowrap"
              style={{ background: "rgba(191,78,48,0.15)", color: "#e8a07a" }}
            >
              AI Generated
            </div>
          </div>

          <div className="text-[9px] font-bold tracking-[1.5px] uppercase mb-2" style={{ color: "#e8a07a" }}>
            Learning Objectives
          </div>
          {[
            "Identify and describe the stages of the water cycle",
            "Explain evaporation and condensation using examples",
            "Describe how precipitation forms and its effects",
          ].map((obj) => (
            <div key={obj} className="flex items-center gap-2 text-[12px] mb-1.5" style={{ color: "#8a7a72" }}>
              <div className="w-[5px] h-[5px] rounded-full flex-shrink-0 bg-dars-terra opacity-60" />
              {obj}
            </div>
          ))}

          <div className="text-[9px] font-bold tracking-[1.5px] uppercase mb-2 mt-4" style={{ color: "#e8a07a" }}>
            Activities
          </div>
          {[
            { num: "i.", text: "Warm-up discussion — \"Where does rain come from?\"", dur: "5 min" },
            { num: "ii.", text: "Diagram labelling exercise", dur: "10 min" },
            { num: "iii.", text: "Group experiment — evaporation in a bag", dur: "20 min" },
            { num: "iv.", text: "Exit ticket — 3 facts learned today", dur: "5 min" },
          ].map(({ num, text, dur }) => (
            <div
              key={num}
              className="flex items-center gap-2.5 px-2.5 py-2 rounded-md mb-1"
              style={{ background: "#1a1410" }}
            >
              <span className="font-serif text-[12px] italic min-w-[20px]" style={{ color: "#bf4e30" }}>{num}</span>
              <span className="text-[12px] truncate" style={{ color: "#7a6a62" }}>{text}</span>
              <span className="text-[10px] ml-auto flex-shrink-0" style={{ color: "#4a3830" }}>{dur}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `components/molecules/feature-card.tsx`**

```typescript
import type { ComponentType } from "react";

const ruledBg = {
  backgroundImage:
    "repeating-linear-gradient(to bottom, transparent, transparent 19px, rgba(208,195,180,0.45) 19px, rgba(208,195,180,0.45) 20px)",
  backgroundSize: "100% 20px",
} as const;

interface FeatureCardProps {
  num: string;
  chapterLabel: string;
  title: string;
  desc: string;
  annotation: string;
  Illus: ComponentType<{ size?: number }>;
  hasBorderBottom?: boolean;
}

export function FeatureCard({
  num,
  chapterLabel,
  title,
  desc,
  annotation,
  Illus,
  hasBorderBottom = true,
}: FeatureCardProps) {
  return (
    <div
      className={`grid grid-cols-[52px_1fr] gap-5 py-7 ${hasBorderBottom ? "border-b border-dars-rule-light" : ""}`}
    >
      <div className="flex flex-col items-center gap-2.5 pt-0.5">
        <span className="font-serif text-xl font-bold text-dars-terra italic leading-none">
          {num}
        </span>
        <Illus size={28} />
      </div>
      <div>
        <div
          className="relative px-0 pr-0 pb-1.5 mb-2.5 rounded-sm"
          style={ruledBg}
        >
          <span
            className="absolute top-0.5 right-0 font-serif text-[9px] italic text-dars-terra leading-none tracking-[0.5px]"
            style={{ opacity: 0.45 }}
          >
            {chapterLabel}
          </span>
          <h3 className="font-serif text-base font-bold text-dars-ink leading-snug relative z-10">
            {title}
          </h3>
        </div>
        <p className="text-[13px] text-dars-muted leading-relaxed">{desc}</p>
        <span
          className="inline-block mt-2 font-serif text-[11px] italic text-dars-terra pb-px border-b border-dashed border-dars-terra/35"
          style={{ opacity: 0.65 }}
        >
          {annotation}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `components/molecules/step-item.tsx`**

```typescript
interface StepItemProps {
  num: string;
  title: string;
  desc: string;
  code?: string | null;
  isFirst?: boolean;
}

export function StepItem({ num, title, desc, code, isFirst = false }: StepItemProps) {
  return (
    <div
      className={`grid grid-cols-[40px_1fr] gap-5 py-8 border-b border-dars-rule-light ${isFirst ? "border-t border-dars-rule-light" : ""} items-start`}
    >
      <span className="font-serif text-2xl font-bold text-dars-terra italic mt-0.5">
        {num}
      </span>
      <div className="min-w-0">
        <h3 className="font-serif text-lg font-bold text-dars-ink mb-2">{title}</h3>
        <p className="text-[13px] text-dars-muted leading-relaxed">{desc}</p>
        {code && (
          <pre className="mt-3.5 bg-dars-ink border border-dars-rule-dark rounded-md px-4 py-3.5 font-mono text-[11px] text-dars-muted-light leading-relaxed overflow-x-auto whitespace-pre">
            {code}
          </pre>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
cd /home/hataf/taleemabad/dars/webapp
git add components/molecules/
git commit -m "feat(webapp): add NavBar, PlanWindow, FeatureCard, StepItem molecules"
```

---

## Task 6: Build LandingTemplate and wire up page

**Files:**
- Create: `webapp/components/templates/landing-template.tsx`
- Modify: `webapp/app/page.tsx`

- [ ] **Step 1: Create `components/templates/landing-template.tsx`**

```typescript
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
```

- [ ] **Step 2: Replace `app/page.tsx`**

```typescript
import { LandingTemplate } from "@/components/templates/landing-template";

export default function Home() {
  return <LandingTemplate />;
}
```

- [ ] **Step 3: Verify dev server renders the landing page**

```bash
cd /home/hataf/taleemabad/dars/webapp
npm run dev
```

Open `http://localhost:3000`. Expected: full landing page with dark hero, product window, features grid, how-it-works, quote, CTA, footer — no errors in terminal or browser console.

- [ ] **Step 4: Commit**

```bash
cd /home/hataf/taleemabad/dars/webapp
git add components/templates/ app/page.tsx
git commit -m "feat(webapp): add LandingTemplate and wire up home page"
```

---

## Task 7: Add CLAUDE.md and clean up scaffold boilerplate

**Files:**
- Create: `webapp/CLAUDE.md`
- Modify: `webapp/.gitignore`
- Delete: `webapp/app/fonts/` (scaffold placeholder fonts directory if present)

- [ ] **Step 1: Create `webapp/CLAUDE.md`**

```markdown
@AGENTS.md

# Webapp — Frontend Conventions

## Component architecture

Components live in `components/` with strict layering:

```
ui/          shadcn components — install via CLI, restyle with Dars tokens
atoms/       Smallest branded primitives (Logo, Eyebrow, Rule, illustrations). No state, no hooks.
molecules/   Composed from atoms + ui/. No page-level logic or data fetching.
templates/   Full page layouts composed from molecules + atoms. Receives all data as props. No hooks, no fetch.
```

### Layer rules
- `ui/` — shadcn only. Style overrides use Dars CSS tokens. Never import atoms/molecules here.
- `atoms/` — props + styling only. May use `ui/`. No logic, no hooks, no data.
- `molecules/` — compose atoms + `ui/`. No hooks, no server calls, no routing logic.
- `templates/` — layout only. All data passed as props. One template per page.
- `app/page.tsx` — owns hooks, data fetching, server actions. Renders exactly one template.

## Styling
- Tailwind utility classes with responsive variants (`sm:`, `md:`, `lg:`). No inline styles for layout or spacing.
- Inline styles only for values that cannot be expressed in Tailwind (e.g. exact opacity, one-off SVG geometry).
- Brand colors are CSS variables defined in `globals.css` via `@theme` (`--color-dars-ink`, `--color-dars-terra`, etc.) — reference as Tailwind classes (`text-dars-ink`, `bg-dars-terra`).

## Base components
- shadcn is the base component library. Install with `npx shadcn add <component>`.
- Installed components live in `components/ui/` — edit freely to match Dars design tokens.
- Never leave shadcn components with default neutral/slate styling — always align to Dars tokens.

## This is NOT the Next.js you know
This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
```

- [ ] **Step 2: Add `.superpowers/` to `.gitignore`**

Open `webapp/.gitignore` and add this line at the end:

```
.superpowers/
```

- [ ] **Step 3: Remove scaffold boilerplate from `app/page.tsx` default content if any remains**

The file should contain exactly:

```typescript
import { LandingTemplate } from "@/components/templates/landing-template";

export default function Home() {
  return <LandingTemplate />;
}
```

If it has any other content (Next.js default landing page), replace it entirely.

- [ ] **Step 4: Commit**

```bash
cd /home/hataf/taleemabad/dars/webapp
git add CLAUDE.md .gitignore
git commit -m "chore(webapp): add CLAUDE.md conventions and update gitignore"
```

---

## Task 8: Update Makefile and verify end-to-end

**Files:**
- Modify: `/home/hataf/taleemabad/dars/Makefile`

- [ ] **Step 1: Check current Makefile webapp target**

```bash
cat /home/hataf/taleemabad/dars/Makefile | grep -A3 "webapp"
```

Expected output shows `cd webapp && npm run dev` or similar. If it already points to `webapp/`, no change needed. If it pointed to the old path, update it.

- [ ] **Step 2: Run `make webapp` from repo root**

```bash
cd /home/hataf/taleemabad/dars
make webapp
```

Expected: Next.js dev server starts at `http://localhost:3000`, no errors, Tailwind resolves correctly from `webapp/node_modules/`.

- [ ] **Step 3: Verify in browser**

Open `http://localhost:3000`. Check each section visually:
- Dark hero with concentric rings and book watermark
- Plan window floating up from hero
- 6 feature cards in 2-column grid
- How it works with 3 steps and code blocks
- Dark quote section
- CTA with ring borders
- Footer

- [ ] **Step 4: Final commit**

```bash
cd /home/hataf/taleemabad/dars
git add Makefile  # only if changed
git commit -m "feat(webapp): webapp rebuild complete — landing page live"
```
