"""WP1 JSON 校验与交换包实际字节校验。"""
import json
from pathlib import Path
from zipfile import BadZipFile
from . import validate
from .package import validate_package


def validate_path(path, target=None, stage="input"):
    path = Path(path)
    try:
        if path.is_dir() or path.suffix.lower() == ".zip":
            return validate_package(path)
        return validate(json.loads(path.read_text()), target, stage)
    except (OSError, ValueError, TypeError, KeyError, BadZipFile) as exc:
        return {"result": "failed", "checks": [{"check": "input", "result": "failed", "errors": [str(exc)]}]}
