"""
Tests for the UG_LP adapter (ug_lp_client) and the /generate-lp-for-unit endpoint.

No live UG_LP call — a fake httpx.AsyncClient / monkeypatched generate_lp stand in.
Covers: D-7 mapping, generate_lp 200 + non-200 + missing key, endpoint 200/502/503.
"""
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import config  # noqa: E402
import main  # noqa: E402
import ug_lp_client  # noqa: E402
from ug_lp_client import UgLpError, build_lp_request, generate_lp  # noqa: E402


SAMPLE_UNIT = {
    "sequence": 1,
    "lp_type": "reading",
    "topic_ids": ["t1"],
    "slo_ids": ["s1"],
    "topic_text": "hello, good morning",
    "rationale": "intro reading",
}


# --------------------------------------------------------------------------
# build_lp_request — D-7 mapping
# --------------------------------------------------------------------------
def test_build_lp_request_mapping():
    body = build_lp_request(SAMPLE_UNIT, subject="Eng", grade=2, curriculum="ICT")
    assert body == {
        "curriculum": "ICT",
        "grade": 2,
        "subject": "Eng",
        "lp_type": "reading",
        "page_content": "hello, good morning",  # == unit.topic_text
        "class_strength": 30,
    }
    assert "page_number" not in body  # page_content takes precedence


def test_build_lp_request_empty_topic_text():
    body = build_lp_request({"lp_type": "revision"}, subject="GK", grade=1, curriculum="Punjab")
    assert body["page_content"] == ""
    assert body["lp_type"] == "revision"


# --------------------------------------------------------------------------
# generate_lp — fake httpx client
# --------------------------------------------------------------------------
def _fake_client(status, json_body=None, text_body=""):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("api-key") == "TEST_KEY"
        if json_body is not None:
            return httpx.Response(status, json=json_body)
        return httpx.Response(status, text=text_body)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _set_key(monkeypatch):
    monkeypatch.setattr(config, "UG_LP_API_KEY", "TEST_KEY")
    monkeypatch.setattr(config, "UG_LP_URL", "https://ug-lp.test")


async def test_generate_lp_200_parsed():
    client = _fake_client(200, json_body={"lesson_plan": "<h1>LP</h1>", "meta": 1})
    data = await generate_lp(SAMPLE_UNIT, "Eng", 2, "ICT", client=client)
    assert data["lesson_plan"] == "<h1>LP</h1>"
    await client.aclose()


async def test_generate_lp_non_200_raises():
    client = _fake_client(500, text_body="boom")
    with pytest.raises(UgLpError) as ei:
        await generate_lp(SAMPLE_UNIT, "Eng", 2, "ICT", client=client)
    assert "500" in str(ei.value)
    await client.aclose()


async def test_generate_lp_missing_key_raises(monkeypatch):
    monkeypatch.setattr(config, "UG_LP_API_KEY", None)
    with pytest.raises(UgLpError) as ei:
        await generate_lp(SAMPLE_UNIT, "Eng", 2, "ICT", client=_fake_client(200, {"lesson_plan": "x"}))
    assert "not configured" in str(ei.value)


# --------------------------------------------------------------------------
# /generate-lp-for-unit endpoint
# --------------------------------------------------------------------------
def _payload():
    return {"subject": "Eng", "grade": 2, "curriculum": "ICT", "unit": SAMPLE_UNIT}


def test_endpoint_generate_lp_200(monkeypatch):
    async def fake_generate(unit, subject, grade, curriculum, *, client=None):
        return {"lesson_plan": "<div>plan</div>", "extra": True}
    monkeypatch.setattr(ug_lp_client, "generate_lp", fake_generate)
    client = TestClient(main.app)
    r = client.post("/generate-lp-for-unit", json=_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["lesson_plan"] == "<div>plan</div>"
    assert body["request"]["page_content"] == "hello, good morning"


def test_endpoint_generate_lp_502(monkeypatch):
    async def boom(unit, subject, grade, curriculum, *, client=None):
        raise UgLpError("UG_LP returned 500: boom")
    monkeypatch.setattr(ug_lp_client, "generate_lp", boom)
    client = TestClient(main.app)
    r = client.post("/generate-lp-for-unit", json=_payload())
    assert r.status_code == 502
    assert "500" in r.json()["detail"]


def test_endpoint_generate_lp_503_missing_key(monkeypatch):
    async def nokey(unit, subject, grade, curriculum, *, client=None):
        raise UgLpError("UG_LP API key not configured")
    monkeypatch.setattr(ug_lp_client, "generate_lp", nokey)
    client = TestClient(main.app)
    r = client.post("/generate-lp-for-unit", json=_payload())
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"]


def test_endpoint_generate_lp_422_missing_unit():
    client = TestClient(main.app)
    r = client.post("/generate-lp-for-unit", json={"subject": "Eng", "grade": 2})
    assert r.status_code == 422
