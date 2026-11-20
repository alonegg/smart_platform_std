"""8.6/8.7；OBJ-029/042/044；仅回环地址上的合成 HTTP 参考接口。"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from urllib.parse import parse_qs, unquote, urlsplit

from service import Service


# HTTP method, path template, Service method, optional path argument.
ROUTES = (
    ("POST", "/applications", "register_application", None),
    ("POST", "/applications/status", "set_application_status", None),
    ("POST", "/applications/rotate-key", "rotate_key", None),
    ("POST", "/grants", "issue_grant", None),
    ("POST", "/grants/validate", "validate_grant", None),
    ("POST", "/grants/subscriptions", "subscribe", None),
    ("POST", "/grants/{id}/revoke", "revoke_grant", "grant_ref"),
    ("POST", "/tokens", "issue_token", None),
    ("POST", "/events", "accept_event", None),
    ("GET", "/events", "query_events", None),
    ("GET", "/receipts/{id}", "get_receipt", "receipt_id"),
    ("GET", "/reconciliation", "reconcile", None),
    ("GET", "/conflicts", "conflicts", None),
    ("GET", "/notifications", "notifications", None),
    ("POST", "/pseudonyms", "pseudonym", None),
    ("POST", "/pseudonyms/resolve", "resolve_pseudonym", None),
    ("POST", "/teaching-assignments", "register_teaching_assignment", None),
    ("POST", "/grades/proposals", "propose_grade", None),
    ("POST", "/grades/confirmations", "confirm_grade", None),
    ("POST", "/grades/registrar-receipts", "registrar_receipt", None),
    ("GET", "/grades", "grade_view", None),
    ("POST", "/methods", "register_method", None),
    ("POST", "/methods/approvals", "approve_method", None),
    ("POST", "/methods/status", "set_method_status", None),
    ("POST", "/methods/check", "check_method_use", None),
    ("POST", "/methods/history", "method_history", None),
    ("POST", "/ai/admission", "admit_ai_output", None),
    ("GET", "/audit", "audit_log", None),
    ("POST", "/audit/verify", "verify", None),
)


class ReferenceHTTPServer(ThreadingHTTPServer):
    """8.7；OBJ-029；并发 HTTP 请求在服务事务边界串行化。"""

    daemon_threads = True

    def __init__(self, address, service):
        self.service = service
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    """8.7；OBJ-029；HTTP 状态不替代 JSON 中的业务结果。"""

    max_body = 1024 * 1024

    def log_message(self, *args):
        pass

    def _send(self, code, result):
        body = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _reject(self, code, reason, token, event_endpoint=False):
        s = self.server.service
        with s.lock, s.db:
            if event_endpoint:
                receipt = s._receipt("rejected", reason)
                s._audit("http_request", {}, "rejected", reason, receipt["receipt_id"])
                result = receipt
            else:
                s._audit("http_request", {}, "rejected", reason)
                result = {"status": "rejected", "reason": reason}
        self._send(code, result)

    def _dispatch(self):
        url = urlsplit(self.path)
        token = self.headers.get("Authorization", "")
        token = token[7:] if token.startswith("Bearer ") else ""
        event_endpoint = self.command == "POST" and url.path == "/events"
        matches = []
        for verb, template, method, argument in ROUTES:
            match = re.fullmatch(re.escape(template).replace(r"\{id\}", r"([^/]+)"), url.path)
            if verb == self.command and match:
                matches.append((method, argument, match))
        if not matches:
            self._reject(404, "unknown route or unsupported HTTP method", token)
            return
        try:
            method, argument, match = matches[0]
            if self.command == "POST":
                if self.headers.get("Transfer-Encoding"):
                    raise ValueError("transfer encoding unsupported")
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Content-Type must be application/json")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= self.max_body:
                    raise ValueError("request body size outside limit")
                data = json.loads(self.rfile.read(length), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON number")))
                if not isinstance(data, dict):
                    raise ValueError("JSON body must be an object")
                if event_endpoint:
                    data = {"event": data}
            else:
                query = parse_qs(url.query, keep_blank_values=True)
                if any(len(v) != 1 for v in query.values()):
                    raise ValueError("query parameters must not repeat")
                data = {k: v[0] for k, v in query.items()}
                if "formal" in data:
                    if data["formal"] not in ("true", "false"):
                        raise ValueError("formal must be true or false")
                    data["formal"] = data["formal"] == "true"
            if argument:
                value = unquote(match.group(1))
                if argument in data:
                    raise ValueError("path argument duplicated in request body")
                data[argument] = ({"object_type": "AccessGrant", "object_id": value,
                                   "version_id": data.pop("version_id", "v1")}
                                  if argument == "grant_ref" else value)
            if "c" in data or "token" in data or "self" in data:
                raise ValueError("authentication is only accepted in Authorization header")
            result = getattr(self.server.service, method)(token, **data)
            self._send(200, result)
        except (ValueError, TypeError, UnicodeError) as exc:
            self._reject(400, str(exc), token, event_endpoint)

    do_POST = _dispatch
    do_GET = _dispatch
    do_PUT = _dispatch
    do_PATCH = _dispatch
    do_DELETE = _dispatch
    do_OPTIONS = _dispatch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8700)
    parser.add_argument("--db", default=":memory:")
    parser.add_argument("--bootstrap", action="store_true", help="print synthetic admin bearer token at startup")
    args = parser.parse_args()
    service = Service(args.db)
    server = ReferenceHTTPServer(("127.0.0.1", args.port), service)
    if args.bootstrap:
        print(json.dumps({"admin_token": service.admin_token, "warning": "synthetic tests only"}), flush=True)
    print(f"Listening on http://127.0.0.1:{server.server_port} (synthetic data only)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.db.close()


if __name__ == "__main__":
    main()
