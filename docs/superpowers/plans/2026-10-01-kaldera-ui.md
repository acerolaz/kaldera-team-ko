# Kaldera UI (console de démo) — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** une console web locale (`make ui`) qui rejoue visuellement un run de
l'équipe Kaldera : composer, pipeline animé, journal, budgets, artefacts et statut.

**Architecture :** FastAPI fin (`src/kaldera/web/`) avec 2 routes JSON et une page
statique. `service.py` appelle le `run_scenario()` existant avec un `TeamState`
qu'il garde en référence, capture `BudgetExceeded` et `RoleViolation`, puis
renvoie un `RunResult` Pydantic. Le front (HTML, CSS et JS vanilla, sans build)
reçoit le résultat complet et rejoue le `log` frame par frame.

**Tech Stack :** Python 3.11, FastAPI, uvicorn, Pydantic v2, httpx et anyio pour
les tests. HTML, CSS et JS vanilla.

**Spec :** `docs/superpowers/specs/2026-10-01-kaldera-ui-design.md`

## Global Constraints

- Le cœur `kaldera` (runner, orchestrator, agents, state, steps) n'est **pas modifié**.
- Dépendances : `fastapi>=0.115,<1` et `uvicorn>=0.30,<1` dans `dependencies` ;
  `httpx>=0.27,<1` dans le groupe `dev`. Aucune autre dépendance.
- Les routes sont en `def` synchrone (exécutées dans le threadpool FastAPI).
- Aucun `except Exception` : on capture seulement `BudgetExceeded` et
  `RoleViolation` (et `TypeError` de `fetch` côté JS).
- `topic` : 1 à 200 caractères ; `required_steps` : 1 à 50 éléments parmi
  `RESEARCH|DRAFT|REVIEW|FINALIZE` ; `max_steps` : 1 à 50 (`HARD_CAP`).
- Style « clair éditorial », desktop 1280–1920px, uniquement en clair. Contraste
  d'au moins 4.5:1. Base 16px. Focus visible.
- Police `Inter, system-ui, sans-serif` et `ui-monospace` : **aucune ressource
  externe**, la page doit fonctionner hors ligne.
- Icônes en SVG Lucide inline, sans emoji. Chaque état est signalé par une icône
  et du texte, jamais par la couleur seule.
- Tout texte dynamique est inséré via `textContent` ou `append(string)`,
  **jamais** via `innerHTML`.
- Une seule animation clé (connecteurs et cartes, 250ms ease-out). Avec
  `prefers-reduced-motion: reduce`, aucune transition ni animation.
- Lecture : 900ms par frame à 1× ; vitesses 0.5×, 1× et 2× ; raccourcis
  `Espace`, `→` et `R`, inactifs dans les champs de saisie et avec une touche modificatrice.
- Ligne de fin de chaque commit :
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`

## Review Focus

1. **`max_steps` égal au nombre d'étapes** (ex. 4 étapes, `max_steps=4`) : on
   s'attend à `done`. Or le runner actuel renvoie `aborted` parce que la vérification
   `END` consomme une itération (bug du cœur, hors périmètre). Il est épinglé par un
   test `xfail(strict=True)` dans la Task 1, qui basculera dès que le runner sera corrigé.
2. **Topic blanc ou contenant du HTML** : `"   "` doit donner 422 (test Task 1).
   `<img src=x onerror=alert(1)>` doit s'afficher tel quel, sans exécution
   (vérification manuelle Task 2).
3. **Étapes sans FINALIZE** (ex. `["RESEARCH"]`) : `done` sans artefact `final`, et
   l'UI ne casse pas (test Task 1, vérification manuelle Task 2).
4. **Relance pendant une lecture, double clic sur Lancer, `Cmd+R`** : une seule
   lecture à la fois, le bouton est désactivé pendant l'appel, et le rechargement
   du navigateur n'est pas intercepté (vérification manuelle Task 3).
5. **Valeurs hors bornes** (`max_steps` 0 ou 51, 0 ou 51 étapes, champ manquant) :
   réponse 422, jamais 500 (test paramétré Task 1).

---

## Structure des fichiers

| Fichier | Rôle |
|---|---|
| `pyproject.toml` (modif) | dépendances fastapi, uvicorn et httpx (dev) |
| `src/kaldera/web/__init__.py` | package |
| `src/kaldera/web/schemas.py` | contrats Pydantic de l'API |
| `src/kaldera/web/service.py` | `list_scenarios()`, `execute_run()` ; aucune notion HTTP |
| `src/kaldera/web/app.py` | app FastAPI : routes fines et montage de `static/` |
| `src/kaldera/web/static/index.html` | structure de la page (layout A) et sprite d'icônes |
| `src/kaldera/web/static/app.css` | tokens et styles |
| `src/kaldera/web/static/app.js` | composer, rendu d'une frame, lecteur |
| `tests/test_web.py` | tests d'acceptance de l'API |
| `Makefile`, `README.md` (modif) | cible `make ui` et doc |

---

### Task 1 : API (schémas, service, routes JSON)

**Files :**
- Modify: `pyproject.toml`
- Create: `src/kaldera/web/__init__.py`, `src/kaldera/web/schemas.py`, `src/kaldera/web/service.py`, `src/kaldera/web/app.py`
- Test: `tests/test_web.py`

**Interfaces :**
- Consumes (code existant) : `kaldera.runner.load_context(state, scenario)`,
  `kaldera.runner.run_scenario(scenario, initial_state=...)`, `kaldera.runner.HARD_CAP`,
  `kaldera.orchestrator.route(state) -> str`, `kaldera.orchestrator.AGENTS_BY_NAME`,
  `kaldera.agents.base.BudgetExceeded`, `kaldera.agents.base.RoleViolation`,
  `kaldera.cli.SCENARIOS: Path`, `kaldera.state.TeamState`.
- Produces :
  - `kaldera.web.app.app: FastAPI`
  - `GET /api/scenarios` → `[{id, topic, required_steps, max_steps}]`
  - `POST /api/runs` body `{topic, required_steps, max_steps}` → `{status, step_count, max_steps, required_steps, artifacts, agent_tokens, token_budgets, log: [{agent_id, message}], error: {type, agent, message} | null}`
  - `tests/test_web.py` avec la fixture async `client` et `pytestmark = pytest.mark.anyio`.

- [ ] **Step 1 : ajouter les dépendances**

Dans `pyproject.toml`, remplacer le bloc `dependencies` et le groupe `dev` par :

```toml
dependencies = [
    "langchain>=0.3,<0.4",
    "langchain-core>=0.3,<0.4",
    "langchain-azure-ai>=0.1,<0.2",
    "langgraph>=0.2,<0.3",
    "fastapi>=0.115,<1",
    "uvicorn>=0.30,<1",
]

[dependency-groups]
dev = [
    "pytest>=8,<9",
    "pytest-cov>=5,<7",
    "ruff>=0.6,<0.10",
    "mypy>=1.10,<2",
    "httpx>=0.27,<1",
]
```

Run : `uv sync`
Expected : installation de fastapi, starlette et uvicorn sans erreur.

- [ ] **Step 2 : écrire les tests qui échouent**

Créer `tests/test_web.py` :

```python
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
        "researcher": 1000, "writer": 1000, "reviewer": 1000, "finalizer": 1000,
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
```

- [ ] **Step 3 : vérifier que les tests échouent**

Run : `uv run pytest tests/test_web.py -v`
Expected : erreur de collecte `ModuleNotFoundError: No module named 'kaldera.web'`.

- [ ] **Step 4 : écrire les schémas**

Créer `src/kaldera/web/__init__.py` :

```python
"""Console web de démo de l'équipe Kaldera."""
```

Créer `src/kaldera/web/schemas.py` :

```python
"""Contrats Pydantic de l'API de la console."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from ..runner import HARD_CAP

StepName = Literal["RESEARCH", "DRAFT", "REVIEW", "FINALIZE"]
RunStatus = Literal["done", "aborted", "error"]


class ScenarioOut(BaseModel):
    id: str
    topic: str
    required_steps: list[StepName]
    max_steps: int


class RunRequest(BaseModel):
    topic: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    required_steps: list[StepName] = Field(min_length=1, max_length=HARD_CAP)
    max_steps: int = Field(ge=1, le=HARD_CAP)


class LogEntry(BaseModel):
    agent_id: str
    message: str


class RunError(BaseModel):
    type: Literal["BudgetExceeded", "RoleViolation"]
    agent: str
    message: str


class RunResult(BaseModel):
    status: RunStatus
    step_count: int
    max_steps: int
    required_steps: list[StepName]
    artifacts: dict[str, str]
    agent_tokens: dict[str, int]
    token_budgets: dict[str, int]
    log: list[LogEntry]
    error: RunError | None = None
```

- [ ] **Step 5 : écrire le service**

Créer `src/kaldera/web/service.py` :

```python
"""Exécution d'un run pour la console : aucune dépendance HTTP."""
from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from ..agents.base import BudgetExceeded, RoleViolation
from ..cli import SCENARIOS
from ..orchestrator import AGENTS_BY_NAME, route
from ..runner import load_context, run_scenario
from ..state import TeamState
from .schemas import LogEntry, RunError, RunRequest, RunResult, RunStatus, ScenarioOut


def list_scenarios(path: Path = SCENARIOS) -> list[ScenarioOut]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        ScenarioOut(
            id=s["id"],
            topic=s["initial_context"]["topic"],
            required_steps=s["initial_context"]["required_steps"],
            max_steps=s["expected"]["max_steps"],
        )
        for s in data["scenarios"]
    ]


def execute_run(request: RunRequest) -> RunResult:
    scenario = {
        "initial_context": {
            "topic": request.topic,
            "required_steps": list(request.required_steps),
        },
        "expected": {"max_steps": request.max_steps},
    }
    # On garde la référence à l'état : il reste lisible même si un agent lève.
    state = TeamState()
    load_context(state, scenario)
    error: RunError | None = None
    try:
        run_scenario(scenario, initial_state=state)
    # L'exception part avant advance() : route(state) désigne l'agent fautif.
    except BudgetExceeded as exc:
        error = RunError(type="BudgetExceeded", agent=route(state), message=str(exc))
    except RoleViolation as exc:
        error = RunError(type="RoleViolation", agent=route(state), message=str(exc))

    status: RunStatus = "error" if error else cast(RunStatus, state.status)
    return RunResult(
        status=status,
        step_count=state.step_count,
        max_steps=request.max_steps,
        required_steps=request.required_steps,
        artifacts=state.artifacts,
        agent_tokens=state.agent_tokens,
        token_budgets={name: agent.token_budget for name, agent in AGENTS_BY_NAME.items()},
        log=[LogEntry(**entry) for entry in state.log],
        error=error,
    )
```

- [ ] **Step 6 : écrire l'app**

Créer `src/kaldera/web/app.py` :

```python
"""Console de démo Kaldera : routes fines, la logique vit dans service.py."""
from __future__ import annotations

from fastapi import FastAPI

from . import service
from .schemas import RunRequest, RunResult, ScenarioOut

app = FastAPI(title="Kaldera Console")


@app.get("/api/scenarios", response_model=list[ScenarioOut])
def get_scenarios() -> list[ScenarioOut]:
    return service.list_scenarios()


@app.post("/api/runs", response_model=RunResult)
def post_run(request: RunRequest) -> RunResult:
    return service.execute_run(request)
```

- [ ] **Step 7 : vérifier que les tests passent**

Run : `uv run pytest tests/test_web.py -v`
Expected : tous `PASSED`, sauf `test_max_steps_equal_to_step_count_is_done` qui est `XFAIL`.

Run : `uv run pytest -q && uv run ruff check . && uv run mypy src`
Expected : toute la suite verte (les 17 tests existants + ceux de `test_web.py`), ruff et mypy sans erreur.

- [ ] **Step 8 : commit**

```bash
git add pyproject.toml src/kaldera/web tests/test_web.py
git commit -m "feat(web): API de la console (scénarios, runs, erreurs métier)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2 : page, styles, composer et rendu d'une frame

Livrable : `make ui` ouvre une console où l'on compose et lance un run. L'état
**final** s'affiche (pipeline, piste, journal, budgets, artefacts, bannière), sans
animation pour l'instant.

**Files :**
- Modify: `src/kaldera/web/app.py`, `Makefile`, `README.md`
- Create: `src/kaldera/web/static/index.html`, `src/kaldera/web/static/app.css`, `src/kaldera/web/static/app.js`
- Test: `tests/test_web.py`

**Interfaces :**
- Consumes : les endpoints et le JSON `RunResult` de la Task 1 ; la fixture `client`.
- Produces (utilisés par la Task 3, dans `app.js`) :
  - `render(result, frame)` : affiche l'état après `frame` frames. `frame` va de
    `0` (rien de joué) à `result.log.length + 1` (état final : bannière, erreur,
    étapes non atteintes). La frame `k` (1 ≤ k ≤ n) signifie « l'entrée `k` du log
    vient d'être jouée, son agent est actif ».
  - `play(result)` : point d'entrée appelé après un `POST /api/runs` réussi.
    Dans cette tâche, il fait `render(result, result.log.length + 1)`.
  - helpers `$(sel)`, `el(tag, attrs, ...children)`, `icon(name, cls)`.
  - le sprite d'icônes `#i-<name>` contient déjà `play`, `pause`, `restart` et `next` pour la Task 3.
  - dans `index.html`, l'élément `<p id="track-note">` sert d'ancre à la Task 3.

- [ ] **Step 1 : écrire les tests qui échouent**

Ajouter à la fin de `tests/test_web.py` :

```python
async def test_index_serves_console(client):
    res = await client.get("/")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert 'id="composer"' in res.text


async def test_static_assets_are_served(client):
    for path in ("/static/app.css", "/static/app.js"):
        assert (await client.get(path)).status_code == 200
```

Run : `uv run pytest tests/test_web.py -k "index or static" -v`
Expected : FAIL, avec 404 sur `/`.

- [ ] **Step 2 : servir la page**

Remplacer `src/kaldera/web/app.py` par :

```python
"""Console de démo Kaldera : routes fines, la logique vit dans service.py."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import service
from .schemas import RunRequest, RunResult, ScenarioOut

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Kaldera Console")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/api/scenarios", response_model=list[ScenarioOut])
def get_scenarios() -> list[ScenarioOut]:
    return service.list_scenarios()


@app.post("/api/runs", response_model=RunResult)
def post_run(request: RunRequest) -> RunResult:
    return service.execute_run(request)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")
```

- [ ] **Step 3 : écrire `index.html`**

Créer `src/kaldera/web/static/index.html` :

```html
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kaldera Console</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <!-- Icônes Lucide (ISC) -->
  <svg width="0" height="0" style="position:absolute" aria-hidden="true">
    <symbol id="i-supervisor" viewBox="0 0 24 24"><rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/></symbol>
    <symbol id="i-researcher" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></symbol>
    <symbol id="i-writer" viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.4 3.6a2.1 2.1 0 0 1 3 3L7.4 18.6a2 2 0 0 1-.9.5l-2.9.8a.5.5 0 0 1-.6-.6l.8-2.9a2 2 0 0 1 .5-.9z"/></symbol>
    <symbol id="i-reviewer" viewBox="0 0 24 24"><path d="M18 6 7 17l-5-5"/><path d="m22 10-7.5 7.5L13 16"/></symbol>
    <symbol id="i-finalizer" viewBox="0 0 24 24"><path d="M11 21.7a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7z"/><path d="M12 22V12"/><path d="m3.3 7 7.7 4.7a2 2 0 0 0 2 0L20.7 7"/><path d="m7.5 4.3 9 5.2"/></symbol>
    <symbol id="i-check" viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></symbol>
    <symbol id="i-x" viewBox="0 0 24 24"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></symbol>
    <symbol id="i-alert" viewBox="0 0 24 24"><path d="m21.7 18-8-14a2 2 0 0 0-3.5 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></symbol>
    <symbol id="i-play" viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3"/></symbol>
    <symbol id="i-pause" viewBox="0 0 24 24"><rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/></symbol>
    <symbol id="i-restart" viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 9-9 9.8 9.8 0 0 0-6.7 2.7L3 8"/><path d="M3 3v5h5"/></symbol>
    <symbol id="i-next" viewBox="0 0 24 24"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" x2="19" y1="5" y2="19"/></symbol>
  </svg>

  <header class="composer">
    <form id="composer" novalidate>
      <h1 class="brand">Kaldera</h1>
      <label class="field">Scénario
        <select id="scenario"></select>
      </label>
      <label class="field">Topic
        <input id="topic" maxlength="200" autocomplete="off">
        <span class="field-error" id="err-topic"></span>
      </label>
      <fieldset class="field">
        <legend>Étapes</legend>
        <ol id="steps" class="chips"></ol>
        <div class="add-steps">
          <button type="button" class="btn small" data-step="RESEARCH">+ RESEARCH</button>
          <button type="button" class="btn small" data-step="DRAFT">+ DRAFT</button>
          <button type="button" class="btn small" data-step="REVIEW">+ REVIEW</button>
          <button type="button" class="btn small" data-step="FINALIZE">+ FINALIZE</button>
        </div>
        <span class="field-error" id="err-required_steps"></span>
      </fieldset>
      <label class="field">max_steps
        <input id="max-steps" type="number" min="1" max="50">
        <span class="field-error" id="err-max_steps"></span>
      </label>
      <div class="field submit">
        <button type="submit" id="run" class="btn primary">Lancer</button>
        <span class="field-error" id="err-form"></span>
      </div>
    </form>
    <div class="presets">
      <span>Presets de démo :</span>
      <button type="button" class="btn small" data-preset="aborted">Interrompu</button>
      <button type="button" class="btn small" data-preset="budget">Budget dépassé</button>
    </div>
  </header>

  <main>
    <section class="pipeline" aria-label="Pipeline">
      <div class="team">
        <div class="card supervisor">
          <svg class="icon lg" aria-hidden="true"><use href="#i-supervisor"/></svg>
          <strong>Superviseur</strong>
          <span class="agent-status" id="supervisor-status">en attente</span>
        </div>
        <div class="card agent" data-agent="researcher" data-state="idle">
          <span class="connector" aria-hidden="true"></span>
          <svg class="icon lg" aria-hidden="true"><use href="#i-researcher"/></svg>
          <strong>researcher</strong><span class="agent-step">RESEARCH</span>
          <span class="agent-status">inactif</span>
        </div>
        <div class="card agent" data-agent="writer" data-state="idle">
          <span class="connector" aria-hidden="true"></span>
          <svg class="icon lg" aria-hidden="true"><use href="#i-writer"/></svg>
          <strong>writer</strong><span class="agent-step">DRAFT</span>
          <span class="agent-status">inactif</span>
        </div>
        <div class="card agent" data-agent="reviewer" data-state="idle">
          <span class="connector" aria-hidden="true"></span>
          <svg class="icon lg" aria-hidden="true"><use href="#i-reviewer"/></svg>
          <strong>reviewer</strong><span class="agent-step">REVIEW</span>
          <span class="agent-status">inactif</span>
        </div>
        <div class="card agent" data-agent="finalizer" data-state="idle">
          <span class="connector" aria-hidden="true"></span>
          <svg class="icon lg" aria-hidden="true"><use href="#i-finalizer"/></svg>
          <strong>finalizer</strong><span class="agent-step">FINALIZE</span>
          <span class="agent-status">inactif</span>
        </div>
      </div>
      <ol id="track" class="track" aria-label="Étapes du run"></ol>
      <p id="track-note" class="track-note"></p>
    </section>

    <section class="panels">
      <div class="panel">
        <h2>Journal</h2>
        <ol id="log" class="log" aria-live="polite"><li class="empty">Aucun run lancé.</li></ol>
      </div>
      <div class="panel">
        <h2>Budgets tokens</h2>
        <div id="budgets"><p class="empty">Aucun run lancé.</p></div>
      </div>
      <div class="panel">
        <h2>Artefacts</h2>
        <dl id="artifacts" class="artifacts"><dd class="empty">Aucun run lancé.</dd></dl>
      </div>
    </section>

    <div id="banner" class="banner" role="status" hidden></div>
  </main>

  <script src="/static/app.js" defer></script>
</body>
</html>
```

- [ ] **Step 4 : écrire `app.css`**

Créer `src/kaldera/web/static/app.css` :

```css
:root {
  --bg: #ffffff;
  --surface: #f8fafc;
  --fg: #0f172a;
  --muted: #475569;
  --border: #cbd5e1;
  --active: #6d28d9;
  --active-bg: #f5f3ff;
  --ok: #15803d;
  --ok-bg: #f0fdf4;
  --warn: #b45309;
  --warn-bg: #fffbeb;
  --danger: #b91c1c;
  --danger-bg: #fef2f2;
  --radius: 10px;
  --font: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, monospace;
}

* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 var(--font); }
button, input, select { font: inherit; }
:focus-visible { outline: 3px solid var(--active); outline-offset: 2px; }

.icon { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 2;
  stroke-linecap: round; stroke-linejoin: round; flex: none; }
.icon.lg { width: 28px; height: 28px; }

/* Composer */
.composer { padding: 16px 24px; border-bottom: 1px solid var(--border);
  display: flex; flex-direction: column; gap: 8px; }
#composer { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 12px 20px; }
.brand { font-size: 1.375rem; margin: 0; padding-top: 24px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: .875rem;
  font-weight: 600; color: var(--muted); border: 0; padding: 0; margin: 0; min-width: 0; }
.field legend { padding: 0; margin-bottom: 4px; }
.field input, .field select { color: var(--fg); font-weight: 400; padding: 6px 10px;
  min-height: 40px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); }
#topic { width: 240px; }
#max-steps { width: 88px; }
.submit { padding-top: 24px; }
.field-error { color: var(--danger); font-size: .8125rem; font-weight: 500; min-height: 1.25em; max-width: 260px; }

.chips { list-style: none; display: flex; flex-wrap: wrap; gap: 4px; margin: 0; padding: 0;
  min-height: 40px; align-items: center; max-width: 520px; }
.chip { display: inline-flex; align-items: center; gap: 2px; padding: 2px 2px 2px 10px;
  border: 1px solid var(--border); border-radius: 999px; background: var(--surface);
  color: var(--fg); font-weight: 500; font-size: .8125rem; }
.chip button { border: 0; background: none; cursor: pointer; color: var(--muted);
  width: 28px; height: 28px; border-radius: 999px; }
.chip button:hover { background: var(--border); color: var(--fg); }
.add-steps { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }

.btn { cursor: pointer; border: 1px solid var(--border); background: var(--bg); color: var(--fg);
  border-radius: 6px; padding: 6px 14px; min-height: 40px; font-weight: 600; font-size: .875rem;
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  transition: background-color .15s ease-out; }
.btn:hover { background: var(--surface); }
.btn.small { min-height: 32px; padding: 4px 10px; font-size: .8125rem; }
.btn.primary { background: var(--fg); color: var(--bg); border-color: var(--fg); min-width: 128px; }
.btn.primary:hover { background: #1e293b; }
.btn:disabled { opacity: .6; cursor: not-allowed; }
.btn[aria-busy="true"]::before { content: ""; width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid currentColor; border-right-color: transparent; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.presets { display: flex; align-items: center; gap: 8px; font-size: .875rem; color: var(--muted); }

/* Pipeline */
main { padding: 24px; display: flex; flex-direction: column; gap: 24px; }
.pipeline { border: 1px solid var(--border); border-radius: var(--radius); padding: 20px; background: var(--surface); }
.team { display: grid; grid-template-columns: repeat(5, 1fr); gap: 32px; }
.card { position: relative; display: flex; flex-direction: column; align-items: center; gap: 4px;
  text-align: center; padding: 16px 12px; background: var(--bg); border: 2px solid var(--border);
  border-radius: var(--radius); transition: border-color .25s ease-out, background-color .25s ease-out; }
.card strong { font-size: 1.0625rem; }
.card.supervisor { border-style: dashed; border-color: var(--fg); }
.agent-step { font-size: .75rem; letter-spacing: .05em; color: var(--muted); }
.agent-status { display: inline-flex; align-items: center; gap: 4px; min-height: 1.5em;
  font-size: .875rem; color: var(--muted); }
.connector { position: absolute; right: 100%; top: 50%; width: 32px; height: 3px;
  background: var(--border); transition: background-color .25s ease-out; }
.card[data-state="active"] { border-color: var(--active); background: var(--active-bg); }
.card[data-state="active"] .agent-status { color: var(--active); font-weight: 600; }
.card[data-state="active"] .connector { background: var(--active); }
.card[data-state="done"] .agent-status { color: var(--ok); font-weight: 600; }
.card[data-state="done"] .connector { background: var(--ok); }
.card[data-state="error"] { border-color: var(--danger); background: var(--danger-bg); }
.card[data-state="error"] .agent-status { color: var(--danger); font-weight: 600; }
.card[data-state="error"] .connector { background: var(--danger); }

.track { list-style: none; display: flex; flex-wrap: wrap; gap: 6px; margin: 20px 0 0; padding: 0; }
.track li { display: inline-flex; align-items: center; gap: 4px; height: 32px; padding: 0 10px;
  border: 1px solid var(--border); border-radius: 999px; background: var(--bg); color: var(--muted);
  font-size: .8125rem; font-weight: 600; }
.track li[data-state="active"] { border: 2px solid var(--active); color: var(--active); }
.track li[data-state="done"] { border-color: var(--ok); color: var(--ok); }
.track li[data-state="error"] { border: 2px solid var(--danger); color: var(--danger); }
.track li[data-state="skipped"] { text-decoration: line-through;
  background: repeating-linear-gradient(45deg, var(--surface) 0 6px, var(--border) 6px 8px); }
.track-note { margin: 8px 0 0; min-height: 1.5em; font-size: .875rem; color: var(--warn); font-weight: 600; }

/* Panneaux */
.panels { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
.panel { border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; min-height: 200px; }
.panel h2 { margin: 0 0 12px; font-size: .8125rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.empty { color: var(--muted); font-style: italic; list-style: none; }
.log { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px;
  max-height: 280px; overflow: auto; font: .875rem/1.5 var(--mono); }
.gauge-row { margin-bottom: 12px; }
.gauge-label { display: flex; justify-content: space-between; font-size: .875rem; }
.gauge-label span:last-child { font-family: var(--mono); }
.gauge { height: 8px; margin-top: 4px; border-radius: 4px; background: var(--border); overflow: hidden; }
.gauge i { display: block; height: 100%; background: var(--ok); transition: width .25s ease-out; }
.gauge-row[data-level="warn"] .gauge i { background: var(--warn); }
.gauge-row[data-level="danger"] .gauge i { background: var(--danger); }
.gauge-msg { margin: 4px 0 0; font-size: .8125rem; color: var(--danger); font-weight: 600; }
.artifacts { margin: 0; font-size: .875rem; }
.artifacts dt { font-weight: 600; }
.artifacts dd { margin: 0 0 8px; font-family: var(--mono); color: var(--muted); overflow-wrap: anywhere; }

/* Bannière */
.banner { display: flex; align-items: center; gap: 10px; padding: 14px 18px; border: 1px solid;
  border-radius: var(--radius); font-weight: 600; }
.banner[hidden] { display: none; }
.banner .icon { width: 20px; height: 20px; }
.banner[data-kind="ok"] { color: var(--ok); background: var(--ok-bg); border-color: var(--ok); }
.banner[data-kind="warn"] { color: var(--warn); background: var(--warn-bg); border-color: var(--warn); }
.banner[data-kind="danger"] { color: var(--danger); background: var(--danger-bg); border-color: var(--danger); }
.banner .btn { margin-left: auto; }

@media (prefers-reduced-motion: reduce) {
  *, *::before { transition: none !important; animation: none !important; }
}
```

- [ ] **Step 5 : écrire `app.js` (composer et rendu d'une frame)**

Créer `src/kaldera/web/static/app.js` :

```js
"use strict";

const AGENTS = ["researcher", "writer", "reviewer", "finalizer"];
const STEP_AGENT = { RESEARCH: "researcher", DRAFT: "writer", REVIEW: "reviewer", FINALIZE: "finalizer" };
const STEP_ARTIFACT = { RESEARCH: "research", DRAFT: "draft", REVIEW: "review", FINALIZE: "final" };
const PRESETS = {
  aborted: { topic: "démo interruption", required_steps: ["RESEARCH", "DRAFT", "REVIEW", "FINALIZE"], max_steps: 2 },
  budget: { topic: "démo budget", required_steps: Array(11).fill("RESEARCH"), max_steps: 15 },
};

const $ = (sel) => document.querySelector(sel);
let scenarios = [];
let steps = [];

// --- helpers DOM : les chaînes passent par append() → jamais interprétées comme HTML
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  node.append(...children);
  return node;
}

function icon(name, cls = "icon") {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", cls);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(ns, "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}

// --- bannière
function showBanner(kind, iconName, text, retry) {
  const banner = $("#banner");
  banner.dataset.kind = kind;
  const children = [icon(iconName), el("span", {}, text)];
  if (retry) {
    const button = el("button", { type: "button", class: "btn small" }, "Réessayer");
    button.addEventListener("click", retry);
    children.push(button);
  }
  banner.replaceChildren(...children);
  banner.hidden = false;
}

function hideBanner() {
  $("#banner").hidden = true;
}

// --- composer
function renderSteps() {
  $("#steps").replaceChildren(
    ...steps.map((step, i) =>
      el("li", { class: "chip" }, `${i + 1}. ${step}`,
        el("button", { type: "button", "data-remove": String(i), "aria-label": `Retirer l'étape ${i + 1} (${step})` }, "×"))),
  );
}

function clearErrors() {
  document.querySelectorAll(".field-error").forEach((node) => { node.textContent = ""; });
}

function fill({ topic, required_steps, max_steps }) {
  $("#topic").value = topic;
  steps = [...required_steps];
  $("#max-steps").value = max_steps;
  renderSteps();
  clearErrors();
}

function showValidation(detail) {
  for (const { loc, msg } of detail) {
    const target = document.getElementById(`err-${loc[1]}`) ?? $("#err-form");
    target.textContent = msg;
  }
}

async function loadScenarios() {
  try {
    const res = await fetch("/api/scenarios");
    if (!res.ok) return showBanner("danger", "x", `Erreur serveur (${res.status})`, loadScenarios);
    scenarios = await res.json();
  } catch (err) {
    if (!(err instanceof TypeError)) throw err;
    return showBanner("danger", "x", "API injoignable, vérifier make ui", loadScenarios);
  }
  hideBanner();
  $("#scenario").replaceChildren(...scenarios.map((s) => el("option", { value: s.id }, s.id)));
  if (scenarios.length) fill(scenarios[0]);
}

async function launch() {
  clearErrors();
  hideBanner();
  const body = { topic: $("#topic").value, required_steps: steps, max_steps: Number($("#max-steps").value) };
  const button = $("#run");
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  try {
    const res = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (res.status === 422) return showValidation((await res.json()).detail);
    if (!res.ok) return showBanner("danger", "x", `Erreur serveur (${res.status})`, launch);
    play(await res.json());
  } catch (err) {
    if (!(err instanceof TypeError)) throw err;
    showBanner("danger", "x", "API injoignable, vérifier make ui", launch);
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
  }
}

// --- rendu d'une frame : 0 = rien joué, k = entrée k du log jouée, n + 1 = état final
function render(result, frame) {
  const n = result.log.length;
  const finished = frame > n;
  const played = result.log.slice(0, Math.min(frame, n));
  const active = !finished && played.length ? played[played.length - 1].agent_id : null;
  const failed = finished && result.error ? result.error.agent : null;

  const counts = {};
  for (const entry of played) counts[entry.agent_id] = (counts[entry.agent_id] ?? 0) + 1;
  const totals = {};
  for (const entry of result.log) totals[entry.agent_id] = (totals[entry.agent_id] ?? 0) + 1;

  // La frame k joue l'entrée k du log, c.-à-d. required_steps[k - 1] (étapes traitées dans l'ordre).
  renderAgents(result, active, failed, counts, result.required_steps[played.length - 1]);
  renderTrack(result, played.length, finished);
  renderLog(played);
  renderBudgets(result, counts, totals, finished);
  renderArtifacts(result, played.length);
  if (finished) renderStatus(result);
  else hideBanner();
}

function renderAgents(result, active, failed, counts, activeStep) {
  const supervisor = $("#supervisor-status");
  if (active) supervisor.textContent = `confie ${activeStep} → ${active}`;
  else supervisor.textContent = Object.keys(counts).length || failed ? "fin du flux" : "en attente";

  for (const name of AGENTS) {
    const card = document.querySelector(`.card[data-agent="${name}"]`);
    const status = card.querySelector(".agent-status");
    if (name === failed) {
      card.dataset.state = "error";
      status.replaceChildren(icon("x"), result.error.type);
    } else if (name === active) {
      card.dataset.state = "active";
      status.replaceChildren(icon("play"), "en cours");
    } else if (counts[name]) {
      card.dataset.state = "done";
      status.replaceChildren(icon("check"), counts[name] > 1 ? `terminé ×${counts[name]}` : "terminé");
    } else {
      card.dataset.state = "idle";
      status.replaceChildren("inactif");
    }
  }
}

function renderTrack(result, playedCount, finished) {
  let skipped = 0;
  $("#track").replaceChildren(
    ...result.required_steps.map((step, i) => {
      let state = "pending";
      if (i < playedCount) state = !finished && i === playedCount - 1 ? "active" : "done";
      else if (finished && result.error && i === playedCount) state = "error";
      else if (finished) { state = "skipped"; skipped += 1; }
      const label = state === "skipped" ? `${step}, non atteinte` : step;
      const li = el("li", { "data-state": state, title: label }, `${i + 1} · ${step}`);
      if (state === "done") li.prepend(icon("check"));
      if (state === "error") li.prepend(icon("x"));
      return li;
    }),
  );
  $("#track-note").textContent = skipped ? `${skipped} étape(s) non atteinte(s)` : "";
}

function renderLog(played) {
  $("#log").replaceChildren(
    ...(played.length
      ? played.map((entry) => el("li", {}, `${entry.agent_id} · ${entry.message}`))
      : [el("li", { class: "empty" }, "En attente de la première étape…")]),
  );
}

function renderBudgets(result, counts, totals, finished) {
  $("#budgets").replaceChildren(
    ...AGENTS.map((name) => {
      const budget = result.token_budgets[name];
      // Coût par étape constant : tokens consommés au prorata des étapes déjà jouées.
      const used = totals[name] ? Math.round((result.agent_tokens[name] ?? 0) * (counts[name] ?? 0) / totals[name]) : 0;
      const exceeded = finished && result.error?.type === "BudgetExceeded" && result.error.agent === name;
      const level = exceeded ? "danger" : used / budget > 0.8 ? "warn" : "ok";
      const fill = el("i");
      fill.style.width = `${Math.min(100, (used / budget) * 100)}%`;
      const row = el("div", { class: "gauge-row", "data-level": level },
        el("div", { class: "gauge-label" }, el("span", {}, name), el("span", {}, `${used} / ${budget}`)),
        el("div", { class: "gauge", role: "img", "aria-label": `${name} : ${used} sur ${budget} tokens` }, fill));
      if (exceeded) row.append(el("p", { class: "gauge-msg" }, result.error.message));
      return row;
    }),
  );
}

function renderArtifacts(result, playedCount) {
  const keys = [...new Set(result.required_steps.slice(0, playedCount).map((s) => STEP_ARTIFACT[s]))]
    .filter((key) => key in result.artifacts);
  $("#artifacts").replaceChildren(
    ...(keys.length
      ? keys.flatMap((key) => [el("dt", {}, key), el("dd", {}, result.artifacts[key])])
      : [el("dd", { class: "empty" }, "Aucun artefact pour l'instant.")]),
  );
}

function renderStatus(result) {
  if (result.status === "done") {
    showBanner("ok", "check", `Terminé · ${result.step_count} étapes / max ${result.max_steps}`);
  } else if (result.status === "aborted") {
    showBanner("warn", "alert",
      `Interrompu · ${result.step_count} étapes traitées sur ${result.required_steps.length} (max_steps = ${result.max_steps})`);
  } else {
    showBanner("danger", "x", `${result.error.type} · ${result.error.agent} : ${result.error.message}`);
  }
}

// --- lecture (remplacée par le lecteur animé en Task 3)
function play(result) {
  render(result, result.log.length + 1);
}

// --- événements
$("#scenario").addEventListener("change", (e) => fill(scenarios.find((s) => s.id === e.target.value)));
$("#composer").addEventListener("submit", (e) => { e.preventDefault(); launch(); });
$(".add-steps").addEventListener("click", (e) => {
  const step = e.target.closest("[data-step]")?.dataset.step;
  if (step) { steps.push(step); renderSteps(); }
});
$("#steps").addEventListener("click", (e) => {
  const index = e.target.closest("[data-remove]")?.dataset.remove;
  if (index !== undefined) { steps.splice(Number(index), 1); renderSteps(); }
});
$(".presets").addEventListener("click", (e) => {
  const preset = e.target.closest("[data-preset]")?.dataset.preset;
  if (preset) fill(PRESETS[preset]);
});

loadScenarios();
```

- [ ] **Step 6 : ajouter `make ui` et documenter**

Dans `Makefile`, remplacer la ligne `.PHONY` et ajouter la cible :

```make
.PHONY: up down test fmt lint typecheck install ui

ui:
	uv run uvicorn kaldera.web.app:app --app-dir src --reload
```

Dans `README.md`, section `## Useful commands`, ajouter dans le bloc bash :

```bash
make ui         # console de démo sur http://127.0.0.1:8000
```

et dans `## Layout`, ajouter :

```markdown
- `src/kaldera/web/` — console de démo (FastAPI + page statique), lancée par `make ui`
```

- [ ] **Step 7 : vérifier les tests**

Run : `uv run pytest -q && uv run ruff check . && uv run mypy src`
Expected : suite verte, avec 1 xfail.

- [ ] **Step 8 : vérification manuelle**

Run : `make ui`, puis ouvrir http://127.0.0.1:8000. Vérifier :

- [ ] Au chargement, le sélecteur contient `happy_path` et `research_only`, et le composer est rempli avec `happy_path`.
- [ ] Lancer `happy_path` : les 4 cartes sont « terminé » (✓), 4 pastilles ✓, 4 lignes de journal, 4 artefacts, jauges à 100/1000, bannière verte « Terminé · 4 étapes / max 5 ».
- [ ] Preset « Interrompu » puis Lancer : researcher et writer « terminé », 2 pastilles hachurées, note « 2 étape(s) non atteinte(s) », bannière ambre « Interrompu · 2 étapes traitées sur 4 (max_steps = 2) ».
- [ ] Preset « Budget dépassé » puis Lancer : carte researcher rouge « BudgetExceeded », 11ᵉ pastille ✕, jauge rouge avec « … 1100 > 1000 », bannière rouge.
- [ ] Étapes = `[RESEARCH]` seul, max 3 : bannière verte, artefact `research` uniquement, aucune erreur dans la console du navigateur.
- [ ] Topic `<img src=x onerror=alert(1)>` : le texte s'affiche tel quel dans l'artefact, sans alerte.
- [ ] Topic vide puis Lancer : message sous le champ Topic. Supprimer toutes les étapes puis Lancer : message sous Étapes.
- [ ] Arrêter le serveur (Ctrl+C) puis Lancer : bannière « API injoignable… » et bouton Réessayer. Relancer `make ui` puis Réessayer : ça fonctionne.
- [ ] Navigation au clavier (Tab) : tout est atteignable, focus visible.
- [ ] DevTools → Network : aucune requête externe (polices, CDN).

- [ ] **Step 9 : commit**

```bash
git add src/kaldera/web Makefile README.md tests/test_web.py
git commit -m "feat(web): page de la console (composer, pipeline, panneaux, statut)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3 : lecteur animé (⏮ ⏯ ⏭, vitesse, raccourcis)

**Files :**
- Modify: `src/kaldera/web/static/index.html`, `src/kaldera/web/static/app.css`, `src/kaldera/web/static/app.js`
- Test: `tests/test_web.py`

**Interfaces :**
- Consumes : `render(result, frame)`, `play(result)` (à remplacer), `$`, l'ancre
  `<p id="track-note">` et les symboles `#i-play`, `#i-pause`, `#i-restart` et `#i-next`
  de la Task 2.
- Produces : `play(result)` animé ; les fonctions `pause()`, `resume()`, `next()`, `restart()`.

- [ ] **Step 1 : écrire le test qui échoue**

Ajouter à `tests/test_web.py` :

```python
async def test_index_has_player_controls(client):
    html = (await client.get("/")).text
    for control in ('id="restart"', 'id="toggle"', 'id="next"', 'id="progress"', 'data-speed="2"'):
        assert control in html
```

Run : `uv run pytest tests/test_web.py::test_index_has_player_controls -v`
Expected : FAIL (`assert 'id="restart"' in html`).

- [ ] **Step 2 : ajouter les contrôles**

Dans `index.html`, juste après `<p id="track-note" class="track-note"></p>`, insérer :

```html
      <div class="player" role="group" aria-label="Lecture">
        <button type="button" class="btn icon-btn" id="restart" aria-label="Recommencer (R)" disabled>
          <svg class="icon" aria-hidden="true"><use href="#i-restart"/></svg>
        </button>
        <button type="button" class="btn icon-btn" id="toggle" aria-label="Lecture (Espace)" disabled>
          <svg class="icon" aria-hidden="true"><use href="#i-play"/></svg>
        </button>
        <button type="button" class="btn icon-btn" id="next" aria-label="Étape suivante (→)" disabled>
          <svg class="icon" aria-hidden="true"><use href="#i-next"/></svg>
        </button>
        <span id="progress" class="progress">étape 0 / 0</span>
        <div class="speeds" role="group" aria-label="Vitesse">
          <button type="button" class="btn small" data-speed="0.5" aria-pressed="false">0.5×</button>
          <button type="button" class="btn small" data-speed="1" aria-pressed="true">1×</button>
          <button type="button" class="btn small" data-speed="2" aria-pressed="false">2×</button>
        </div>
      </div>
```

Ajouter à `app.css`, juste avant le bloc `@media (prefers-reduced-motion: reduce)` :

```css
/* Lecteur */
.player { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
.icon-btn { width: 44px; height: 44px; padding: 0; }
.icon-btn .icon { width: 20px; height: 20px; }
.progress { margin: 0 8px; font-family: var(--mono); color: var(--muted); }
.speeds { display: flex; gap: 4px; margin-left: auto; }
.speeds [aria-pressed="true"] { background: var(--fg); color: var(--bg); border-color: var(--fg); }
```

Run : `uv run pytest tests/test_web.py::test_index_has_player_controls -v`
Expected : PASS.

- [ ] **Step 3 : remplacer `play` par le lecteur**

Dans `app.js`, remplacer le bloc entier :

```js
// --- lecture (remplacée par le lecteur animé en Task 3)
function play(result) {
  render(result, result.log.length + 1);
}
```

par :

```js
// --- lecteur : une frame toutes les BASE_DELAY / speed ms
const BASE_DELAY = 900;
const player = { result: null, frame: 0, timer: null, speed: 1 };

const lastFrame = () => player.result.log.length + 1;

function show(frame) {
  player.frame = frame;
  render(player.result, frame);
  const done = Math.min(frame, player.result.log.length);
  $("#progress").textContent = `étape ${done} / ${player.result.required_steps.length}`;
  if (frame >= lastFrame()) pause();
}

function setToggle(playing) {
  const button = $("#toggle");
  button.setAttribute("aria-label", playing ? "Pause (Espace)" : "Lecture (Espace)");
  button.querySelector("use").setAttribute("href", playing ? "#i-pause" : "#i-play");
}

function pause() {
  clearInterval(player.timer);
  player.timer = null;
  setToggle(false);
}

function resume() {
  if (!player.result) return;
  if (player.frame >= lastFrame()) show(0);
  clearInterval(player.timer);
  player.timer = setInterval(() => show(player.frame + 1), BASE_DELAY / player.speed);
  setToggle(true);
}

function next() {
  if (!player.result) return;
  pause();
  if (player.frame < lastFrame()) show(player.frame + 1);
}

function restart() {
  if (!player.result) return;
  pause();
  show(0);
  resume();
}

function play(result) {
  pause(); // une seule lecture à la fois, même si on relance pendant une lecture
  player.result = result;
  for (const id of ["#restart", "#toggle", "#next"]) $(id).disabled = false;
  show(0);
  resume();
}

$("#restart").addEventListener("click", restart);
$("#next").addEventListener("click", next);
$("#toggle").addEventListener("click", () => (player.timer ? pause() : resume()));
$(".speeds").addEventListener("click", (e) => {
  const button = e.target.closest("[data-speed]");
  if (!button) return;
  player.speed = Number(button.dataset.speed);
  for (const b of document.querySelectorAll("[data-speed]")) b.setAttribute("aria-pressed", String(b === button));
  if (player.timer) resume();
});
document.addEventListener("keydown", (e) => {
  if (e.metaKey || e.ctrlKey || e.altKey) return; // ne jamais intercepter Cmd+R & co
  if (e.target.closest("input, select, textarea")) return;
  if (e.key === " ") {
    if (e.target.closest("button")) return; // le bouton focus gère déjà Espace
    e.preventDefault();
    player.timer ? pause() : resume();
  } else if (e.key === "ArrowRight") {
    next();
  } else if (e.key === "r" || e.key === "R") {
    restart();
  }
});
```

- [ ] **Step 4 : vérifier les tests**

Run : `uv run pytest -q && uv run ruff check . && uv run mypy src`
Expected : suite verte, avec 1 xfail.

- [ ] **Step 5 : vérification manuelle**

Run : `make ui`, puis ouvrir http://127.0.0.1:8000. Vérifier :

- [ ] Lancer `happy_path` : la lecture démarre seule, chaque agent passe « en cours » (bordure violette, connecteur violet) puis « terminé », environ 0,9s par étape. Le journal, les jauges et les artefacts avancent au même rythme. La bannière apparaît à la fin et ⏯ repasse en « Lecture ».
- [ ] « étape k / 4 » suit la lecture.
- [ ] ⏯ met en pause et reprend ; ⏭ avance d'une frame et met en pause ; ⏮ recommence depuis 0 et relance.
- [ ] À 2×, la lecture est deux fois plus rapide ; le changement pendant la lecture est immédiat.
- [ ] Clavier, focus hors des champs : `Espace` ⏯, `→` ⏭, `R` ⏮. Focus dans Topic : taper « r » et espace écrit dans le champ sans piloter la lecture.
- [ ] `Cmd+R` (ou `Ctrl+R`) recharge toujours la page.
- [ ] Lancer « Budget dépassé », puis relancer `happy_path` pendant la lecture : la première lecture s'arrête net, la seconde repart de 0, sans clignotement entre les deux runs.
- [ ] Après une lecture terminée, ⏯ relance depuis le début.
- [ ] macOS Réglages → Accessibilité → Affichage → « Réduire les animations » : les états changent sans transition et la lecture fonctionne toujours.
- [ ] Wi-Fi coupé : la page se recharge et fonctionne.

- [ ] **Step 6 : commit**

```bash
git add src/kaldera/web/static tests/test_web.py
git commit -m "feat(web): lecteur animé (pas à pas, vitesse, raccourcis clavier)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
