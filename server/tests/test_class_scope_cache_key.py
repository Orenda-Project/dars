"""F-2.5 / D-12 — class-scope LP cache key is topic-set aware (pure, no DB).

Pins the keying invariants for multi-topic LP units:
  - two distinct multi-topic units (same CST/curriculum/lp_type) get distinct
    keys (no collision),
  - order matters (a merged lesson A→B is a different lesson from B→A),
  - a multi-topic key never collides with the single-topic class key for any
    of its member topics (the `:set:` segment disambiguates).
"""
from uuid import uuid4

from dars.generated_lps.service import (
    _build_cache_key_class,
    _build_cache_key_class_topic_set,
)


def test_two_distinct_multi_topic_units_dont_collide():
    cur, cst = uuid4(), uuid4()
    a, b, c = uuid4(), uuid4(), uuid4()
    k_ab = _build_cache_key_class_topic_set(cur, cst, [a, b], "reading")
    k_ac = _build_cache_key_class_topic_set(cur, cst, [a, c], "reading")
    assert k_ab != k_ac


def test_topic_order_changes_key():
    cur, cst = uuid4(), uuid4()
    a, b = uuid4(), uuid4()
    assert _build_cache_key_class_topic_set(
        cur, cst, [a, b], "reading"
    ) != _build_cache_key_class_topic_set(cur, cst, [b, a], "reading")


def test_lp_type_changes_key():
    cur, cst = uuid4(), uuid4()
    a, b = uuid4(), uuid4()
    assert _build_cache_key_class_topic_set(
        cur, cst, [a, b], "reading"
    ) != _build_cache_key_class_topic_set(cur, cst, [a, b], "grammar")


def test_multi_topic_key_distinct_from_single_topic_class_key():
    cur, cst = uuid4(), uuid4()
    a, b = uuid4(), uuid4()
    multi = _build_cache_key_class_topic_set(cur, cst, [a, b], "reading")
    single_a = _build_cache_key_class(cur, cst, a, "reading")
    single_b = _build_cache_key_class(cur, cst, b, "reading")
    assert multi != single_a
    assert multi != single_b
