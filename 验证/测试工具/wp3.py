"""智慧教学-数据模型标准 WP3 命令行。"""
import argparse
import json
import os
from pathlib import Path

from conformance.profiles import CASE_IDS, PROFILES
from conformance.report import write
from conformance.runner import exit_code, metadata, run
from conformance.targets import open_target
from conformance.validate_cmd import validate_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validation = commands.add_parser("validate")
    validation.add_argument("paths", nargs="+", type=Path)
    validation.add_argument("--target")
    validation.add_argument("--stage", choices=["input", "stored", "exchange"], default="input")
    validation.add_argument("--json", action="store_true")
    listing = commands.add_parser("list")
    listing.add_argument("--json", action="store_true")
    execution = commands.add_parser("run")
    execution.add_argument("--target", required=True)
    execution.add_argument("--role", choices=["public-service"], required=True)
    execution.add_argument("--profile", choices=list(PROFILES), action="append", required=True)
    execution.add_argument("--grd-stages", default="P,C,A,R")
    execution.add_argument("--cases")
    execution.add_argument("--trigger", action="append", default=[])
    execution.add_argument("--admin-token-env", default="WP2_ADMIN_TOKEN")
    execution.add_argument("--json-out", type=Path, required=True)
    execution.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "validate":
        results = [{"path": str(p), **validate_path(p, args.target, args.stage)} for p in args.paths]
        result = results[0] if len(results) == 1 else {"result": "failed" if any(r["result"] == "failed" for r in results) else "passed", "paths": results}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(result["result"] == "failed")
    if args.command == "list":
        values = [metadata(c) for c in CASE_IDS]
        print(json.dumps(values, ensure_ascii=False, indent=2) if args.json else "\n".join(v["case_id"] + " " + v["title"] for v in values))
        return 0
    target = None
    try:
        target = open_target(args.target, os.environ.get(args.admin_token_env))
        result = run(target, args.target, args.role, args.profile, args.grd_stages.split(","), args.cases.split(",") if args.cases is not None else None, args.trigger)
        write(result, args.json_out, args.report_out)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    finally:
        if target:
            target.close()
    print("总体：" + result["overall"] + "；跳过不计为通过")
    print(json.dumps(result["summary"], ensure_ascii=False))
    print("JSON：" + str(args.json_out))
    print("报告：" + str(args.report_out))
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
