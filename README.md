## Axiom (public-safe build)

This directory (`axiom-public/`) is a **copy-and-sanitize** public distribution of the private Axiom repo. It is intended for **local development and demos** only.

## License & Use

Axiom is **source-available** and free to use for **personal, academic, and research** work.

It is licensed under the **PolyForm Noncommercial License 1.0.0**, with an explicit path
to commercial licensing for aligned partners.

You may, under the default license:

- ✅ Run and modify Axiom for personal projects, learning, and experimentation  
- ✅ Use Axiom in academic and research settings  
- ✅ Use it internally for non-revenue-generating prototypes and exploration  
- ✅ Share improvements and forks under the same non-commercial terms  

You may **not**, under the default license:

- ❌ Sell Axiom or Axiom-derived systems as a paid product or service  
- ❌ Embed Axiom in a commercial SaaS or platform  
- ❌ Use Axiom in revenue-generating business operations  
- ❌ Wrap Axiom in a closed, monetised offering without a separate license  

### Commercial Use & Partnerships

Axiom **is** intended to be used in the real world — just not as free
fuel for opaque, fully-commercial products.

If you’d like to:

- run Axiom in production,
- embed it into a paid product or platform,
- or build a commercial service on top of Axiom,

we’re open to **commercial and partnership licensing** (including revenue-share
and co-development arrangements).

📩 To discuss commercial use, reach out via:
`kurtbannister79@gmail.com`  
Please include **"AXIOM LICENSING"** in the email subject line so it doesn’t get lost.

### Ethical Use

Axiom is not licensed for systems whose primary purpose is:

- physical harm,
- mass surveillance or repression, or
- violation of fundamental human rights.

See [LICENSE](./LICENSE) for full terms.

### Quick start (local-only)

- **Install**:
  - `python -m venv .venv && . .venv/bin/activate`
  - `pip install -r services/memory/requirements.txt`
- **Run the Memory API (dev)**:
  - `PYTHONPATH=. MEMORY_POD_URL=http://localhost:8002 python -m pods.memory.pod2_memory_api`

### Configuration

- **Environment templates** live in `configs/`.
- **Do not commit secrets**. Copy `configs/.env.example` to `.env` locally and edit as needed.

### Example data

- **World map example**: `examples/world_map.example.json`
  - Example data only — replace with your own private configuration.

### Layout

- **Core library**: `src/axiom/`
- **Services**: `services/` (memory/vector/cockpit)
- **Docs**: `docs/`
- **Scripts**: `scripts/`
- **Tests**: `tests/`

