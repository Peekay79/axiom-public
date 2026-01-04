Contracts v2 – Versioned Stateful Payloads
==========================================

Overview
--------
Contracts v2 adds strict, versioned schemas for stateful payloads and a validator that can run in soft or strict mode. It prevents silent drift across pods by tagging payloads with `schema_version: "v2"` and validating fields for journal entries, memory writes, and belief updates.

Env Flags (safe defaults)
-------------------------
- CONTRACTS_V2_ENABLED: true | Enable Contracts v2 tagging and validation
- CONTRACTS_REJECT_UNKNOWN: true | If version is not "v2", return 400 at pod edges (fail-closed)

Schemas (v2)
------------
- contracts/v2/schemas/journal_entry.json
- contracts/v2/schemas/memory_write.json
- contracts/v2/schemas/belief_update.json

Behavior
--------
- When enabled, stateful tool payloads and pod-edge writes must include `schema_version: "v2"` and validate against the relevant schema.
- If `jsonschema` is missing, validation soft-accepts but emits a Cockpit violation.
- In soft mode (`CONTRACTS_REJECT_UNKNOWN=false`), unknown versions are accepted but a Cockpit violation is emitted.

Cockpit Signals & Gauges
------------------------
- Signals: `contracts_v2.violation.<kind>.json`, `contracts_v2.version_seen.json`
- Aggregated in Cockpit status under `contracts_v2` with:
  - violations_5m: recent violations by kind (journal, memory, belief)
  - version_mix: proportion of v2 vs v1 observed
- Exported metrics:
  - cockpit.contracts_v2.violations_5m.journal
  - cockpit.contracts_v2.violations_5m.memory
  - cockpit.contracts_v2.violations_5m.belief
  - cockpit.contracts_v2.version_mix.v2
  - cockpit.contracts_v2.version_mix.v1

Strict vs Soft
--------------
- Strict (default): reject non-v2 with HTTP 400 `schema_version_invalid`
- Soft: accept unknowns; emit Cockpit violation so you can migrate clients incrementally

Integration Points
------------------
- LLM → tools: stateful tools tag `schema_version: "v2"` when enabled
- Memory API `/memory/add`: validate journal (JSON mode) and memory_write (file mode)
- Belief API `PATCH /beliefs/{id}`: validate belief_update

Smoke Tests
-----------
- With `CONTRACTS_REJECT_UNKNOWN=true`, send v1 payload → 400
- With `CONTRACTS_REJECT_UNKNOWN=false`, the same payload is accepted and a Cockpit violation is logged

