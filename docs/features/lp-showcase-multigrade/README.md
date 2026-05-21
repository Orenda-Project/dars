# LP Showcase — Multi-Grade LPs

Add 2–3 **multi-grade lesson plans** to the existing public LP showcase (`/showcase/<tag>`). The current showcase ships 10 single-grade LPs grouped by Grade 2 and Grade 5; this feature extends it with a third **"Multi-Grade"** group so prospective clients can see Dars handling the UNESCO MG-DLP rotation model.

This is a small feature. One folder, one phase, one PR. The work has three moving parts: extending the generator script to call LP Assistant's `/api/v1/generate-lp-multigrade` webhook + polling, widening the showcase data shape (`grade` → can be a range), and adding a sidebar group for multi-grade entries.

## Index

1. [01-decision-log.md](01-decision-log.md) — frozen architectural decisions (D-1 … D-5)
2. [03-phase-1-multigrade-showcase.md](03-phase-1-multigrade-showcase.md) — the one-phase build with numbered features (F-1.1 … F-1.5)
3. [04-reference-lp-assistant-multigrade.md](04-reference-lp-assistant-multigrade.md) — frozen LP Assistant `/api/v1/generate-lp-multigrade` contract
4. [ONRAMP.md](ONRAMP.md) — single entry point for any future agent picking this up

## Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. phase doc                  (specs derived from decisions)
3. reference doc              (external API shape, frozen)
4. running code               (last; code may be stale)
```

If two docs disagree, this is the order. Code is **lowest** authority. Surface conflicts; don't silently pick a side.
