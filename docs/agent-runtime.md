# Agent Runtime Steering

## Current State

The public web app uses `/agent` as the stable product boundary. The browser sends chat messages, selected agent type, and research depth. The backend owns authentication, feedback capture, cost/routing controls, runtime selection, and response normalization.

The MCP endpoint remains private. Do not expose `/mcp` or an OpenCode server directly to public users.

PR #7 refactors the server-side agent layer so the backend can use different runtimes without changing the browser contract.

## Runtime Modes

`KOMMUNALPOLITIK_AGENT_RUNTIME=tool-loop` is the default LLM-backed runtime. The Python backend asks the configured provider for one allowed tool decision at a time, executes only local allowlisted tools, and returns the final answer.

`KOMMUNALPOLITIK_AGENT_RUNTIME=deterministic` disables LLM tool-loop behavior and uses deterministic retrieval for local debugging and tests. When `KOMMUNALPOLITIK_LLM_PROVIDER=none`, deterministic retrieval is always used.

`KOMMUNALPOLITIK_AGENT_RUNTIME=opencode` delegates agent reasoning to OpenCode behind the same `/agent` API. OpenCode is invoked server-side; the browser never receives provider keys and never talks to OpenCode or MCP directly.

## OpenCode Runtime Findings

OpenCode `run --format json` returns newline-delimited JSON events. Final text can appear as `part.text` inside events with `type: "text"`. The adapter must parse those events instead of expecting a single JSON response object.

Do not pass the app's internal `general`, `research`, `briefing`, `drafting`, or `scrutiny` names directly as OpenCode agents unless a matching OpenCode primary agent is explicitly configured. In the local OpenCode setup, `general` is a subagent, so the adapter omits `--agent` by default and lets OpenCode use its default primary agent.

Plain `opencode run` can be slow because each request can pay process/session startup overhead. For lower latency, run a private OpenCode server on loopback and configure:

```env
KOMMUNALPOLITIK_OPENCODE_ATTACH=http://127.0.0.1:PORT
```

This still keeps OpenCode private behind the backend boundary.

## Source And Reference Handling

The custom tool-loop returns structured `sources` and `related_sources`. The frontend can link inline citations like `[1]` to source boxes.

OpenCode currently returns answer text but not normalized structured source objects through the adapter. Until we extract tool traces or structured output from OpenCode, the frontend uses a fallback: if an answer ends with a `## Quellen`, `## Sources`, `## Referenzen`, or `## References` section containing lines like `[1] Title https://example.invalid`, it converts that section into source boxes and links inline `[1]` citations to those boxes.

Preferred near-term prompt contract for OpenCode answers:

```md
## Antwort
<answer text with inline citations like [1]>

## Quellen
[1] <source title or description> <source URL if available>
[2] <source title or description> <source URL if available>
```

Longer term, the adapter should return structured sources from OpenCode tool events/session export instead of relying on text parsing.

## Safety Boundaries

The backend remains the only public app boundary for the pilot. It must continue to own:

- application authentication
- session cookie handling
- request validation
- feedback persistence
- runtime selection
- source/answer normalization
- operational logging that avoids full prompts, answers, credentials, private hostnames, and private paths

Before using OpenCode for a public pilot, run it in a constrained environment with a reviewed agent/tool configuration. The current adapter is suitable for local spike and PR review, but not enough by itself as a public safety boundary.

OpenCode deployment requirements before public use:

- loopback/private-only OpenCode server if `serve` is used
- no public exposure of OpenCode or MCP
- restricted file-system and shell/tool permissions
- no write/deploy/server-control permissions for public user prompts
- private runtime configuration kept out of the repository
- request timeouts and backend logs enabled

## Known Limitations

- OpenCode runtime source extraction is text-based fallback only.
- `opencode run` can be slow without `KOMMUNALPOLITIK_OPENCODE_ATTACH`.
- The OpenCode adapter does not yet capture a complete tool trace for feedback.
- OpenCode output formatting depends on prompt compliance until structured output is implemented.
- Public deployment still needs sandbox and permission review.

## Next Steps

1. Tighten the OpenCode prompt so every answer uses a consistent `## Antwort` and `## Quellen` format.
2. Evaluate `opencode serve` plus `--attach` latency and reliability locally.
3. Extract structured sources and trace data from OpenCode events or session export.
4. Define a dedicated OpenCode primary agent for kommunalpolitik work with restricted permissions.
5. Keep `/agent` as the public boundary and keep `/mcp` private or disabled in public pilot runtimes.
