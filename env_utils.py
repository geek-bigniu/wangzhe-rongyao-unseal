import os
from pathlib import Path


def load_env(path=None):
    env_path = Path(path) if path else Path(__file__).with_name(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]

        os.environ.setdefault(key, value)


def get_env(name, default=None):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def require_env(name):
    value = get_env(name)
    if value is None:
        raise RuntimeError(f"missing required .env value: {name}")
    return value
