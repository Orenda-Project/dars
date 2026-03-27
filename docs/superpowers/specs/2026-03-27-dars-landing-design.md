# Dars Landing Page — Design Spec
_Approved 2026-03-27_

## Vision

Dars presents itself as **a serious edtech infrastructure product** — not a teacher tool, not a consumer app. The audience is product teams and edtech founders who want to integrate lesson plan generation into their own products.

The brand personality is **Warm & Purposeful**: minimal and professional, but with the soul of a library. Think ink, paper, knowledge — a product made by people who care about education deeply. References: Loom, Craft, editorial journals.

---

## Color Palette

| Role | Hex | Usage |
|---|---|---|
| Ink (background dark) | `#1c1410` | Dark sections, hero, nav |
| Ink Soft | `#2c2420` | Quote section background |
| Parchment | `#faf7f2` | Light section backgrounds, cards |
| Parchment Mid | `#f0ebe3` | Alternating light sections, how-it-works |
| Parchment Deep | `#e8dfd3` | Borders, code block bg hints |
| Terracotta | `#bf4e30` | Primary accent — CTAs, numbers, highlights |
| Terracotta Light | `#e8a07a` | Secondary accent — code keys, badges |
| Muted | `#7a6b62` | Body text on light sections |
| Muted Light | `#a89890` | Body text on dark sections, nav links |
| Rule Dark | `#2e2420` | Borders on dark sections |
| Rule Light | `#e0d5c8` | Borders on light sections |

### Alternating section rhythm (top to bottom):
1. **Dark** — Hero (ink `#1c1410`)
2. **Dark** — Plan preview (ink, floats into next)
3. **Light** — Features (parchment `#faf7f2`)
4. **Light Mid** — How it works (parchment-mid `#f0ebe3`)
5. **Dark** — Quote (ink-soft `#2c2420`)
6. **Light** — CTA (parchment `#faf7f2`)
7. **Light Mid** — Footer (parchment-mid)

---

## Typography

| Element | Typeface | Weight | Notes |
|---|---|---|---|
| Headings (h1, h2, h3) | Georgia, serif | 700 | Letter-spacing: -1px to -2px on large sizes |
| Italic accent | Georgia, serif | 400 italic | Used for terracotta em spans, section numbers |
| Body / UI | System sans (-apple-system, Inter) | 400 | Clean, readable |
| Code | SF Mono, Monaco, monospace | 400 | Dark background code blocks |
| Eyebrows / labels | System sans | 700 | Uppercase, letter-spacing: 2px |

### Section numbering:
- Sections labeled **I.**, **II.**, **III.** in italic Georgia terracotta
- Feature entries labeled **i.** through **vi.** (same style, smaller)
- Steps labeled **i.**, **ii.**, **iii.** — never Arabic numerals in structural UI
- Chapter markers: `ch. i` / `ch. ii` etc. as faint top-right corner labels

---

## Illustrations

All illustrations are **inline SVG line drawings** — ink style, no fill, stroke width 1.3–1.5px.

- Primary stroke: `#2c2420` (ink)
- Accent stroke: `#bf4e30` (terracotta) — used for one meaningful element per illustration
- Opacity: accent elements at 0.7, secondary detail at 0.35–0.45

### Per-feature illustration subjects:
| Feature | Illustration |
|---|---|
| AI Generation | Quill/pen nib with ink line underline |
| Versioned Storage | Stacked book rectangles with terracotta spine marks |
| Structured Output | Open book with text lines (ink left, terra right) |
| API Key Auth | Magnifier with inner circle + key handle |
| Curriculum Alignment | Dashed compass circle with north arrow |
| React Components | Three connected rectangles (component tree) |

---

## Layout Patterns

### Hero
- Full-width dark section, min-height 92vh
- **Centered** text layout
- Background: faint open-book SVG watermark at 4.5% opacity
- Concentric terracotta rings radiating from center (4 rings, 12%→2.5% opacity)
- Eyebrow line with `::before` / `::after` dashes flanking the text
- H1: 68px, italic terracotta em on key phrase
- Sub: 18px muted-light, max-width 480px
- Two CTAs: primary (terracotta) + ghost (muted, border-bottom only)
- Scroll hint: thin vertical line fading to transparent at bottom

### Product Window (hero → features transition)
- Browser chrome mockup, max-width 700px, centered
- `transform: translateY(-48px)` — floats up out of the hero into the next section
- Sidebar + main content layout showing a real lesson plan
- Dark background (`#231c18`), heavy drop shadow

### Features Section — Manuscript Marginalia
- Two-column grid
- Each entry: `52px margin column` + `1fr content column`
- Margin: italic Roman numeral (terra) + SVG illustration below
- Heading sits on **faint ruled-paper background**:
  ```css
  background-image: repeating-linear-gradient(
    to bottom,
    transparent, transparent 19px,
    rgba(208,195,180,0.45) 19px,
    rgba(208,195,180,0.45) 20px
  );
  ```
- Faint `ch. i` label top-right of heading block (Georgia italic, 9px, 45% opacity)
- Body text: 13px muted
- Annotation: italic terracotta, 11px, dashed underline — "See also:", "cf.", short note

### How It Works
- Two-column: `1fr` sticky left + `2fr` step list right
- Left column sticky at `top: 100px`
- Steps separated by `rule-light` borders
- Code blocks: dark ink background on the parchment-mid section for contrast

### Quote Section
- Large `"` quote mark (120px Georgia, terracotta, 25% opacity)
- 24px italic Georgia quote
- Key word in terracotta, non-italic `em`

### CTA Section
- Centered on parchment
- Two concentric ring `div`s behind content (border only, rule-light colors)
- H2 with italic terracotta em phrase

---

## Decorative Motifs

- **Book watermark**: Open book SVG at ~4% opacity, centered behind dark hero
- **Concentric rings**: Terracotta-tinted, used in hero (dark) and CTA (light)
- **Ruled lines**: Faint horizontal lines under feature headings — notebook paper feel
- **Dashed annotation underline**: Terracotta dashed border-bottom on `ms-annotation` elements
- **Page lines texture**: Repeating thin lines in card corners (opacity 0.08–0.12)

---

## Voice & Copy Patterns

- Section headers: declarative, confident — "Everything a curriculum product needs."
- Hero: platform-first — "The platform behind great teaching."
- AI is a feature, not the identity — mentioned in sub-headline, not headline
- Annotations use scholarly shorthand: "cf.", "See also:", "render-ready, always"
- Chapter labels reinforce the library metaphor throughout
- Quote: "A good lesson plan is not a script. It is a *map* — and every student takes a different path."

---

## Component Reference

The approved HTML mockup lives at:
```
.superpowers/brainstorm/107634-1774623549/content/landing-v5.html
```
(with Roman numeral fix applied — steps use i./ii./iii.)

This is the source of truth for the Next.js implementation.
