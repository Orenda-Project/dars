---
type: reference
last_verified: 2026-04-08
owner: hataf
---

# Dars — Design System

Source of truth: `webapp-archive/pen/theme.pen`

**To read it:** use the pencil MCP `batch_get` tool — never use `Read` or `Grep` on `.pen` files, contents are encrypted and only accessible via pencil MCP tools.

## Color tokens

| Token | Hex | Use |
|-------|-----|-----|
| **Ink** | `#1c1410` | Dark bg, hero, nav |
| **Ink Soft** | `#2c2420` | Quote section bg |
| **Terracotta** | `#bf4e30` | CTAs, numbers, accents (primary brand color) |
| **Terra Light** | `#e8a07a` | Code keys, badges |
| **Parchment** | `#faf7f2` | Light section bg |
| **Parchment Mid** | `#f0ebe3` | Alternating sections |
| **Muted** | `#7a6b62` | Body text on light |
| **Muted Light** | `#a89890` | Body text on dark |

## Typography

| Role | Font | Size | Notes |
|------|------|------|-------|
| Display / headings | Georgia or Lora serif | — | Tight tracking |
| UI / body | Inter | 13px | Line-height 1.75 |
| Eyebrow / labels | Inter | 11px | Weight 700, ALL CAPS, tracking 2px, terracotta |

## Visual language

Manuscript + parchment aesthetic. Sections alternate dark (Ink) / light (Parchment) top to bottom. Terracotta is the **only** accent color — no teal, no blue, no gradients.

Always read `theme.pen` via pencil MCP before making any color or typography decisions.
