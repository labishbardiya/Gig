"""Process-wide configuration bootstrap for local GIG entry points."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_project_env() -> None:
    """Load local settings without replacing variables supplied by the OS."""
    path = PROJECT_ROOT / ".env"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name and name not in os.environ:
            os.environ[name] = value.strip().strip('"').strip("'")
