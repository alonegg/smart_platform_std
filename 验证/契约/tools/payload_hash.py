"""7.6.4 / E13 候选摘要算法，H-11；不做 Unicode 规范化。"""
import hashlib
import json


def canonical_json(body):
    return json.dumps(body, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def payload_hash(event, members, *, serializer=canonical_json):
    body = {key: event[key] for key in members if key in event
            and key not in {"event_id", "received_at", "auth_context", "payload_hash", "payload"}}
    body["payload"] = event["payload"]
    return hashlib.sha256(serializer(body)).hexdigest()
