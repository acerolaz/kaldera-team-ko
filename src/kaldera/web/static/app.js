"use strict";

const AGENTS = ["researcher", "writer", "reviewer", "finalizer"];
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
