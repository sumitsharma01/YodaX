/* Evidence is computed from saved predictions; historical replay never updates live state. */
(() => {
  const $ = (id) => document.getElementById(id);
  let data = null,
    mode = "live",
    loading = false;
  const usd = (value) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(value);
  const num = (value) => value.toFixed(3);
  function el(tag, text, parent, css) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (css) node.className = css;
    if (parent) parent.append(node);
    return node;
  }
  function stat(label, value, note, parent) {
    const card = el("article", undefined, parent);
    el("span", label, card);
    el("strong", value, card);
    el("p", note, card);
  }
  function render() {
    if (!data) return;
    const live = mode === "live",
      report = live ? data.live : data.replay,
      summary = report.summary;
    $("evidence-live").setAttribute("aria-pressed", String(live));
    $("evidence-replay").setAttribute("aria-pressed", String(!live));
    $("evidence-kicker").textContent = live
      ? "PUBLISHED BEFORE THE OUTCOME"
      : "SIMULATION · NEVER ADDED TO THE LIVE RECORD";
    $("evidence-headline").textContent = live
      ? summary.count
        ? "The live record is taking shape."
        : "Improvement hasn’t been demonstrated yet."
      : Math.abs(summary.improvement || 0) < 1
        ? "Almost no difference in this replay."
        : `The replay ${summary.improvement > 0 ? "reduced" : "increased"} average error.`;
    $("evidence-description").textContent = live
      ? summary.count
        ? `${summary.count} saved predictions have actual outcomes across ${summary.sessions} sessions. Compare the same outcomes below; a short record does not establish consistent improvement.`
        : `${report.pending.length} predictions are saved in advance. There are no settled live outcomes yet, so there is no live improvement claim. You can inspect the saved prices or explore the separate historical replay.`
      : `We replayed ${summary.count} existing historical forecasts over ${summary.sessions} sessions. Each adjustment uses only earlier outcomes in the replay. This demonstrates how the update behaves, not how it performed live.`;
    const stats = $("evidence-stats");
    stats.replaceChildren();
    if (live && !summary.count) {
      stat(
        "Saved in advance",
        String(report.pending.length),
        "Immutable predictions awaiting evaluation",
        stats,
      );
      stat(
        "Completed outcomes",
        "Pending",
        "Scores follow the actual market close",
        stats,
      );
      stat(
        "What changes",
        "Forecast blend",
        "TimesFM itself is not retrained",
        stats,
      );
    } else {
      stat(
        "Unadjusted model",
        num(summary.raw_error) + " pp",
        "Mean absolute return error",
        stats,
      );
      stat(
        "Adaptive blend",
        num(summary.adaptive_error) + " pp",
        "Mean absolute return error",
        stats,
      );
      stat(
        "Difference",
        summary.improvement === null
          ? "—"
          : Math.abs(summary.improvement).toFixed(2) + "%",
        summary.improvement === null
          ? "No relative comparison available"
          : summary.improvement >= 0
            ? "Less error on these outcomes"
            : "More error on these outcomes",
        stats,
      );
    }
    const pending = live ? report.pending : [];
    $("pending-evidence").hidden = !pending.length;
    if (pending.length) {
      const first = pending[0];
      const waiting = pending.some((r) => r.status === "awaiting_daily_run");
      $("evidence-due").textContent = first.target;
      $("evidence-next").textContent = waiting
        ? "At least one saved target session is eligible for scoring. The daily forecasting job must run to fetch its closing price and record the update."
        : `The earliest scoring checkpoint is ${new Date(first.score_after).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} (your local time), one hour after the target session closes. The daily job records the outcome when it runs.`;
      const body = $("evidence-pending-rows");
      body.replaceChildren();
      pending.forEach((r) => {
        const tr = el("tr", undefined, body);
        [
          `${r.symbol} · ${r.target}`,
          usd(r.raw),
          usd(r.adaptive),
          r.created_at.slice(0, 19).replace("T", " "),
        ].forEach((t) => el("td", t, tr));
      });
    }
    $("evidence-comparison").hidden = !summary.count;
    $("evidence-audit").hidden = !report.rows.length;
    if (summary.count) {
      const chart = $("evidence-chart");
      chart.replaceChildren();
      const max = Math.max(
        summary.raw_error,
        summary.adaptive_error,
        summary.baseline_error,
        0.001,
      );
      [
        ["TimesFM", summary.raw_error],
        ["Adaptive blend", summary.adaptive_error],
        ["No-change baseline", summary.baseline_error],
      ].forEach(([name, value]) => {
        const row = el("div", undefined, chart, "evidence-bar-row");
        el("span", name, row);
        const track = el("div", undefined, row, "evidence-bar-track");
        const bar = el("div", undefined, track, "evidence-bar-fill");
        bar.style.width = `${(value / max) * 100}%`;
        el("strong", num(value) + " pp", row);
      });
      $("evidence-comparison-note").textContent =
        `${summary.sessions} sessions · ${summary.count} outcomes · identical comparison set. ${live ? "This is the observed live result, not a guarantee of future improvement." : "The first replay prediction uses initial weights. Later predictions use weights updated after prior outcomes. No replay result changes the live learner."}`;
    }
    const select = $("evidence-outcome");
    select.replaceChildren();
    const ordered = report.rows
      .map((row, index) => ({ row, index }))
      .sort(
        (a, b) =>
          b.row.target.localeCompare(a.row.target) ||
          a.row.symbol.localeCompare(b.row.symbol),
      );
    ordered.forEach(({ row, index }) => {
      const option = el("option", `${row.symbol} · ${row.target}`, select);
      option.value = String(index);
    });
    if (ordered.length) {
      select.value = String(ordered[0].index);
      audit();
    }
    $("evidence-provenance").textContent =
      `Model: ${data.model}. Saved data published ${new Date(data.generated_at).toLocaleString()}. Evidence read ${new Date(data.as_of).toLocaleString()}. Full timestamps, input hashes and update states are in the download.`;
  }
  function audit() {
    const report = mode === "live" ? data.live : data.replay;
    const row = report.rows[Number($("evidence-outcome").value)];
    const body = $("evidence-audit-body");
    body.replaceChildren();
    const prices = el("div", undefined, body, "audit-prices");
    stat(
      "TimesFM prediction",
      usd(row.raw),
      mode === "live" ? "Saved before the session" : "Before the replay update",
      prices,
    );
    stat(
      "Adaptive prediction",
      usd(row.adaptive),
      mode === "live" ? "Saved before the session" : "Before the replay update",
      prices,
    );
    stat("Actual close", usd(row.actual), row.target, prices);
    const delta = row.raw_error - row.adaptive_error;
    el(
      "p",
      Math.abs(delta) < 0.0005
        ? "The two estimates had practically the same error on this outcome (less than 0.001 percentage points apart)."
        : `The adaptive estimate was ${delta >= 0 ? "closer by" : "further away by"} ${Math.abs(delta).toFixed(3)} percentage points of return error on this outcome.`,
      body,
      "audit-verdict",
    );
    if (!row.state_before || !row.state_after) {
      el(
        "p",
        "A before-and-after state audit was not stored for this older outcome. The saved prediction and result remain available.",
        body,
      );
      return;
    }
    el("h4", "Weight change after observing the close", body);
    const names = ["TimesFM", "No-change", "Bias-corrected"];
    names.forEach((name, i) => {
      const before = row.state_before.weights[i] * 100,
        after = row.state_after.weights[i] * 100;
      const line = el("div", undefined, body, "weight-audit");
      el("span", name, line);
      const track = el("div", undefined, line, "weight-audit-track");
      const old = el("i", undefined, track, "weight-before");
      old.style.width = before + "%";
      const current = el("i", undefined, track, "weight-after");
      current.style.width = after + "%";
      el("strong", `${before.toFixed(1)}% → ${after.toFixed(1)}%`, line);
    });
    el(
      "p",
      `Update ${row.state_before.count} → ${row.state_after.count}. The new weights apply to later forecasts; they do not rewrite the prediction above.`,
      body,
      "muted",
    );
    el(
      "small",
      mode === "live"
        ? `Outcome recorded ${row.evaluated_at}.`
        : `Replay only. Original historical forecast generated ${row.source_created_at}.`,
      body,
    );
  }
  async function load() {
    if (loading || data) return;
    loading = true;
    try {
      const response = await fetch("/api/evidence", { cache: "no-store" });
      if (!response.ok) throw new Error();
      data = await response.json();
      $("evidence-loading").hidden = true;
      $("evidence-content").hidden = false;
      render();
    } catch {
      $("evidence-loading").textContent =
        "Saved evidence is unavailable. Please refresh after the local server is running.";
    } finally {
      loading = false;
    }
  }
  $("evidence-live").onclick = () => {
    mode = "live";
    render();
  };
  $("evidence-replay").onclick = () => {
    mode = "replay";
    render();
  };
  $("evidence-outcome").onchange = audit;
  document
    .querySelector('.nav[data-view="methodology"]')
    .addEventListener("click", load);
  if (new URLSearchParams(location.search).get("view") === "methodology")
    load();
})();
