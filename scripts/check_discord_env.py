import os
import re


def mask(v):
    return v[:6] + "…" + v[-4:] if v and len(v) > 10 else "(missing)"


print("DISCORD_TOKEN:", mask(os.getenv("DISCORD_TOKEN", "")))
url = os.getenv("QDRANT_URL", "")
host = os.getenv("QDRANT_HOST", "")
port = os.getenv("QDRANT_PORT", "")
print("QDRANT:", url or f"{host}:{port or '6333'}")
print("USE_LOCAL_EMBEDDINGS:", os.getenv("USE_LOCAL_EMBEDDINGS", "false"))
