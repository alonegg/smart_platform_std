"""8.2.4—8.2.9；FLD-MAN-008、FLD-MAN-009；H-26、W3-01。只读归档，不解压。"""
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from . import validate


def safe(path):
    return isinstance(path, str) and bool(re.fullmatch(r"[A-Za-z0-9%._~/-]+", path)) and not path.startswith("/") and ".." not in path and "\\" not in path


def validate_package(path):
    checks = []

    def check(name, errors, status=None):
        checks.append(dict(check=name, result=status or ("failed" if errors else "passed"), errors=errors))

    archive = None
    try:
        path = Path(path)
        if path.is_dir():
            entries = list(path.rglob("*"))
            if any(p.is_symlink() for p in entries):
                raise ValueError("symbolic links not allowed")
            names = [p.relative_to(path).as_posix() for p in entries if p.is_file()]
            read = lambda name: (path / name).read_bytes()
        else:
            archive = ZipFile(path)
            names = [i.filename for i in archive.infolist() if not i.is_dir()]
            if any((i.external_attr >> 16) & 0o170000 == 0o120000 for i in archive.infolist()):
                raise ValueError("symbolic links not allowed")
            read = archive.read
        if len(names) != len(set(names)) or any(not safe(n) for n in names):
            raise ValueError("unsafe or duplicate package path")
        manifest = json.loads(read("manifest.json"))
        result = validate(manifest, "manifest", "exchange")
        checks.extend({**c, "check": "manifest/" + c["check"]} for c in result["checks"])
        if result["result"] == "failed":
            return dict(result="failed", checks=checks)
        declared = {"manifest.json"}
        for entry in manifest["files"]:
            name = entry["path"]
            declared.add(name)
            errors = []
            if not safe(name) or name not in names:
                errors.append("路径不安全或文件不存在")
            else:
                data = read(name)
                if len(data) != entry["byte_length"]:
                    errors.append("byte_length 不符")
                if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                    errors.append("sha256 不符")
            check("file/" + name, errors)
        for entry in manifest["objects"]:
            name, reference = entry["path"], entry["object_ref"]
            declared.add(name)
            if not safe(name) or name not in names:
                check("object/" + name, ["路径不安全或对象不存在"])
                continue
            obj = json.loads(read(name))
            validation = validate(obj, reference["object_type"], "exchange")
            checks.extend({**c, "check": "object/" + name + "/" + c["check"]} for c in validation["checks"])
            check("object-ref/" + name, ["object_ref 与对象内容不一致"] if any(obj.get(k) != reference.get(k) for k in ("object_type", "object_id", "version_id")) else [])
        check("declared-files", ["清单外文件：" + n for n in sorted(set(names) - declared)])
        for name in ("dependency-resolution", "deterministic-packaging", "independent-recovery"):
            check(name, ["本工具未执行，不计通过"], "skipped")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        check("package", [str(exc)])
    finally:
        if archive:
            archive.close()
    return dict(result="failed" if any(c["result"] == "failed" for c in checks) else "passed", checks=checks)
