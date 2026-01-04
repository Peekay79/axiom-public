# scripts/check_no_hardcoded_llama.py
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parents[1]
bad = []
for p in root.rglob("*.py"):
    if any(seg in {"venv", ".venv", "logs", "site-packages"} for seg in p.parts):
        continue
    s = p.read_text(encoding="utf-8", errors="ignore")
    if re.search(r'["\']model["\']\s*:\s*["\']llama["\']', s) or re.search(
        r'\bmodel\s*=\s*["\']llama["\']', s
    ):
        bad.append(str(p))
if bad:
    print("Found hardcoded 'llama' in:\n" + "\n".join(bad))
    sys.exit(1)
print("OK: no hardcoded 'llama' models found.")
