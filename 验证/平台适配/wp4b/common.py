"""WP4b offline projections and the unchanged WP1 validation gate."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT.parent / "契约"
sys.path.insert(0, str(CONTRACT / "tools"))
from validate import validate as wp1_validate

VERSION = "0.1.0-candidate"
EVIDENCE = "真实平台导出（合成课程/学员）"


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def digest(data):
    return sha256(data).hexdigest()


def utc(epoch):
    return datetime.fromtimestamp(int(epoch), timezone.utc).isoformat().replace("+00:00", "Z")


def by(rows, key):
    result = {r[key]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError(f"non-unique source key: {key}")
    return result


def safe_member(name):
    path = PurePosixPath(name)
    return name == path.as_posix() and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def archive(path):
    result = {}
    with tarfile.open(path, "r:*") as src:
        for member in src:
            if member.isdir():
                continue
            if not member.isfile() or not safe_member(member.name) or member.name in result:
                raise ValueError(f"unsafe/duplicate archive member: {member.name}")
            result[member.name] = src.extractfile(member).read()
    return result


class Projection:
    def __init__(self, platform, samples, profile_id, profile_version):
        self.platform, self.samples = platform, samples
        self.profile = {"profile_id": profile_id, "profile_version": profile_version}
        self.records, self.observations, self.blobs = [], [], {}
        inventory = self.read("manifest.json")
        if not inventory.get("deployed"):
            raise ValueError("WP4b requires deployed WP4a evidence")
        for item in inventory["files"]:
            path = samples / item["file"]
            if path.is_symlink() or path.name != item["file"]:
                raise ValueError("unexpected inventory path")
            data = path.read_bytes()
            if (len(data), digest(data)) != (item["bytes"], item["sha256"]):
                raise ValueError(f"sample inventory mismatch: {path.name}")

    def read(self, filename):
        return json.loads((self.samples / filename).read_bytes())

    def rows(self, table):
        return self.read(f"{table}.json")

    def jsonl(self, table):
        return [json.loads(line) for line in (self.samples / f"{table}.jsonl").read_bytes().splitlines()]

    def key(self, table, native_id):
        if native_id is None or native_id == "":
            raise ValueError(f"missing native key: {table}")
        return f"urn:wp4b:{self.platform}:{table}:{quote(str(native_id), safe='')}"

    def ref(self, kind, table, native_id, version=None):
        ref = {"object_type": kind, "object_id": self.key(table, native_id)}
        if version is not None:
            ref["version_id"] = version
        return ref

    def object(self, kind, table, native_id, **fields):
        return dict(self.ref(kind, table, native_id), schema_version=VERSION,
                    source_system=self.platform, source_id=str(native_id), **fields)

    def event(self, name, source_event_id=None, **fields):
        definition = json.loads((CONTRACT / "events" / f"{name}.json").read_bytes())
        result = dict(event_type=name, event_type_version=definition["event_type_version"],
                      event_class=definition["event_class"], schema_version=VERSION,
                      source_system=self.platform, **self.profile, **fields)
        if source_event_id is not None:
            result["source_event_id"] = source_event_id
        return result

    def offering(self, table, native_id):
        ref = self.ref("Offering", table, native_id)
        return dict(scope_type="offering", scope_refs=[ref], offering_id=ref["object_id"])

    def add(self, target, instance, sources, elements, *, fields=None, gaps=None):
        validation = wp1_validate(instance, target, stage="input")
        missing = set()
        for check in validation["checks"]:
            if check["result"] != "failed":
                continue
            for error in check["errors"]:
                match = re.match(r"'([^']+)' is (?:a required property|a dependency of )", error["reason"])
                if match:
                    missing.add(f"{error['pointer']}/{match.group(1)}")
                elif error["rule_id"] == "R-EVENT-DEF-002":
                    missing.add(error["pointer"])
        record = dict(target=target, instance=instance, sources=list(sources),
                      elements=list(elements), fields=fields or {}, gaps=gaps or {},
                      missing_fields=sorted(missing), validation=validation)
        self.records.append(record)
        return record

    def note(self, kind, sources, elements, **facts):
        self.observations.append(dict(kind=kind, sources=list(sources), elements=list(elements), facts=facts))

    def retain(self, payload):
        checksum = digest(payload)
        path = f"blobs/{checksum}"
        self.blobs[path] = payload
        return path

    def asset(self, table, native_id, payload, sources, **fields):
        instance = self.object("Resource", table, native_id, file_based=True,
                               byte_length=len(payload), content_hash=digest(payload), **fields)
        marks = {"/byte_length": "FLD-RES-012", "/content_hash": "FLD-RES-013"}
        for key, element in {"title": "FLD-RES-001", "media_type": "FLD-RES-011"}.items():
            if key in fields:
                marks[f"/{key}"] = element
        return self.add("Resource", instance, sources, ["OBJ-020"], fields=marks,
                        gaps={"/version_id": "只有导出快照，未证明原生资产版本",
                              "/storage_ref": "本地包内路径不是学校受控存储引用",
                              "/rights_ref": "原生文件元数据不是已登记的权利档案"})

    @property
    def passed(self):
        return [r for r in self.records if r["validation"]["result"] == "passed" and not r["gaps"]]

    @property
    def blocked(self):
        return [r for r in self.records if r["validation"]["result"] != "passed" or r["gaps"]]


def row_source(table, value, key="id"):
    return f"{table}.json#{key}={value}"


def member_source(filename, member):
    return f"{filename}#{member}"


def check_field(instance, pointer):
    if not re.fullmatch(r"(/[a-z_]+)+", pointer):
        raise ValueError(f"unexpected mapping pointer: {pointer}")
    for key in pointer[1:].split("/"):
        instance = instance[key]
    if instance is None:
        raise ValueError(f"mapped field is null: {pointer}")
    return instance
