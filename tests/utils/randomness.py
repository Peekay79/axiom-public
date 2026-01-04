import os
import random

try:
    import numpy as _np  # optional
except Exception:
    _np = None


def seed_all(seed=1337):
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    if _np is not None:
        _np.random.seed(seed)
    return seed

