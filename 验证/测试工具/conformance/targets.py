"""8.6/8.7；OBJ-029/042/044；WP2 JSON 接口适配。"""
import json
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from . import ROOT

ROUTES = {
    "register_application": ("POST", "/applications"),
    "set_application_status": ("POST", "/applications/status"),
    "rotate_key": ("POST", "/applications/rotate-key"),
    "issue_grant": ("POST", "/grants"),
    "validate_grant": ("POST", "/grants/validate"),
    "subscribe": ("POST", "/grants/subscriptions"),
    "revoke_grant": ("POST", "/grants/{grant_ref}/revoke"),
    "issue_token": ("POST", "/tokens"),
    "accept_event": ("POST", "/events"),
    "query_events": ("GET", "/events"),
    "get_receipt": ("GET", "/receipts/{receipt_id}"),
    "reconcile": ("GET", "/reconciliation"),
    "conflicts": ("GET", "/conflicts"),
    "notifications": ("GET", "/notifications"),
    "pseudonym": ("POST", "/pseudonyms"),
    "resolve_pseudonym": ("POST", "/pseudonyms/resolve"),
    "register_teaching_assignment": ("POST", "/teaching-assignments"),
    "propose_grade": ("POST", "/grades/proposals"),
    "confirm_grade": ("POST", "/grades/confirmations"),
    "registrar_receipt": ("POST", "/grades/registrar-receipts"),
    "grade_view": ("GET", "/grades"),
    "register_method": ("POST", "/methods"),
    "approve_method": ("POST", "/methods/approvals"),
    "set_method_status": ("POST", "/methods/status"),
    "check_method_use": ("POST", "/methods/check"),
    "method_history": ("POST", "/methods/history"),
    "admit_ai_output": ("POST", "/ai/admission"),
    "audit_log": ("GET", "/audit"),
    "verify": ("POST", "/audit/verify"),
}


class InProcess:
    def __init__(self, service):
        self.service = service
        self.admin_token = service.admin_token

    def call(self, method, token, /, **kwargs):
        return getattr(self.service, method)(token, **kwargs)

    def close(self):
        self.service.db.close()


class HTTP:
    def __init__(self, url, admin_token=None):
        parts = urlsplit(url)
        if parts.scheme != "http" or not parts.netloc or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("target must be an http:// URL without credentials/query/fragment")
        self.url = url.rstrip("/")
        self.admin_token = admin_token

    def call(self, method, token, /, **kwargs):
        verb, path = ROUTES[method]
        data = dict(kwargs)
        for argument in ("receipt_id", "grant_ref"):
            if "{" + argument + "}" in path:
                value = data.pop(argument)
                if isinstance(value, dict):
                    data["version_id"] = value.get("version_id", "v1")
                    value = value["object_id"]
                path = path.replace("{" + argument + "}", quote(value, safe=""))
        body = None
        if verb == "GET":
            data = {k: str(v).lower() if isinstance(v, bool) else v for k, v in data.items()}
            path += "?" + urlencode(data)
        else:
            body = json.dumps(data["event"] if method == "accept_event" else data, allow_nan=False).encode()
        request = Request(self.url + path, data=body, method=verb,
                          headers={"Authorization": "Bearer " + (token or ""), "Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as exc:
            response = exc
        with response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise ValueError("target response must be a JSON object")
        return result

    def close(self):
        pass


def open_target(target, admin_token=None):
    if target.startswith("http://"):
        return HTTP(target, admin_token)
    sys.path.insert(0, str(ROOT.parent / "参考公共服务"))
    from service import Service
    if target == "inproc:reference":
        return InProcess(Service())
    if target.startswith("inproc:bad:"):
        from bad_impls import REGISTRY
        name = target.removeprefix("inproc:bad:")
        if name in REGISTRY:
            return InProcess(REGISTRY[name]())
        raise ValueError("unregistered defect: " + name)
    raise ValueError("unsupported target")
