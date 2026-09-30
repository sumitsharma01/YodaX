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
  const svg = document.querySelector("#price-chart");
  const mode = document.querySelector("#chart-mode").value;
  const returns = mode === "returns";
  const start = Math.max(1, selected.history.length - range);
  const prices = selected.history.slice(start), dates = selected.dates.slice(start);
  const values = returns ? prices.map((v,i)=>v/selected.history[start+i-1]-1) : prices;
  const averages = prices.map((_,i)=>{
    const end=start+i+1;
    return end>=20 ? mean(selected.history.slice(end-20,end)) : null;
  });
  const showAverage = !returns && document.querySelector("#chart-average").checked;
  const f=selected.forecast, format=returns?pct:money;
  const plotted = [...values,...(returns?[0]:[f.low,f.high]),...(showAverage?averages.filter(v=>v!==null):[])];
  const low=Math.min(...plotted), high=Math.max(...plotted), pad=(high-low||Math.abs(high)||1)*.12;
  const min=low-pad,max=high+pad;
  const y=v=>210-(v-min)/(max-min)*185;
  const x=i=>20+i/Math.max(1,values.length-1)*(returns?700:620);
  const path=vs=>vs.map((v,i)=>v===null?"":`${i&&vs[i-1]!==null?"L":"M"}${x(i)},${y(v)}`).join(" ");
  const ticks=Array.from({length:5},(_,i)=>{
    const v=min+(max-min)*i/4;
    return `<line x1="20" x2="730" y1="${y(v)}" y2="${y(v)}" stroke="#303029" stroke-dasharray="3 5"/><text x="740" y="${y(v)+4}" fill="#a5a59b" font-size="10">${returns?(v*100).toFixed(1)+"%":(v*fxRate()).toFixed(0)}</text>`;
  }).join("");
  const marks=returns?values.map((v,i)=>`<rect x="${x(i)-Math.max(1,280/values.length)}" y="${Math.min(y(0),y(v))}" width="${Math.max(2,560/values.length)}" height="${Math.max(1,Math.abs(y(v)-y(0)))}" fill="${v>=0?"#a3b7a0":"#ca9990"}"/>`).join(""):`
    ${mode==="area"?`<path d="${path(values)} L640,215 L20,215Z" fill="#d8d7cc" opacity=".09"/>`:""}
    <path d="${path(values)}" fill="none" stroke="#dad9ce" stroke-width="2"/>
    ${showAverage?`<path d="${path(averages)}" fill="none" stroke="#b7a77e" stroke-width="1.8"/>`:""}
    <path d="M640,${y(prices.at(-1))} L720,${y(f.high)} L720,${y(f.low)}Z" fill="#dddccf" opacity=".12"/>
    <path d="M640,${y(prices.at(-1))} L720,${y(f.predicted)}" fill="none" stroke="#dddccf" stroke-width="2" stroke-dasharray="5 4"/>
    <circle class="chart-beacon" cx="640" cy="${y(prices.at(-1))}" r="6" fill="none" stroke="#dddccf"/>
    <circle cx="720" cy="${y(f.predicted)}" r="4" fill="#dddccf"/>
    <text x="664" y="16" fill="#aaa99f" font-size="10">FORECAST</text>`;
  svg.innerHTML=ticks+marks+`<text x="20" y="243" fill="#aaa99f" font-size="11">${shortDate(dates[0])}</text><text x="590" y="243" fill="#aaa99f" font-size="11">${shortDate(dates.at(-1))}</text><g id="chart-cursor" visibility="hidden"><line y1="20" y2="215" stroke="#e0dfd6" stroke-dasharray="3 4"/><circle r="4" fill="#e0dfd6"/></g>`;
  svg.setAttribute("tabindex","0");
  svg.setAttribute("aria-label",`${selected.name} ${returns?"daily returns":"closing prices"}. Use left and right arrows to inspect sessions.`);
  const readout=document.querySelector("#chart-readout");
  const hint="Hover over the chart or use ← → to inspect · Daily closing data";
  readout.textContent=hint;
  document.querySelector("#chart-legend").textContent=returns?"Daily return · green: gain / rose: loss":`Closing price · dashed: forecast${showAverage?" · gold: 20-session average":""}`;
  document.querySelector("#chart-average").disabled=returns;
  let index=values.length-1;
  function inspect(i){
    index=Math.max(0,Math.min(values.length,i));
    const future=index===values.length;
    if(returns&&future)index=values.length-1;
    const isForecast=!returns&&index===values.length;
    const px=isForecast?720:x(index), val=isForecast?f.predicted:values[index];
    const cursor=svg.querySelector("#chart-cursor");cursor.setAttribute("visibility","visible");
    cursor.querySelector("line").setAttribute("x1",px);cursor.querySelector("line").setAttribute("x2",px);
    cursor.querySelector("circle").setAttribute("cx",px);cursor.querySelector("circle").setAttribute("cy",y(val));
    readout.textContent=isForecast?`${f.target} · Forecast ${money(val)} · Range ${money(f.low)} – ${money(f.high)}`:`${dates[index]} · ${returns?"Daily return":"Close"} ${format(val)}${showAverage&&averages[index]!==null?" · SMA 20 "+money(averages[index]):""}`;
  }
  svg.onpointermove=e=>{
    const matrix=svg.getScreenCTM();if(!matrix)return;
    const point=new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse());
    inspect(!returns&&point.x>680?values.length:Math.round((point.x-20)/(returns?700:620)*(values.length-1)));
  };
  svg.onpointerleave=()=>{svg.querySelector("#chart-cursor").setAttribute("visibility","hidden");readout.textContent=hint;};
  svg.onfocus=()=>inspect(index);
  svg.onkeydown=e=>{if(["ArrowLeft","ArrowRight","Home","End"].includes(e.key)){e.preventDefault();inspect(e.key==="Home"?0:e.key==="End"?values.length:index+(e.key==="ArrowRight"?1:-1));}};
  document.querySelector("#range-label").textContent=returns?"Change from the previous session’s close":`Estimated range ${money(f.low)} – ${money(f.high)}`;
}
document.querySelector("#chart-mode").onchange=()=>{if(selected)chart();};
document.querySelector("#chart-average").onchange=()=>{if(selected)chart();};

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
let refreshing = false;
async function boot(manual = false) {
  if (refreshing) return;
  refreshing = true;
  const button = document.querySelector('#refresh-forecasts');
  const status = document.querySelector('#refresh-status');
  button.disabled = true;
  button.textContent = 'Refreshing…';
  try {
    const response = await fetch("/api/dashboard", { cache: "no-store", signal: AbortSignal.timeout(60000) });
    if (!response.ok)
      throw new Error(
        "Forecasts unavailable. Start the API and run the local prediction job.",
      );
    const previous = payload?.generated_at;
    const symbol = selected?.symbol;
    payload = await response.json();
    stocks = payload.stocks;
    selected = stocks.find(s => s.symbol === symbol) || stocks[0];
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
    status.textContent = manual && previous === payload.generated_at
      ? `No newer forecasts published. Latest market close: ${payload.cutoff}.`
      : `Checked ${new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}. Market close: ${payload.cutoff}.`;
  } catch (error) {
    document.querySelector(".notice").hidden = false;
    document.querySelector(".notice").textContent =
      "Forecasts are temporarily unavailable. Please try again shortly.";
    status.textContent = 'Refresh failed. Please try again; previously loaded forecasts remain available.';
    if (!payload) document.querySelector(".demo-badge").textContent = "DATA UNAVAILABLE";
  } finally {
    refreshing = false;
    button.disabled = false;
    button.textContent = '↻ Refresh forecasts';
  }
}
document.querySelector('#refresh-forecasts').onclick = () => boot(true);
setInterval(() => { if (!document.hidden) boot(); }, 5 * 60 * 1000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) boot(); });
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
