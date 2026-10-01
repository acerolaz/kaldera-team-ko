# Kaldera UI — console de démo

Date : 2026-10-01
Statut : validé en brainstorming, en attente de relecture

## 1. Objectif

Une interface web locale qui rend visible l'orchestration multi-agents de Kaldera
pendant la soutenance du brief : le superviseur confie chaque étape à un agent,
les artefacts s'accumulent, les budgets se consomment, et le flux se termine
(`done`) ou s'arrête sur un garde-fou (`aborted`, `BudgetExceeded`).

- **Public** : jury et formateurs. Priorité : lisibilité à distance et impact visuel.
- **Données** : rejeu déterministe via `run_scenario()`, sans LLM, Azure ni réseau.
- **Interaction** : le présentateur charge un scénario JSON ou compose un run
  (topic, étapes ordonnées, `max_steps`), le lance, puis pilote l'animation.

### Hors périmètre

Exécution live (LLM), authentification, persistance des runs, mobile ou tablette,
multi-utilisateur, modification du cœur `kaldera`.

### Critères de succès

1. `happy_path` : les 4 agents s'activent tour à tour jusqu'à `done`.
2. Preset « Interrompu » (4 étapes, `max_steps=2`) : `aborted` clairement signalé.
3. Preset « Budget dépassé » (11 × RESEARCH, `max_steps=15`) : `BudgetExceeded`
   affiché sur `researcher`.
4. `make ui` suffit pour lancer l'interface. Elle fonctionne hors ligne et ne
   renvoie jamais de 500 sur une entrée utilisateur.

## 2. Architecture

FastAPI fin et une page statique HTML, CSS et JS vanilla, sans build front.
Le cœur `kaldera` n'est **pas modifié**.

```
src/kaldera/web/
  __init__.py
  app.py        # FastAPI : routes fines, montage de static/
  schemas.py    # Pydantic : ScenarioOut, RunRequest, RunResult, LogEntry, RunError
  service.py    # list_scenarios(), execute_run()
  static/
    index.html
    app.css
    app.js
tests/test_web.py
```

- Les routes sont en `def` synchrone : FastAPI les exécute dans son threadpool,
  donc aucun appel bloquant sur l'event loop.
- `service.py` ne connaît rien de HTTP. Il prend et renvoie des schémas Pydantic.
- Le chemin des scénarios réutilise la constante `SCENARIOS` de `kaldera.cli`.
  Pas de `pydantic-settings` : il n'y a pas d'autre config. Host et port passent
  par les flags uvicorn.

**Dépendances** : `fastapi` et `uvicorn` dans `dependencies`, `httpx` dans le
groupe `dev`.
**Makefile** : cible `ui` qui lance `uv run uvicorn kaldera.web.app:app --reload`.
**.gitignore** : ajouter `.superpowers/`.

## 3. API

### `GET /api/scenarios` → `list[ScenarioOut]`

```
ScenarioOut { id: str, topic: str, required_steps: list[StepName], max_steps: int }
```

Source : `scenarios/scenarios_test.json`. `max_steps` vient de `expected.max_steps`.

### `POST /api/runs` → `RunResult`

```
StepName   = Literal["RESEARCH", "DRAFT", "REVIEW", "FINALIZE"]

RunRequest {
  topic: str                    # 1..200 caractères
  required_steps: list[StepName] # 1..50 éléments
  max_steps: int                # 1..50 (aligné sur HARD_CAP)
}

RunResult {
  status: Literal["done", "aborted", "error"]
  step_count: int
  max_steps: int
  required_steps: list[StepName]
  artifacts: dict[str, str]
  agent_tokens: dict[str, int]   # tokens consommés par agent
  token_budgets: dict[str, int]  # budget par agent (depuis AGENTS_BY_NAME)
  log: list[LogEntry]
  error: RunError | None
}

LogEntry { agent_id: str, message: str }
RunError { type: Literal["BudgetExceeded", "RoleViolation"], agent: str, message: str }
```

### `GET /`

Sert `static/index.html`. Les assets sont servis sous `/static`.

### Fonctionnement de `execute_run()`

1. Construit un dict scénario `{initial_context: {topic, required_steps}, expected: {max_steps}}`.
2. Crée un `TeamState`, appelle `load_context(state, scenario)`, puis
   `run_scenario(scenario, initial_state=state)`. On garde ainsi la référence à
   l'état, même partiel.
3. Capture **uniquement** `BudgetExceeded` et `RoleViolation`. Dans ce cas :
   `status="error"` et `error.agent = route(state)`. L'exception est levée avant
   `advance()`, donc l'étape courante est celle qui a échoué.
4. Mappe l'état vers `RunResult`.

Chaque entrée de `state.log` correspond à une étape traitée (`record()` puis
`advance()` dans `Agent.run`). Le front rejoue donc la timeline à partir du log seul.

## 4. Interface

### Direction visuelle : « clair éditorial »

- Fond blanc, contraste maximal : choisi pour la lisibilité sur vidéoprojecteur.
- Tokens CSS sur `:root` : `--bg`, `--fg`, `--muted`, `--border`, `--surface`,
  `--active` (violet), `--ok` (vert), `--warn` (ambre), `--danger` (rouge).
  Chaque paire texte/fond respecte un contraste d'au moins 4.5:1.
- Police : `Inter, system-ui, sans-serif` pour l'UI, `ui-monospace, monospace`
  pour les artefacts et le log. **Aucun chargement externe**, pour garantir le
  fonctionnement hors ligne.
- Base 16px, focus visible, icônes en SVG Lucide inline (pas d'emoji comme icône).

### Layout : « pipeline horizontal », desktop 1280–1920px

```
┌ Kaldera · [scénario ▾] topic [______] étapes [chips…][+R][+D][+Rv][+F] max [5]  [▶ Lancer] ┐
│ presets : [Interrompu] [Budget dépassé]                                                  │
├──────────────────────────────── Pipeline ──────────────────────────────────────────────┤
│ [Superviseur] → [researcher] → [writer] → [reviewer] → [finalizer]                       │
│ ① ② ③ ④ …   (piste d'étapes)                       ⏮ ⏯ ⏭ · étape 2/4 · 0.5× 1× 2×     │
├── Journal ──────────────┬── Budgets tokens ────────┬── Artefacts ─────────────────────┤
│ researcher · a traité … │ researcher ▰▱▱ 100/1000  │ research  research[researcher]:… │
└─────────────────────────┴──────────────────────────┴──────────────────────────────────┘
[Bannière de statut]
```

### Composer

- Le sélecteur de scénario préremplit `topic`, les étapes et `max_steps`. Tout
  reste modifiable ensuite.
- Étapes : les boutons `+ STEP` ajoutent une étape en fin de liste, le `×` d'une
  chip la retire. Pas de glisser-déposer.
- `max_steps` : `<input type="number" min="1" max="50">`. Chaque champ a un label visible.
- Presets de démo :
  - « Interrompu » : topic `démo interruption`, étapes
    RESEARCH/DRAFT/REVIEW/FINALIZE, `max_steps=2` ;
  - « Budget dépassé » : topic `démo budget`, 11 × RESEARCH, `max_steps=15`.
- `Lancer` est désactivé et affiche un spinner pendant l'appel.

### Pipeline

- Superviseur suivi des 4 cartes d'agents, toujours affichées dans cet ordre.
  Icônes : researcher `search`, writer `pen-line`, reviewer `check-check`,
  finalizer `package`.
- États d'une carte, toujours signalés par icône et texte :

  | État    | Rendu                                                   |
  |---------|---------------------------------------------------------|
  | inactif | bordure `--border`, texte `--muted`                     |
  | actif   | bordure 2px `--active`, « en cours »                    |
  | terminé | ✓ `--ok`, compteur `×n` si l'agent a traité n > 1 étapes |
  | erreur  | ✕ `--danger`, type d'erreur                             |

- Animation clé unique : le connecteur entre le superviseur et l'agent actif
  s'allume (250ms, ease-out). Avec `prefers-reduced-motion: reduce`, les états
  changent sans transition.
- Piste d'étapes : une pastille numérotée par `required_steps` (retour à la
  ligne si nécessaire). États : à venir, en cours, faite, en erreur. En cas
  d'`aborted`, les étapes non atteintes sont hachurées avec la mention « non atteinte ».

### Lecture

- Après réception du `RunResult`, la lecture démarre automatiquement : une
  entrée du `log` toutes les 900ms à 1× (vitesses 0.5×, 1×, 2×).
- ⏮ recommence, ⏯ met en pause ou reprend, ⏭ passe à l'étape suivante.
  L'indicateur affiche « étape k / n ».
- Raccourcis : `Espace` pour ⏯, `→` pour ⏭, `R` pour ⏮. Ils sont inactifs
  quand le focus est dans un champ de saisie.
- Après la dernière entrée du log, l'état final s'affiche : carte en erreur si
  `error`, étapes non atteintes, bannière.

### Panneaux

- **Journal** : une ligne par entrée jouée (`agent_id · message`),
  `aria-live="polite"`.
- **Budgets** : une jauge par agent (`agent_tokens / token_budgets`). Ambre au-delà
  de 80 %, rouge pour l'agent de `error` en cas de `BudgetExceeded`, avec le
  message d'erreur (`1100 > 1000`).
- **Artefacts** : clé et contenu en mono. Un artefact apparaît quand l'étape qui
  le produit est jouée.

### Bannière de statut (en fin de lecture, `role="status"`)

| Statut  | Rendu                                                          |
|---------|----------------------------------------------------------------|
| done    | ✓ Terminé · `step_count` étapes / max `max_steps`              |
| aborted | ⚠ Interrompu · `step_count` étapes traitées sur `n` (max_steps = `max_steps`) |
| error   | ✕ `error.type` · `error.agent` : `error.message`               |

## 5. Gestion d'erreurs

| Cas                                    | API                                  | Front                                              |
|----------------------------------------|--------------------------------------|----------------------------------------------------|
| Entrée invalide                        | 422, format Pydantic par défaut      | message sous le champ concerné (via `loc`)         |
| `BudgetExceeded` / `RoleViolation`     | 200, `status="error"` + état partiel | carte en erreur, jauge rouge, bannière ✕           |
| Fichier de scénarios absent ou invalide | 500 (bug de déploiement, non masqué) | bannière « Erreur serveur (500) » + Réessayer      |
| API arrêtée ou réseau KO               | —                                    | bannière « API injoignable, vérifier `make ui` » + Réessayer |

Aucun `except Exception` : seuls les deux types métier sont capturés.

## 6. Tests

`tests/test_web.py` : tests d'acceptance avec `httpx.AsyncClient` et
`ASGITransport(app=app)`, marqués `@pytest.mark.anyio` (plugin fourni avec anyio,
pas de `pytest-asyncio`).

| # | Requête                                    | Attendu                                                            |
|---|--------------------------------------------|--------------------------------------------------------------------|
| 1 | `GET /api/scenarios`                       | 2 scénarios ; `happy_path` a 4 étapes et `max_steps=5`             |
| 2 | `POST /api/runs` (happy_path)              | `done`, `step_count=4`, 4 artefacts, log researcher→writer→reviewer→finalizer |
| 3 | 4 étapes, `max_steps=2`                    | `aborted`, `step_count=2`, `error=null`                            |
| 4 | 11 × RESEARCH, `max_steps=15`              | `error`, `error.type="BudgetExceeded"`, `error.agent="researcher"`, `step_count=10` |
| 5 | `required_steps=["FOO"]`                   | 422                                                                |
| 6 | `GET /`                                    | 200, `text/html`                                                   |

Pas de test unitaire séparé du service (couvert de bout en bout), ni de tests JS
automatisés. Le front est vérifié à la main via `make ui` : happy_path et les
deux presets, raccourcis clavier, `prefers-reduced-motion`, fonctionnement Wi-Fi
coupé.
