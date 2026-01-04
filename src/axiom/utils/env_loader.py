import os


def reload_env(filepath=".env", verbose=False):
    if not os.path.isfile(filepath):
        print(f"⚠️ .env not found at {filepath}")
        return

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key] = value
            if verbose:
                k = (key or "").upper()
                if any(s in k for s in ("TOKEN", "KEY", "SECRET", "PASSWORD")):
                    shown = "****REDACTED****"
                else:
                    shown = value
                print(f"🔄 Loaded: {key} = {shown}")
