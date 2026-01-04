import os
import sys
import logging


def envbool(k: str, default: bool = False) -> bool:
    return str(os.getenv(k, "1" if default else "0")).lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


PLAIN_LOGS = envbool("AXIOM_PLAIN_LOGS", False)


class Utf8StreamHandler(logging.StreamHandler):
    REPLACERS = (
        ("📂", "[FOLDER]"),
        ("✅", "[OK]"),
        ("❌", "[X]"),
        ("🔍", "[SEARCH]"),
        ("🔄", "[RELOAD]"),
        ("🧠", "[MEM]"),
    )

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        try:
            msg = self.format(record)
            if PLAIN_LOGS:
                for bad, rep in self.REPLACERS:
                    msg = msg.replace(bad, rep)
            try:
                self.stream.write(msg + self.terminator)  # type: ignore[attr-defined]
            except UnicodeEncodeError:
                # Fallback to explicit UTF-8 bytes with replacement
                self.stream.buffer.write(  # type: ignore[attr-defined]
                    (msg + self.terminator).encode("utf-8", "replace")
                )
            self.flush()
        except Exception:
            # Last-chance best-effort
            try:
                s = self.format(record)
                self.stream.write(  # type: ignore[attr-defined]
                    s.encode("ascii", "ignore").decode("ascii")
                    + self.terminator  # type: ignore[attr-defined]
                )
                self.flush()
            except Exception:
                # Give up silently to avoid cascading failures
                pass


def install_basic_utf8_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        h = Utf8StreamHandler(sys.stdout)
        h.setFormatter(fmt)
        root.addHandler(h)
    root.setLevel(level)


def emoji(fmt_emoji: str, fallback_ascii: str) -> str:
    return fallback_ascii if PLAIN_LOGS else fmt_emoji
