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
