"""
Prompt loader for the breakdown engine.

Per D-66 / phase doc F2.3: prompts live as .txt files inside this package.
No DB-backed prompt storage — keep it simple.
"""
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"

_PROMPT_FILES = {
    # Subject-specific SLO → sub-SLO breakdown (used by slo_breakdown_service)
    "english_slo_breakdown": "english_prompt.txt",
    "math_slo_breakdown": "math_prompt.txt",
    "urdu_slo_breakdown": "urdu_prompt.txt",
    # Chapter / topic flow (used by chapter_breakdown_service + future F2.5)
    "topic_breakdown": "topic_breakdown_prompt.txt",
    "chapter_plan": "chapter_plan_prompt.txt",
    "slo_mapping": "mapping_prompt.txt",
    # LP tagging (used in Phase 3)
    "lp_tagging": "lp_tagging_prompt.txt",
}


def get_prompt(key: str) -> str:
    """Return the prompt text for `key`. Raises if unknown."""
    if key not in _PROMPT_FILES:
        raise KeyError(f"Unknown prompt key: {key!r}. Known: {sorted(_PROMPT_FILES)}")
    path = _PROMPTS_DIR / _PROMPT_FILES[key]
    if not path.exists():
        raise FileNotFoundError(f"Prompt file missing: {path}")
    return path.read_text(encoding="utf-8")
