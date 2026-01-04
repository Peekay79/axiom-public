import os
import logging

log = logging.getLogger(__name__)

# Env precedence: new first, then legacy fallbacks
# AXIOM_EMBEDDING_MODEL is preferred; legacy vars are accepted with a warning
_MODEL = (
    os.getenv("AXIOM_EMBEDDING_MODEL")
    or os.getenv("EMBEDDING_MODEL")
    or os.getenv("PROPAGATION_EMBED_MODEL")
    or "all-MiniLM-L6-v2"
)

# Normalize to the short form if someone passes "sentence-transformers/all-MiniLM-L6-v2"
if _MODEL.startswith("sentence-transformers/"):
    log.warning("[EMBEDDING] Normalizing model name from %s to %s", _MODEL, _MODEL.split("/", 1)[1])
    _MODEL = _MODEL.split("/", 1)[1]

# Known dims for common models (extendable; default 384 to match MiniLM-L6-v2)
_KNOWN_DIMS = {
    "all-MiniLM-L6-v2": 384,
}
_DIM = int(os.getenv("AXIOM_EMBEDDING_DIM", _KNOWN_DIMS.get(_MODEL, 384)))

_NORMALIZE = (os.getenv("AXIOM_EMBEDDING_NORMALIZE") or "true").lower() in ("1", "true", "yes")

# Warn if legacy envs are driving the choice
if not os.getenv("AXIOM_EMBEDDING_MODEL"):
    if os.getenv("EMBEDDING_MODEL") or os.getenv("PROPAGATION_EMBED_MODEL"):
        log.warning("[EMBEDDING] Using legacy env var (EMBEDDING_MODEL / PROPAGATION_EMBED_MODEL). Prefer AXIOM_EMBEDDING_MODEL for consistency.")


def embedding_model_name() -> str:
    return _MODEL


def embedding_dim() -> int:
    return _DIM


def embedding_normalize() -> bool:
    return _NORMALIZE


def log_embedding_banner(component: str) -> None:
    log.info("[EMBEDDING] %s → model=%s dim=%s normalize=%s", component, _MODEL, _DIM, _NORMALIZE)

