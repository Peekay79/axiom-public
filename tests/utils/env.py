import os
from contextlib import contextmanager


@contextmanager
def temp_env(overrides: dict):
    old = {}
    try:
        for k, v in overrides.items():
            old[k] = os.environ.get(k)
            if v is None and k in os.environ:
                del os.environ[k]
            elif v is not None:
                os.environ[k] = str(v)
        yield
    finally:
        for k, v in old.items():
            if v is None and k in os.environ:
                del os.environ[k]
            elif v is not None:
                os.environ[k] = v

