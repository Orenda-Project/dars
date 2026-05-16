"""
Prompt loader for the breakdown engine.

Per D-66 / phase doc F2.3: prompts live as .txt files inside this package.
No DB-backed prompt storage — keep it simple.
"""
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"

_PROMPT_FILES = {
    "english_slo_breakdown": "english_prompt.txt",
    # F2.3 will add: math_slo_breakdown, urdu_slo_breakdown, topic_breakdown,
    # chapter_plan, slo_mapping, lp_tagging
}


def get_prompt(key: str) -> str:
    """Return the prompt text for `key`. Raises if unknown."""
    if key not in _PROMPT_FILES:
        raise KeyError(f"Unknown prompt key: {key!r}. Known: {sorted(_PROMPT_FILES)}")
    path = _PROMPTS_DIR / _PROMPT_FILES[key]
    if not path.exists():
        raise FileNotFoundError(f"Prompt file missing: {path}")
    return path.read_text(encoding="utf-8")
