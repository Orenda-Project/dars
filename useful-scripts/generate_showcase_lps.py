#!/usr/bin/env python3
"""Generate the 10 showcase LPs via LP Assistant and write static HTML into the webapp.

Usage:
    LP_ASSISTANT_API_KEY=... python3 useful-scripts/generate_showcase_lps.py \
        [--curriculum ICT|Punjab|Sindh] \
        [--tag ali-sipra-2026-05-15] \
        [--concurrency 3]

    # Re-run only the AI reviewer against existing LP HTML (no LP regeneration):
    LP_ASSISTANT_API_KEY=... python3 useful-scripts/generate_showcase_lps.py --reviews-only

Output:
    webapp/public/showcase/<tag>/lp-NN.html         raw lesson_plan HTML
    webapp/public/showcase/<tag>/lp-NN.review.json  rubric-based AI review for that LP
    webapp/public/showcase/<tag>/index.json         {id,grade,skill,page,topic,status,html_file,
                                                     review_file,review_status,error?,review_error?}[]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html as html_lib
import json
import logging
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = REPO_ROOT / "webapp" / "public" / "showcase"
DEFAULT_LP_ASSISTANT_URL = "https://lp-assistant.taleemabad.com"
DEFAULT_TAG = "lp-showcase"
DEFAULT_CONCURRENCY = 3
REQUEST_TIMEOUT = 300.0


@dataclass
class LPSpec:
    id: int
    grade: int | list[int]
    skill: str
    page: str
    topic: str
    lp_type: str
    # Populated only for multi-grade specs (D-6). Keys are grade ints, values are page strings
    # forwarded to LP Assistant as ``per_grade_page_numbers``.
    per_grade_pages: dict[int, str] | None = None

    @property
    def html_file(self) -> str:
        return f"lp-{self.id:02d}.html"

    @property
    def is_multigrade(self) -> bool:
        return isinstance(self.grade, list)

    @property
    def grade_label(self) -> str:
        """Human-readable grade label for headings and the index.

        Single grade: ``"2"``.
        Contiguous range: ``"2–3"`` (em dash).
        Non-contiguous set: ``"1, 3, 5"``.
        """
        if not self.is_multigrade:
            return str(self.grade)
        grades = sorted(self.grade)  # type: ignore[arg-type]
        if len(grades) >= 2 and grades == list(range(grades[0], grades[-1] + 1)):
            return f"{grades[0]}–{grades[-1]}"
        return ", ".join(str(g) for g in grades)


SPECS: list[LPSpec] = [
    LPSpec(1, 2, "Reading", "111", "Journey through text", "reading"),
    LPSpec(2, 2, "Comprehension w/ meanings", "15", "New words to know", "comprehension_word_meanings"),
    LPSpec(3, 2, "Comprehension Q&A", "127-128", "Activity 2", "comprehension_qa"),
    LPSpec(4, 2, "Grammar", "10", "Activity 3", "grammar"),
    LPSpec(5, 2, "Creative writing", "133", "", "creative_writing"),
    LPSpec(6, 5, "Reading", "32-33", "Journey through text", "reading"),
    LPSpec(7, 5, "Comprehension w/ meanings", "44-45", "Memory lane", "comprehension_word_meanings"),
    LPSpec(8, 5, "Comprehension Q&A", "49", "Activity 3", "comprehension_qa"),
    LPSpec(9, 5, "Grammar", "39", "Activity 3", "grammar"),
    LPSpec(10, 5, "Creative writing", "15", "Activity 3", "creative_writing"),
    # Multi-grade specs (D-2). lp_type is "multigrade" — descriptive only; LP Assistant's
    # multigrade endpoint doesn't accept a per-LP lp_type field. The `page` string is the
    # display label shown in the sidebar; the real per-grade page numbers live in per_grade_pages.
    LPSpec(
        11, [2, 3], "Reading", "G2 p. 111 · G3 p. 127–128", "Journey through text",
        "multigrade",
        per_grade_pages={2: "111", 3: "127-128"},
    ),
    LPSpec(
        12, [4, 5], "Comprehension Q&A", "G4 p. 30 · G5 p. 49", "Activity 3",
        "multigrade",
        per_grade_pages={4: "30", 5: "49"},
    ),
    LPSpec(
        13, [1, 2, 3, 4, 5], "Creative writing",
        "G1 p. 10 · G2 p. 133 · G3 p. 32 · G4 p. 39 · G5 p. 15",
        "Memory lane",
        "multigrade",
        per_grade_pages={1: "10", 2: "133", 3: "32", 4: "39", 5: "15"},
    ),
]


@dataclass
class LPResult:
    spec: LPSpec
    status: str  # "OK" | "ERROR"
    error: str | None = None
    html: str | None = field(default=None, repr=False)


_BODY_RE = re.compile(r"<body[^>]*>(.*?)</body\s*>", re.IGNORECASE | re.DOTALL)
_HTML_INNER_RE = re.compile(r"<html[^>]*>(.*?)</html\s*>", re.IGNORECASE | re.DOTALL)
_HEAD_RE = re.compile(r"<head[^>]*>.*?</head\s*>", re.IGNORECASE | re.DOTALL)
_TARGET_EMOJI = "\U0001f3af"  # bullseye emoji used by LP Assistant in h2/h3 headings


def _extract_body_content(raw_html: str) -> str:
    """Pull the inner content from raw LP Assistant HTML.

    LP Assistant returns either ``<html><head>…</head><body>…</body></html>`` or
    looser shapes (no body, content directly under html). We accept both and
    return the inner content suitable for injection inside a new <body>.
    """
    m = _BODY_RE.search(raw_html)
    if m:
        return m.group(1).strip()
    m = _HTML_INNER_RE.search(raw_html)
    if m:
        inner = _HEAD_RE.sub("", m.group(1))
        return inner.strip()
    return raw_html.strip()


def wrap_html(spec: LPSpec, raw_html: str) -> str:
    """Wrap raw LP Assistant HTML in a Dars-styled document.

    - Links the shared stylesheet at /showcase/_assets/lp.css.
    - Strips the bullseye emoji from headings (cleaner than CSS hiding).
    - Injects an <h1> with "Grade {N} — {skill}" derived from the spec.
    - Adds a tiny <footer> credit line.
    """
    inner = _extract_body_content(raw_html)
    inner = inner.replace(_TARGET_EMOJI, '')
    inner = re.sub(r"(<h[1-6][^>]*>)\s+", r"\1", inner, flags=re.IGNORECASE)
    inner = re.sub(r"\s+(</h[1-6]\s*>)", r"\1", inner, flags=re.IGNORECASE)

    skill = html_lib.escape(spec.skill)
    topic = html_lib.escape(spec.topic) if spec.topic else ""
    grade_word = "Grades" if spec.is_multigrade else "Grade"
    title = f"{grade_word} {spec.grade_label} — {skill}"
    heading = f"{grade_word} {spec.grade_label} — {skill}"

    page_line = f"Page {html_lib.escape(spec.page)}" if spec.page else ""
    if topic:
        page_line = f"{page_line} · {topic}" if page_line else topic
    page_label = (
        f"<p class=\"lp-page-ref\" style=\"max-width:720px;margin:0 auto 8px;"
        f"font-size:13px;color:#7a6b62;\">{page_line}</p>"
        if page_line
        else ""
    )

    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
        f"<title>{title}</title>\n"
        "<link rel=\"stylesheet\" href=\"/showcase/_assets/lp.css\">\n"
        "</head>\n"
        "<body class=\"lp-doc\">\n"
        f"<span class=\"lp-eyebrow\">Lesson plan</span>\n"
        f"<h1>{heading}</h1>\n"
        f"{page_label}\n"
        "<hr class=\"lp-divider\">\n"
        f"{inner}\n"
        "<div class=\"lp-footer\">Generated by Dars</div>\n"
        "</body>\n"
        "</html>\n"
    )


def generate_one(
    spec: LPSpec, base_url: str, api_key: str, curriculum: str
) -> LPResult:
    """Call LP Assistant for a single spec. Returns LPResult; never raises."""
    payload: dict[str, Any] = {
        "curriculum": curriculum,
        "grade": spec.grade,
        "subject": "Eng",
        "page_number": spec.page,
        "class_strength": 30,
        "generate_bilingual": False,
        "reasoning_enabled": True,
        "lp_type": spec.lp_type,
    }
    logger.info(
        "generate_one: enter id=%s grade=%s page=%s skill=%s lp_type=%s curriculum=%s",
        spec.id, spec.grade, spec.page, spec.skill, spec.lp_type, curriculum,
    )
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as http:
            resp = http.post(
                f"{base_url.rstrip('/')}/api/generate-lp",
                json=payload,
                headers={"api-key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
        html = data.get("lesson_plan")
        if not isinstance(html, str) or not html.strip():
            raise ValueError(f"empty lesson_plan field in response: keys={list(data)}")
        logger.info("generate_one: ok id=%s bytes=%d", spec.id, len(html))
        return LPResult(spec=spec, status="OK", html=html)
    except httpx.HTTPStatusError as e:
        body = (e.response.text or "")[:500]
        msg = f"HTTP {e.response.status_code}: {body}"
        logger.error("generate_one: http error id=%s %s", spec.id, msg, exc_info=True)
        return LPResult(spec=spec, status="ERROR", error=msg)
    except Exception as e:
        logger.error("generate_one: error id=%s", spec.id, exc_info=True)
        return LPResult(spec=spec, status="ERROR", error=f"{type(e).__name__}: {e}")


# Multigrade polling parameters (D-4). LP Assistant estimates ~90s per multigrade job;
# 5s × 60 attempts = 5 minute ceiling.
_MG_POLL_INTERVAL_S = 5.0
_MG_POLL_MAX_ATTEMPTS = 60


# Multigrade renderer (D-7). The multigrade endpoint returns a parsed JSON dict with
# the UNESCO MG-DLP structure; we port LP Assistant's JS renderer
# (UG_LessonPlan/static/index.html displayMultigradeLessonPlan, ~L2014–2238) to Python.
# Output is a self-contained HTML document using the same <body class="lp-doc"> shell
# and /showcase/_assets/lp.css stylesheet that single-grade LPs use, so the iframe
# rendering in showcase-template.tsx needs no changes.

_MG_COLORS = {
    "slo":     {"border": "#0d9488", "bg": "#f0fdfa", "text": "#0d9488"},
    "opening": {"border": "#d97706", "bg": "#fffbeb", "text": "#d97706"},
    "board":   {"border": "#475569", "bg": "#f8fafc", "text": "#475569"},
    "closing": {"border": "#ea580c", "bg": "#fff7ed", "text": "#ea580c"},
    "peer":    {"border": "#16a34a", "bg": "#f0fdf4", "text": "#16a34a"},
}
_MG_ROTATION_COLORS = [
    {"border": "#4f46e5", "bg": "#eef2ff", "text": "#4f46e5"},
    {"border": "#7c3aed", "bg": "#f5f3ff", "text": "#7c3aed"},
    {"border": "#db2777", "bg": "#fdf2f8", "text": "#db2777"},
]


def _esc(s: Any) -> str:
    """HTML-escape a value, coercing None to empty and non-strings to str."""
    if s is None:
        return ""
    return html_lib.escape(str(s))


def _mg_section_card(color: dict[str, str], header_html: str, body_html: str) -> str:
    return (
        f'<div style="border-left:4px solid {color["border"]};border-radius:8px;'
        f'margin-bottom:20px;overflow:hidden;border:1px solid {color["border"]}22">'
        f'<div style="background:{color["bg"]};padding:10px 16px;'
        f'border-bottom:1px solid {color["border"]}33">'
        f'<h3 style="margin:0;color:{color["text"]};font-size:1em;font-weight:700">'
        f'{header_html}</h3></div>'
        f'<div style="padding:14px 16px;background:#fff">{body_html}</div></div>'
    )


def _mg_render_steps(steps: Any) -> str:
    if not isinstance(steps, list) or not steps:
        return ""
    parts: list[str] = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        type_label = _esc(s.get("type") or s.get("label") or s.get("phase") or "")
        time_html = (
            f'<span style="color:#6b7280;font-size:0.82em;margin-left:8px">'
            f'{_esc(s.get("time"))}</span>'
            if s.get("time") else ""
        )
        instr = _esc(s.get("instruction") or s.get("description") or s.get("activity") or "")
        parts.append(
            '<div style="margin-bottom:10px;padding:10px 12px;background:#f9fafb;'
            'border-radius:6px;border:1px solid #e5e7eb">'
            f'<div style="font-weight:600;margin-bottom:4px">{type_label}{time_html}</div>'
            f'<div style="white-space:pre-wrap;font-size:0.95em">{instr}</div></div>'
        )
    return "".join(parts)


def _mg_render_rotations(rotations: Any) -> str:
    if not isinstance(rotations, list) or not rotations:
        return ""
    out: list[str] = []
    for idx, rot in enumerate(rotations):
        if not isinstance(rot, dict):
            continue
        color = _MG_ROTATION_COLORS[idx % len(_MG_ROTATION_COLORS)]
        focus = _esc(rot.get("focus_group") or rot.get("group_label") or f"Group {idx + 1}")
        dur = (
            f' <span style="font-weight:400;opacity:0.8">({_esc(rot.get("duration"))})</span>'
            if rot.get("duration") else ""
        )
        time_html = (
            f' <span style="font-weight:400;opacity:0.7;font-size:0.85em">{_esc(rot.get("time"))}</span>'
            if rot.get("time") else ""
        )
        badge = (
            f'<span style="background:{color["border"]}18;color:{color["border"]};'
            f'font-size:0.75em;padding:2px 8px;border-radius:4px;margin-left:8px;'
            f'font-weight:600">{focus}</span>'
        )
        body_parts: list[str] = []

        ga = rot.get("group_activities")
        if isinstance(ga, dict) and ga:
            body_parts.append(
                '<div style="font-size:0.75em;font-weight:700;text-transform:uppercase;'
                'letter-spacing:1px;color:#6b7280;margin-bottom:8px">Group Activities</div>'
            )
            for grade_key, activity in ga.items():
                if not isinstance(activity, dict):
                    continue
                mode = activity.get("mode")
                mode_badge = (
                    f'<span style="text-transform:uppercase;font-size:0.72em;'
                    f'background:{color["border"]}18;color:{color["border"]};'
                    f'padding:1px 6px;border-radius:4px;margin-left:6px">{_esc(mode)}</span>'
                    if mode else ""
                )
                board_instr_html = ""
                if activity.get("board_instruction"):
                    board_instr_html = (
                        f'<div style="margin-top:6px;padding:6px 10px;'
                        f'border-left:3px solid {color["border"]};font-size:0.88em;'
                        f'white-space:pre-wrap;color:#374151">'
                        f'{_esc(activity.get("board_instruction"))}</div>'
                    )
                body_parts.append(
                    '<div style="margin-bottom:8px;padding:8px 12px;background:#f9fafb;'
                    'border-radius:6px;border:1px solid #e5e7eb">'
                    f'<div style="font-weight:600">{_esc(grade_key)}{mode_badge}</div>'
                    f'<div style="margin-top:4px;font-size:0.93em">{_esc(activity.get("task"))}</div>'
                    f'{board_instr_html}</div>'
                )

        teacher_steps = rot.get("teacher_steps")
        if isinstance(teacher_steps, list) and teacher_steps:
            body_parts.append(
                '<div style="font-size:0.75em;font-weight:700;text-transform:uppercase;'
                'letter-spacing:1px;color:#6b7280;margin:12px 0 8px">Teacher Steps</div>'
            )
            body_parts.append(_mg_render_steps(teacher_steps))

        tc = rot.get("transition_cue")
        if isinstance(tc, dict):
            confirm = (
                f'<div style="margin-top:4px;font-size:0.85em;color:#475569">'
                f'✅ {_esc(tc.get("confirm_before_turning"))}</div>'
                if tc.get("confirm_before_turning") else ""
            )
            says = (
                f'<div style="margin-top:4px;white-space:pre-wrap">{_esc(tc.get("teacher_says"))}</div>'
                if tc.get("teacher_says") else ""
            )
            time_label = f" ({_esc(tc.get('time'))})" if tc.get("time") else ""
            body_parts.append(
                f'<div style="margin-top:10px;padding:10px 12px;'
                f'border:1px dashed {color["border"]}66;border-radius:6px;'
                f'font-size:0.9em;background:{color["bg"]}">'
                f'<div><strong>Transition</strong>{time_label}: {_esc(tc.get("signal"))}</div>'
                f'{says}{confirm}</div>'
            )
        out.append(
            _mg_section_card(color, f'Rotation {idx + 1}{badge}{dur}{time_html}', "".join(body_parts))
        )
    return "".join(out)


def _mg_render_closing(cl: dict[str, Any]) -> str:
    title = _esc(cl.get("title") or "Closing")
    dur = (
        f' <span style="font-weight:400;opacity:0.8">({_esc(cl.get("duration"))})</span>'
        if cl.get("duration") else ""
    )
    time_html = (
        f' <span style="font-weight:400;opacity:0.65;font-size:0.85em">{_esc(cl.get("time"))}</span>'
        if cl.get("time") else ""
    )
    steps = cl.get("steps") or []
    if not isinstance(steps, list):
        steps = []
    rendered_steps: list[str] = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        step_type = _esc(s.get("type") or "")
        step_time = (
            f'<span style="color:#6b7280;font-size:0.82em;margin-left:8px">{_esc(s.get("time"))}</span>'
            if s.get("time") else ""
        )
        instr = _esc(s.get("instruction") or s.get("description") or s.get("activity") or "")
        extras: list[str] = []
        exit_tickets = s.get("exit_tickets")
        if isinstance(exit_tickets, dict) and exit_tickets:
            tickets_html = "".join(
                f'<div style="flex:1;min-width:200px;padding:6px 10px;background:#fff7ed;'
                f'border:1px solid #fdba74;border-radius:6px;font-size:0.88em">'
                f'<strong>{_esc(g)}:</strong> {_esc(t)}</div>'
                for g, t in exit_tickets.items()
            )
            extras.append(
                '<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:8px">'
                f'{tickets_html}</div>'
            )
        homework = s.get("homework")
        if isinstance(homework, dict) and homework:
            hw_html = "".join(
                f'<div style="flex:1;min-width:200px;padding:6px 10px;background:#f0fdf4;'
                f'border:1px solid #86efac;border-radius:6px;font-size:0.88em">'
                f'<strong>{_esc(g)}:</strong> {_esc(h)}</div>'
                for g, h in homework.items()
            )
            extras.append(
                '<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:8px">'
                f'{hw_html}</div>'
            )
        rendered_steps.append(
            '<div style="margin-bottom:10px;padding:10px 12px;background:#f9fafb;'
            'border-radius:6px;border:1px solid #e5e7eb">'
            f'<div style="font-weight:600;margin-bottom:4px">{step_type}{step_time}</div>'
            f'<div style="white-space:pre-wrap;font-size:0.95em">{instr}</div>'
            f'{"".join(extras)}</div>'
        )
    return _mg_section_card(_MG_COLORS["closing"], f"{title}{dur}{time_html}", "".join(rendered_steps))


def render_multigrade_html(spec: LPSpec, lp: dict[str, Any]) -> str:
    """Render the multigrade ``lesson_plan`` JSON to a Dars-styled HTML document (D-7).

    Mirrors ``displayMultigradeLessonPlan`` in
    ``UG_LessonPlan/static/index.html`` (L2014–2238) but emits a self-contained
    document using the same ``<body class="lp-doc">`` shell + ``lp.css`` as
    single-grade entries so the showcase iframe path is unchanged.
    """
    skill = _esc(spec.skill)
    page_line_text = (
        f"Page {_esc(spec.page)}"
        if spec.page else ""
    )
    if spec.topic:
        page_line_text = (
            f"{page_line_text} · {_esc(spec.topic)}"
            if page_line_text else _esc(spec.topic)
        )
    page_label = (
        f'<p class="lp-page-ref" style="max-width:720px;margin:0 auto 8px;'
        f'font-size:13px;color:#7a6b62;">{page_line_text}</p>'
        if page_line_text else ""
    )

    parts: list[str] = []

    lp_title = _esc(lp.get("title") or f"Multigrade Lesson — Grades {spec.grade_label}")
    parts.append(f'<h2 style="margin-bottom:4px">{lp_title}</h2>')

    time_breakdown = lp.get("time_breakdown")
    resources = lp.get("resources")
    if time_breakdown or (isinstance(resources, list) and resources):
        chips = []
        if time_breakdown:
            chips.append(f'<span>🕐 {_esc(time_breakdown)}</span>')
        if isinstance(resources, list) and resources:
            res_text = " · ".join(_esc(r) for r in resources)
            chips.append('<span style="color:#9ca3af">|</span>')
            chips.append(f'<span>📦 {res_text}</span>')
        parts.append(
            '<div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px;'
            'padding:10px 14px;background:#f8fafc;border-radius:6px;'
            'border:1px solid #e5e7eb;font-size:0.88em;color:#374151">'
            f'{"".join(chips)}</div>'
        )

    slo_progression = lp.get("slo_progression")
    if isinstance(slo_progression, dict) and slo_progression:
        color = _MG_COLORS["slo"]
        rows = []
        for grade, slo in slo_progression.items():
            slo_text = slo if isinstance(slo, str) else json.dumps(slo)
            rows.append(
                f'<tr><td style="padding:8px 12px;border:1px solid {color["border"]}44;'
                f'font-weight:600;white-space:nowrap;background:{color["bg"]}">{_esc(grade)}</td>'
                f'<td style="padding:8px 12px;border:1px solid {color["border"]}44">{_esc(slo_text)}</td></tr>'
            )
        table_html = (
            '<table style="width:100%;border-collapse:collapse"><thead>'
            f'<tr style="background:{color["bg"]}">'
            f'<th style="padding:8px 12px;text-align:left;border:1px solid {color["border"]}66;'
            f'color:{color["text"]}">Grade</th>'
            f'<th style="padding:8px 12px;text-align:left;border:1px solid {color["border"]}66;'
            f'color:{color["text"]}">Learning Objective</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )
        parts.append(_mg_section_card(color, "Learning Objectives by Grade", table_html))

    opening = lp.get("combined_opening")
    if isinstance(opening, dict):
        otitle = _esc(opening.get("title") or "Opening")
        odur = (
            f' <span style="font-weight:400;opacity:0.8">({_esc(opening.get("duration"))})</span>'
            if opening.get("duration") else ""
        )
        otime = (
            f' <span style="font-weight:400;opacity:0.65;font-size:0.85em">{_esc(opening.get("time"))}</span>'
            if opening.get("time") else ""
        )
        parts.append(
            _mg_section_card(_MG_COLORS["opening"], f'{otitle}{odur}{otime}', _mg_render_steps(opening.get("steps")))
        )

    board = lp.get("board_prep")
    if isinstance(board, dict):
        bp_parts: list[str] = []
        if board.get("when"):
            bp_parts.append(
                f'<div style="font-size:0.82em;font-weight:600;color:#475569;'
                f'margin-bottom:10px;padding:4px 8px;background:#f1f5f9;'
                f'border-radius:4px;display:inline-block">⏰ {_esc(board.get("when"))}</div>'
            )
        if board.get("layout"):
            bp_parts.append(
                f'<div style="margin-bottom:12px;font-size:0.95em">{_esc(board.get("layout"))}</div>'
            )
        sections = board.get("sections")
        if isinstance(sections, list) and sections:
            for sec in sections:
                if not isinstance(sec, dict):
                    continue
                heading = _esc(sec.get("heading") or sec.get("group_section") or "")
                lines = sec.get("lines")
                lines_html = ""
                if isinstance(lines, list) and lines:
                    items = "".join(
                        f'<li style="margin-bottom:3px">{_esc(l)}</li>' for l in lines
                    )
                    lines_html = (
                        '<ul style="margin:0 0 6px;padding-left:18px;font-size:0.9em">'
                        f'{items}</ul>'
                    )
                prep_note = (
                    f'<div style="font-size:0.82em;color:#64748b;font-style:italic">'
                    f'📌 {_esc(sec.get("prep_note"))}</div>'
                    if sec.get("prep_note") else ""
                )
                bp_parts.append(
                    '<div style="margin-bottom:10px;padding:10px 12px;background:#f8fafc;'
                    'border-radius:6px;border:1px solid #e2e8f0">'
                    f'<div style="font-weight:700;font-size:0.9em;margin-bottom:6px;color:#1e293b">'
                    f'{heading}</div>{lines_html}{prep_note}</div>'
                )
        parts.append(_mg_section_card(_MG_COLORS["board"], "Board Setup (Before Class)", "".join(bp_parts)))

    parts.append(_mg_render_rotations(lp.get("rotations")))

    closing = lp.get("combined_closing")
    if isinstance(closing, dict):
        parts.append(_mg_render_closing(closing))

    peer = lp.get("peer_tutoring_setup")
    if peer:
        parts.append(
            _mg_section_card(
                _MG_COLORS["peer"], "Peer Tutoring Setup",
                f'<div style="white-space:pre-wrap;font-size:0.95em">{_esc(peer)}</div>',
            )
        )

    doc_title = f"Grades {spec.grade_label} — {skill}"
    heading = doc_title

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{doc_title}</title>\n"
        '<link rel="stylesheet" href="/showcase/_assets/lp.css">\n'
        "</head>\n"
        '<body class="lp-doc">\n'
        '<span class="lp-eyebrow">Lesson plan · Multigrade</span>\n'
        f"<h1>{heading}</h1>\n"
        f"{page_label}\n"
        '<hr class="lp-divider">\n'
        f'{"".join(parts)}\n'
        '<div class="lp-footer">Generated by Dars</div>\n'
        "</body>\n"
        "</html>\n"
    )


def generate_one_multigrade(
    spec: LPSpec, base_url: str, api_key: str, curriculum: str
) -> LPResult:
    """Call LP Assistant ``/api/v1/generate-lp-multigrade`` for a multi-grade spec.

    Webhook-only endpoint: POST returns 202 + job_id; we poll
    ``GET /api/webhook-status/{job_id}`` until terminal (D-4). The completed
    payload is nested at ``data.response.lesson_plan`` (RedisCache convention).
    Never raises — same contract as ``generate_one``.
    """
    if not spec.is_multigrade:
        raise ValueError(f"generate_one_multigrade: expected list grade, got {spec.grade!r}")
    if not spec.per_grade_pages:
        return LPResult(
            spec=spec,
            status="ERROR",
            error="spec.per_grade_pages is required for multi-grade entries",
        )
    base = base_url.rstrip("/")
    # Placeholder callback_url — LP Assistant's POST sink at the same path is a no-op,
    # so this is safe even though we don't intend to receive the callback (D-4).
    callback_url = f"{base}/api/webhook-status/dars-showcase-placeholder"
    payload: dict[str, Any] = {
        "callback_url": callback_url,
        "curriculum": curriculum,
        "grades": sorted(spec.grade),  # type: ignore[arg-type]
        "subject": "Eng",
        "topic": spec.topic or None,
        "per_grade_page_numbers": {str(g): p for g, p in spec.per_grade_pages.items()},
        "class_strength": 30,
    }
    logger.info(
        "generate_one_multigrade: enter id=%s grades=%s pages=%s topic=%s curriculum=%s",
        spec.id, payload["grades"], payload["per_grade_page_numbers"], spec.topic, curriculum,
    )
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as http:
            resp = http.post(
                f"{base}/api/v1/generate-lp-multigrade",
                json=payload,
                headers={"api-key": api_key},
            )
            resp.raise_for_status()
            accepted = resp.json()
            job_id = accepted.get("job_id")
            if not job_id:
                raise ValueError(f"no job_id in 202 response: {accepted!r}")
            logger.info(
                "generate_one_multigrade: accepted id=%s job_id=%s eta_s=%s",
                spec.id, job_id, accepted.get("estimated_time_seconds"),
            )

            poll_url = f"{base}/api/webhook-status/{job_id}"
            for attempt in range(1, _MG_POLL_MAX_ATTEMPTS + 1):
                time.sleep(_MG_POLL_INTERVAL_S)
                pr = http.get(poll_url, headers={"api-key": api_key})
                pr.raise_for_status()
                body = pr.json()
                job_status = body.get("job_status")
                logger.info(
                    "generate_one_multigrade: poll id=%s job=%s attempt=%d/%d status=%s",
                    spec.id, job_id, attempt, _MG_POLL_MAX_ATTEMPTS, job_status,
                )
                if job_status == "completed":
                    data = body.get("data") or {}
                    response = data.get("response") or {}
                    lp_payload = response.get("lesson_plan")
                    # D-7: multigrade returns parsed JSON, not an HTML string. Render to
                    # Dars-styled HTML here so write_results can persist it directly.
                    if not isinstance(lp_payload, dict) or not lp_payload:
                        raise ValueError(
                            f"completed job {job_id} missing lesson_plan dict: "
                            f"data.keys={list(data)} response.keys={list(response)} "
                            f"lp_type={type(lp_payload).__name__}"
                        )
                    rendered = render_multigrade_html(spec, lp_payload)
                    logger.info(
                        "generate_one_multigrade: ok id=%s job=%s bytes=%d",
                        spec.id, job_id, len(rendered),
                    )
                    return LPResult(spec=spec, status="OK", html=rendered)
                if job_status == "failed":
                    err = (body.get("data") or {}).get("error") or "unknown failure"
                    raise RuntimeError(f"job {job_id} failed: {err}")
                # else: pending | processing → continue polling
            raise TimeoutError(
                f"multigrade job {job_id} did not finish within "
                f"{int(_MG_POLL_INTERVAL_S * _MG_POLL_MAX_ATTEMPTS)}s"
            )
    except httpx.HTTPStatusError as e:
        body = (e.response.text or "")[:500]
        msg = f"HTTP {e.response.status_code}: {body}"
        logger.error("generate_one_multigrade: http error id=%s %s", spec.id, msg, exc_info=True)
        return LPResult(spec=spec, status="ERROR", error=msg)
    except Exception as e:
        logger.error("generate_one_multigrade: error id=%s", spec.id, exc_info=True)
        return LPResult(spec=spec, status="ERROR", error=f"{type(e).__name__}: {e}")


def generate_dispatch(
    spec: LPSpec, base_url: str, api_key: str, curriculum: str
) -> LPResult:
    """Pick the right generator based on whether the spec is multi-grade (D-3)."""
    if spec.is_multigrade:
        return generate_one_multigrade(spec, base_url, api_key, curriculum)
    return generate_one(spec, base_url, api_key, curriculum)


@dataclass
class ReviewResult:
    spec: LPSpec
    status: str  # "OK" | "ERROR"
    error: str | None = None
    payload: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def review_file(self) -> str:
        return f"lp-{self.spec.id:02d}.review.json"


def review_one(
    spec: LPSpec,
    html_path: Path,
    base_url: str,
    api_key: str,
) -> ReviewResult:
    """Call LP Assistant /api/review-lp for a single LP. Never raises."""
    logger.info(
        "review_one: enter id=%s grade=%s page=%s skill=%s html=%s",
        spec.id, spec.grade, spec.page, spec.skill, html_path.name,
    )
    try:
        html_text = html_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("review_one: cannot read html id=%s path=%s", spec.id, html_path, exc_info=True)
        return ReviewResult(spec=spec, status="ERROR", error=f"read_html: {type(e).__name__}: {e}")

    payload: dict[str, Any] = {
        "lesson_plan_html": html_text,
        "subject": "Eng",
        "grade": spec.grade,
        "class_strength": 30,
    }
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as http:
            resp = http.post(
                f"{base_url.rstrip('/')}/api/review-lp",
                json=payload,
                headers={"api-key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
        if not isinstance(data, dict) or data.get("status") != "success":
            raise ValueError(f"unexpected response shape: keys={list(data) if isinstance(data, dict) else type(data).__name__}")
        review = data.get("review")
        if not isinstance(review, dict) or "evaluation" not in review:
            raise ValueError("response missing review.evaluation")
        crit_count = len(review.get("evaluation") or [])
        logger.info(
            "review_one: ok id=%s percentage=%s grandTotal=%s criteria=%d",
            spec.id, review.get("percentage"), review.get("grandTotal"), crit_count,
        )
        return ReviewResult(spec=spec, status="OK", payload=data)
    except httpx.HTTPStatusError as e:
        body = (e.response.text or "")[:500]
        msg = f"HTTP {e.response.status_code}: {body}"
        logger.error("review_one: http error id=%s %s", spec.id, msg, exc_info=True)
        return ReviewResult(spec=spec, status="ERROR", error=msg)
    except Exception as e:
        logger.error("review_one: error id=%s", spec.id, exc_info=True)
        return ReviewResult(spec=spec, status="ERROR", error=f"{type(e).__name__}: {e}")


def _spec_by_id(entry: dict[str, Any]) -> LPSpec | None:
    """Reconstruct an LPSpec from an index.json entry.

    Accepts either ``grade: int`` (single-grade) or ``grade: list[int]``
    (multi-grade, D-6). ``per_grade_pages`` is not round-tripped through
    ``index.json`` — it's only needed at generation time, not review time.
    """
    try:
        raw_grade = entry["grade"]
        if isinstance(raw_grade, list):
            grade: int | list[int] = [int(g) for g in raw_grade]
        else:
            grade = int(raw_grade)
        return LPSpec(
            id=int(entry["id"]),
            grade=grade,
            skill=str(entry["skill"]),
            page=str(entry["page"]),
            topic=str(entry.get("topic") or ""),
            lp_type=str(entry.get("lp_type") or ""),
        )
    except (KeyError, TypeError, ValueError):
        return None


def run_reviews(
    out_dir: Path,
    base_url: str,
    api_key: str,
    concurrency: int,
) -> int:
    """Read existing index.json + lp-NN.html, call /api/review-lp per LP, write
    review JSONs alongside, and update index.json in place with review fields.

    Returns 0 on success (even if individual reviews errored).
    """
    index_path = out_dir / "index.json"
    logger.info("run_reviews: enter out_dir=%s index=%s concurrency=%d", out_dir, index_path, concurrency)
    if not index_path.exists():
        logger.error("run_reviews: missing index.json at %s — generate LPs first", index_path)
        return 3
    try:
        raw_index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        logger.error("run_reviews: cannot parse index.json", exc_info=True)
        return 4
    if not isinstance(raw_index, list):
        logger.error("run_reviews: index.json is not a list")
        return 5

    tasks: list[tuple[LPSpec, Path, dict[str, Any]]] = []
    for entry in raw_index:
        if not isinstance(entry, dict):
            continue
        spec = _spec_by_id(entry)
        if spec is None:
            logger.error("run_reviews: skipping malformed entry %r", entry)
            continue
        if spec.is_multigrade:
            # D-5: LP Assistant has no multi-grade reviewer; never POST these to /api/review-lp.
            logger.info("run_reviews: skipping multi-grade lp id=%s grades=%s", spec.id, spec.grade)
            entry["review_file"] = f"lp-{spec.id:02d}.review.json"
            entry["review_status"] = "MISSING"
            entry["review_error"] = "no multi-grade reviewer available"
            continue
        if entry.get("status") != "OK":
            logger.info("run_reviews: skipping non-OK lp id=%s status=%s", spec.id, entry.get("status"))
            entry["review_file"] = f"lp-{spec.id:02d}.review.json"
            entry["review_status"] = "MISSING"
            entry["review_error"] = "lp generation failed; no html to review"
            continue
        html_path = out_dir / spec.html_file
        if not html_path.exists():
            logger.error("run_reviews: html missing for id=%s path=%s", spec.id, html_path)
            entry["review_file"] = f"lp-{spec.id:02d}.review.json"
            entry["review_status"] = "MISSING"
            entry["review_error"] = f"html file not found: {html_path.name}"
            continue
        tasks.append((spec, html_path, entry))

    results: list[ReviewResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(review_one, spec, html_path, base_url, api_key): (spec, entry)
            for (spec, html_path, entry) in tasks
        }
        for fut in concurrent.futures.as_completed(futures):
            spec, entry = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                logger.error("run_reviews: future failed id=%s", spec.id, exc_info=True)
                r = ReviewResult(spec=spec, status="ERROR", error=f"{type(e).__name__}: {e}")
            results.append(r)

            review_path = out_dir / r.review_file
            if r.status == "OK" and r.payload is not None:
                review_path.write_text(json.dumps(r.payload, indent=2), encoding="utf-8")
                entry["review_file"] = r.review_file
                entry["review_status"] = "OK"
                entry.pop("review_error", None)
            else:
                err_doc = {"status": "error", "error": r.error or "unknown error"}
                review_path.write_text(json.dumps(err_doc, indent=2), encoding="utf-8")
                entry["review_file"] = r.review_file
                entry["review_status"] = "ERROR"
                entry["review_error"] = r.error or "unknown error"

    index_path.write_text(json.dumps(raw_index, indent=2), encoding="utf-8")

    ok = sum(1 for r in results if r.status == "OK")
    err = sum(1 for r in results if r.status == "ERROR")
    logger.info(
        "run_reviews: exit ok=%d err=%d skipped=%d total_index=%d",
        ok, err, len(raw_index) - len(results), len(raw_index),
    )
    return 0


def reset_output_dir(tag: str) -> Path:
    out = OUTPUT_ROOT / tag
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    logger.info("reset_output_dir: cleaned out=%s", out)
    return out


def write_results(out_dir: Path, results: list[LPResult]) -> None:
    """Persist HTML files + index.json. Sorted by spec.id.

    Multi-grade entries (D-5/D-6) write ``grade`` as a list and force
    ``review_status="MISSING"`` since LP Assistant has no multi-grade reviewer.
    """
    results_sorted = sorted(results, key=lambda r: r.spec.id)
    index: list[dict[str, Any]] = []
    for r in results_sorted:
        entry: dict[str, Any] = {
            "id": r.spec.id,
            "grade": r.spec.grade,
            "skill": r.spec.skill,
            "page": r.spec.page,
            "topic": r.spec.topic,
            "lp_type": r.spec.lp_type,
            "status": r.status,
            "html_file": r.spec.html_file,
            "review_file": f"lp-{r.spec.id:02d}.review.json",
            "review_status": "MISSING",
        }
        if r.spec.is_multigrade:
            entry["review_error"] = "no multi-grade reviewer available"
        if r.status == "OK" and r.html is not None:
            # Multigrade results are already a full Dars-styled HTML document (D-7);
            # only single-grade results go through wrap_html.
            doc = r.html if r.spec.is_multigrade else wrap_html(r.spec, r.html)
            (out_dir / r.spec.html_file).write_text(doc, encoding="utf-8")
        else:
            entry["error"] = r.error or "unknown error"
        index.append(entry)
    (out_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    logger.info(
        "write_results: wrote %d entries (ok=%d err=%d) to %s",
        len(index),
        sum(1 for e in index if e["status"] == "OK"),
        sum(1 for e in index if e["status"] == "ERROR"),
        out_dir,
    )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Generate showcase LPs via LP Assistant.")
    parser.add_argument("--curriculum", default="ICT", help="Curriculum to use (default ICT)")
    parser.add_argument("--tag", default=DEFAULT_TAG, help="Showcase tag / subdirectory name")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument(
        "--lp-assistant-url",
        default=os.environ.get("LP_ASSISTANT_URL", DEFAULT_LP_ASSISTANT_URL),
    )
    parser.add_argument(
        "--reviews-only",
        action="store_true",
        help="Skip LP generation; only run /api/review-lp against existing HTML",
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("LP_ASSISTANT_API_KEY", "").strip()
    if not api_key:
        logger.error("main: LP_ASSISTANT_API_KEY env var is required")
        return 2

    logger.info(
        "main: enter tag=%s curriculum=%s concurrency=%d url=%s count=%d reviews_only=%s",
        args.tag, args.curriculum, args.concurrency, args.lp_assistant_url,
        len(SPECS), args.reviews_only,
    )

    if args.reviews_only:
        out_dir = OUTPUT_ROOT / args.tag
        if not out_dir.exists():
            logger.error("main: tag dir does not exist: %s", out_dir)
            return 3
        rc = run_reviews(out_dir, args.lp_assistant_url, api_key, args.concurrency)
        logger.info("main: exit (reviews-only) rc=%d out=%s", rc, out_dir)
        return rc

    out_dir = reset_output_dir(args.tag)

    results: list[LPResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(generate_dispatch, s, args.lp_assistant_url, api_key, args.curriculum): s
            for s in SPECS
        }
        for fut in concurrent.futures.as_completed(futures):
            spec = futures[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                logger.error("main: future failed id=%s", spec.id, exc_info=True)
                results.append(LPResult(spec=spec, status="ERROR", error=f"{type(e).__name__}: {e}"))

    write_results(out_dir, results)

    ok = sum(1 for r in results if r.status == "OK")
    err = len(results) - ok
    logger.info("main: exit ok=%d err=%d total=%d out=%s", ok, err, len(results), out_dir)
    # exit 0 even with partial errors so the showcase page can render them
    return 0


if __name__ == "__main__":
    sys.exit(main())
