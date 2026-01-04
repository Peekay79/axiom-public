Axiom — Getting Started & Running the System

Axiom is a research-grade cognitive architecture designed to support persistent identity, structured memory, belief tracking, and autonomous reasoning across time.

This guide explains how to:

run Axiom locally

start the core pods

configure memory + vector recall

verify the system is working

If you get stuck, open an issue — or email
kurtbannister79@gmail.com
 with subject line AXIOM LICENSING.

1️⃣ System Overview

Axiom runs as a small distributed system with three cooperating components:

Component	Purpose
LLM Pod	Model inference + interaction layer
Memory Pod	Episodic + semantic memory + journaling API
Vector Backend (Qdrant)	Optional semantic recall

The system is designed to:

run in fallback JSON memory mode (no vector DB)

or switch to Qdrant-backed semantic recall when available

Both paths are fully supported.

2️⃣ Quick Start — Local Dev (No Vector Required)

This is the fastest way to get Axiom running.

git clone https://github.com/Peekay79/axiom-public.git
cd axiom-public

python3 -m venv venv
source venv/bin/activate

pip install -e .[dev]


Run smoke tests:

make smoke


Run the memory pod:

python -m pods.memory.pod2_memory_api


Check health:

curl http://localhost:5000/health


You now have:

persistent fallback memory

journaling

belief storage

recall pipeline running locally

No external services needed 👍

3️⃣ Enable Semantic Recall (Qdrant)

Start Qdrant locally:

docker compose -f docker-compose.qdrant.yml up -d


Then configure Axiom:

cp configs/.env.example .env
$EDITOR .env


Minimum recommended values:

USE_QDRANT_BACKEND=true
QDRANT_URL=http://127.0.0.1:6333
VECTOR_PATH=qdrant


Restart the Memory Pod:

python -m pods.memory.pod2_memory_api


Verify collections:

curl $QDRANT_URL/collections

4️⃣ Recommended Workflow

Install tooling:

make install
make hooks


Validate schema:

make schema


Run tests:

make test


Replay retrieval diagnostics (optional):

python retrieval/test_replay.py --verbose

5️⃣ Common Configuration Flags

Environment variables are documented in:

configs/.env.example

comments in pods/memory/pod2_memory_api.py

docs under /docs

Key toggles:

Flag	Meaning
USE_QDRANT_BACKEND	Enable vector recall
VECTOR_PATH	qdrant or adapter
RERANK_ENABLED	Enable cross-encoder reranking
JOURNAL_VECTOR_ENABLED	Vectorize journal entries
AXIOM_EMBEDDING_URL	Remote embedder endpoint
AX_VECTOR_SYNC	Strict vector sync mode

All features are fail-closed — Axiom continues to run even if
individual subsystems are unavailable.

6️⃣ Troubleshooting

No space / package install failures

ensure you’re inside the venv

upgrade pip:

pip install -U pip


Vector recall connection refused

Qdrant isn’t running

or URL mismatch in .env

Check with:

docker ps
curl $QDRANT_URL/health


Embeddings fail to load

Set a remote embedder:

AXIOM_EMBEDDING_URL=http://host:port


Axiom falls back automatically.

Cross-encoder timeout

Disable reranking:

RERANK_ENABLED=false

7️⃣ Safety & Research Intent

Axiom is a cognitive research system.

It simulates:

identity continuity

belief modeling

memory persistence

contradiction handling

It does not claim:

sentience

volition

subjective experience

See full philosophy + license in:

LICENSE

COMMERCIAL_LICENSE_OVERVIEW.md

If you use or extend Axiom — please consider submitting improvements via PR or issues. Contributions that improve robustness, safety, or research value are especially welcome.

💬 Contact

Commercial licensing & research partnership enquiries:

📧 kurtbannister79@gmail.com

Please include subject line → AXIOM LICENSING
