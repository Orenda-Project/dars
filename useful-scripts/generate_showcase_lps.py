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
    grade: int
    skill: str
    page: str
    topic: str

    @property
    def custom_prompt(self) -> str:
        topic_clause = f" Topic: {self.topic}." if self.topic else ""
        return f"Focus this lesson on the {self.skill} skill.{topic_clause}"

    @property
    def html_file(self) -> str:
        return f"lp-{self.id:02d}.html"


SPECS: list[LPSpec] = [
    LPSpec(1, 2, "Reading", "111", "Journey through text"),
    LPSpec(2, 2, "Comprehension w/ meanings", "15", "New words to know"),
    LPSpec(3, 2, "Comprehension Q&A", "127-128", "Activity 2"),
    LPSpec(4, 2, "Grammar", "10", "Activity 3"),
    LPSpec(5, 2, "Creative writing", "133", ""),
    LPSpec(6, 5, "Reading", "32-33", "Journey through text"),
    LPSpec(7, 5, "Comprehension w/ meanings", "44-45", "Memory lane"),
    LPSpec(8, 5, "Comprehension Q&A", "49", "Activity 3"),
    LPSpec(9, 5, "Grammar", "39", "Activity 3"),
    LPSpec(10, 5, "Creative writing", "15", "Activity 3"),
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
    title = f"Grade {spec.grade} — {skill}"
    heading = f"Grade {spec.grade} — {skill}"

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
        "custom_prompt": spec.custom_prompt,
    }
    logger.info(
        "generate_one: enter id=%s grade=%s page=%s skill=%s curriculum=%s",
        spec.id, spec.grade, spec.page, spec.skill, curriculum,
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
    """Reconstruct an LPSpec from an index.json entry."""
    try:
        return LPSpec(
            id=int(entry["id"]),
            grade=int(entry["grade"]),
            skill=str(entry["skill"]),
            page=str(entry["page"]),
            topic=str(entry.get("topic") or ""),
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
    """Persist HTML files + index.json. Sorted by spec.id."""
    results_sorted = sorted(results, key=lambda r: r.spec.id)
    index: list[dict[str, Any]] = []
    for r in results_sorted:
        entry: dict[str, Any] = {
            "id": r.spec.id,
            "grade": r.spec.grade,
            "skill": r.spec.skill,
            "page": r.spec.page,
            "topic": r.spec.topic,
            "status": r.status,
            "html_file": r.spec.html_file,
            "review_file": f"lp-{r.spec.id:02d}.review.json",
            "review_status": "MISSING",
        }
        if r.status == "OK" and r.html is not None:
            wrapped = wrap_html(r.spec, r.html)
            (out_dir / r.spec.html_file).write_text(wrapped, encoding="utf-8")
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
            pool.submit(generate_one, s, args.lp_assistant_url, api_key, args.curriculum): s
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
