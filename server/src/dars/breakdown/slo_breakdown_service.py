"""
F2.1 — Async port of Schema's slo_breakdown service.

Generates sub-SLOs from SLOs via an LLM and persists them to `sub_slos`
with `source='schema_breakdown'`. Idempotent: existing schema_breakdown
sub-SLOs for an SLO are kept unless `force=True`.

Public surface:
    - run_breakdown_for_slos(conn, slo_ids, *, subject_key, force) -> result
    - parse_breakdown_markdown(text) -> list[dict]
"""
import logging
import re
from typing import Awaitable, Callable
from uuid import UUID

import asyncpg

from dars.breakdown.llm_client import call_llm as default_call_llm
from dars.breakdown.prompt_store import get_prompt

log = logging.getLogger("breakdown.slo")

# Subject key → prompt key in prompt_store
SUBJECT_PROMPT_KEY = {
    "english": "english_slo_breakdown",
    # F2.3: "math": "math_slo_breakdown", "urdu": "urdu_slo_breakdown"
}

LLMCallable = Callable[[str, str], Awaitable[str]]


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

_SEPARATOR_RE = re.compile(r"^\|[\s\-:|]+\|$")


def parse_breakdown_markdown(md: str) -> list[dict]:
    """
    Parse the LLM's markdown table into rows.

    The English prompt's output format:
        | SLO Code | Main SLO (verbatim) | Sub SLO Code | Sub SLOs |

    Returns a list of {slo_code, main_slo, sub_slo_code, sub_slo} dicts.
    Header rows and the separator are skipped. Unknown column layouts
    raise ValueError so callers can surface the LLM error.
    """
    headers: list[str] | None = None
    rows: list[dict] = []
    for raw_line in md.strip().splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        if _SEPARATOR_RE.match(line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if headers is None:
            headers = [c.lower() for c in cells]
            continue
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))

    if not rows:
        raise ValueError("no markdown table rows found in LLM response")

    # Locate columns we care about, tolerating header variants.
    # Needles are tried in order; the first matching header is returned.
    # Order matters: list more-specific needles first.
    def _find(*needles: str, exclude: tuple[str, ...] = ()) -> str:
        assert headers is not None
        for n in needles:
            for h in headers:
                if any(x in h for x in exclude):
                    continue
                if n in h:
                    return h
        raise ValueError(f"no column matching {needles} in headers={headers}")

    slo_code_col = _find("slo code", exclude=("sub",))
    main_slo_col = _find("main slo")
    sub_code_col = _find("sub slo code", "sub-slo code")
    # Sub-SLO text column: exclude the code column we just identified.
    sub_slo_col = _find("sub slos", "sub-slos", "sub slo", exclude=("code",))

    parsed: list[dict] = []
    for r in rows:
        slo_code = r.get(slo_code_col, "").strip()
        if not slo_code:
            continue
        parsed.append({
            "slo_code": slo_code,
            "main_slo": r.get(main_slo_col, "").strip(),
            "sub_slo_code": r.get(sub_code_col, "").strip(),
            "sub_slo": r.get(sub_slo_col, "").strip(),
        })
    return parsed


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

async def run_breakdown_for_slos(
    conn: asyncpg.Connection,
    slo_ids: list[UUID],
    *,
    subject_key: str,
    force: bool = False,
    llm: LLMCallable | None = None,
) -> dict:
    """
    Run the SLO → sub-SLO breakdown for the given SLOs.

    Args:
        conn:        an open asyncpg connection
        slo_ids:     list of slos.id UUIDs to break down (must share subject_key)
        subject_key: 'english' | 'math' | 'urdu'
        force:       if True, re-run even if schema_breakdown sub-SLOs exist
        llm:         async callable(system_prompt, user_message) -> str
                     (override for tests; defaults to anthropic via llm_client)

    Returns:
        {
          "subject": str,
          "slo_count": int,
          "skipped_slo_ids": [UUID],         # already had schema_breakdown rows
          "inserted_sub_slo_count": int,
          "markdown": str,                    # raw LLM response (or "" if skipped)
        }

    Raises:
        KeyError:   subject_key not supported
        ValueError: no SLOs found, or LLM response unparseable
    """
    log.info(
        "run_breakdown_for_slos: entry subject=%s slo_count=%d force=%s",
        subject_key, len(slo_ids), force,
    )
    if subject_key not in SUBJECT_PROMPT_KEY:
        raise KeyError(
            f"unsupported subject_key={subject_key!r}; "
            f"supported: {sorted(SUBJECT_PROMPT_KEY)}"
        )
    if not slo_ids:
        raise ValueError("slo_ids is empty")

    # Load SLOs and figure out which need processing.
    rows = await conn.fetch(
        """
        SELECT id, code, statement, position
        FROM slos
        WHERE id = ANY($1::uuid[])
        ORDER BY position, code
        """,
        slo_ids,
    )
    if len(rows) != len(slo_ids):
        missing = set(slo_ids) - {r["id"] for r in rows}
        raise ValueError(f"SLO ids not found: {sorted(str(m) for m in missing)}")

    skipped: list[UUID] = []
    targets: list[asyncpg.Record] = []
    if force:
        targets = list(rows)
    else:
        existing = await conn.fetch(
            """
            SELECT DISTINCT slo_id
            FROM sub_slos
            WHERE slo_id = ANY($1::uuid[]) AND source = 'schema_breakdown'
            """,
            slo_ids,
        )
        existing_ids = {r["slo_id"] for r in existing}
        for r in rows:
            if r["id"] in existing_ids:
                skipped.append(r["id"])
            else:
                targets.append(r)

    if not targets:
        log.info(
            "run_breakdown_for_slos: all %d SLOs already have schema_breakdown sub-SLOs, skipping LLM",
            len(skipped),
        )
        return {
            "subject": subject_key,
            "slo_count": len(slo_ids),
            "skipped_slo_ids": skipped,
            "inserted_sub_slo_count": 0,
            "markdown": "",
        }

    # Build the prompt.
    system_prompt = get_prompt(SUBJECT_PROMPT_KEY[subject_key])
    slo_text = "\n".join(f"{r['code']}: {r['statement']}" for r in targets)
    user_message = (
        f"Subject: {subject_key.capitalize()}\n"
        f"Total SLOs: {len(targets)}\n\n"
        f"Here are the main SLOs:\n\n{slo_text}\n"
    )

    llm_call = llm or default_call_llm
    markdown = await llm_call(system_prompt, user_message)
    if not markdown:
        raise ValueError("LLM returned empty response")

    parsed_rows = parse_breakdown_markdown(markdown)

    # Index targets by code for FK resolution.
    by_code: dict[str, asyncpg.Record] = {r["code"]: r for r in targets}

    # Group parsed rows by SLO code (in order of appearance) and assign positions.
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for pr in parsed_rows:
        code = pr["slo_code"]
        if code not in by_code:
            log.warning(
                "run_breakdown_for_slos: LLM emitted unknown SLO code=%s — skipping row",
                code,
            )
            continue
        if code not in grouped:
            grouped[code] = []
            order.append(code)
        grouped[code].append(pr)

    inserted = 0
    async with conn.transaction():
        for slo_code in order:
            slo_row = by_code[slo_code]
            slo_id = slo_row["id"]
            for position, pr in enumerate(grouped[slo_code], start=1):
                sub_code = pr["sub_slo_code"] or f"{slo_code}.{position}"
                sub_statement = pr["sub_slo"]
                if not sub_statement:
                    continue
                result = await conn.execute(
                    """
                    INSERT INTO sub_slos (slo_id, code, statement, position, source)
                    VALUES ($1, $2, $3, $4, 'schema_breakdown')
                    ON CONFLICT (slo_id, code) DO NOTHING
                    """,
                    slo_id, sub_code, sub_statement, position,
                )
                if result.endswith(" 1"):
                    inserted += 1

    log.info(
        "run_breakdown_for_slos: exit subject=%s processed=%d skipped=%d inserted=%d",
        subject_key, len(targets), len(skipped), inserted,
    )
    return {
        "subject": subject_key,
        "slo_count": len(slo_ids),
        "skipped_slo_ids": skipped,
        "inserted_sub_slo_count": inserted,
        "markdown": markdown,
    }
