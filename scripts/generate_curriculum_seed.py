#!/usr/bin/env python3
"""
Generate supabase/migrations/20260413000006_seed_punjab_curriculum.sql
from Punjab Curriculum Matrix — Enrichment Pipeline Reference.xlsx

Usage:
    python3 scripts/generate_curriculum_seed.py
"""

import re
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("openpyxl not installed. Run: pip install openpyxl", file=sys.stderr)
    sys.exit(1)

XLSX_PATH = Path("/home/hataf/Downloads/Punjab Curriculum Matrix — Enrichment Pipeline Reference.xlsx")
SHEET_NAME = "All Segments + SLOs"
OUTPUT_PATH = Path(__file__).parent.parent / "supabase/migrations/20260413000006_seed_punjab_curriculum.sql"

SUBJECT_MAP = {
    "English": "Eng",
    "Maths": "Maths",
    "Urdu": "Urdu",
}

GRADE_MAP = {
    "1": "G1",
    "2": "G2",
    "3": "G3",
    "4": "G4",
    "5": "G5",
}


def classify_segment(day_label: str) -> str:
    if not day_label:
        return "lesson"
    if "↻" in day_label or "spiral" in day_label.lower():
        return "spiral_review"
    if "📋" in day_label or "review" in day_label.lower():
        return "chapter_review"
    return "lesson"


def parse_day_number(day_label: str) -> int | None:
    if not day_label:
        return None
    m = re.search(r"Day\s+(\d+)", day_label, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def esc(val: str) -> str:
    """Escape single quotes for SQL."""
    return val.replace("'", "''")


def safe_str(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def main() -> None:
    print(f"Loading {XLSX_PATH} ...")
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb[SHEET_NAME]

    rows = list(ws.iter_rows(values_only=True))
    # Row 0 = title, Row 1 = header, Rows 2+ = data
    data_rows = rows[2:]
    print(f"Found {len(data_rows)} data rows")

    # Collect unique SLOs keyed by (code, board)
    slos: dict[tuple[str, str], dict] = {}
    # Collect curriculum days (list of dicts, preserving order)
    days: list[dict] = []
    # day -> slo_codes mapping
    day_slo_map: list[list[str]] = []

    board = "Punjab"
    sequence_counters: dict[tuple[str, str], int] = {}  # (subject_short, grade_short) -> seq

    for i, row in enumerate(data_rows):
        subject_raw = safe_str(row[0])
        grade_raw = safe_str(row[1])
        chapter_number_raw = safe_str(row[2])
        chapter_title = safe_str(row[3])
        day_label = safe_str(row[4])
        topic = safe_str(row[5])
        skill_type = safe_str(row[6])
        cpa_phase = safe_str(row[7])
        pages = safe_str(row[8])
        slo_codes_raw = safe_str(row[9])
        slo_descriptions_raw = safe_str(row[10])
        blooms = safe_str(row[11])
        duration = safe_str(row[12])
        slides = safe_str(row[13])
        enriched = safe_str(row[14])
        verified = safe_str(row[15]) if len(row) > 15 else ""

        subject_short = SUBJECT_MAP.get(subject_raw)
        if not subject_short:
            print(f"WARNING: unknown subject '{subject_raw}' at data row {i}, skipping")
            continue

        grade_short = GRADE_MAP.get(grade_raw)
        if not grade_short:
            print(f"WARNING: unknown grade '{grade_raw}' at data row {i}, skipping")
            continue

        try:
            chapter_number = int(chapter_number_raw) if chapter_number_raw else 0
        except ValueError:
            chapter_number = 0

        segment_type = classify_segment(day_label)
        day_number = parse_day_number(day_label)

        key = (subject_short, grade_short)
        seq = sequence_counters.get(key, 0) + 1
        sequence_counters[key] = seq

        # Parse SLO codes and descriptions
        slo_codes = [c.strip() for c in slo_codes_raw.split(",") if c.strip()]
        slo_descs = [d.strip() for d in slo_descriptions_raw.split("|") if d.strip()]

        for j, code in enumerate(slo_codes):
            desc = slo_descs[j] if j < len(slo_descs) else ""
            slos[(code, board)] = {
                "code": code,
                "description": desc,
                "subject_short": subject_short,
                "grade_short": grade_short,
                "board": board,
            }

        try:
            dur_int = int(duration) if duration else None
        except ValueError:
            dur_int = None

        try:
            slides_int = int(slides) if slides else None
        except ValueError:
            slides_int = None

        is_enriched = enriched.lower() == "yes"
        is_verified = verified.lower() == "yes"

        days.append({
            "subject_short": subject_short,
            "grade_short": grade_short,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "sequence": seq,
            "day_label": day_label,
            "day_number": day_number,
            "segment_type": segment_type,
            "topic": topic,
            "skill_type": skill_type,
            "cpa_phase": cpa_phase,
            "pages": pages,
            "blooms_level": blooms,
            "duration_minutes": dur_int,
            "slide_count": slides_int,
            "is_enriched": is_enriched,
            "is_verified": is_verified,
        })
        day_slo_map.append(slo_codes)

    print(f"Unique SLOs: {len(slos)}")
    print(f"Curriculum days: {len(days)}")

    # Build SQL
    lines = []
    lines.append("-- Auto-generated by scripts/generate_curriculum_seed.py")
    lines.append("-- DO NOT EDIT MANUALLY")
    lines.append("")
    lines.append("DO $$")
    lines.append("DECLARE")
    lines.append("    v_curriculum_id uuid;")

    # Declare grade vars
    for short in sorted(set(GRADE_MAP.values())):
        lines.append(f"    v_grade_{short.lower()} uuid;")

    # Declare subject vars
    for short in sorted(set(SUBJECT_MAP.values())):
        safe = short.lower().replace(" ", "_")
        lines.append(f"    v_subject_{safe} uuid;")

    # Declare SLO vars
    for idx, (code, _board) in enumerate(sorted(slos.keys())):
        var = "v_slo_" + re.sub(r"[^a-z0-9]", "_", code.lower())
        lines.append(f"    {var} uuid;")

    # Declare day vars
    for i in range(len(days)):
        lines.append(f"    v_day_{i} uuid;")

    lines.append("BEGIN")
    lines.append("")

    # Resolve curriculum
    lines.append("    SELECT id INTO v_curriculum_id FROM curriculums WHERE board = 'Punjab' AND name = 'Punjab SNC 2020';")
    lines.append("")

    # Resolve grades
    for short in sorted(set(GRADE_MAP.values())):
        lines.append(f"    SELECT id INTO v_grade_{short.lower()} FROM grades WHERE short_code = '{short}';")
    lines.append("")

    # Resolve subjects
    for short in sorted(set(SUBJECT_MAP.values())):
        safe = short.lower().replace(" ", "_")
        lines.append(f"    SELECT id INTO v_subject_{safe} FROM subjects WHERE short_code = '{short}';")
    lines.append("")

    # Insert SLOs
    lines.append("    -- Insert SLOs (ON CONFLICT DO NOTHING — idempotent)")
    for (code, board_val), slo in sorted(slos.items()):
        subject_safe = slo["subject_short"].lower().replace(" ", "_")
        grade_safe = slo["grade_short"].lower()
        var = "v_slo_" + re.sub(r"[^a-z0-9]", "_", code.lower())
        lines.append(
            f"    INSERT INTO slos (code, description, subject_id, grade_id, board)"
            f" VALUES ('{esc(code)}', '{esc(slo['description'])}', v_subject_{subject_safe}, v_grade_{grade_safe}, '{esc(board_val)}')"
            f" ON CONFLICT (code, board) DO NOTHING"
            f" RETURNING id INTO {var};"
        )
        lines.append(
            f"    IF {var} IS NULL THEN SELECT id INTO {var} FROM slos WHERE code = '{esc(code)}' AND board = '{esc(board_val)}'; END IF;"
        )
    lines.append("")

    # Insert curriculum days
    lines.append("    -- Insert curriculum days")
    for i, day in enumerate(days):
        subject_safe = day["subject_short"].lower().replace(" ", "_")
        grade_safe = day["grade_short"].lower()

        def sql_str(v):
            if v is None or v == "":
                return "NULL"
            return f"'{esc(str(v))}'"

        def sql_int(v):
            if v is None:
                return "NULL"
            return str(v)

        def sql_bool(v):
            return "true" if v else "false"

        lines.append(
            f"    INSERT INTO curriculum_days"
            f" (curriculum_id, grade_id, subject_id, chapter_number, chapter_title,"
            f" sequence, day_label, day_number, segment_type, topic, skill_type,"
            f" cpa_phase, pages, blooms_level, duration_minutes, slide_count,"
            f" is_enriched, is_verified)"
            f" VALUES"
            f" (v_curriculum_id, v_grade_{grade_safe}, v_subject_{subject_safe},"
            f" {day['chapter_number']}, {sql_str(day['chapter_title'])},"
            f" {day['sequence']}, {sql_str(day['day_label'])}, {sql_int(day['day_number'])},"
            f" '{esc(day['segment_type'])}', {sql_str(day['topic'])}, {sql_str(day['skill_type'] or None)},"
            f" {sql_str(day['cpa_phase'] or None)}, {sql_str(day['pages'] or None)}, {sql_str(day['blooms_level'] or None)},"
            f" {sql_int(day['duration_minutes'])}, {sql_int(day['slide_count'])},"
            f" {sql_bool(day['is_enriched'])}, {sql_bool(day['is_verified'])})"
            f" RETURNING id INTO v_day_{i};"
        )

    lines.append("")
    # Insert day-slo links
    lines.append("    -- Insert curriculum_day_slos")
    for i, slo_codes in enumerate(day_slo_map):
        for code in slo_codes:
            if (code, board) not in slos:
                continue
            var = "v_slo_" + re.sub(r"[^a-z0-9]", "_", code.lower())
            lines.append(
                f"    IF v_day_{i} IS NOT NULL AND {var} IS NOT NULL THEN"
                f" INSERT INTO curriculum_day_slos (curriculum_day_id, slo_id)"
                f" VALUES (v_day_{i}, {var}) ON CONFLICT DO NOTHING; END IF;"
            )

    lines.append("")
    lines.append("END $$;")
    lines.append("")

    sql = "\n".join(lines)
    OUTPUT_PATH.write_text(sql, encoding="utf-8")
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
