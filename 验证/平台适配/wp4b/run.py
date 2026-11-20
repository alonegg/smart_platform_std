"""CLI for WP4b; only writes to a newly created output directory."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moodle.adapter.convert import convert as moodle
from openedx.adapter.convert import convert as openedx
from wp4b.common import EVIDENCE, ROOT, VERSION, digest, encode, safe_member, wp1_validate
from wp4b.loss import csv_bytes, loss_rows

FORMAT = "wp4b-offline-diagnostic-v1"
PROJECTIONS = {"openedx": openedx, "moodle": moodle}
PROFILE = ("wp4b-offline", "1")


def inventory(files):
    return {name: {"sha256": digest(data), "bytes": len(data)} for name, data in sorted(files.items())}


def write_packet(p, out):
    out.mkdir()
    docs = {"candidate-passed.json": [r["instance"] for r in p.passed],
            "candidate-blocked.json": p.blocked, "native-evidence.json": p.observations,
            "validation-passed.json": p.passed}
    files = {**{name: encode(value) for name, value in docs.items()}, **p.blobs}
    ledger = inventory(files)
    metadata = dict(format=FORMAT, platform=p.platform, evidence=EVIDENCE, entries=ledger)
    for name, value in docs.items():
        (out / name).write_bytes(encode(value))
    with ZipFile(out / "diagnostic.zip", "x", ZIP_DEFLATED) as dst:
        for name, data in sorted({**files, "index.json": encode(metadata)}.items()):
            # No wall-clock timestamp or file-system metadata in the diagnostic archive.
            dst.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)
    candidate = {"schema_version": VERSION, "files": [
        {"path": name, "byte_length": entry["bytes"], "sha256": entry["sha256"],
         "media_type": "application/json" if name.endswith(".json") else "application/octet-stream"}
        for name, entry in ledger.items()
    ]}
    attempt = dict(candidate=candidate, validation=wp1_validate(candidate, "manifest"), gaps={
        "/package_type": "诊断包不是候选契约定义的正式包类型",
        "/export_scope/grant_refs": "样本无学校认可的导出授权",
        "/rights_summary": "没有完整许可、署名和受限组成档案",
        "/objects": "没有通过的对象及可权威解析的引用闭包",
    })
    (out / "manifest-attempt.json").write_bytes(encode(attempt))


def read_packet(path):
    """Read only the diagnostic ZIP; no original LMS, samples or loose JSON files."""
    with ZipFile(path) as src:
        names = src.namelist()
        if len(names) != len(set(names)) or not all(map(safe_member, names)):
            raise ValueError("unsafe/duplicate diagnostic archive path")
        metadata = json.loads(src.read("index.json"))
        files = {name: src.read(name) for name in names if name != "index.json"}
    if metadata["format"] != FORMAT or metadata["entries"] != inventory(files):
        raise ValueError("diagnostic archive format/inventory mismatch")
    return files


def run(out):
    projections = []
    for platform, convert in PROJECTIONS.items():
        projection = convert(ROOT / platform / "samples", *PROFILE)
        projections.append(projection)
        write_packet(projection, out / platform)
        print(f"{platform}: WP1 passed={len(projection.passed)}, blocked={len(projection.blocked)}, "
              f"evidence={len(projection.observations)}, blobs={len(projection.blobs)}; diagnostic ZIP written")
    rows = list(loss_rows(projections))
    (out / "loss.csv").write_bytes(csv_bytes(rows))
    (out / "differences.csv").write_bytes(csv_bytes([
        row for row in rows if row["comparison"] in {"样本证实较多", "样本低于静态潜力"}
    ]))
    print(f"loss: {len(rows)} platform/element rows; {sum(r['wp1_scope'] == '首批' for r in rows)} in scope")
    return rows


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, help="new directory (default: create a temporary directory)")
    args = cli.parse_args()
    if args.output:
        args.output.mkdir()
    out = args.output or Path(tempfile.mkdtemp(prefix="wp4b-"))
    run(out)
    print(out)


if __name__ == "__main__":
    main()
