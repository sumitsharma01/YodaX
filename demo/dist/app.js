let stocks = [],
  selected = null,
  range = 21,
  payload = null,
  scope = "prospective";
let currency = "USD";
try {
  currency = localStorage.getItem("yodax-currency") || "USD";
} catch {}
const fxRate = () => payload?.fx?.rates?.[currency] || 1;
const money = (n) =>
  (n * fxRate()).toLocaleString(currency === "INR" ? "en-IN" : "en-US", {
    style: "currency",
    currency,
    currencyDisplay: currency === "CAD" ? "code" : "symbol",
  });
const pct = (n) => `${n >= 0 ? "+" : ""}${(n * 100).toFixed(2)}%`;
const mean = (a) => a.reduce((s, n) => s + n, 0) / a.length;
const shortDate = (d) =>
  new Date(d + "T12:00:00Z").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
const recordsFor = (s) => s.records.filter((r) => r.kind === scope);
function renderList() {
  const query = document.querySelector("#search").value.trim().toLowerCase();
  const filtered = stocks.filter((s) =>
    (s.name + s.symbol).toLowerCase().includes(query),
  );
  document.querySelector("#stock-list").innerHTML = filtered.length
    ? filtered
        .map(
          (s) =>
            `<button class="stock-button ${s === selected ? "selected" : ""}" data-stock="${s.symbol}" aria-pressed="${s === selected}"><span class="company-logo" style="color:${s.color}">${s.logo}</span><span class="company-copy"><strong>${s.symbol}</strong><small>${s.name}</small></span><span class="company-price">${money(s.price)}<small class="${s.change > 0 ? "up" : "down"}">${pct(s.change)}</small></span></button>`,
        )
        .join("")
    : '<p class="empty">No matching companies.</p>';
  document.querySelectorAll("[data-stock]").forEach(
    (b) =>
      (b.onclick = () => {
        selected = stocks.find((s) => s.symbol === b.dataset.stock);
        render();
      }),
  );
}
function row(r, label) {
  const delta = r.predicted - r.actual;
  return `<tr><td>${label || r.date}</td><td>${money(r.predicted)}</td><td>${money(r.actual)}</td><td>${money(Math.abs(delta))} ${delta > 0 ? "too high" : delta < 0 ? "too low" : "exact"}</td><td><span class="result ${r.correct ? "" : "miss"}">${r.correct ? "Correct" : "Missed"}</span></td><td>${r.scoring ? r.scoring.score.toFixed(0) : "Not available"}</td></tr>`;
}
function chart() {
  const values = selected.history.slice(-range),
    forecast = selected.forecast.predicted,
    lo = selected.forecast.low,
    hi = selected.forecast.high,
    min = Math.min(...values, lo) * 0.99,
    max = Math.max(...values, hi) * 1.01;
  const y = (v) => 210 - ((v - min) / (max - min)) * 185;
  const x = (i) => 14 + (i / (values.length - 1)) * 627;
  const path = values
    .map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(2)},${y(v).toFixed(2)}`)
    .join(" ");
  const ticks = Array.from({ length: 5 }, (_, i) => {
    const v = min + ((max - min) * i) / 4;
    return `<line x1="14" x2="742" y1="${y(v)}" y2="${y(v)}" stroke="#303029" stroke-dasharray="3 5"/><text x="751" y="${y(v) + 4}" fill="#92968a" font-size="11">${(v * fxRate()).toLocaleString("en-US", { maximumFractionDigits: 0 })}</text>`;
  }).join("");
  document.querySelector("#price-chart").innerHTML =
    `<defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e0dfd6" stop-opacity=".16"/><stop offset="1" stop-color="#e0dfd6" stop-opacity="0"/></linearGradient></defs>${ticks}<rect x="642" y="12" width="99" height="201" fill="#e0dfd6" opacity=".025"/><path d="${path} L641,214 L14,214 Z" fill="url(#fill)"/><path d="${path}" fill="none" stroke="#bdbeb2" stroke-width="2.5" stroke-linejoin="round"/><path d="M641,${y(selected.price)} L719,${y(hi)} L719,${y(lo)} Z" fill="#e0dfd6" opacity=".13"/><line x1="641" x2="641" y1="12" y2="215" stroke="#787d6d" stroke-dasharray="4 5"/><path d="M641,${y(selected.price)} L719,${y(forecast)}" fill="none" stroke="#e0dfd6" stroke-width="2.5" stroke-dasharray="5 4"/><circle cx="719" cy="${y(forecast)}" r="5" fill="#e0dfd6"/><text x="660" y="${Math.max(12, y(hi) - 9)}" fill="#e0dfd6" font-size="11">FORECAST</text><text x="14" y="243" fill="#92968a" font-size="11">${shortDate(selected.dates.slice(-range)[0])}</text><text x="310" y="243" fill="#92968a" font-size="11">${shortDate(selected.dates.slice(-range)[Math.floor(values.length / 2)])}</text><text x="611" y="243" fill="#92968a" font-size="11">${shortDate(selected.forecast.cutoff)}</text><text x="698" y="243" fill="#e0dfd6" font-size="11">${shortDate(selected.forecast.target)}</text>`;
  document
    .querySelector("#price-chart")
    .setAttribute(
      "aria-label",
      `${selected.name}: ${range} historical sessions, forecast ${money(forecast)}, model quantile range ${money(lo)} to ${money(hi)}`,
    );
  document.querySelector("#range-label").textContent =
    `Estimated range ${money(lo)} – ${money(hi)}`;
}
function render() {
  document.querySelector("#recent-rows").closest("table").tHead.hidden =
    !selected.records.some((r) => r.kind === "prospective");
  renderList();
  document.querySelector("#selected-logo").textContent = selected.logo;
  document.querySelector("#selected-logo").style.color = selected.color;
  document.querySelector("#selected-name").textContent = selected.name;
  document.querySelector("#selected-ticker").textContent =
    `${selected.symbol} · NASDAQ · ${currency}${currency === "USD" ? "" : " converted"}`;
  document.querySelector("#selected-price").innerHTML =
    `${money(selected.price)}<small class="${selected.change > 0 ? "up" : "down"}">${pct(selected.change)}</small>`;
  document.querySelector("#predicted-price").textContent = money(
    selected.price * (1 + selected.drift),
  );
  document.querySelector("#predicted-move").textContent =
    `${pct(selected.drift)} estimated move`;
  document.querySelector("#predicted-move").className =
    selected.drift > 0 ? "up" : "down";
  document.querySelector("#ledger-company").textContent = selected.name;
  document.querySelector("#recent-rows").innerHTML =
    [...selected.records.filter((r) => r.kind === "prospective")]
      .reverse()
      .slice(0, 5)
      .map((r) => row(r))
      .join("") ||
    '<tr><td colspan="6">Results available after market close. Your prediction is saved; we’ll show how close it was once the closing price arrives.</td></tr>';
  document.querySelector(".forecast-footer strong").textContent =
    selected.forecast.target;
  chart();
}
function view(name) {
  document.body.dataset.view = name;
  document.querySelector("#currency-note").hidden = [
    "future",
    "methodology",
  ].includes(name);
  document.querySelector("#evaluation-control").hidden = name !== "performance";
  ["overview", "tomorrow", "performance", "methodology", "future"].forEach(
    (v) => (document.getElementById(v).hidden = v !== name),
  );
  document.querySelectorAll(".nav[data-view]").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === name);
    b.setAttribute("aria-current", b.dataset.view === name ? "page" : "false");
  });
  const titles = {
    future: [
      "Future Market",
      "Understand what moves commodities.",
      "A weekly view of supply, demand and the world in between.",
    ],
    tomorrow: [
      "Tomorrow’s forecast",
      "Your next market outlook.",
      "A forecast for each company. Results after the closing bell.",
    ],
    overview: [
      "Overview",
      "A clearer view of what’s next.",
      "Explore tomorrow’s possibilities. Measure today’s results.",
    ],
    performance: [
      "Track record",
      "How close were our predictions?",
      "Compare our forecasts with what actually happened.",
    ],
    methodology: [
      "Methodology",
      "Evidence, before claims.",
      "See what was saved, what changed, and what the results support.",
    ],
  };
  const t = titles[name];
  document.querySelector("#breadcrumb").textContent = t[0];
  document.querySelector("#page-title").textContent = t[1];
  document.querySelector("#page-description").textContent = t[2];
}

function renderMetrics() {
  const records = stocks.flatMap(recordsFor),
    count = records.length;
  document.querySelector("#all-rows").closest("table").tHead.hidden = !count;
  const scores = records.filter((r) => r.scoring);
  document.querySelector("#results-summary").textContent = count
    ? `${scope === "historical" ? "Historical tests — generated after the fact." : "Published before the trading session."} ${count} results${scores.length ? ` · Average score ${mean(scores.map((r) => r.scoring.score)).toFixed(0)}/100` : ""}. Scores measure closeness, not the probability of being correct.`
    : "Results available after market close. Your first predictions are saved and waiting for actual closing prices.";
  document.querySelector("#all-rows").innerHTML =
    stocks
      .flatMap((s) =>
        [...recordsFor(s)]
          .reverse()
          .map((r) => row(r, `${s.symbol} · ${r.date}`)),
      )
      .join("") ||
    '<tr><td colspan="6">Results available after market close.</td></tr>';
  document.querySelector("#ledger-description").textContent =
    scope === "historical"
      ? "Historical tests, not predictions published in advance."
      : "Predictions saved before trading, compared with the actual close.";
}
document
  .querySelectorAll(".nav[data-view]")
  .forEach((b) => (b.onclick = () => view(b.dataset.view)));
document.querySelector("#view-record").onclick = () => {
  view("performance");
  window.scrollTo({ top: 0, behavior: "smooth" });
};
document.querySelector("#search").oninput = renderList;
document.querySelectorAll("[data-range]").forEach(
  (b) =>
    (b.onclick = () => {
      range = Number(b.dataset.range);
      document.querySelectorAll("[data-range]").forEach((x) => {
        x.classList.toggle("active", x === b);
        x.setAttribute("aria-pressed", String(x === b));
      });
      if (selected) chart();
    }),
);
document.querySelector("#evaluation-scope").onchange = (e) => {
  scope = e.target.value;
  renderMetrics();
  render();
};
async function boot() {
  try {
    const response = await fetch("/api/dashboard", { cache: "no-store" });
    if (!response.ok)
      throw new Error(
        "Forecasts unavailable. Start the API and run the local prediction job.",
      );
    payload = await response.json();
    stocks = payload.stocks;
    selected = stocks[0];
    configureCurrency();

    document.querySelector(".demo-badge").textContent =
      `Updated ${shortDate(payload.cutoff)}`;

    document.querySelector(".asof").innerHTML =
      `Latest completed session<strong>${payload.cutoff}</strong>`;
    const age = (Date.now() - Date.parse(payload.generated_at)) / 86400000;
    document.querySelector(".notice").hidden = age <= 3;
    document.querySelector(".notice").textContent =
      "These forecasts may be out of date. Waiting for the next update.";
    renderMetrics();
    render();
    renderLearning();
    view(document.body.dataset.view || "overview");
  } catch (error) {
    document.querySelector(".notice").hidden = false;
    document.querySelector(".notice").textContent =
      "Forecasts are temporarily unavailable. Please try again shortly.";
    document.querySelector(".demo-badge").textContent = "DATA UNAVAILABLE";
    document.querySelector("#overview").hidden = true;
  }
}
boot();

function renderLearning() {
  document.querySelector("#tomorrow-date").textContent = payload.target;
  document.querySelector("#tomorrow-cards").innerHTML = stocks
    .map(
      (s) =>
        `<article class="tomorrow-card"><div class="stock-heading"><strong>${s.symbol}</strong><span class="muted">${s.name}</span></div><div class="muted card-caption">Predicted close</div><div class="tomorrow-price">${money(s.forecast.predicted)}</div><span class="${s.drift >= 0 ? "up" : "down"}">${pct(s.drift)} expected change</span><div class="adaptive-price"><span>Last close</span><strong>${money(s.price)}</strong></div><p class="muted">Estimated range<br>${money(s.forecast.low)} – ${money(s.forecast.high)}</p></article>`,
    )
    .join("");
}

function configureCurrency() {
  const select = document.querySelector("#currency");
  for (const option of select.options)
    option.disabled = !payload.fx?.rates?.[option.value];
  if (!payload.fx?.rates?.[currency]) currency = "USD";
  select.value = currency;
  const note = document.querySelector("#currency-note");
  note.hidden = currency === "USD" && !payload.fx?.stale;
  note.textContent = payload.fx?.stale
    ? "Currency conversion is unavailable. Prices are shown in USD."
    : `Converted from USD using ${payload.fx.source} rates dated ${payload.fx.date}. All dates use this same rate; this is not a historical FX return.`;
}
document.querySelector("#currency").onchange = (e) => {
  currency = e.target.value;
  try {
    localStorage.setItem("yodax-currency", currency);
  } catch {}
  configureCurrency();
  renderMetrics();
  render();
  renderLearning();
};

const requestedView = new URLSearchParams(location.search).get("view");
if (
  ["overview", "tomorrow", "performance", "methodology", "future"].includes(
    requestedView,
  )
) {
  view(requestedView);
}
