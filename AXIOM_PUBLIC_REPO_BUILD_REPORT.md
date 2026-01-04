## AXIOM public tree build report (sanitized copy)

This report documents how `axiom-public/` was created **without modifying the original repo content**. It follows the authoritative audit decisions in the existing root-level `AXIOM_PUBLIC_REPO_BUILD_REPORT.md` (treated as canonical).

### What was created

- **Public-safe tree root**: `axiom-public/`
- **Core mapping (per audit)**:
  - `axiom-public/src/axiom/`: merged core packages (`axiom/`, `memory/`, `belief_graph/`, `beliefs/`, `governor/`, `retrieval/`, `vector/`, `utils/`, `infra/`, `observability/`, `tracing/`, `liveness/`, `lifecycle/`, `contracts/`, `llm_contracts/`, `config/`, `schemas/`, `context_allocator/`, `moderation/`, `resilience/`)
  - `axiom-public/services/`: service implementations copied from `pods/*` (`services/memory`, `services/vector`, `services/cockpit`)
  - `axiom-public/configs/`: `.env` templates copied from `.env.template`, `.env.example`, `.env.discord.example`, `.env.presets/`
  - `axiom-public/docs/`, `axiom-public/scripts/`, `axiom-public/tests/`: copied from `docs/`, `scripts/`, `tests/`

### Files rewritten / redacted (public copy only)

- **Hard-coded endpoints replaced with local-safe defaults**
  - `src/axiom/memory/belief_reflection.py`: default URLs → `http://localhost:*` and logs dir → `./logs`
  - `src/axiom/utils/url_utils.py`: removed production IP examples/asserts
  - `scripts/rag_smoke.py`: default URL → localhost; probes and meta patterns rewritten to generic examples
  - `tests/test_qdrant_resolution.py`: replaced hard-coded public IPs with `http://example.com:6333`
  - `configs/.env.example`: removed token-like placeholder (`sk-...`) and removed real IP from examples

- **World-map / entity strings sanitized**
  - Replaced references to a previously flagged entity name/id with fictional placeholders (**ExamplePerson/example_person**) across a small set of public files (docs/tests/code) to avoid exposing real-world-map entities.

- **Compose + Docker build paths fixed for the public layout**
  - `docker-compose-debug.yml`, `docker-compose.override.yml`, `docker-compose.qdrant.yml`
  - `services/memory/Dockerfile`, `services/vector/Dockerfile`

- **Public-facing root files added (public tree only)**
  - `README.md`, `.gitignore`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`
  - Example artifacts: `examples/world_map.example.json`, `examples/seed_world_model.py`

### Intentionally excluded (per audit)

Not copied into `axiom-public/`:

- **Secrets / credentials**: `.env.backup`
- **PII source**: `world_map.json`
- **Runtime/user data**: `logs/`, `simulation_logs/`, `journal/`, `journals/`, `cognitive/logs/`, `demo_output/`, `data/`, `stevebot/**`
- **Runtime artifacts**: `axiom_boot/*.ready`, `axiom_boot/*.start`
- **Operational / infra-specific**: `ops/`, `runbootstrap/`, `start.sh` (and similar RunPod-/mnt-data-specific launch scaffolding)
- **Derived/binary artifacts**: `BigGuy/vectors.faiss`, `installed_packages.txt`, vendored installer scripts under `persist/`

### Light safety scan results (public tree only)

Scanned `axiom-public/` for:

- **Known production IPs** from the audit: **no matches**
- **Token-like prefixes** (`hf_`, `sk-`, `AKIA`, Slack tokens, private keys): **no matches**
- **Previously flagged entity strings**: **no matches**

### TODOs / manual review

- **Docs pass**: review `axiom-public/docs/` for any remaining overly-operational guidance you don’t want in a public repo (even if it contains no secrets).
- **Packaging**: consider adding a minimal `pyproject.toml` and CI lint/test workflow in the public repo if you plan to publish from `axiom-public/`.
- **Root report name conflict**: this build report was written under `axiom-public/` to avoid overwriting the root-level audit file.

### Final `axiom-public/` tree (depth 3)

```text
axiom-public/
├── configs/
├── docs/
│   ├── audit/
│   │   ├── Axiom_Deep_Audit_2025-08-15.md
│   │   └── next_steps_2025-08-15.md
│   ├── BELIEF_GOVERNANCE.md
│   ├── CHAOS_AND_CI.md
│   ├── CONTEXT_BUDGETS.md
│   ├── CONTRACTS_V2.md
│   ├── DATA_LIFECYCLE.md
│   ├── DEDUPE.md
│   ├── EMBEDDER_REGISTRY.md
│   ├── EVENT_SOURCING.md
│   ├── GOVERNOR_OVERVIEW.md
│   ├── HYBRID_RETRIEVAL.md
│   ├── INGEST_WORLD_MAP.md
│   ├── OUTBOX_PLAYBOOK.md
│   ├── PROMPT_CONTRACTS.md
│   ├── QUARANTINE.md
│   ├── REEMBED_PLAYBOOK.md
│   ├── RESILIENCE_PLAYBOOK.md
│   ├── SCHEMA.md
│   ├── VECTOR_SYNC.md
│   ├── audit_report.md
│   ├── axiom_architecture_map.md
│   ├── belief_confidence_engine.md
│   ├── belief_engine.md
│   ├── belief_influence_mapper.md
│   ├── belief_pressure_mapper.md
│   ├── belief_propagation_engine.md
│   ├── belief_registry.md
│   ├── belief_resolution_engine.md
│   ├── cognitive_audits.md
│   ├── composite_scoring_for_axiom.md
│   ├── contradiction_explainer.md
│   ├── contradiction_pipeline_phase2.md
│   ├── contradiction_resolution.md
│   ├── contradiction_resolver.md
│   ├── goal_drive_engine.md
│   ├── journaling_enhancer.md
│   ├── neo4j_strand_memory.md
│   ├── nli_conflict_checker.md
│   ├── planning_memory.md
│   ├── safe_autofractor_guide.md
│   ├── self_modeling_engine.md
│   ├── strand_memory_developer_guide.md
│   ├── theory_of_mind.md
│   ├── value_inference_engine.md
│   ├── world_map.schema.json
│   └── world_model_visualizer.md
├── examples/
│   ├── seed_world_model.py
│   └── world_map.example.json
├── pods/
│   └── __init__.py
├── scripts/
├── services/
├── src/
│   └── axiom/
├── tests/
├── AXIOM_PUBLIC_REPO_BUILD_REPORT.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── SECURITY.md
├── docker-compose-debug.yml
├── docker-compose.override.example.yml
├── docker-compose.override.yml
└── docker-compose.qdrant.yml
```

