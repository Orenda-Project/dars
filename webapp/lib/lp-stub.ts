/**
 * Temporary: the backend may not have generated LP content yet (we're
 * iterating on the slot model, not the LP body). The webapp renders this
 * canned HTML in place of `generated_lps.content` so the UI feels
 * complete while we keep working on breakdowns / slots.
 *
 * Remove this stub when real LP generation is reliable end-to-end on
 * staging.
 */

export const STUB_LP_HTML = `
<h2>Lesson Plan</h2>
<p><em>(Sample lesson plan — content generation is paused while we iterate on the slot model.)</em></p>

<h3>Learning objective</h3>
<p>By the end of this lesson, students will be able to identify and pronounce
the target words from the passage, and answer comprehension questions about
what they have read.</p>

<h3>Materials</h3>
<ul>
  <li>Textbook</li>
  <li>Whiteboard and markers</li>
  <li>Picture cards for vocabulary</li>
</ul>

<h3>Warm-up (5 min)</h3>
<p>Greet the class. Ask 2–3 students to share one thing they remember from
yesterday's lesson. Write key words on the board.</p>

<h3>Introduction (10 min)</h3>
<p>Show the picture on the page and ask students to describe what they see.
Introduce the new vocabulary words one at a time. Pronounce each word, have
the class repeat, then point at the matching picture.</p>

<h3>Main activity (20 min)</h3>
<ol>
  <li>Read the passage aloud while students follow along.</li>
  <li>Re-read paragraph by paragraph, pausing to check understanding.</li>
  <li>In pairs, students take turns reading one sentence each.</li>
  <li>Ask volunteers to answer the comprehension questions at the end.</li>
</ol>

<h3>Practice (10 min)</h3>
<p>Students complete the matching exercise in their workbook: match each
vocabulary word to its picture. Walk around the class and help where needed.</p>

<h3>Wrap-up (5 min)</h3>
<p>Recap the new words. Ask one student to use each word in a sentence.
Praise effort, not just correctness.</p>

<h3>Homework</h3>
<p>Re-read the passage at home and write three new sentences using the
vocabulary words.</p>
`.trim();
