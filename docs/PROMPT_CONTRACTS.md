### Prompt Contracts

Prompt Contracts harden stateful tool paths by enforcing:

- Deterministic decoding for stateful tools (temperature=0.0, top_p=1.0)
- JSON‑only envelopes validated against versioned schemas
- Governor idempotency and correlation headers injected at the LLM caller

This feature is additive, environment‑gated, and fail‑closed.

### Enablement

Set the following environment variables (defaults shown):

- `PROMPT_CONTRACTS_ENABLED=true`
- `STATEFUL_TOOLS=["write_memory","update_belief","append_journal"]`

When `CONTRACTS_V2_ENABLED=true`, stateful tool payloads are tagged with `schema_version:"v2"` at egress. Pod edges validate these under Contracts v2 (strict/soft per env). Legacy tools and non-stateful payloads remain tagged as `v1`.
- `DETERMINISTIC_TEMP=0.0`
- `DETERMINISTIC_TOP_P=1.0`

When enabled and a tool is stateful, decoding is forced deterministic and the LLM output must be strict JSON per the tool schema. Idempotency and correlation headers are attached using Governor middleware.

### Deterministic Decode Policy

- `temperature` pinned to `DETERMINISTIC_TEMP`
- `top_p` pinned to `DETERMINISTIC_TOP_P`
- Multi‑sample gimmicks disabled (`n=1`; `beam_width`, `best_of`, `top_k` dropped)

This ensures replay safety and avoids drift in stateful writes.

### Schemas (v1)

Schemas live under `llm_contracts/schemas/v1/` and use `additionalProperties:false` to prevent schema creep under STRICT modes. Minimal provided schemas:

- `write_memory.json`: `{text, tags[], metadata?}`
- `update_belief.json`: `{belief_id, update:{confidence?, provenance?[]}}`
- `append_journal.json`: `{entry, context?}`

If `jsonschema` is unavailable, validation is skipped but a Cockpit signal is emitted (fail‑closed acceptance).

### Cockpit / Governor Integration

Violations emit signals best‑effort:

- `prompt_contracts.violation.invalid_json`
- `prompt_contracts.violation.schema`
- `prompt_contracts.violation.unknown_tool`

The Cockpit aggregator exposes a `prompt_contracts` section:

```
{
  "prompt_contracts": {
    "violations_last_5m": {"invalid_json": N, "schema": M, "unknown_tool": K},
    "violations_total": N+M+K
  }
}
```

Exported gauges (optional):

- `cockpit.prompt_contracts.violations_total`
- `cockpit.prompt_contracts.invalid_json_5m`
- `cockpit.prompt_contracts.schema_5m`
- `cockpit.prompt_contracts.unknown_tool_5m`

### Evolving Schemas

Schemas are versioned (`v1`, `v2`, …). STRICT modes in Governor continue to validate edge payloads; Prompt Contracts adds earlier validation and normalization on the LLM side.

### Troubleshooting

- Model outputs extra text → invalid_json. Update the prompt to instruct: “Output JSON only, no prose.”
- Unknown tool warning → add the tool name to `STATEFUL_TOOLS` or correct the tool call.
- Validation errors without `jsonschema` installed → install `jsonschema` or rely on downstream Governor validation; Cockpit will show a soft violation record.

