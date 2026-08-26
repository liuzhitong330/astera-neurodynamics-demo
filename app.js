(function () {
  "use strict";

  const data = window.ASTERA_DATA;
  const stateCodes = ["fwd", "slow", "rev1", "rev2", "revsus", "dt", "vt", "nostate"];
  const stateLabels = data.meta.state_labels;
  const transitionSelect = document.getElementById("transition-select");
  const balance = document.getElementById("evidence-balance");
  const balanceValue = document.getElementById("balance-value");
  const ranking = document.getElementById("ranking");
  const profileSvg = document.getElementById("hero-viz");
  const readout = document.getElementById("readout");
  const modelTabs = document.getElementById("model-tabs");
  const modelSvg = document.getElementById("model-viz");
  const modelReadout = document.getElementById("model-readout");
  let selectedName = null;
  let selectedModel = String(data.chmm.best_clones);

  const ns = "http://www.w3.org/2000/svg";
  const makeSvg = (tag, attrs, text) => {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    return node;
  };

  Object.entries(data.transitions).forEach(([key, block]) => {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = block.label;
    transitionSelect.appendChild(option);
  });

  function score(candidate) {
    const activityWeight = Number(balance.value) / 100;
    const activity = 0.75 * candidate.activity_percentile + 0.25 * candidate.reliability;
    return activityWeight * activity + (1 - activityWeight) * candidate.anatomy_percentile;
  }

  function rankedCandidates() {
    return [...data.transitions[transitionSelect.value].candidates]
      .map((candidate) => ({ ...candidate, score: score(candidate) }))
      .sort((left, right) => right.score - left.score);
  }

  function intervention(candidate) {
    const aim = document.querySelector('input[name="aim"]:checked').value;
    const targetHigh = candidate.effect >= 0;
    if (aim === "promote") {
      return targetHigh ? "stimulate" : "inhibit";
    }
    return targetHigh ? "inhibit" : "stimulate";
  }

  function drawProfile(candidate) {
    profileSvg.replaceChildren();
    const width = 600;
    const height = 300;
    const margin = { top: 30, right: 18, bottom: 72, left: 46 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const values = candidate.profile;
    const min = Math.min(-1.2, ...values) - 0.08;
    const max = Math.max(1.2, ...values) + 0.08;
    const x = (index) => margin.left + (index / (values.length - 1)) * plotWidth;
    const y = (value) => margin.top + ((max - value) / (max - min)) * plotHeight;

    [-1, 0, 1].forEach((tick) => {
      if (tick < min || tick > max) return;
      profileSvg.appendChild(makeSvg("line", { x1: margin.left, x2: width - margin.right, y1: y(tick), y2: y(tick), class: tick === 0 ? "zero-line" : "grid-line" }));
      profileSvg.appendChild(makeSvg("text", { x: margin.left - 10, y: y(tick) + 4, class: "axis-label", "text-anchor": "end" }, String(tick)));
    });

    const points = values.map((value, index) => `${x(index)},${y(value)}`).join(" ");
    profileSvg.appendChild(makeSvg("polyline", { points, class: "profile-line" }));
    values.forEach((value, index) => {
      profileSvg.appendChild(makeSvg("circle", { cx: x(index), cy: y(value), r: 5, class: "profile-point" }));
      profileSvg.appendChild(makeSvg("text", { x: x(index), y: height - 48, class: "state-label", "text-anchor": "end", transform: `rotate(-35 ${x(index)} ${height - 48})` }, stateLabels[index]));
    });
    profileSvg.appendChild(makeSvg("text", { x: margin.left, y: 17, class: "chart-title" }, `${candidate.name} mean activity by annotated motor state`));
    profileSvg.appendChild(makeSvg("text", { x: 14, y: margin.top + plotHeight / 2, class: "axis-title", "text-anchor": "middle", transform: `rotate(-90 14 ${margin.top + plotHeight / 2})` }, "within-recording z-score"));
  }

  function updateReadout(candidate) {
    const block = data.transitions[transitionSelect.value];
    const action = intervention(candidate);
    const anatomy = Math.round(candidate.anatomy_percentile * 100);
    const anatomyText = candidate.anatomy_percentile >= 0.99 ? "the top 1%" : `the ${anatomy}th percentile`;
    const aim = document.querySelector('input[name="aim"]:checked').value;
    const targetNames = block.target_states.map((code) => stateLabels[stateCodes.indexOf(code)]).join(" / ");
    const outcome = aim === "promote" ? `increase entry into ${targetNames}` : `reduce entry into ${targetNames}`;
    readout.innerHTML = `<strong>${candidate.name}</strong> is the current first experiment: ${action} it, then test whether that manipulation can ${outcome}. Its mean target-minus-source shift is <strong>${candidate.effect.toFixed(2)} z</strong> across ${candidate.recordings} recordings with ${Math.round(candidate.agreement * 100)}% sign agreement; its anatomical strength is in <strong>${anatomyText}</strong> (${candidate.chemical_in.toFixed(0)} chemical input, ${candidate.chemical_out.toFixed(0)} chemical output, ${candidate.gap.toFixed(0)} gap-junction weight). Keep a sham perturbation and the opposite motor state as controls.`;
  }

  function renderRanking() {
    balanceValue.textContent = `${balance.value}%`;
    const candidates = rankedCandidates().slice(0, 6);
    if (!candidates.some((candidate) => candidate.name === selectedName)) selectedName = candidates[0].name;
    ranking.replaceChildren();
    candidates.forEach((candidate, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `rank-row${candidate.name === selectedName ? " active" : ""}`;
      button.setAttribute("aria-pressed", candidate.name === selectedName ? "true" : "false");
      button.innerHTML = `<span class="rank-index">${index + 1}</span><span class="rank-name">${candidate.name}</span><span class="rank-track"><span style="width:${(candidate.score * 100).toFixed(1)}%"></span></span><span class="rank-score">${(candidate.score * 100).toFixed(0)}</span>`;
      button.addEventListener("click", () => {
        selectedName = candidate.name;
        renderRanking();
      });
      ranking.appendChild(button);
    });
    const candidate = candidates.find((row) => row.name === selectedName) || candidates[0];
    drawProfile(candidate);
    updateReadout(candidate);
  }

  function drawModel() {
    modelSvg.replaceChildren();
    const models = data.chmm.models;
    const current = models[selectedModel];
    const width = 600;
    const height = 260;
    const margin = { top: 34, right: 22, bottom: 54, left: 58 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const all = Object.values(models).flatMap((model) => model.fold_bps);
    const min = Math.min(...all) - 0.01;
    const max = Math.max(...all) + 0.01;
    const x = (value) => margin.left + ((value - min) / (max - min)) * plotWidth;
    const rowY = (index) => margin.top + 28 + index * 52;

    [0.22, 0.25, 0.28].forEach((tick) => {
      if (tick < min || tick > max) return;
      modelSvg.appendChild(makeSvg("line", { x1: x(tick), x2: x(tick), y1: margin.top, y2: height - margin.bottom, class: "grid-line" }));
      modelSvg.appendChild(makeSvg("text", { x: x(tick), y: height - 28, class: "axis-label", "text-anchor": "middle" }, tick.toFixed(2)));
    });

    Object.entries(models).forEach(([clones, model], rowIndex) => {
      const y = rowY(rowIndex);
      modelSvg.appendChild(makeSvg("text", { x: margin.left - 14, y: y + 4, class: "axis-label", "text-anchor": "end" }, `${clones} clone${clones === "1" ? "" : "s"}`));
      model.fold_bps.forEach((value, foldIndex) => {
        modelSvg.appendChild(makeSvg("circle", { cx: x(value), cy: y + (foldIndex - 2) * 3, r: 4, class: clones === selectedModel ? "fold-point selected" : "fold-point" }));
      });
      modelSvg.appendChild(makeSvg("line", { x1: x(model.mean_bps - model.sd_bps), x2: x(model.mean_bps + model.sd_bps), y1: y, y2: y, class: "error-line" }));
      modelSvg.appendChild(makeSvg("circle", { cx: x(model.mean_bps), cy: y, r: 7, class: clones === selectedModel ? "mean-point selected" : "mean-point" }));
    });
    modelSvg.appendChild(makeSvg("text", { x: margin.left, y: 17, class: "chart-title" }, "Held-out prediction across five animals"));
    modelSvg.appendChild(makeSvg("text", { x: margin.left + plotWidth / 2, y: height - 5, class: "axis-title", "text-anchor": "middle" }, "bits per step (lower is better)"));

    const best = String(data.chmm.best_clones);
    const verdict = selectedModel === best ? "This is the lowest mean held-out score" : `The ${best}-clone model is lower`;
    modelReadout.innerHTML = `<strong>${selectedModel} clone${selectedModel === "1" ? "" : "s"} per observed state:</strong> ${current.mean_bps.toFixed(4)} ± ${current.sd_bps.toFixed(4)} held-out bits per step. ${verdict}. The best mean improves on one clone by ${data.chmm.improvement_percent.toFixed(2)}%, but the overlapping fold distributions argue for testing more animals before fixing model complexity.`;
  }

  function renderModelTabs() {
    modelTabs.replaceChildren();
    Object.keys(data.chmm.models).forEach((clones) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = clones === selectedModel ? "active" : "";
      button.textContent = `${clones} clone${clones === "1" ? "" : "s"}`;
      button.setAttribute("aria-pressed", clones === selectedModel ? "true" : "false");
      button.addEventListener("click", () => {
        selectedModel = clones;
        renderModelTabs();
        drawModel();
      });
      modelTabs.appendChild(button);
    });
    drawModel();
  }

  transitionSelect.value = "fwd_rev";
  transitionSelect.addEventListener("change", () => {
    selectedName = null;
    renderRanking();
  });
  balance.addEventListener("input", () => {
    selectedName = null;
    renderRanking();
  });
  document.querySelectorAll('input[name="aim"]').forEach((input) => input.addEventListener("change", renderRanking));
  renderRanking();
  renderModelTabs();
})();
