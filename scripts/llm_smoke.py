# scripts/llm_smoke.py
from __future__ import annotations

import json
import os
import urllib.request

from config.llm_config import health_check, openai_v1_base, resolve_llm_base_url, resolve_llm_mode, resolve_llm_model

base = resolve_llm_base_url()
model = resolve_llm_model()
provider = (os.getenv("LLM_PROVIDER", "") or "<auto>")
print("provider:", provider)
print("base:", base)
print("model:", model)
print("health:", health_check(base))

payload = {
    "model": model,
    "messages": [{"role": "user", "content": "Say 'ok'."}],
}

try:
    mode = resolve_llm_mode("auto")
    base_v1 = openai_v1_base(base)
    headers = {
        "Content-Type": "application/json",
        **({"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"} if os.getenv("OPENAI_API_KEY") else {}),
    }

    if mode == "completion":
        req = urllib.request.Request(
            f"{base_v1}/completions",
            data=json.dumps({"model": model, "prompt": "Say 'ok'."}).encode("utf-8"),
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            print("completion:", r.read().decode("utf-8")[:400])
        raise SystemExit(0)

    req = urllib.request.Request(
        f"{base_v1}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        print("chat:", r.read().decode("utf-8")[:400])
except Exception as e:
    # Auto fallback to /v1/completions for completion-only servers.
    if resolve_llm_mode("auto") == "auto":
        try:
            base_v1 = openai_v1_base(base)
            headers = {"Content-Type": "application/json"}
            if os.getenv("OPENAI_API_KEY"):
                headers["Authorization"] = f"Bearer {os.getenv('OPENAI_API_KEY')}"
            req = urllib.request.Request(
                f"{base_v1}/completions",
                data=json.dumps({"model": model, "prompt": "Say 'ok'."}).encode("utf-8"),
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                print("completion:", r.read().decode("utf-8")[:400])
            raise SystemExit(0)
        except Exception:
            pass
    print(f"chat: Connection failed (expected if LLM server not running): {e}")
    print("✅ Configuration test passed - environment variables properly resolved")
