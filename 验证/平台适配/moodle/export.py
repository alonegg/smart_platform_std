"""Collect the upstream synthetic fixture, not a local platform export."""
import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import urllib.request
import xml.etree.ElementTree as ET

COMMIT = "2d4bafe8548a6d6c01494c862ec3d9749ba6ea84"
FIXTURE = "public/mod/subsection/tests/fixtures/subsections_with_descriptions.mbz"
URL = f"https://raw.githubusercontent.com/moodle/moodle/{COMMIT}/{FIXTURE}"
BASE = Path(__file__).resolve().parent


def inspect(data):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        names = archive.getnames()
        if "users.xml" in names:
            raise ValueError("User-bearing fixture is not permitted")
        root = ET.fromstring(archive.extractfile("moodle_backup.xml").read())
        settings = root.findall("information/settings/setting")
        if not any(s.findtext("name") == "users" and s.findtext("value") == "0"
                   for s in settings):
            raise ValueError("Expected a no-user backup")
        files = ET.fromstring(archive.extractfile("files.xml").read())
        if list(files):
            raise ValueError("Unexpected embedded file content")
        return {key: root.findtext(f"information/{key}") for key in
                ("moodle_version", "moodle_release", "backup_date")}


def collect(data, output):
    version = inspect(data)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Output must be empty; existing samples are never overwritten")
    name = "upstream-subsections-no-users.mbz"
    manifest = {
        "evidence_level": "official_example_only_not_local_platform_data",
        "deployed": False,
        "source_snapshot_commit": COMMIT,
        "source_snapshot_release": "6.0dev (Build: 20261117)",
        "files": [{"file": name, "bytes": len(data),
                   "sha256": hashlib.sha256(data).hexdigest(),
                   "source_url": URL,
                   "source_command": "python3 export.py --update-samples",
                   "collected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "platform_version": version,
                   "platform_commit": None,
                   "coverage": ["official synthetic course backup without users"],
                   "not_covered": ["local deployment", "two offerings", "enrolment",
                                   "video views", "quiz attempts", "assignment reopen",
                                   "grade changes", "groups", "database exports"]}]
    }
    (output / name).write_bytes(data)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--output", type=Path)
    group.add_argument("--update-samples", action="store_true")
    parser.add_argument("--source", type=Path, help="Offline copy of the exact upstream fixture")
    args = parser.parse_args()
    output = BASE / "samples" if args.update_samples else args.output
    if output is None:
        output = Path(tempfile.mkdtemp(prefix="moodle-official-example-"))
    data = args.source.read_bytes() if args.source else urllib.request.urlopen(URL, timeout=60).read()
    print(collect(data, output))


if __name__ == "__main__":
    main()
