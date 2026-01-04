import os
from datetime import datetime

LOG_PATH = "logs/axiom_action_log.txt"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


def log_event(tag, message):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp} [{tag.upper()}] {message}"

    # Print to console
    print(entry)

    # Write to log file
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
