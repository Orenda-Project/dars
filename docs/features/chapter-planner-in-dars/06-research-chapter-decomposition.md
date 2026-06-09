# Research — Best Practices for Dividing a Chapter into Lesson Plans

**Status:** Compiled from a deep-research run (2026-06-09) that fanned out across 5 angles, fetched ~15 sources, and adversarially verified each extracted claim with a 3-vote panel (≥2/3 refutations kill a claim). The run was interrupted before the auto-synthesis step, so this report is compiled directly from the **verified-claims layer** (20 surviving claims, 4 killed). Killed claims are retained as **anti-patterns** — intuitive-but-wrong heuristics the evidence specifically refutes.

This feeds the dars chapter planner (`server/src/dars/breakdown/planner_prompts.py` + `planner.py`, post #128/#129 port). See "Translating to planner heuristics" at the end.

---

## Verified sources

| Source | What it anchors |
|---|---|
| Rosenshine, *Principles of Instruction* (AFT American Educator, Spring 2012) — aft.org/ae/spring2012/rosenshine | Small steps, weekly/monthly review, high success rate |
| Wiggins & McTighe, *Understanding by Design* white paper (ASCD) — files.ascd.org/.../UbD_WhitePaper0312.pdf | Backward design, unit-not-lesson planning, prioritise content |
| Gagné, *Conditions of Learning* — instructionaldesign.org/theories/conditions-learning | Learning hierarchies; different outcomes need different instruction |
| Reigeluth, *Elaboration Theory* — instructionaldesign.org/theories/elaboration-theory | Simple-to-complex; epitome; internal vs within-set synthesis |
| *Sequencing of Instruction* — instructionaldesign.org/concepts/sequence-instruction | Order of activities affects processing/retention |
| BSCS *5E Instructional Model* full report — media.bscs.org/.../bscs_5e_full_report.pdf | 5E for science; learning-cycle evidence |
| Jin et al. 2019, *Toward coherence…* (Science Education 103:1206) — doi 10.1002/sce.21525 | Learning-progression coherence (see killed claim K4) |
| Piper & Dubeck 2024, *Structured pedagogy in sub-Saharan Africa* (Int. J. Educational Development) — PMC11422479 | Structured-pedagogy 4 components; common lesson elements; FLN |
| OpenDeved, *Science of Teaching for FLN — Curriculum & Scope-and-Sequence* how-to guide — docs.opendeved.net | Concrete sequencing rules for early literacy & numeracy |
| J-PAL, *Teaching at the Right Level* — povertyactionlab.org/evidence-effect/teaching-at-the-right-level | Level-based grouping; among largest measured gains |

---

## A. Sequencing — how to order within a chapter

**Order objectives by prerequisite dependency, simplest-first.** Multiple independent sources converge:

- **Gagné's learning hierarchies** (VERIFIED, high): "Learning tasks for intellectual skills can be organized in a hierarchy according to complexity: stimulus recognition, response generation, procedure following, use of terminology, discriminations, concept formation, rule application, and problem solving… Learning hierarchies provide a basis for the sequencing of instruction." Their "primary significance is to identify prerequisites." → **A lower-order objective that another depends on must be taught first.**
- **Reigeluth's elaboration theory** (VERIFIED, high): "instruction should be organized in increasing order of complexity for optimal learning"; present the simplest version first, then add complexity. Open with an **epitome** — "just a few fundamental or representative ideas or skills" the rest elaborates.
- **Scope-and-sequence as the instrument** (VERIFIED, high, Piper & Dubeck): "A carefully planned scope and sequence helps to ensure that students have the prior knowledge they need to master new ideas."
- **Sequence matters at all** (VERIFIED): "The order and organization of learning activities affects the way information is processed and retained."

**For early numeracy** (VERIFIED, high, OpenDeved): "Group any aligned skills together (e.g., number recognition and object counting). Develop pacing across and within domains, ensuring that concepts are revisited with depth (e.g., geometry is integrated throughout the year instead of blocked into one month). Develop mini-developmental progressions for objectives (e.g., the steps that lead to proficiency in addition and subtraction)."

**For early literacy** (VERIFIED, medium–high, OpenDeved): "Establish parameters to ensure consistency and appropriate increases of difficulty (e.g., quantity of new letters, decodable words, sight words, and vocabulary per week; and word, sentence, and story length)… Establish internal checks to verify that new content is not introduced abruptly or too slowly."

---

## B. Chunking — how much per lesson

**Keep each lesson small; gate on mastery of the prior step.** (VERIFIED, high, Rosenshine): "Our working memory, the place where we process information, is small. It can only handle a few bits of information at once — too much information swamps our working memory… Only after the students have mastered the first step do teachers proceed to the next step." And: "Present new material in small steps with student practice after each step."

Implications:
- A **dense** objective (many sub-skills, or a sub-skill chain) should be **split across several lessons**.
- **Thin, aligned** objectives may be **combined** — but only when genuinely related. Combining unrelated objectives to fill a period re-loads working memory.
- "Right-sized" = a single lesson advances one coherent step a young learner can hold and practise to mastery before the next.

> The research did **not** surface a hard universal "N objectives per lesson" number for K-5; the governing constraint is cognitive load + mastery-before-advance, not a fixed count. "One main teaching point, ≤ a small handful of tightly-related SLOs" is the safe default, not a cited rule.

---

## C. Lesson-type / instructional-format assignment

**Different learning outcomes require different instruction** (VERIFIED, Gagné: "Different instruction is required for different learning outcomes"). So assigning a *type* per unit is right; the type should follow the **nature of the SLO**.

- **5E for science/inquiry** (VERIFIED, high, BSCS): engagement, exploration, explanation, elaboration, evaluation — "frames a sequence and organization of programs, units, and lessons"; exploration "should be concrete and hands on" before explanation. Six studies found learning-cycle instruction produced greater subject-knowledge gains than traditional approaches, persisting in delayed post-tests. (dars maps Science→`revision` only today — see gap.)
- **Gradual release ("I do / we do / you do")** (VERIFIED, high, Piper & Dubeck): widely used for literacy and numeracy — **but** "most math education experts have argued that this linear structure for mathematics is inappropriate. Yet the overarching concept of gradual release… is relevant to math exploration and higher-order skills."
- **Reading vs grammar vs comprehension vs writing**: evidence supports *type-by-outcome* (Gagné) + smooth difficulty progression (OpenDeved), but yielded no single canonical rule among literacy sub-types. Drive the choice off the SLO's verb/outcome (decode → reading; define words → word-meanings; identify/apply a rule → grammar; answer about a text → comprehension_qa; produce text → creative_writing).

---

## D. Pacing & coverage

**Plan the unit first, backward from outcomes — not lesson-by-lesson.**

- **Backward design** (VERIFIED, high, UbD): "Effective curriculum is planned backward from long-term, desired results through a three-stage design process (Desired Results, Evidence, and Learning Plan)."
- **Plan at the unit level** (VERIFIED, high, UbD): "we do not recommend isolated lesson planning separate from unit planning… essential questions are meant to be explored and revisited over time, not answered by the end of a single class period." → The chapter is the right planning grain.
- **You must prioritise** (VERIFIED, high, UbD): "Because there is typically more content than can reasonably be addressed within the available time, teachers are obliged to make choices." → When periods are tight, **prioritise**; don't silently thin everything.
- **Spaced, cumulative review** (VERIFIED, high, Rosenshine): "review the previous week's work every Monday and the previous month's work every fourth Monday… classes that had weekly quizzes scored better on final exams." → For multi-week chapters, **insert periodic review units**, not just one at the end.

---

## E. Early-grade & low-resource (FLN / Pakistan-relevant)

- **Structured pedagogy works and has a recognised shape** (VERIFIED, high, Piper & Dubeck). Four components: "(1) student books and materials, often at a 1:1 ratio, (2) teachers' guides that provide daily lesson plans… with some level of structure and specificity, (3) teacher training… and (4) continuous support to teachers." → A planner emitting structured daily lesson units **is** component (2).
- **Teaching at the Right Level (TaRL)** (VERIFIED, high, J-PAL): "TaRL has led to some of the largest learning gains among rigorously evaluated education programs," corroborated by the 2023 GEEAP panel. Loop: **assess → group by level → teach foundational skills → track → regroup**, "focusing on foundational skills rather than solely on the curriculum."

---

## F. Anti-patterns (claims the evidence KILLED — do not encode these)

The 3-vote panel **refuted** each (≥2/3, high confidence).

- **K1 — "Re-summarise ALL prior material in EVERY lesson."** *Refuted.* Misreads Reigeluth. Elaboration theory distinguishes **internal** summarizers/synthesizers (single lesson) from **within-set** ones (a related set of lessons, at **checkpoints**). Cumulative synthesis is **periodic**, at unit/strand boundaries — not every lesson. *Encode periodic review (D), not every-lesson total recall.*
- **K2 — "Use an 80% success rate as a between-lesson mastery gate."** *Refuted.* Rosenshine's 82%-vs-73% fourth-grade-maths figures are real, but the success rate is "judged by the quality of oral responses during guided practice and individual work" — an **in-lesson** pacing indicator, not a between-unit advancement threshold. *Don't build a numeric mastery gate on this number.*
- **K3 — "Lessons follow a fixed 7-element sequence (direct explanation → modeling → guided practice → independent practice → formative assessment → discussion → monitoring)."** *Refuted as a template.* Piper & Dubeck list these as "common **elements** that are **seen in** the lesson plans" — descriptive, not prescriptive; the next sentence says "How those elements are provided… **depends on** other characteristics." *Treat as a palette, not a mandatory skeleton.*
- **K4 — "Learning progressions give developmental/vertical/horizontal coherence, so model three design dimensions."** *Refuted as mis-defined.* The three types are real (Jin et al. 2019) but the claim **swapped definitions**: horizontal = alignment among curriculum/instruction/assessment; vertical = linkage between classroom and large-scale assessment; developmental = student growth over time. *Use correct definitions if citing; doesn't cleanly map to planner "design dimensions."*

---

## Translating to planner heuristics (dars-specific)

> **Status (2026-06-09):** Recommendations 1, 2, 4 are **implemented** — D-10 added Planning principles A–D to the live system prompt (`server/src/dars/breakdown/planner_prompts.py`). Recommendation 3 (wire the heuristic table in as an lp_type prior) was **declined** by the user — `lp_type` stays a free LLM pick (principle C gives it outcome-based criteria instead). Recommendation 5 (5E for Science) is **not done** — Science still maps to `revision` only in `VALID_LP_TYPES`. Retained as the research rationale behind each principle.

Mapped against the planner (`server/src/dars/breakdown/planner_prompts.py` + `planner.py`):

1. **Explicit sequencing guidance.** The prompt asked for a `sequence` permutation but gave **zero ordering criteria**. Added: order by prerequisite dependency and simplest-to-complex; foundational SLO before dependents; open with the most fundamental idea (Gagné + Reigeluth + scope-and-sequence, §A). → principle A.

2. **Chunking guidance.** The one-liner ("combine thin topics or split a dense one — you decide") had no principle. Added: each unit advances one coherent step a young learner can master before the next; split dense SLOs; combine only genuinely-aligned topics (Rosenshine, §B). → principle B.

3. **lp_type by outcome (free pick).** Gagné: outcome-type drives format. lp_type remains a free LLM pick from the allowed list; `recommended_lp_type` is NOT passed and `lp_type_heuristics.py` is NOT wired in as a prior (user decision). Principle C gives outcome-based selection criteria. → principle C.

4. **Spaced review for longer chapters.** `revision` is allowed but nothing told the planner *when* to use it. Added: for multi-week chapters, allocate periodic cumulative-review units — **periodic, not every-lesson** (avoids K1) — and prioritise-don't-thin when periods are tight (Rosenshine + UbD, §D). → principle D.

5. **Science → `revision` only** (`VALID_LP_TYPES["Science"]`). The 5E evidence (§C) is strong; if Science gets real lesson types, a 5E-derived progression (concrete exploration before explanation) is the evidence-backed default. *Not done.*

6. **Do not encode K2/K3/K4** (§F): no numeric success-rate gate, no fixed lesson skeleton, no mis-defined coherence dimensions.
