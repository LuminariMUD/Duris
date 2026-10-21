# PostHog AI Observability report

## Result

No LLM calls were instrumented because this repository does not contain an LLM provider SDK, agent framework, or model-generation call site.

The project is a C++20 game server with Python operational scripts and a static Node-based site build. The reviewed manifests and source paths did not reveal a supported LLM dependency or a call path for OpenAI, Anthropic, Gemini, or another model provider. The only Node manifest is for static-site dependencies and has no LLM SDK.

## Workflow followed

- Selected the `ai-observability-manual-capture` workflow because no vendor LLM SDK is declared.
- Reviewed the server, scripts, and site source for LLM SDK references and generation calls.
- Did not add a PostHog SDK, configuration, or capture helper: without a real model-call path, those additions would be unused and would not instrument AI activity.
- Did not modify existing PostHog initialization, identity, event capture, or dashboards.

## Verification

There is no runnable model-generation path to trigger, so delivery is **not yet verified**. No build was run because no application source or dependency manifest was changed.

When an LLM integration is added, instrument the function that accepts one turn and returns one model response. Use one `$ai_session_id` per conversation, one `$ai_trace_id` per turn, and capture each model request as `$ai_generation`. If the integration executes tools, record each tool execution as an `$ai_span` sharing that turn's trace ID. Then trigger two turns in the same conversation and check the newest trace in **AI Observability → Traces** for the expected session and trace grouping.

## Privacy mode

No AI Observability client or manual AI capture exists in this project, so there is no effective privacy-mode setting or code location to change yet.

When an SDK-based integration is added, leave privacy mode off only when capturing prompt and completion content is appropriate; enable the SDK-wide privacy setting before capturing sensitive prompt or response content. Privacy mode excludes SDK-captured `$ai_input` and `$ai_output_choices`; it does not automatically remove arbitrary custom properties, manually captured payloads, or events already stored. For explicit manual capture, omit sensitive prompt and response fields before sending the event.

See [AI Observability privacy mode](https://posthog.com/docs/ai-observability/privacy-mode) for the supported controls.

## Next step

After the application has a concrete LLM provider or agent framework and a generation call site, rerun this setup so the matching provider/framework workflow can install the appropriate integration and attach capture at the real call boundary.
