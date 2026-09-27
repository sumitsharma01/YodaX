# Future Market

Future Market is a local commodity research demo. Enter a commodity to investigate the past week, open the evidence branches, and ask follow-up questions.

## Setup

Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/api-keys) in a project without billing enabled. Save it in the ignored `.env` file:

If the file does not exist, copy `.env.example` to `.env` first. Do not overwrite an existing configuration or commit your key.

```dotenv
GEMINI_API_KEY=your_key
```

Restart the web server after installing this feature. Keys remain on the Python server and are never sent to the browser.

## How research works

The server retrieves recent Google News RSS headlines about production, trade and demand. Gemini analyses those supplied headlines; it does not read the full articles. A second search follows an unresolved question from the first pass and investigates competing explanations and next-week scenarios. Follow-up questions use the saved report and another news-feed query. Expand the report branches to see the text and numbered news-feed sources.

Each investigation uses at most two generation requests; each question uses one. Reports are cached by commodity and UTC date. A persistent local allowance caps requests at 12 per UTC day, including failures. Only one investigation runs at a time. Quota failures stop without retrying or switching providers.

## Free-tier setup

The integration uses `gemini-3.8-flash` text generation, which has a documented free tier. It does not enable Google's paid search-grounding tool. News comes from public RSS feeds instead. An earlier verification found Gemini 2.5 Flash unavailable to new users, so that model is not used.

The application cannot verify a project's billing configuration from its API key. Keep billing disabled in your Google project. Local request caps do not override Google's quotas or guarantee zero charges in a billing-enabled project. Free-tier inputs may be used by Google to improve its products; avoid entering private information.

See [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) and [search grounding](https://ai.google.dev/gemini-api/docs/generate-content/google-search).

## What this demo does not establish

Economic scenarios are qualitative, experimental research. They do not change TimesFM forecasts or supply validated commodity price targets. TimesFM takes numerical history, not news articles. A future research-to-forecast layer needs dated numerical features and prospective evaluation before its performance can be claimed.

The agent is instructed to distinguish reporting periods, missing data, correlations and causal hypotheses. Source links are evidence for review, not proof that every generated claim is correct. The expandable source tree is a simple evidence map, not a learned causal graph.

This endpoint is restricted to localhost. Add authentication, per-user quotas and a job queue before public deployment. No automated commodity research schedule is enabled.

## Verification and troubleshooting

Basic Gemini text generation succeeded during the September 28, 2026 check. Full research requests returned Google's temporary high-demand error, so a complete live investigation has not yet been verified. Automated tests cover the persistent request limit, invalid responses and citations, absence of paid search tools, and quota handling; they do not establish the quality of generated research.

- **Gemini is busy:** try again later. The application does not retry automatically.
- **Daily allowance used:** the local allowance resets at midnight UTC. Failed generation attempts count toward it.
- **News feed unavailable:** no report is published without source headlines.
- **Key not configured:** check `GEMINI_API_KEY` in the repository's `.env` file. Never paste it into a bug report.

Research runs synchronously in this local demo; keep the page open until it finishes. Completed reports are cached, but an interrupted investigation cannot resume midway.
