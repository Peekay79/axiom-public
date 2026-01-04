from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, Tuple, Dict, List, Optional

from utils.url_utils import (
    debug_assert_url_normalization,
    join_host_port,
    mask_url_userinfo,
    normalize_base_url,
)
from config.llm_config import (
    decide_llm_mode_from_capabilities,
    fetch_openai_models,
    parse_openai_models_capabilities,
    resolve_llm_mode,
)


def _strip_inline_comment(value: str) -> str:
    """
    Best-effort: strip inline comments for unquoted values.
    Examples:
      FOO=bar # comment  -> "bar"
      FOO="bar # ok"     -> "bar # ok"
    """
    v = value.strip()
    if not v:
        return v
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    # Unquoted: treat " #" as comment start. Keep it conservative.
    if " #" in v:
        v = v.split(" #", 1)[0].strip()
    return v


def _parse_env_lines(lines: Iterable[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        key = k.strip()
        if not key:
            continue
        val = _strip_inline_comment(v)
        out[key] = val
    return out


def _load_env_via_dotenv(env_path: Path) -> Optional[Dict[str, str]]:
    """
    If python-dotenv is installed, use it to parse the file.
    Returns dict on success, or None if python-dotenv is unavailable.
    """
    try:
        from dotenv import dotenv_values  # type: ignore
    except Exception:
        return None

    vals = dotenv_values(str(env_path))
    out: Dict[str, str] = {}
    for k, v in vals.items():
        if not k or v is None:
            continue
        out[str(k)] = str(v)
    return out


def _read_env_file(env_path: Path) -> Dict[str, str]:
    parsed = _load_env_via_dotenv(env_path)
    if parsed is not None:
        return parsed
    with env_path.open("r", encoding="utf-8") as f:
        return _parse_env_lines(f)


def _mask_token_presence(token: Optional[str]) -> str:
    if not token:
        return "unset"
    return f"SET(len={len(token)})"


def _env_bool(name: str, default: bool = False) -> bool:
    try:
        return str(os.getenv(name, "true" if default else "false")).strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "on",
        }
    except Exception:
        return bool(default)


def normalize_discord_env_inplace(env: Optional[dict] = None) -> None:
    """
    Apply safe aliases + URL normalization for Discord startup.

    - Supports BOTH LLM_MODEL and LLM_MODEL_ID (normalizes to LLM_MODEL_ID)
    - Supports BOTH LLM_API_BASE and LLM_API_URL (normalizes to LLM_API_BASE and mirrors LLM_API_URL)
    - Normalizes Memory URL using host+port join rules to prevent malformed concatenations

    This mutates os.environ (or provided env dict) but never prints secrets.
    """
    e = env or os.environ

    # --- LLM model alias ---
    model_id = (e.get("LLM_MODEL_ID", "") or "").strip()
    model_legacy = (e.get("LLM_MODEL", "") or "").strip()
    if not model_id and model_legacy:
        e["LLM_MODEL_ID"] = model_legacy

    # --- LLM base URL alias ---
    provider = (e.get("LLM_PROVIDER", "") or "").strip().lower() or "openai_compatible"

    if provider != "ollama":
        base = (e.get("LLM_API_BASE", "") or "").strip()
        url = (e.get("LLM_API_URL", "") or "").strip()

        # Default to localhost for modular local LLM unless explicitly overridden.
        if not base and not url:
            base = "http://127.0.0.1:11434"

        # Prefer BASE, fall back to URL.
        effective = base or url
        effective = normalize_base_url(effective)
        if effective:
            e["LLM_API_BASE"] = effective
            # Keep URL alias in sync (some older callers still read this).
            e["LLM_API_URL"] = effective

    # --- Memory URL normalization ---
    # Prefer explicit MEMORY_API_URL, fall back to MEMORY_POD_URL, else synthesize from host+port if available.
    raw_mem_api = (e.get("MEMORY_API_URL", "") or "").strip()
    raw_mem_pod = (e.get("MEMORY_POD_URL", "") or "").strip()
    mem = raw_mem_api or raw_mem_pod
    mem_port = (e.get("MEMORY_API_PORT", "") or "").strip()
    mem_host = (e.get("MEMORY_API_HOST", "") or "").strip() or (e.get("MEMORY_POD_HOST", "") or "").strip()

    # Track where the value came from for debug logs (never includes secrets).
    mem_source = "unset"
    if mem:
        mem_source = "MEMORY_API_URL" if raw_mem_api else "MEMORY_POD_URL"
    elif mem_host:
        mem_source = "MEMORY_API_HOST:MEMORY_API_PORT" if (e.get("MEMORY_API_HOST") or "").strip() else "MEMORY_POD_HOST:MEMORY_API_PORT"

    # Rule: if a value already looks like a full URL (http(s)://host:port), do not reconstruct it.
    # If we *must* join host+port, always join with ":" (handled by join_host_port).
    try:
        # Heuristic repair: handle rare mangling like "http://example.com8002" when we know the intended port.
        if mem and mem_port and "://" in mem and mem.endswith(mem_port):
            try:
                import re

                tail = mem.split("://", 1)[1]
                # Only attempt this for plain IPv4 without any ":" already present.
                if ":" not in tail:
                    base = mem[: -len(mem_port)]
                    if re.match(r"^https?://\d{1,3}(?:\.\d{1,3}){3}$", base):
                        mem = base + ":" + mem_port
                        mem_source = mem_source + "+heuristic_fix"
            except Exception:
                pass

        from urllib.parse import urlparse

        if not mem and mem_host:
            mem = join_host_port(mem_host, mem_port or None)
        elif mem:
            parsed = urlparse(mem if "://" in mem else f"http://{mem}")
            has_port = parsed.port is not None
            has_netloc = bool(parsed.netloc)
            has_scheme = bool(parsed.scheme)

            if has_scheme and has_netloc and has_port:
                # Already a full URL with an explicit port: keep as-is (just normalize).
                pass
            else:
                if mem_port:
                    mem = join_host_port(mem, mem_port or None)
    except Exception:
        if not mem and mem_host:
            mem = join_host_port(mem_host, mem_port or None)

    mem = normalize_base_url(mem)
    if mem:
        e["MEMORY_API_URL"] = mem
        # Debug-only provenance (safe string, no secrets).
        e["AXIOM_MEMORY_URL_SOURCE"] = mem_source

    # --- Qdrant URL normalization (for log clarity; does not force-enable) ---
    q = (e.get("QDRANT_URL", "") or "").strip()
    q_host = (e.get("QDRANT_HOST", "") or "").strip()
    q_port = (e.get("QDRANT_PORT", "") or "").strip() or "6333"
    if not q and q_host:
        q = join_host_port(q_host, q_port)
    q = normalize_base_url(q)
    if q:
        e["QDRANT_URL"] = q

    # Optional self-checks (debug mode only).
    debug_assert_url_normalization()


def _mask_url_for_logs(url: str) -> str:
    return mask_url_userinfo(url or "")


def resolve_llm_model_id(env: Optional[dict] = None) -> str:
    e = env or os.environ
    normalize_discord_env_inplace(e)
    return ((e.get("LLM_MODEL_ID") or "").strip() or (e.get("LLM_MODEL") or "").strip())


def resolve_llm_base_with_branch(env: Optional[dict] = None) -> Tuple[str, str]:
    """
    Resolve the effective LLM base URL and return (base, branch_name).
    Considers both LLM_API_BASE and legacy LLM_API_URL. Never returns secrets.
    """
    e = env or os.environ
    normalize_discord_env_inplace(e)
    provider = (e.get("LLM_PROVIDER", "") or "").strip().lower() or "openai_compatible"

    if provider == "ollama":
        base = (e.get("OLLAMA_URL", "") or "").strip()
        return base, "ollama:OLLAMA_URL"

    # OpenAI-compatible: prefer explicit BASE, fall back to URL.
    base = (e.get("LLM_API_BASE", "") or "").strip()
    if base:
        return normalize_base_url(base), "openai_compatible:LLM_API_BASE"

    url = (e.get("LLM_API_URL", "") or "").strip()
    if url:
        return normalize_base_url(url), "openai_compatible:LLM_API_URL"

    # Final fallback: first-party OpenAI base if key exists.
    if (e.get("OPENAI_API_KEY", "") or "").strip():
        obase = (e.get("OPENAI_BASE_URL", "") or "").strip() or "https://api.openai.com/v1"
        return obase.rstrip("/"), "openai:OPENAI_BASE_URL"

    return "", "unset"


def _candidate_env_paths(
    repo_root: Path,
    cwd: Path,
    env_filename: str = ".env.discord",
) -> List[Path]:
    candidates: List[Path] = []
    candidates.append(repo_root / env_filename)
    if cwd.resolve() != repo_root.resolve():
        candidates.append(cwd / env_filename)
    # De-dupe while preserving order
    seen = set()
    uniq: List[Path] = []
    for p in candidates:
        s = str(p)
        if s in seen:
            continue
        seen.add(s)
        uniq.append(p)
    return uniq


def load_discord_env(
    *,
    repo_root: Path,
    cwd: Optional[Path] = None,
    env_var: str = "DISCORD_ENV_FILE",
    env_filename: str = ".env.discord",
    override: bool = True,
) -> Tuple[Dict[str, str], Optional[str], List[str]]:
    """
    Deterministically load Discord env:
      - If DISCORD_ENV_FILE is set: load that file (absolute or relative).
      - Else: try repo_root/.env.discord, then cwd/.env.discord.

    Returns: (loaded_env_dict, loaded_from_path_or_None, attempted_paths)
    Side effects: updates os.environ with loaded values (override by default).
    """
    cwd = cwd or Path.cwd()
    attempted: List[str] = []

    env_file = (os.getenv(env_var) or "").strip()
    candidates: List[Path] = []

    if env_file:
        p = Path(env_file)
        if p.is_absolute():
            candidates = [p]
        else:
            # Prefer as provided (cwd-relative), then repo_root-relative as fallback.
            candidates = [cwd / p, repo_root / p]
    else:
        candidates = _candidate_env_paths(repo_root=repo_root, cwd=cwd, env_filename=env_filename)

    loaded_env: Dict[str, str] = {}
    loaded_from: Optional[str] = None

    for path in candidates:
        attempted.append(str(path))
        if not path.exists() or not path.is_file():
            continue
        try:
            loaded_env = _read_env_file(path)
            loaded_from = str(path)
            break
        except Exception:
            # Continue trying other candidates
            continue

    if loaded_env:
        if override:
            os.environ.update(loaded_env)
        else:
            for k, v in loaded_env.items():
                os.environ.setdefault(k, v)

    return loaded_env, loaded_from, attempted


def validate_discord_startup_env(
    *,
    attempted_paths: List[str],
    loaded_from: Optional[str],
    require_llm: bool = True,
) -> None:
    """
    Validate required env vars. Raises RuntimeError with an actionable message.
    """
    normalize_discord_env_inplace()
    token = (os.getenv("DISCORD_TOKEN") or "").strip()
    if not token:
        tried = "\n".join(f"  - {p}" for p in attempted_paths) or "  - (none)"
        raise RuntimeError(
            "DISCORD_TOKEN is not set.\n\n"
            "Fix:\n"
            "  - Create a .env.discord file (recommended) in the repo root, OR\n"
            "  - Set DISCORD_ENV_FILE=/absolute/path/to/.env.discord\n\n"
            f"Loaded from: {loaded_from or 'None'}\n"
            f"Attempted files:\n{tried}\n"
        )

    if require_llm:
        base, branch = resolve_llm_base_with_branch()
        provider = (os.getenv("LLM_PROVIDER", "") or "").strip().lower() or "openai_compatible"
        if provider == "ollama":
            if not (os.getenv("OLLAMA_URL") or "").strip():
                raise RuntimeError(
                    "LLM is not configured: LLM_PROVIDER=ollama but OLLAMA_URL is not set.\n"
                    "Set OLLAMA_URL (e.g. http://127.0.0.1:11434) in .env.discord.\n"
                )
        else:
            if not base:
                raise RuntimeError(
                    "LLM is not configured: set one of LLM_API_BASE or LLM_API_URL "
                    "(or set LLM_PROVIDER=ollama + OLLAMA_URL).\n"
                    f"Resolved branch: {branch}\n"
                )
        model = resolve_llm_model_id()
        if not model:
            raise RuntimeError(
                "LLM model is not configured: set LLM_MODEL_ID (preferred) or LLM_MODEL in .env.discord.\n"
            )


def format_discord_env_summary(
    *,
    loaded_env: Dict[str, str],
    loaded_from: Optional[str],
    attempted_paths: List[str],
) -> str:
    """
    Secret-safe summary for logs/console. Never prints token values.
    """
    normalize_discord_env_inplace()
    token = (os.getenv("DISCORD_TOKEN") or "").strip()
    provider = (os.getenv("LLM_PROVIDER", "") or "").strip().lower() or "openai_compatible"
    llm_base, llm_branch = resolve_llm_base_with_branch()
    model_id = resolve_llm_model_id() or "unset"
    mode_setting = resolve_llm_mode("auto")
    resolved_mode = mode_setting
    if mode_setting == "auto":
        # Best-effort resolve via /v1/models. If unknown, prefer chat (auto still has runtime fallback).
        if provider != "ollama" and llm_base and model_id and model_id != "unset":
            api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "").strip() or None
            models = fetch_openai_models(llm_base, api_key=api_key, timeout=2.0)
            caps = parse_openai_models_capabilities(models or {}, model_id) if models else None
            resolved_mode = decide_llm_mode_from_capabilities(caps) or "chat"
        else:
            resolved_mode = "chat"

    raw_memory_url = ((loaded_env.get("MEMORY_API_URL") or loaded_env.get("MEMORY_POD_URL") or "") or "").strip()
    memory_url = (os.getenv("MEMORY_API_URL") or os.getenv("MEMORY_POD_URL") or "").strip()
    vector_url = (os.getenv("VECTOR_POD_URL") or "").strip()
    qdrant_url = (os.getenv("QDRANT_URL") or "").strip()
    qdrant_host = (os.getenv("QDRANT_HOST") or "").strip()
    qdrant_port = (os.getenv("QDRANT_PORT") or "").strip()

    tried = ", ".join(attempted_paths) if attempted_paths else "(none)"
    keys = ", ".join(sorted(loaded_env.keys())) if loaded_env else "(none)"

    # Keep output stable and grep-friendly.
    lines = [
        "[DISCORD_ENV] loaded_from=" + (loaded_from or "None"),
        "[DISCORD_ENV] attempted=" + tried,
        "[DISCORD_ENV] keys_loaded=" + keys,
        f"[DISCORD_ENV] DISCORD_TOKEN={_mask_token_presence(token)}",
        f"[DISCORD_ENV] LLM_PROVIDER={provider} LLM_MODEL_ID={model_id} LLM_BASE={_mask_url_for_logs(llm_base) if llm_base else 'unset'} LLM_MODE={mode_setting}{('→' + resolved_mode) if mode_setting == 'auto' else ''} (branch={llm_branch})",
        f"[DISCORD_ENV] MEMORY_API_URL raw={_mask_url_for_logs(raw_memory_url) if raw_memory_url else 'unset'} resolved={_mask_url_for_logs(memory_url) if memory_url else 'unset'} (source={(os.getenv('AXIOM_MEMORY_URL_SOURCE') or 'unknown')})",
        f"[DISCORD_ENV] VECTOR_POD_URL={vector_url or 'unset'}",
    ]
    if qdrant_url:
        lines.append(f"[DISCORD_ENV] QDRANT_URL={_mask_url_for_logs(qdrant_url)}")
    elif qdrant_host:
        lines.append(f"[DISCORD_ENV] QDRANT_HOST:QDRANT_PORT={qdrant_host}:{qdrant_port or '6333'}")
    else:
        lines.append("[DISCORD_ENV] QDRANT=unset")

    return "\n".join(lines) + "\n"


def failfast_print_and_exit(msg: str, exit_code: int = 2) -> "None":
    sys.stderr.write(msg)
    sys.stderr.flush()
    raise SystemExit(exit_code)

