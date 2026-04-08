# Webapp Rebuild Design

**Date:** 2026-03-30
**Status:** Approved
**Scope:** Recreate the Dars landing page webapp from scratch using a clean `create-next-app` scaffold, replacing the broken `webapp/` directory.

---

## Background

The existing `webapp/` had an unresolvable Tailwind v4 module resolution bug caused by Turbopack looking for `tailwindcss` in the monorepo root (`/dars`) rather than `webapp/node_modules/`. The root cause was a stale `pnpm-workspace.yaml` file combined with no root `package.json`. After removing the workspace file and trying multiple PostCSS config workarounds, the scaffold itself was determined to be the problem. The fix is to create a fresh `webapp/` using `create-next-app`, which produces a known-good Tailwind v4 configuration.

The old directory is archived as `webapp-archive/` for reference.

---

## Goals

1. A working Next.js + Tailwind v4 dev server (`make webapp` runs without errors)
2. The same landing page recreated with identical sections, copy, and visual design
3. Clean component architecture documented and enforced via `CLAUDE.md`
4. No workspace/monorepo entanglement — `webapp/` is a standalone npm project

---

## Scaffold

- **Tool:** `create-next-app` (official Next.js CLI)
- **Options:** TypeScript, Tailwind CSS, App Router, ESLint, no `src/` directory
- **Package manager:** npm (no pnpm, no workspace file)
- **Location:** `dars/webapp/`

After scaffolding: install shadcn, port design tokens, rebuild components.

---

## Folder Structure

```
webapp/
├── app/
│   ├── layout.tsx          ← fonts (Lora + Geist Mono), metadata, root HTML
│   ├── globals.css         ← Tailwind v4 import + Dars CSS custom properties
│   └── page.tsx            ← renders <LandingTemplate /> only
├── components/
│   ├── ui/                 ← shadcn components, restyled with Dars tokens
│   ├── atoms/              ← Logo, Eyebrow, Rule, SVG illustrations
│   ├── molecules/          ← NavBar, FeatureCard, PlanWindow, StepItem
│   └── templates/          ← LandingTemplate
├── public/                 ← static assets
├── CLAUDE.md               ← frontend conventions (carried over from archive)
├── next.config.ts
├── postcss.config.mjs
├── tailwind.config.ts      ← only if needed; Tailwind v4 is mostly config-free
└── package.json
```

---

## Component Architecture

### Layer Rules

| Layer | Contents | Rules |
|---|---|---|
| `ui/` | shadcn components | Install via CLI only. Style overrides use Dars tokens. Never import atoms/molecules here. |
| `atoms/` | Logo, Eyebrow, Rule, illustrations | Props + styling only. No state, no hooks, no logic. |
| `molecules/` | NavBar, FeatureCard, PlanWindow, StepItem | Compose atoms + ui/. No hooks, no server calls, no routing logic. |
| `templates/` | LandingTemplate | Layout only. All data passed as props. One template per page. |
| `app/page.tsx` | Entry point | Owns data/hooks. Renders exactly one template. |

### Components to Recreate

**Atoms:**
- `Logo` — "Dars درس" wordmark with Urdu subtitle in terracotta
- `Eyebrow` — centered section label with flanking dashes
- `Rule` — `<hr>` variant, light and dark modes
- `illustrations/` — six inline SVG line drawings: Books, Compass, Components, Key, OpenBook, Quill

**Molecules:**
- `NavBar` — sticky, ink background, backdrop blur, logo left + "Get access" CTA right; nav links hidden on mobile
- `FeatureCard` — two-column layout (52px margin column with numeral + illustration, content column with ruled-paper heading background)
- `PlanWindow` — browser chrome mockup with sidebar + lesson plan preview content
- `StepItem` — numbered step with title, description, optional dark code block

**Templates:**
- `LandingTemplate` — assembles all sections; receives FEATURES array and STEPS array as props (or defines them internally as constants)

---

## Landing Page Sections

| # | Section | Background | Key Elements |
|---|---|---|---|
| 1 | NavBar | Ink (sticky, blur) | Logo, "Get access" CTA |
| 2 | Hero | Ink | Concentric rings watermark, eyebrow, headline, subheading, CTA button |
| 3 | Product Window | Parchment | PlanWindow mockup floating −48px into section |
| 4 | Features | Parchment Mid | 6 FeatureCards in 2-col grid (1-col on mobile) |
| 5 | How It Works | Parchment | Sticky left intro + 3 StepItems scrolling right (stacked on mobile) |
| 6 | Quote | Ink Soft | Large decorative quote mark, italic quote with terracotta `<em>` |
| 7 | CTA | Ink | Concentric ring borders, centered headline + button |
| 8 | Footer | Ink | Logo, tagline, copyright |

---

## Design System

### Colors (CSS custom properties in `globals.css`)

| Token | Hex | Usage |
|---|---|---|
| `--dars-ink` | `#1c1410` | Dark section backgrounds, primary text on light |
| `--dars-ink-soft` | `#2c2420` | Quote section background |
| `--dars-parchment` | `#faf7f2` | Light section backgrounds |
| `--dars-parchment-mid` | `#f0ebe3` | Alternate light sections |
| `--dars-parchment-deep` | `#e8dfd3` | Borders, code block backgrounds |
| `--dars-terra` | `#bf4e30` | Primary accent: CTAs, highlights, numerals |
| `--dars-terra-light` | `#e8a07a` | Secondary accent |
| `--dars-muted` | `#7a6b62` | Body text on light backgrounds |
| `--dars-muted-light` | `#a89890` | Body text on dark backgrounds |

### Typography

- **Headings:** Lora (serif), weight 700, italic accent spans in terracotta
- **Body:** System sans (Inter fallback)
- **Code:** Geist Mono
- Fonts loaded via `next/font/google` in `layout.tsx`, applied as CSS variables

### Tailwind v4

Tailwind v4 is largely config-free. Design tokens are registered via `@theme` in `globals.css`:

```css
@import "tailwindcss";

@theme {
  --color-dars-ink: #1c1410;
  --color-dars-terra: #bf4e30;
  /* etc. */
  --font-serif: "Lora", Georgia, serif;
  --font-mono: "Geist Mono", monospace;
}
```

No `tailwind.config.ts` needed unless custom plugins are required.

---

## Responsive Behaviour

- **Mobile-first** throughout — all breakpoints additive
- Features grid: 1-col → `md:grid-cols-2`
- How It Works: stacked → `lg:` sticky-left + scrolling-right
- NavBar links: hidden → `md:flex`
- PlanWindow: reduced height on mobile, full chrome on `md:`

---

## Copy

All copy (feature names, descriptions, step text, quote, CTA) is ported verbatim from `webapp-archive/`. The source of truth for copy is `webapp-archive/src/components/templates/landing-template.tsx`.

---

## Non-Goals

- No new sections or features beyond the original landing page
- No authentication, routing, or data fetching in this phase
- No dashboard or admin UI (Phase 2.5 follow-on work)
- No changes to the visual design or brand

---

## CLAUDE.md

The existing `webapp/CLAUDE.md` (referencing component architecture and styling conventions) is carried over verbatim into the new `webapp/`. It is the in-repo reference for all future frontend work.
