/* Conversation state lives on the server. Model text is never rendered as HTML. */
(() => {
  const $ = (id) => document.getElementById(id);
  const messages = $("research-messages");
  const status = $("research-status");
  const focus = $("commodity");
  const input = $("research-question");
  const map = $("research-map");
  let conversationId = localStorage.getItem("yodax-research-conversation");
  let busy = false;
  let currentReport = null;
  let zoom = 1;
  let selectedMessage = null;
  const welcome = $("research-welcome").cloneNode(true);
  const svgNS = "http://www.w3.org/2000/svg";
  function el(tag, text, parent, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    if (parent) parent.append(node);
    return node;
  }
  function svg(tag, attrs, parent, text) {
    const node = document.createElementNS(svgNS, tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    if (text) node.textContent = text;
    parent.append(node);
    return node;
  }
  async function api(path, body) {
    const response = await fetch(
      "/api/research" + path,
      body
        ? {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }
        : {},
    );
    const data = await response.json();
    if (!response.ok)
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "The request could not be completed.",
      );
    return data;
  }
  function setBusy(value) {
    busy = value;
    $("research-send").disabled = value;
    $("new-research").disabled = value;
    focus.disabled = value || !!conversationId;
    $("research-send").textContent = value ? "Working…" : "Send ↑";
  }
  function link(source, parent, number) {
    if (!source) return;
    const anchor = el(
      "a",
      `${number ? "[" + number + "] " : ""}${source.title}`,
      parent,
    );
    try {
      if (new URL(source.url).protocol !== "https:") return;
    } catch {
      return;
    }
    anchor.href = source.url;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
  }
  function citedText(text, parent, report) {
    let offset = 0;
    for (const match of text.matchAll(/\[([0-9, ]+)\]/g)) {
      parent.append(document.createTextNode(text.slice(offset, match.index)));
      parent.append(document.createTextNode("["));
      match[1]
        .split(",")
        .map((value) => Number(value.trim()))
        .forEach((id, index) => {
          if (index) parent.append(document.createTextNode(", "));
          const source = report.sources[id - 1];
          if (source) {
            const anchor = el("a", String(id), parent, "fm-citation");
            anchor.href = source.url;
            anchor.target = "_blank";
            anchor.rel = "noopener noreferrer";
            anchor.title = source.title;
          } else parent.append(document.createTextNode(String(id)));
        });
      parent.append(document.createTextNode("]"));
      offset = match.index + match[0].length;
    }
    parent.append(document.createTextNode(text.slice(offset)));
  }
  function message(role, text, report = null) {
    $("research-welcome")?.remove();
    const article = el("article", "", messages, "fm-message " + role);
    el(
      "div",
      role === "user"
        ? "You"
        : role === "error"
          ? "Research paused"
          : "YodaX · Research",
      article,
      "fm-message-label",
    );
    const body = el("div", "", article, "fm-message-body");
    if (report) {
      citedText(text, body, report);
      const button = el("button", "Explore this answer’s map ↗", article);
      button.type = "button";
      button.onclick = () => selectReport(report, article);
      if (report.note) el("p", report.note, article, "fm-footnote");
    } else body.textContent = text;
    messages.scrollTop = messages.scrollHeight;
    return article;
  }
  function selectReport(report, article) {
    selectedMessage?.classList.remove("selected-answer");
    selectedMessage = article;
    article.classList.add("selected-answer");
    currentReport = report;
    zoom = 1;
    $("map-caption").textContent = report.outlook;
    drawGraph();
    showNode(report.nodes.find((n) => n.kind === "outlook").id);
    const sources = $("research-sources");
    sources.replaceChildren();
    el("p", `Research date: ${report.date} · ${report.model}`, sources);
    el("h4", "Questions explored", sources);
    report.queries.forEach((query, i) =>
      el("p", `${i + 1}. ${query}`, sources),
    );
    el("h4", "Headline sources", sources);
    const list = el("ol", "", sources);
    report.sources.forEach((source) => {
      const item = el("li", "", list);
      link(source, item);
      el(
        "small",
        `${source.publisher} · ${source.published} · Headline only`,
        item,
      );
    });
  }
  function showNode(id) {
    const report = currentReport;
    const node = report.nodes.find((n) => n.id === id);
    if (!node) return;
    map
      .querySelectorAll(".graph-node")
      .forEach((g) => g.classList.toggle("selected", g.dataset.node === id));
    const detail = $("map-detail");
    detail.replaceChildren();
    const names = {
      evidence: "HEADLINE EVIDENCE",
      mechanism: "PROPOSED MECHANISM",
      risk: "RISK / COUNTERARGUMENT",
      outlook: "CONDITIONAL OUTLOOK",
    };
    el("span", names[node.kind], detail, "fm-kicker");
    el("h3", node.label, detail);
    el("p", node.detail, detail);
    if (node.source_ids.length) {
      const list = el("ul", "", detail);
      node.source_ids.forEach((id) =>
        link(report.sources[id - 1], el("li", "", list), id),
      );
    } else
      el(
        "p",
        "An analytical hypothesis; no direct source is attached to this node.",
        detail,
      );
    const connected = report.edges.filter((e) => e.from === id || e.to === id);
    if (connected.length) {
      el("h4", "Linked context", detail);
      connected.forEach((edge) => {
        const from = report.nodes.find((n) => n.id === edge.from);
        const to = report.nodes.find((n) => n.id === edge.to);
        const button = el(
          "button",
          `${from.label} → ${edge.label} → ${to.label}`,
          detail,
        );
        button.type = "button";
        button.style.cssText =
          "display:block;text-align:left;margin-top:8px;font-size:11px";
        button.onclick = () => showNode(edge.from === id ? edge.to : edge.from);
      });
    }
  }
  function wrapLabel(label) {
    const words = label.split(/\s+/);
    const lines = [""];
    words.forEach((word) => {
      if (
        (lines[lines.length - 1] + " " + word).length > 27 &&
        lines.length < 3
      )
        lines.push(word);
      else
        lines[lines.length - 1] += (lines[lines.length - 1] ? " " : "") + word;
    });
    return lines.map((line) =>
      line.length > 30 ? line.slice(0, 29) + "…" : line,
    );
  }
  function drawGraph() {
    if (!currentReport) return;
    map.replaceChildren();
    const groups = [
      currentReport.nodes.filter((n) => n.kind === "evidence"),
      currentReport.nodes.filter((n) => ["mechanism", "risk"].includes(n.kind)),
      currentReport.nodes.filter((n) => n.kind === "outlook"),
    ];
    const height = Math.max(
      380,
      Math.max(...groups.map((g) => g.length)) * 122 + 40,
    );
    const width = 880;
    const root = svg(
      "svg",
      {
        viewBox: `0 0 ${width} ${height}`,
        class: "fm-graph",
        role: "group",
        "aria-label":
          "Evidence linked through hypotheses and risks to the outlook",
      },
      map,
    );
    root.style.width = `${100 * zoom}%`;
    root.style.height = `${Math.max(340, height * 0.7) * zoom}px`;
    const marker = svg(
      "marker",
      {
        id: "fm-arrow",
        viewBox: "0 0 10 10",
        refX: 9,
        refY: 5,
        markerWidth: 5,
        markerHeight: 5,
        orient: "auto-start-reverse",
      },
      svg("defs", {}, root),
    );
    svg("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#728d65" }, marker);
    const positions = new Map();
    groups.forEach((nodes, column) =>
      nodes.forEach((node, row) =>
        positions.set(node.id, {
          x: 20 + column * 320,
          y: (height / (nodes.length + 1)) * (row + 1) - 44,
        }),
      ),
    );
    for (const edge of currentReport.edges) {
      const start = positions.get(edge.from),
        end = positions.get(edge.to);
      const forward = end.x > start.x;
      const x1 = start.x + (forward ? 210 : 105),
        y1 = start.y + (forward ? 44 : 88);
      const x2 = end.x + (forward ? 0 : 105),
        y2 = end.y + (forward ? 44 : 0);
      const midpoint = (x1 + x2) / 2;
      svg(
        "path",
        {
          d: `M ${x1} ${y1} C ${midpoint} ${y1}, ${midpoint} ${y2}, ${x2} ${y2}`,
          class: "graph-edge",
          "marker-end": "url(#fm-arrow)",
        },
        root,
      );
      svg(
        "text",
        {
          x: midpoint,
          y: (y1 + y2) / 2 - 6,
          "text-anchor": "middle",
          class: "edge-label",
        },
        root,
        edge.label.length > 22 ? edge.label.slice(0, 21) + "…" : edge.label,
      );
    }
    const colors = {
      evidence: ["#182c34", "#6593ac"],
      mechanism: ["#272332", "#a398bf"],
      risk: ["#32291d", "#b59264"],
      outlook: ["#2b3c1d", "#c8f675"],
    };
    for (const node of currentReport.nodes) {
      const pos = positions.get(node.id);
      const [fill, stroke] = colors[node.kind];
      const group = svg(
        "g",
        {
          transform: `translate(${pos.x},${pos.y})`,
          class: "graph-node",
          tabindex: 0,
          role: "button",
          "aria-label": `${node.kind}: ${node.label}`,
        },
        root,
      );
      group.dataset.node = node.id;
      svg(
        "rect",
        { width: 210, height: 88, rx: 12, fill, stroke, "stroke-width": 1 },
        group,
      );
      svg(
        "text",
        { x: 13, y: 19, class: "node-type", fill: stroke },
        group,
        node.kind === "mechanism" ? "HYPOTHESIS" : node.kind.toUpperCase(),
      );
      wrapLabel(node.label).forEach((line, index) =>
        svg(
          "text",
          { x: 13, y: 39 + index * 14, class: "node-label" },
          group,
          line,
        ),
      );
      group.onclick = () => showNode(node.id);
      group.onkeydown = (e) => {
        if (["Enter", " "].includes(e.key)) {
          e.preventDefault();
          showNode(node.id);
        }
      };
    }
  }
  function failure(text, question) {
    const article = message("error", text);
    const retry = el("button", "Retry this message", article);
    retry.type = "button";
    retry.onclick = () => {
      if (!busy) send(question);
    };
  }
  async function poll(turnId, question) {
    let failures = 0;
    while (true) {
      let turn;
      try {
        turn = await api("/turns/" + encodeURIComponent(turnId));
        failures = 0;
      } catch (error) {
        if (++failures >= 3)
          throw new Error(
            "Connection interrupted. Reload to resume this saved conversation.",
          );
        status.textContent = "Reconnecting to your research…";
        await new Promise((resolve) => setTimeout(resolve, 2000));
        continue;
      }
      status.textContent = turn.stage;
      if (turn.state === "done") {
        const article = message("assistant", turn.result.answer, turn.result);
        selectReport(turn.result, article);
        status.textContent = "";
        return;
      }
      if (turn.state === "error") {
        failure(turn.error, question);
        status.textContent = "";
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
  }
  async function availability() {
    try {
      const data = await api("/status");
      $("research-connection").textContent = data.configured
        ? "Gemini Flash-Lite"
        : "Key needed";
      $("research-connection").title =
        `${data.remaining} local requests remaining today`;
    } catch {
      $("research-connection").textContent = "Offline";
    }
  }
  async function send(value) {
    if (busy) return;
    const text = (value || input.value).trim();
    if (text.length < 2) return;
    message("user", text);
    input.value = "";
    setBusy(true);
    status.textContent = "Starting research…";
    try {
      const result = await api("/chat", {
        topic: focus.value.trim(),
        message: text,
        conversation_id: conversationId || null,
      });
      conversationId = result.conversation_id;
      localStorage.setItem("yodax-research-conversation", conversationId);
      focus.disabled = true;
      await poll(result.turn_id, text);
    } catch (error) {
      failure(error.message, text);
      status.textContent = "";
    } finally {
      setBusy(false);
      availability();
      input.focus();
    }
  }
  function attachPrompts() {
    document.querySelectorAll("[data-prompt]").forEach(
      (button) =>
        (button.onclick = () => {
          focus.value = button.dataset.topic;
          send(button.dataset.prompt);
        }),
    );
  }
  $("research-chat").onsubmit = (e) => {
    e.preventDefault();
    send();
  };
  input.onkeydown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!busy) send();
    }
  };
  $("new-research").onclick = () => {
    if (busy) return;
    conversationId = null;
    currentReport = null;
    selectedMessage = null;
    localStorage.removeItem("yodax-research-conversation");
    messages.replaceChildren(welcome.cloneNode(true));
    attachPrompts();
    focus.disabled = false;
    input.value = "";
    status.textContent = "";
    map.replaceChildren();
    el(
      "p",
      "Ask a question to build a new evidence map.",
      map,
      "fm-map-placeholder",
    );
    $("map-caption").textContent =
      "Your evidence map will appear here as the conversation develops.";
    $("map-detail").textContent =
      "Select a node to see its context, supporting sources and connections.";
    $("research-sources").textContent =
      "Sources appear after your first answer.";
    input.focus();
  };
  $("map-plus").onclick = () => {
    zoom = Math.min(2.5, zoom + 0.25);
    drawGraph();
  };
  $("map-minus").onclick = () => {
    zoom = Math.max(0.75, zoom - 0.25);
    drawGraph();
  };
  $("map-reset").onclick = () => {
    zoom = 1;
    drawGraph();
  };
  async function restore() {
    attachPrompts();
    availability();
    if (!conversationId) return;
    setBusy(true);
    try {
      const chat = await api(
        "/conversations/" + encodeURIComponent(conversationId),
      );
      focus.value = chat.topic;
      for (const turn of chat.turns) {
        message("user", turn.question);
        if (turn.state === "done") {
          const article = message("assistant", turn.result.answer, turn.result);
          selectReport(turn.result, article);
        } else if (turn.state === "error") failure(turn.error, turn.question);
        else await poll(turn.id, turn.question);
      }
    } catch (error) {
      status.textContent =
        error.message + " Start a new conversation to continue.";
    } finally {
      setBusy(false);
    }
  }
  document.querySelector('[data-view="future"]').addEventListener('click', () => {
    requestAnimationFrame(() => { messages.scrollTop = messages.scrollHeight; });
  });
  restore();
})();
