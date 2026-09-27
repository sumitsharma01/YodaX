/* All model output is rendered as text. Search suggestions use an isolated frame. */
(() => {
  const status = document.querySelector('#research-status');
  const map = document.querySelector('#research-map');
  const answer = document.querySelector('#research-answer');
  let activeTopic = '';
  let busy = false;
  function element(tag, text, parent) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (parent) parent.append(node);
    return node;
  }
  async function availability() {
    try {
      const response = await fetch('/api/research/status');
      if (!response.ok) throw new Error();
      const value = await response.json();
      status.textContent = value.configured ? `Ready to research · ${value.remaining} requests remaining today` : 'Save your Gemini key in .env to start researching.';
    } catch { status.textContent = 'Research is unavailable. Restart the local server to load the latest version.'; }
  }
  function render(report, target) {
    target.replaceChildren();
    element('h3', `${report.topic} · ${report.date}`, target);
    const branches = element('div', '', target);
    branches.className = 'research-branches';
    for (const branch of report.branches) {
      const card = element('details', '', branches);
      card.className = 'research-branch';
      element('summary', branch.title, card);
      const text = element('div', branch.text, card);
      text.className = 'research-text';
      element('h4', 'Research sources', card);
      const sources = element('ol', '', card);
      branch.sources.forEach(source => {
        const item = element('li', '', sources);
        const link = element('a', source.title, item);
        element('small', ` · ${source.published || ''} · Headline evidence`, item);
        if (new URL(source.url).protocol !== 'https:') return;
        link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      });
      if (branch.search_suggestions) {
        const frame = element('iframe', '', card);
        frame.title = 'Google Search suggestions';
        frame.setAttribute('sandbox', 'allow-popups allow-popups-to-escape-sandbox');
        frame.srcdoc = branch.search_suggestions;
        frame.className = 'search-suggestions';
      }
    }
  }
  async function run(question = '') {
    if (busy) return;
    busy = true;
    const topic = question ? activeTopic : document.querySelector('#commodity').value.trim();
    document.querySelectorAll('#future button, #future input').forEach(e => e.disabled = true);
    status.textContent = question ? 'Checking evidence for your question…' : 'Researching the past week, then following the evidence… This may take a few minutes.';
    try {
      const response = await fetch('/api/research', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({topic, question})});
      const report = await response.json();
      if (!response.ok) throw new Error(typeof report.detail === 'string' ? report.detail : 'Research request failed.');
      render(report, question ? answer : map);
      if (!question) { activeTopic = topic; answer.replaceChildren(); }
      document.querySelector('#research-chat').hidden = false;
      await availability();
    } catch (error) { status.textContent = error.message; }
    finally { busy = false; document.querySelectorAll('#future button, #future input').forEach(e => e.disabled = false); }
  }
  document.querySelector('#research-form').addEventListener('submit', e => {e.preventDefault(); run();});
  document.querySelector('#research-chat').addEventListener('submit', e => {e.preventDefault(); run(document.querySelector('#research-question').value);});
  availability();
})();
