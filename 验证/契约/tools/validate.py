"""离线候选契约校验入口；仅结构证据，不代表权限核验或符合性认证。"""
import argparse
from datetime import datetime
from functools import lru_cache
import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator, FormatChecker
from packaging.licenses import InvalidLicenseExpression, canonicalize_license_expression
from referencing import Registry, Resource

from payload_hash import payload_hash

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://example.edu/smart-teaching/contracts/0.1.0-candidate/"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


SCHEMAS = {str(p.relative_to(ROOT)): load(p) for p in (ROOT / "schema").rglob("*.json")}
REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in SCHEMAS.values())


def nearest_rule(node, sought, inherited=None, keyword="x-rule-id"):
    if isinstance(node, dict):
        inherited = node.get(keyword, inherited)
    if node is sought:
        return inherited
    children = node.values() if isinstance(node, dict) else node if isinstance(node, list) else []
    for child in children:
        found = nearest_rule(child, sought, inherited, keyword)
        if found:
            return found
    return None


def pointer(path):
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in path)


def error(rule, path, reason, hint=None):
    return {"rule_id": rule, "pointer": path, "reason": reason,
            "hint": hint or RULE_HINTS.get(rule, "按条款及候选契约修正后重试")}


def schema_errors(instance, schema):
    validator = Draft202012Validator(schema, registry=REGISTRY, format_checker=FormatChecker())
    result = []
    located_false_fields = set()
    for e in validator.iter_errors(instance):
        node, nearest, hint = schema, None, None
        resolver = REGISTRY.resolver(schema.get("$id", BASE))
        for part in e.absolute_schema_path:
            if isinstance(node, dict):
                nearest = node.get("x-rule-id", nearest)
                hint = node.get("x-hint", hint)
                while part not in node and "$ref" in node:
                    resolved = resolver.lookup(node["$ref"])
                    node, resolver = resolved.contents, resolved.resolver
                    if isinstance(node, dict):
                        nearest = node.get("x-rule-id", nearest)
                        hint = node.get("x-hint", hint)
                    else:
                        break
            try:
                node = node[part]
            except (KeyError, TypeError, IndexError):
                break
        if isinstance(e.schema, dict):
            nearest = e.schema.get("x-rule-id", nearest)
            for document in [schema, *SCHEMAS.values()]:
                found = nearest_rule(document, e.schema)
                if found:
                    nearest = found
                    break
            for document in [schema, *SCHEMAS.values()]:
                found = nearest_rule(document, e.schema, keyword="x-hint")
                if found:
                    hint = found
                    break
        path = list(e.absolute_path)
        schema_path = list(e.absolute_schema_path)
        if e.schema is False and len(schema_path) >= 2 and schema_path[-2] == "properties":
            path.append(schema_path[-1])
        elif e.schema is False and schema_path and schema_path[-1] == "properties" and isinstance(node, dict):
            parent = instance
            for part in path:
                parent = parent[part]
            for key, constraint in node.items():
                marker = (*path, key)
                if constraint is False and key in parent and parent[key] is e.instance and marker not in located_false_fields:
                    located_false_fields.add(marker)
                    path.append(key)
                    break
        result.append(error(nearest or "SCHEMA-" + str(e.validator), pointer(path), e.message, hint))
    return result


def walk(value, path=()):
    if isinstance(value, dict):
        yield value, path
        for key, child in value.items():
            yield from walk(child, (*path, key))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk(child, (*path, i))


@lru_cache(maxsize=None)
def field_target_types(name):
    targets = set()
    for schema in SCHEMAS.values():
        for node, _ in walk(schema):
            field = node.get("properties", {}).get(name)
            if isinstance(field, dict):
                targets.update(field.get("x-target-types", []))
    return targets


RULE_HINTS = {node["x-rule-id"]: node["x-hint"]
              for schema in SCHEMAS.values() for node, _ in walk(schema)
              if "x-rule-id" in node and "x-hint" in node}
RULE_HINTS.update({
    "R-RESOURCE-004": "将 Resource.contributors 改为所引用 RightsRecord 同版本的 contributors，不覆盖权利档案。",
    "R-RESOURCE-005": "将 Resource.license 改为所引用 RightsRecord.license.identifier，不能反向覆盖权利档案。",
    "R-RELATED-001": "提供符合候选 Schema 的 RightsRecord，且 object_id/version_id 与 rights_ref 一致。",
    "R-LICENSE-001": "填写 packaging SPDX 表认可的单一许可标识，或 school:学校域:注册代码；学校代码注册情况仍需核验。",
    "R-COG-008": "为显式 null 字段添加同名 JSON Pointer 的 missing_reasons；uncertainty 为空时原因必须是 unknown。",
    "R-COG-009": "观察或自我报告省略 method_ref 时，登记 /method_ref、not_applicable 及适用性 rule_id。",
    "R-EVIDENCELINK-002": "内嵌 EvidenceLink.owner_ref 必须指向包含它的 CognitiveState 记录。",
    "R-TIME-002": "调整时间范围，确保开始时间不晚于结束时间；保留 RFC3339 时区。",
    "R-APPLICATIONINSTANCE-002": "source_instance 应使用本部署实例的稳定 object_id，而不是产品级 source_system。",
    "WP2": "通过权威解析、登记和授权服务核验；离线合成样例不能证明存在性、实际权限或当前准入。",
})


def matching_rights(instance, related_objects):
    reference = instance.get("rights_ref", {})
    return next((obj for obj in related_objects
                 if obj.get("object_type") == "RightsRecord"
                 and obj.get("object_id") == reference.get("object_id")
                 and obj.get("version_id") == reference.get("version_id")), None)


def valid_license(identifier):
    if re.fullmatch(r"school:[A-Za-z0-9.-]+:[A-Za-z0-9._-]+", identifier):
        return True
    if re.search(r"\s|[()]", identifier) or identifier.lower().startswith("licenseref-"):
        return False
    try:
        return canonicalize_license_expression(identifier) == identifier
    except InvalidLicenseExpression:
        return False


def semantic_rules(instance, target, definition=None, related_objects=()):
    errors = []
    add = lambda rule, path, reason, hint=None: errors.append(error(rule, path, reason, hint))
    types = {o["object_type"]: o for o in load(ROOT / "vocab/object_types.json")["values"]}
    for value, path in walk(instance):
        t = value.get("object_type")
        if t not in types:
            implied = field_target_types(path[-1]) if path and isinstance(path[-1], str) else set()
            is_record = (target == "RecordRef" and not path) or (implied and all(types[k]["versioning"] == "不可变记录" for k in implied))
            if is_record and "version_id" in value and value["version_id"] != value.get("object_id"):
                add("R-REF-004", pointer((*path, "version_id")), "不可变记录 version_id 应等于 object_id")
        if t in types:
            if types[t]["versioning"] == "不可变记录" and "version_id" in value and value.get("version_id") != value.get("object_id"):
                add("R-REF-004", pointer((*path, "version_id")), "不可变记录 version_id 应等于 object_id")
            owners = types[t]["owner_types"]
            if owners and owners != ["所在记录"] and "owner_ref" in value and value["owner_ref"].get("object_type") not in owners:
                add("R-REF-005", pointer((*path, "owner_ref")), "所属对象类型与表5-1不一致")
    if target == "Segment" and instance.get("locator_type") == "time_range":
        start, end = instance.get("start_ms"), instance.get("end_ms")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)) and start >= end:
            add("R-SEG-002", "/end_ms", "应满足 start_ms < end_ms")
        if isinstance(end, (int, float)) and isinstance(instance.get("source_duration_ms"), (int, float)) and end > instance["source_duration_ms"]:
            add("R-SEG-003", "/end_ms", "片段结束超过源时长")
    if target in ["Resource", "RightsRecord"]:
        identifier = instance["license"] if target == "Resource" else instance["license"]["identifier"]
        if not valid_license(identifier):
            add("R-LICENSE-001", "/license" if target == "Resource" else "/license/identifier", "不是有效的单一 SPDX 许可标识或候选学校注册代码")
        if target == "RightsRecord":
            for i, component in enumerate(instance["third_party_components"]):
                if not valid_license(component["license"]):
                    add("R-LICENSE-001", f"/third_party_components/{i}/license", "第三方组成许可标识无效")
        rights = matching_rights(instance, related_objects) if target == "Resource" else None
        if rights:
            if instance["contributors"] != rights["contributors"]:
                add("R-RESOURCE-004", "/contributors", "与所引用 RightsRecord 的贡献者投影不一致")
            if instance["license"] != rights["license"]["identifier"]:
                add("R-RESOURCE-005", "/license", "与所引用 RightsRecord 的许可标识不一致")
    if target == "ApplicationInstance" and instance["source_instance"] != instance["object_id"]:
        add("R-APPLICATIONINSTANCE-002", "/source_instance", "来源实例标识与部署实例 object_id 不一致（H-17）")
    if target == "CognitiveState":
        reasons = instance.get("missing_reasons", [])
        for field in ["value", "uncertainty", "evidence_links"]:
            if field in instance and instance[field] is None:
                matches = [r for r in reasons if r["pointer"] == "/" + field and r["reason"] != "not_applicable"]
                if not matches or (field == "uncertainty" and not any(r["reason"] == "unknown" for r in matches)):
                    add("R-COG-008", "/missing_reasons", "显式null缺少对应原因，或不确定性原因不是unknown")
        if "method_ref" not in instance and not any(r["pointer"] == "/method_ref" and r["reason"] == "not_applicable" for r in reasons):
            add("R-COG-009", "/missing_reasons", "省略方法引用须登记不适用规则")
        for i, link in enumerate(instance["evidence_links"] or []):
            if link["owner_ref"]["object_type"] != "CognitiveState" or link["owner_ref"]["object_id"] != instance["object_id"]:
                add("R-EVIDENCELINK-002", f"/evidence_links/{i}/owner_ref", "证据关联的所属记录与包含它的认知记录不一致")
    pairs = {"TeachingAssignment": [("starts_at", "ends_at")],
             "AccessGrant": [("valid_from", "valid_until")],
             "MethodApproval": [("valid_from", "valid_until")],
             "CognitiveState": [("as_of", "valid_until")]}
    for start_key, end_key in pairs.get(target, []):
        if datetime.fromisoformat(instance[start_key]) > datetime.fromisoformat(instance[end_key]):
            add("R-TIME-002", "/" + end_key, "结束时间早于开始时间")
    if target == "CognitiveState":
        window = instance["evidence_window"]
        if datetime.fromisoformat(window["start"]) > datetime.fromisoformat(window["end"]):
            add("R-TIME-002", "/evidence_window/end", "证据时间范围倒置")
    if target in ["manifest", "export-receipt"]:
        window = instance["export_scope"]["time_window"]
        if datetime.fromisoformat(window["start"]) > datetime.fromisoformat(window["end"]):
            add("R-TIME-002", "/export_scope/time_window/end", "导出时间窗口倒置")
    if target == "manifest":
        paths = [item["path"] for item in instance["files"]]
        if len(paths) != len(set(paths)) or "manifest.json" in paths:
            add("R-MAN-006", "/files", "归档成员重复或包含manifest自身", "每个非manifest归档成员恰好登记一次；manifest.json不自摘要。")
        for i, item in enumerate(instance["objects"]):
            if item["path"] not in paths:
                add("R-MAN-007", f"/objects/{i}/path", "对象文件没有登记到files", "在files中登记对象文件的字节数、SHA-256与媒体类型。")
    if target == "receipt":
        completed, pending = set(instance["completed_stages"]), set(instance["pending_stages"])
        durability = instance.get("durability", "none")
        if completed & pending or (durability == "queue" and "school_registered" in completed) or (durability == "none" and completed & {"school_received", "school_registered"}):
            add("R-RCP-005", "/completed_stages", "阶段与持久化边界不一致", "queue不能证明入库；none不能证明学校接收；已完成与待完成阶段不能重叠。")
        required_stage = {"queue": "school_received", "evidence_store": "school_registered"}.get(durability)
        if required_stage and required_stage not in completed:
            add("R-RCP-005", "/completed_stages", "回执缺少其持久化边界证明的阶段", "queue对应school_received，evidence_store对应school_registered。")
    if target == "export-receipt" and instance["authorization_refs"] != instance["export_scope"]["grant_refs"]:
        add("R-EXR-002", "/authorization_refs", "回执授权引用与冻结范围不一致", "保留导出任务冻结时同一组具体授权版本；交付时授权仍须重新校验。")
    if target == "event":
        scopes = instance.get("scope_refs", [])
        if "offering_id" in instance and len(scopes) == 1 and instance["offering_id"] != scopes[0].get("object_id"):
            add("R-EVT-021", "/offering_id", "offering_id 与 scope_refs 不一致")
        if "attested_at" in instance and "source_recorded_at" in instance:
            try:
                if datetime.fromisoformat(instance["attested_at"]) > datetime.fromisoformat(instance["source_recorded_at"]):
                    add("R-EVT-022", "/attested_at", "凭证时间晚于源持久化时间")
            except (ValueError, TypeError):
                pass
        if "group_ref" in instance and instance.get("event_class") in ["learner_event", "artifact_event"]:
            subjects = instance.get("subject_refs", [instance.get("actor_ref", {})])
            members = {v.get("object_id") for v in instance.get("member_refs", [])}
            if any(s.get("object_id") not in members for s in subjects):
                add("R-EVT-023", "/member_refs", "提交成员不在成员快照中")
        if instance.get("event_type") == "grade.proposed" and instance.get("payload", {}).get("proposer_type") != instance.get("actor_type"):
            add("R-AI-004", "/payload/proposer_type", "提议来源应与 actor_type 一致")
        if instance["event_type"] == "media.progressed":
            for i, interval in enumerate(instance["payload"]["intervals"]):
                if interval["start_ms"] >= interval["end_ms"]:
                    add("R-MEDIA-001", f"/payload/intervals/{i}/end_ms", "有效播放区间须满足start_ms小于end_ms", "修正播放区间边界，不能用累计时长替代有效区间。")
        if instance["event_type"] == "permission.revoked" and instance["payload"]["revoked_grant_ref"] != instance["object_ref"]:
            add("R-REVOKE-001", "/payload/revoked_grant_ref", "被撤销授权与事件对象不一致", "引用同一AccessGrant具体版本，真实影响范围另交权威服务核验。")
        if definition and "payload_hash" in instance:
            if instance["payload_hash"] != payload_hash(instance, definition["hash_envelope_members"]):
                add("R-HASH-001", "/payload_hash", "摘要与候选算法复算结果不一致")
    return errors


def validate(instance, target=None, stage="input", related_objects=None):
    related_objects = list(related_objects or [])
    if isinstance(instance, dict) and "fixture" in instance and "instance" in instance:
        related_objects.extend(instance.get("related_instances", []))
        meta = instance["fixture"]
        target = target or meta["target"]
        stage = meta.get("stage", stage)
        instance = instance["instance"]
    checks = []
    def check(name, errors, result=None):
        checks.append({"check": name, "result": result or ("failed" if errors else "passed"), "errors": errors})
    if not isinstance(instance, dict):
        check("structure", [error("R-INPUT-001", "", "根值必须为对象")])
        return {"result": "failed", "checks": checks}
    target = target or ("event" if "event_type" in instance else instance.get("object_type"))
    if not target and "receipt_id" in instance:
        target = "export-receipt" if "manifest_sha256" in instance else "receipt"
    if not target and "package_id" in instance and "package_type" in instance:
        target = "manifest"
    definition = None
    if target == "event":
        path = f"schema/event-envelope.{stage}.schema.json"
        event_path = ROOT / "events" / (str(instance.get("event_type", "")).replace("/", "_") + ".json")
        if event_path.is_file():
            definition = load(event_path)
    elif target in ["ObjectRef", "IndependentRef", "EmbeddedRef", "EmbeddedInRecordRef", "RecordRef", "NonVersionedRef"]:
        path = "schema/common.schema.json"
    elif target in ["manifest", "receipt", "export-receipt"]:
        path = f"schema/{target}.schema.json"
    else:
        path = f"schema/objects/{target}.schema.json"
    if path not in SCHEMAS:
        check("structure", [error("R-TARGET-001", "", "目标尚未纳入当前契约", "显式选择已实现的目标")])
        return {"result": "failed", "checks": checks}
    schema = SCHEMAS[path]
    if target in ["ObjectRef", "IndependentRef", "EmbeddedRef", "EmbeddedInRecordRef", "RecordRef", "NonVersionedRef"]:
        schema = {"$ref": schema["$id"] + "#/$defs/" + target}
    errors = schema_errors(instance, schema)
    if target == "event" and definition:
        if "payload" in instance:
            payload_errors = schema_errors(instance["payload"], {"$id": BASE + "events/payload", **definition["payload_schema"]})
            errors += [{**e, "pointer": "/payload" + e["pointer"]} for e in payload_errors]
        for field, values in [("actor_type", definition["allowed_actor_types"]), ("entry_mode", definition["allowed_entry_modes"]),
                              ("scope_type", definition["scope_types"]), ("event_type_version", [definition["event_type_version"]])]:
            if instance.get(field) not in values:
                errors.append(error("R-EVENT-DEF-001", "/" + field, "不满足逐事件定义", "使用本事件定义登记的主体、进入方式、真实范围类型与事件版本。"))
        required = [field for flag, field in [("requires_attempt_ref", "attempt_ref"),
                    ("requires_teaching_assignment_ref", "teaching_assignment_ref"),
                    ("requires_source_recorded_at", "source_recorded_at")] if definition[flag]]
        if definition["subject_refs"] == "required":
            required.append("subject_refs")
        if definition["artifact_refs"] == "required":
            required.append("artifact_refs")
        for field in required:
            if field not in instance:
                errors.append(error("R-EVENT-DEF-002", "/" + field, "缺少逐事件定义必填关联", "按本事件业务语义补齐" + field + "，不得伪造范围或来源。"))
        if "object_ref" in instance:
            errors += schema_errors(instance["object_ref"], {**target_schema(definition["object_ref_types"]), "$id": BASE + "events/object"})
    elif target == "event":
        errors.append(error("R-EVENT-DEF-001", "/event_type", "事件类型没有已发布的候选逐事件定义", "使用表7-2首批24个已登记事件类型。"))
    check("structure", errors)
    related_errors = []
    if target == "Resource":
        for index, related in enumerate(related_objects):
            if not isinstance(related, dict) or related.get("object_type") != "RightsRecord":
                related_errors.append(error("R-RELATED-001", f"/related_instances/{index}", "关联输入只接受 RightsRecord"))
            else:
                detail = schema_errors(related, SCHEMAS["schema/objects/RightsRecord.schema.json"])
                detail += semantic_rules(related, "RightsRecord") if not detail else []
                if detail:
                    related_errors.append(error("R-RELATED-001", f"/related_instances/{index}", "关联 RightsRecord 未通过结构或语义校验"))
        if related_objects:
            check("related-structure", related_errors)
    check("semantic", semantic_rules(instance, target, definition, related_objects) if not errors and not related_errors else [], None if not errors and not related_errors else "skipped")
    reference_errors = [e for e in errors if e["rule_id"].startswith("R-REF-")]
    check("reference-structure", reference_errors, "failed" if reference_errors else "passed" if not errors else "skipped")
    check("reference-resolution", [error("WP2", "", "需解析服务（WP2）：存在性、访问权限、证据资格、修读/任务尝试一致性、授课安排和调整适用性")], "skipped")
    if target == "event":
        check("event-definition", [], "passed" if definition else "failed")
        check("event-preconditions", [error("WP2", "", "真实修读关系、授课权限、采集能力、帮助规则、撤回时限及接收状态需权威服务核验")], "skipped")
    if target == "Segment" and "source_duration_ms" not in instance:
        check("source-duration", [error("WP2", "", "缺少源时长，需解析服务（WP2）")], "skipped")
    if target == "Resource":
        if not errors and not related_errors and matching_rights(instance, related_objects) is None:
            check("rights-projection", [error("WP2", "/rights_ref", "未同时提供所引用具体版本的 RightsRecord，贡献者/许可一致性需解析服务（WP2）")], "skipped")
        check("resource-registries", [error("WP2", "", "资源类型/适用对象/教育用途、国家分类适用性、BCP47与IANA注册、学校许可代码与存储控制需权威登记服务")], "skipped")
    if target in ["MethodRegistration", "MethodApproval", "CognitiveState"]:
        check("method-admission", [error("WP2", "", "当前方法准入、量尺值域、验证覆盖和用途范围需运行时权威服务；静态校验不授予用途权限")], "skipped")
    if target == "RightsRecord":
        check("rights-registry", [error("WP2", "", "学校许可代码、用途批准、权利依据及第三方组成真实范围需权威服务核验")], "skipped")
    if target in ["manifest", "export-receipt"]:
        check("package-integrity", [error("WP2", "", "未提供归档字节及权威任务：实际文件摘要、确定性打包、引用闭包、权限、独立恢复和受控回执登记均未核验")], "skipped")
    return {"result": "failed" if any(c["result"] == "failed" for c in checks) else "passed", "checks": checks}


def target_schema(types):
    return {"$ref": BASE + "schema/common.schema.json#/$defs/ObjectRef", "properties": {"object_type": {"enum": types}}, "x-target-types": types}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument("--target")
    parser.add_argument("--stage", choices=["input", "stored", "exchange"], default="input")
    parser.add_argument("--related", type=Path, action="append", default=[], help="同时提供 RightsRecord JSON，可重复")
    args = parser.parse_args()
    try:
        related = [load(p) for p in args.related]
        related = [value.get("instance", value) if isinstance(value, dict) else value for value in related]
        result = validate(load(args.file), args.target, args.stage, related_objects=related)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {"result": "failed", "checks": [{"check": "structure", "result": "failed", "errors": [error("R-INPUT-001", "", str(exc))]}]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
