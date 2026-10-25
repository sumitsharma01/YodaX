# Research chat and numerical forecasts

The chat now receives a server-generated coverage description and saved model outputs before Gemini answers. It can explain those outputs, investigate headlines and answer follow-ups. It must identify the forecast's original cutoff, horizon and target rather than treating it as a live quote.

## Data flow

1. Match known stocks and commodity aliases in the question. Pronoun follow-ups can inherit the previous question's asset; an unrelated question does not.
2. Load the browser owner's saved numerical requests and bounded experimental model evidence. Private request histories are never shared across owners. Shadow forecast values are available through chat; administrator logs and controls remain private.
3. Gemini researches headlines and returns a cited answer, evidence map and optional typed forecast request.
4. Validate the symbol and 1–60-session horizon on the server. Save the research sources, collection timestamp and query alongside the request.
5. The separate worker fetches prices directly from the provider. Five-session requests in the configured 23-asset beta universe attach the current frozen global-event output; missing current event outputs leave the request queued. Other supported requests use TimesFM. There is no silent fallback from the event candidate.
6. Save the numerical output, model route and provenance. Score it when its target close becomes available. Follow-up chat can retrieve the saved result; the Predictions requested in chat section also shows it.

## Coverage

All 20 configured research stocks and the existing dashboard stocks are in the chat's coverage context. Additional unambiguous US stock tickers are accepted and checked against provider instrument/exchange metadata by the worker. Historical price and session validation still apply.

WTI oil (`CL=F`) and copper (`HG=F`) use continuous futures **price proxies**, in USD/barrel and USD/pound respectively. Their horizons use a US equity-session sampling grid for consistency with the existing market context. The worker separately waits for the futures calendar close plus a one-hour buffer. It permits issuance during the next unfinished futures session and stops an hour before the next reference-session close. These are not official exchange settlements, physical demand estimates or roll-adjusted investment returns. Negative/nonfinite prices and incomplete contexts are rejected rather than imputed into a forecast.

Brent, silicon, lithium, steel and forex remain available for conversation and sourced research. Numerical forecasts remain unavailable where benchmark data or a calendar contract has not been validated. A mining stock is not silently substituted for a metal. Ambiguous oil requests must clarify the benchmark.

## The boundary that matters

Newly researched headlines are **not yet numeric model features**. The chat stores them as research context, and the broader frozen event model consumes structured GDELT global event statistics through the same feature builder used in training. The original two-company model separately uses dated country exposure features. Passing arbitrary Gemini-extracted numbers into a model trained on different features would be invalid.

The broader global-event candidate covers the 20 research stocks, Tesla, WTI and copper at five sessions. The original AAPL/FCX country-linked model remains a separate frozen experiment. Other supported horizons and additional equities use a clearly labelled price-only TimesFM route. See [the beta study](global-event-beta.md) for the actual training coverage, historical errors and limitations. No-change had lower pooled historical error than the broader candidate, so this is experimental coverage, not production approval.

The interface displays saved numerical outputs separately from conversational explanations. It never fabricates an uncertainty interval for the residual model. The TimesFM ranges are uncalibrated model outputs. Research sources and a source-linked graph explain the evidence, not proven causes of a forecast.

## Operations

The public daily job handles baseline requests. After the shadow worker finishes, the workflow runs the request worker again so eligible event-model requests can attach that session's output. No inference runs inside the web process. A newly queued request is not an immediate prediction; collection and model failures can defer it. Request outcomes remain owner-scoped.
