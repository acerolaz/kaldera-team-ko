"""Acceptance de l'API de la console Kaldera (HTTP → runner)."""

import httpx
import pytest

from kaldera.web.app import app

pytestmark = pytest.mark.anyio

ALL_STEPS = ["RESEARCH", "DRAFT", "REVIEW", "FINALIZE"]


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def run(client, **overrides):
    body = {"topic": "lancement produit", "required_steps": ALL_STEPS, "max_steps": 5}
    body.update(overrides)
    return await client.post("/api/runs", json=body)


async def test_lists_scenarios(client):
    res = await client.get("/api/scenarios")
    assert res.status_code == 200
    by_id = {s["id"]: s for s in res.json()}
    assert set(by_id) == {"happy_path", "research_only"}
    assert by_id["happy_path"] == {
        "id": "happy_path",
        "topic": "lancement produit",
        "required_steps": ALL_STEPS,
        "max_steps": 5,
    }


async def test_happy_path_is_done(client):
    res = await run(client)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "done"
    assert body["step_count"] == 4
    assert body["error"] is None
    assert sorted(body["artifacts"]) == ["draft", "final", "research", "review"]
    assert [e["agent_id"] for e in body["log"]] == ["researcher", "writer", "reviewer", "finalizer"]
    assert body["token_budgets"] == {
        "researcher": 1000,
        "writer": 1000,
        "reviewer": 1000,
        "finalizer": 1000,
    }


async def test_step_budget_aborts(client):
    body = (await run(client, max_steps=2)).json()
    assert body["status"] == "aborted"
    assert body["step_count"] == 2
    assert body["error"] is None
    assert body["required_steps"] == ALL_STEPS


async def test_token_budget_exceeded_is_reported(client):
    res = await run(client, topic="démo budget", required_steps=["RESEARCH"] * 11, max_steps=15)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "error"
    assert body["error"]["type"] == "BudgetExceeded"
    assert body["error"]["agent"] == "researcher"
    assert "1100 > 1000" in body["error"]["message"]
    assert body["step_count"] == 10
    assert len(body["log"]) == 10
    assert body["agent_tokens"] == {"researcher": 1000}


async def test_steps_without_finalize_are_done(client):
    body = (await run(client, required_steps=["RESEARCH"], max_steps=3)).json()
    assert body["status"] == "done"
    assert body["artifacts"] == {"research": "research[researcher]:lancement produit"}


@pytest.mark.xfail(
    strict=True,
    reason="runner : la vérification END consomme une itération, max_steps == nb d'étapes → aborted",
)
async def test_max_steps_equal_to_step_count_is_done(client):
    body = (await run(client, max_steps=4)).json()
    assert body["status"] == "done"


async def test_unknown_step_is_rejected(client):
    res = await run(client, required_steps=["FOO"])
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "required_steps", 0]


async def test_blank_topic_is_rejected(client):
    res = await run(client, topic="   ")
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "topic"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_steps": 0},
        {"max_steps": 51},
        {"required_steps": []},
        {"required_steps": ["RESEARCH"] * 51},
        {"topic": "x" * 201},
    ],
)
async def test_out_of_range_values_are_rejected(client, overrides):
    assert (await run(client, **overrides)).status_code == 422


async def test_missing_field_is_rejected(client):
    res = await client.post("/api/runs", json={"topic": "x", "required_steps": ["RESEARCH"]})
    assert res.status_code == 422


async def test_index_serves_console(client):
    res = await client.get("/")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert 'id="composer"' in res.text


async def test_static_assets_are_served(client):
    for path in ("/static/app.css", "/static/app.js"):
        assert (await client.get(path)).status_code == 200


async def test_index_has_player_controls(client):
    html = (await client.get("/")).text
    for control in ('id="restart"', 'id="toggle"', 'id="next"', 'id="progress"', 'data-speed="2"'):
        assert control in html
