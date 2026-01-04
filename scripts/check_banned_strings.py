#!/usr/bin/env python3
import re
import subprocess
import sys

BANNED = [
    r"\bupsert_points\b",
]
WARN_PATTERNS = [
    r'(?<!collections\.)"axiom_memory"',  # hard-coded legacy
    r'(?<!collections\.)"memory"',  # hard-coded collection literal
]


def git_ls_files():
    out = subprocess.check_output(["git", "ls-files"], text=True)
    return [
        p
        for p in out.splitlines()
        if not p.startswith(".git")
        and "__pycache__" not in p
        and not p.endswith(".pyc")
    ]


def scan(paths, patterns):
    hits = []
    for p in paths:
        try:
            with open(p, "r", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    for pat in patterns:
                        if re.search(pat, line):
                            hits.append((p, i, line.strip(), pat))
        except Exception:
            pass
    return hits


paths = git_ls_files()
banned = scan(paths, BANNED)
warns = scan(paths, WARN_PATTERNS)

if banned:
    print("ERROR: banned symbols found:")
    for p, i, ln, pat in banned:
        print(f"  {p}:{i}: {ln}  [pattern: {pat}]")
    sys.exit(1)

if warns:
    print("WARNING: hard-coded collection strings detected (verify):")
    for p, i, ln, pat in warns:
        print(f"  {p}:{i}: {ln}  [pattern: {pat}]")

print("check_banned_strings: OK")
