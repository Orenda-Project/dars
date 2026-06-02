# Glossary — Chapter Breakdown & Chapter Plan

Inherits the v2 rebuild glossary and the `breakdown-slot-editing` glossary. Only terms specific to this feature are defined here.

| Term | Definition |
|---|---|
| **Chapter Breakdown** | The first of the two explicit authoring actions: deciding the **order** of chapters and the explicit **calendar date range** each occupies. Operates on `breakdown_chapters` rows. The "when and how long" layer. |
| **Chapter Plan** | The second action: breaking **one chapter** into its sequence of typed slots (lessons + assessments), each with a page range. Operates on `breakdown_slots` rows scoped to a single `breakdown_chapter_id`. The "what happens inside a chapter" layer. |
| **Date range** | A chapter's `start_date` + `end_date` on `breakdown_chapters`. Explicit calendar dates, not derived from a year anchor. The number of teaching days a chapter gets is *derived* from the range against the academic calendar (weekends/holidays excluded). |
| **Page range** | `page_start` + `page_end` on a `breakdown_slot`. The book pages a lesson or assessment covers. Both nullable (not every slot maps to pages, e.g. a pure revision slot). |
| **Manual build** | Authoring a Chapter Plan by adding slots one at a time with explicit type + page range, **without** invoking the auto-build algorithm. The default action per D-3. |
| **Seed (auto-build as seed)** | Running the existing auto-build algorithm for one chapter to produce an editable *starting set* of slots that the user then edits manually. Auto-build demoted from "the way you build" to "an optional first draft" (D-3). |
| **Derived teaching days** | The count of actual teaching days inside a chapter's date range, computed from the academic calendar. Supersedes the manually-entered `teaching_days` as the source of truth once date ranges exist (D-2). |
