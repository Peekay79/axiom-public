#!/usr/bin/env python3
"""
Sanitize language in docs, comments, and Python docstrings across the workspace.

Scope:
- README, Markdown docs, and .txt: process entire file
- Python: process only docstrings and comments
- TypeScript/JavaScript: process only comments (// and /* */)

Patterns (applied as specified):
1) "Empathy Engine" → "Empathy Engine"
   - Regex: \bEmpathy\s+Engine\b
2) "Theory of Mind" (and optional Engine/Module/Layer) → "Theory of Mind"
   - Regex: \bTheory of Mind(?:\s+(?:Engine|Module|Layer)?)?\b
3) Optional: [Dd]ream [Ee]ngine → "Speculative Simulation Module"
   - Regex: \b[Dd]ream\s+[Ee]ngine\b
4) Optional: Replace anthropomorphic verbs in comments/docstrings only (light touch)
   - "Axiom (feels|experiences|understands|believes|wants)" → "Axiom models $1"

Include:
- **/*.md, **/*.py, **/*.ts, **/*.js, **/*.txt

Exclude:
- **/node_modules/**, **/dist/**, **/__pycache__/**, **/*.test.*, **/*.spec.*

Condition (file-level precheck):
- Empathy Engine | Theory of Mind | Speculative Simulation Module | Axiom (feels|understands|believes|wants)

Note: We restrict modifications to the allowed regions to avoid changing executable code.
"""

from __future__ import annotations

import ast
import io
import os
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple


# ----------------------------- Configuration ----------------------------- #

WORKSPACE_ROOT = Path("/workspace").resolve()

INCLUDE_GLOBS: Sequence[str] = [
    "**/*.md",
    "**/*.py",
    "**/*.ts",
    "**/*.js",
    "**/*.txt",
]

EXCLUDE_GLOBS: Sequence[str] = [
    "**/node_modules/**",
    "**/dist/**",
    "**/__pycache__/**",
    "**/*.test.*",
    "**/*.spec.*",
]

# Compile replacement patterns
PATTERN_EMPATHY_ENGINE = re.compile(r"\bEmpathy\s+Engine\b")
PATTERN_THEORY_OF_MIND = re.compile(r"\bTheory of Mind(?:\s+(?:Engine|Module|Layer)?)?\b")
PATTERN_DREAM_ENGINE = re.compile(r"\b[Dd]ream\s+[Ee]ngine\b")
PATTERN_ANTHRO = re.compile(r"\bAxiom\s+(feels|experiences|understands|believes|wants)\b")

REPLACEMENTS: Sequence[Tuple[re.Pattern, str]] = (
    (PATTERN_EMPATHY_ENGINE, "Empathy Engine"),
    (PATTERN_THEORY_OF_MIND, "Theory of Mind"),
    (PATTERN_DREAM_ENGINE, "Speculative Simulation Module"),
)

# File-level condition precheck
# Make Speculative Simulation Module case-insensitive by matching initial letters and include "experiences"
FILE_CONDITION = re.compile(
    r"Empathy\s+Engine|Theory of Mind|[Dd]ream\s+[Ee]ngine|Axiom\s+(feels|experiences|understands|believes|wants)",
)


# ------------------------------ Utilities -------------------------------- #

def path_matches_any_glob(path: Path, patterns: Sequence[str]) -> bool:
    relative = path.relative_to(WORKSPACE_ROOT).as_posix()
    for pattern in patterns:
        if Path(relative).match(pattern):
            return True
    return False


def iter_candidate_files() -> Iterable[Path]:
    for pattern in INCLUDE_GLOBS:
        for path in WORKSPACE_ROOT.glob(pattern):
            if path.is_dir():
                continue
            if path_matches_any_glob(path, EXCLUDE_GLOBS):
                continue
            yield path


def safe_read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
    except Exception:
        return None


def write_text_if_changed(path: Path, original: str, updated: str) -> bool:
    if original == updated:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def apply_basic_replacements(text: str) -> Tuple[str, int]:
    total = 0
    for pattern, replacement in REPLACEMENTS:
        new_text, count = pattern.subn(replacement, text)
        text = new_text
        total += count
    return text, total


def apply_anthro_replacement(text: str) -> Tuple[str, int]:
    # Replace: "Axiom <verb>" -> "Axiom models <verb>" for specified verbs
    # Case-sensitive by specification
    return PATTERN_ANTHRO.subn(r"Axiom models \1", text)


# --------------------------- Python processing --------------------------- #

@dataclass
class TextRange:
    start: int  # absolute start index in file text
    end: int    # absolute end index in file text (exclusive)


def _line_col_to_index(line_starts: List[int], line_no: int, col: int) -> int:
    # line_no is 1-based per ast/tokenize; line_starts is 0-based
    return line_starts[line_no - 1] + col


def _compute_line_starts(text: str) -> List[int]:
    positions = [0]
    for match in re.finditer("\n", text):
        positions.append(match.end())
    return positions


def _collect_python_docstring_ranges(text: str) -> List[TextRange]:
    ranges: List[TextRange] = []
    try:
        module = ast.parse(text)
    except SyntaxError:
        return ranges

    line_starts = _compute_line_starts(text)

    def add_range(node: ast.AST):
        if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
            return
        lineno = getattr(node, "lineno")
        end_lineno = getattr(node, "end_lineno")
        col = getattr(node, "col_offset", 0) or 0
        end_col = getattr(node, "end_col_offset", 0) or 0
        try:
            start_index = _line_col_to_index(line_starts, lineno, col)
            end_index = _line_col_to_index(line_starts, end_lineno, end_col)
            ranges.append(TextRange(start=start_index, end=end_index))
        except Exception:
            return

    # Module docstring
    if module.body:
        first_stmt = module.body[0]
        if isinstance(first_stmt, ast.Expr) and isinstance(getattr(first_stmt, "value", None), (ast.Str, ast.Constant)):
            value = first_stmt.value
            if isinstance(value, ast.Constant) and not isinstance(value.value, str):
                pass
            else:
                add_range(first_stmt)

    # Function and class docstrings (recursive)
    def visit(node: ast.AST):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if child.body:
                    first = child.body[0]
                    if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), (ast.Str, ast.Constant)):
                        value = first.value
                        if isinstance(value, ast.Constant) and not isinstance(value.value, str):
                            pass
                        else:
                            add_range(first)
            visit(child)

    visit(module)
    return ranges


def _collect_python_comment_ranges(text: str) -> List[TextRange]:
    ranges: List[TextRange] = []
    line_starts = _compute_line_starts(text)
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except tokenize.TokenError:
        return ranges
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            (start_line, start_col) = tok.start
            (end_line, end_col) = tok.end
            start_index = _line_col_to_index(line_starts, start_line, start_col)
            end_index = _line_col_to_index(line_starts, end_line, end_col)
            ranges.append(TextRange(start=start_index, end=end_index))
    return ranges


def process_python_text(text: str) -> Tuple[str, int]:
    # Identify docstrings and comments; apply replacements only within those regions
    doc_ranges = _collect_python_docstring_ranges(text)
    comment_ranges = _collect_python_comment_ranges(text)

    target_ranges = doc_ranges + comment_ranges
    if not target_ranges:
        return text, 0

    # Merge overlapping ranges to avoid double-processing
    target_ranges.sort(key=lambda r: (r.start, r.end))
    merged: List[TextRange] = []
    for r in target_ranges:
        if not merged or r.start > merged[-1].end:
            merged.append(TextRange(r.start, r.end))
        else:
            merged[-1].end = max(merged[-1].end, r.end)

    updated_parts: List[str] = []
    last_index = 0
    total_replacements = 0
    for r in merged:
        # unchanged segment before range
        updated_parts.append(text[last_index:r.start])

        segment = text[r.start:r.end]
        segment, count_basic = apply_basic_replacements(segment)
        segment, count_anthro = apply_anthro_replacement(segment)
        total_replacements += count_basic + count_anthro

        updated_parts.append(segment)
        last_index = r.end

    # tail after last range
    updated_parts.append(text[last_index:])
    updated_text = "".join(updated_parts)
    return updated_text, total_replacements


# ----------------------- JS/TS comment processing ------------------------ #

def process_js_ts_text(text: str) -> Tuple[str, int]:
    # Process only comments: // ... and /* ... */
    i = 0
    n = len(text)
    in_single_quote = False
    in_double_quote = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False
    escape = False
    comment_ranges: List[TextRange] = []
    comment_start: Optional[int] = None

    while i < n:
        ch = text[i]

        if in_line_comment:
            if ch == "\n":
                # End of line comment (exclude the newline)
                comment_ranges.append(TextRange(start=comment_start or i, end=i))
                in_line_comment = False
                comment_start = None
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and i + 1 < n and text[i + 1] == "/":
                # Include the closing */
                i += 2
                comment_ranges.append(TextRange(start=comment_start or i, end=i))
                in_block_comment = False
                comment_start = None
                continue
            i += 1
            continue

        if in_backtick:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "`":
                in_backtick = False
            i += 1
            continue

        if in_single_quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                in_single_quote = False
            i += 1
            continue

        if in_double_quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_double_quote = False
            i += 1
            continue

        # Not in string or comment
        if ch == "/" and i + 1 < n:
            next_ch = text[i + 1]
            if next_ch == "/":
                in_line_comment = True
                comment_start = i
                i += 2
                continue
            if next_ch == "*":
                in_block_comment = True
                comment_start = i
                i += 2
                continue

        if ch == "`":
            in_backtick = True
            i += 1
            continue

        if ch == "'":
            in_single_quote = True
            i += 1
            continue

        if ch == '"':
            in_double_quote = True
            i += 1
            continue

        i += 1

    # If file ends while in a comment, close the range at EOF
    if in_line_comment and comment_start is not None:
        comment_ranges.append(TextRange(start=comment_start, end=n))
    if in_block_comment and comment_start is not None:
        comment_ranges.append(TextRange(start=comment_start, end=n))

    if not comment_ranges:
        return text, 0

    # Apply replacements within comment ranges only
    updated_parts: List[str] = []
    last_index = 0
    total_replacements = 0
    for r in comment_ranges:
        updated_parts.append(text[last_index:r.start])
        segment = text[r.start:r.end]
        segment, count_basic = apply_basic_replacements(segment)
        segment, count_anthro = apply_anthro_replacement(segment)
        total_replacements += count_basic + count_anthro
        updated_parts.append(segment)
        last_index = r.end

    updated_parts.append(text[last_index:])
    return "".join(updated_parts), total_replacements


# -------------------------- Markdown/Text processing --------------------- #

def process_entire_text(text: str) -> Tuple[str, int]:
    text, total = apply_basic_replacements(text)
    # By specification, anthropomorphic replacement is for comments/docstrings only
    return text, total


# ------------------------------- Runner --------------------------------- #

def should_process_file(text: str) -> bool:
    return bool(FILE_CONDITION.search(text))


def process_file(path: Path) -> Tuple[bool, int]:
    original = safe_read_text(path)
    if original is None:
        return False, 0

    if not should_process_file(original):
        return False, 0

    ext = path.suffix.lower()
    updated: str
    replacements: int

    if ext in {".md", ".txt"}:
        updated, replacements = process_entire_text(original)
    elif ext == ".py":
        updated, replacements = process_python_text(original)
    elif ext in {".ts", ".js"}:
        updated, replacements = process_js_ts_text(original)
    else:
        return False, 0

    if replacements <= 0:
        return False, 0

    changed = write_text_if_changed(path, original, updated)
    return changed, replacements if changed else 0


def main() -> int:
    changed_files = 0
    total_replacements = 0
    processed_files = 0

    for file_path in sorted(set(iter_candidate_files())):
        processed_files += 1
        changed, count = process_file(file_path)
        if changed:
            changed_files += 1
            total_replacements += count

    print(f"Processed files: {processed_files}")
    print(f"Changed files:   {changed_files}")
    print(f"Replacements:    {total_replacements}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

