#!/usr/bin/env python3
"""Generate the 10 showcase LPs via LP Assistant and write static HTML into the webapp.

Usage:
    LP_ASSISTANT_API_KEY=... python3 useful-scripts/generate_showcase_lps.py \
        [--curriculum ICT|Punjab|Sindh] \
        [--tag ali-sipra-2026-05-15] \
        [--concurrency 3]

Output:
    webapp/public/showcase/<tag>/lp-NN.html       raw lesson_plan HTML
    webapp/public/showcase/<tag>/index.json       {id,grade,skill,page,topic,status,html_file,error?}[]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
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
DEFAULT_TAG = "ali-sipra-2026-05-15"
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
    LPSpec(3, 2, "Comprehension Q&A", "127,128", "Activity 2"),
    LPSpec(4, 2, "Grammar", "10", "Activity 3"),
    LPSpec(5, 2, "Creative writing", "133", ""),
    LPSpec(6, 5, "Reading", "32,33", "Journey through text"),
    LPSpec(7, 5, "Comprehension w/ meanings", "44,45", "Memory lane"),
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


def generate_one(
    spec: LPSpec, base_url: str, api_key: str, curriculum: str
) -> LPResult:
    """Call LP Assistant for a single spec. Returns LPResult; never raises."""
    payload: dict[str, Any] = {
        "curriculum": curriculum,
        "grade": spec.grade,
        "subject": "English",
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
        }
        if r.status == "OK" and r.html is not None:
            (out_dir / r.spec.html_file).write_text(r.html, encoding="utf-8")
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
    args = parser.parse_args(argv)

    api_key = os.environ.get("LP_ASSISTANT_API_KEY", "").strip()
    if not api_key:
        logger.error("main: LP_ASSISTANT_API_KEY env var is required")
        return 2

    logger.info(
        "main: enter tag=%s curriculum=%s concurrency=%d url=%s count=%d",
        args.tag, args.curriculum, args.concurrency, args.lp_assistant_url, len(SPECS),
    )

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
