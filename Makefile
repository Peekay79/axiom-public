# Axiom Public — Development Makefile
# ====================================

.PHONY: install test-core test-all smoke lint clean

# Create a virtual environment and install the package in editable mode with dev extras.
install:
	python -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"

# Run the known-passing pure unit tests (no network, no Docker, no Qdrant required).
test-core:
	PYTHONPATH=src/axiom:$$PYTHONPATH pytest -q \
		tests/test_boot.py \
		tests/test_champ_engine.py \
		tests/test_cockpit_contracts.py \
		tests/test_beliefs.py \
		tests/test_belief_engine.py \
		tests/test_compaction.py \
		tests/test_context_allocator.py \
		tests/test_contradiction_applier.py \
		tests/test_contradictions.py \
		tests/test_idempotency.py \
		tests/test_memory_debug_empty_state.py \
		tests/test_memory_debug_factors.py \
		tests/test_memory_manager_defensive.py \
		tests/test_metacognition.py \
		tests/test_narrative_layer.py \
		tests/test_observer.py \
		tests/test_outbox.py \
		tests/test_quarantine.py \
		tests/test_resilience.py \
		tests/test_scoring.py \
		tests/test_scoring_beliefs.py \
		tests/test_stub_guard.py

# Run the entire test suite (may fail without Qdrant / Docker / network access).
test-all:
	pytest tests/

# Run the demo application.
smoke:
	./apps/run_demo.sh

# Basic syntax check on key source files (placeholder for a full linter).
lint:
	python -m py_compile src/axiom/config/axiom_config.py
	python -m py_compile src/axiom/memory/memory_manager.py
	python -m py_compile services/memory/pod2_memory_api.py

# Remove generated / cached artifacts.
clean:
	rm -rf .venv __pycache__ .pytest_cache
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -type d -exec rm -rf {} +
