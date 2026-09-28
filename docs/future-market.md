# Future Market

Future Market is a conversational commodity research assistant. Ask about oil, copper, iron ore or another commodity, then explore the evidence map beside the answer. Follow-up questions use the last four completed exchanges. Each answer keeps its own map, so earlier conclusions remain inspectable.

## Setup

Create a key in [Google AI Studio](https://aistudio.google.com/api-keys) using a project without billing enabled. Copy `.env.example` to `.env` if it does not already exist and set:

```dotenv
GEMINI_API_KEY=your_key
```

Start the server using the README command and open **Future Market**. The key stays on the Python server. Never include it in screenshots or bug reports.

## From question to evidence map

1. The server retrieves up to eight recent Google News RSS headlines for the commodity.
2. Gemini receives compact headline titles, dates and publishers, plus recent conversation context. Article URLs stay outside the model prompt.
3. Gemini can propose a focused follow-up query. The server retrieves those headlines and asks it to synthesize an answer from the expanded evidence.
4. The server checks citations, graph node references and connections before publishing the result.

The map links **headline evidence → proposed economic mechanisms → a conditional outlook**, with risks and counterarguments where identified. Click a node to read its explanation, open its sources or follow a connection. Zoom controls help explore larger maps. The graph is a public explanation of evidence and assumptions, not a transcript of the model's internal reasoning.

The chat retains earlier messages and maps. Refreshing restores the current conversation, including progress on an active request. **New conversation** starts a separate topic; it does not delete the previous conversation from the local database. The browser remembers only the current conversation ID.

## Free-tier controls

The integration uses `gemini-3.1-flash-lite` text generation, whose documented free tier does not require paid search grounding. Public RSS feeds supply the headlines. No paid tools or model fallback are enabled.

There is a persistent local cap of **40 generation attempts per UTC day**. A turn normally uses one or two calls. Temporary server errors receive one retry per call, so a turn can use up to four attempts. Failed attempts count toward the cap. Google quota errors are not retried. Keep billing disabled: the application cannot determine a project's billing status from its API key, and local caps do not guarantee free usage on a billing-enabled project.

Free-tier inputs may be used by Google to improve its products. Do not put confidential information in the chat. See [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) and the [model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite).

## Limits

The research currently reads **headlines, not full articles or production datasets**. Publication dates are available; the underlying event date or reporting period may not be. Source links let the reader check the original coverage. Validation checks references and graph structure, not the truth of every model claim.

Outlooks are qualitative and conditional. They are not validated commodity price predictions, numerical causal estimates or measured correlations. Research does not yet modify TimesFM stock forecasts. That connection needs dated numerical features and prospective evaluation.

Only one local research turn runs at a time. Work runs in a background thread and is recorded in SQLite. A server restart marks unfinished turns as interrupted so they can be retried; it does not resume model execution midway. If follow-up synthesis fails after a valid initial answer, the initial answer is shown with a clear limitation instead of being discarded.

This is a local demo. Public deployment needs authentication, per-user quotas and a durable job queue. It does not automatically schedule commodity investigations.

## Troubleshooting

- **Google is busy:** the server retries once; after that, use the message's Retry button later.
- **Quota reached:** Google's free allowance or the local daily cap has been reached. Local usage resets at midnight UTC.
- **News feed unavailable:** the question remains in the conversation so it can be retried.
- **Invalid evidence links:** the answer was withheld because its citations or graph did not pass validation.
- **Server restarted:** previous completed messages remain available; retry the interrupted message.

A live oil conversation and contextual follow-up were verified on September 28, 2026, including a second research query, 16 source headlines and a linked evidence map. Reloading restored the saved conversation.

Tests cover retry bounds, quotas, citation and graph validation, conversation context, interrupted-turn recovery and origin checks. They do not prove forecasting performance.
