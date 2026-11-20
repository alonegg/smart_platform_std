"""8.6/8.7、9.2.4；OBJ-029/034/044；HTTP 不替代业务回执。"""
import inspect
import json
import re
import threading
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from helpers import ROOT, Service, ServiceCase, fixture, ref
from server import ReferenceHTTPServer, ROUTES


class HTTPTests(ServiceCase):
    def setUp(self):
        super().setUp()
        self.http = ReferenceHTTPServer(("127.0.0.1", 0), self.s)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()

    def request(self, method, path, body=None, token=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        request = Request(f"http://127.0.0.1:{self.http.server_port}" + path, data=data, method=method,
                          headers={"Authorization": "Bearer " + (token or self.admin), "Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def test_T05_positive_http_accept_query_receipt(self):
        """7.6、8.7；OBJ-029；事件受理与回执查询通过 HTTP。"""
        code, receipt = self.request("POST", "/events", self.event(), self.token())
        self.assertEqual(code, 200)
        self.ok(receipt)
        code, queried = self.request("GET", "/receipts/" + quote(receipt["receipt_id"], safe=""), token=self.token())
        self.assertEqual(code, 200)
        self.assertEqual(queried, receipt)

    def test_T25_reject_http_forged_fields_and_bad_json(self):
        """7.2.3、8.7；OBJ-029；HTTP 200 也可能是业务拒收。"""
        code, receipt = self.request("POST", "/events", self.event(event_id="forged"), self.token())
        self.assertEqual(code, 200)
        self.denied(receipt)
        _, queried = self.request("GET", "/receipts/" + quote(receipt["receipt_id"], safe=""))
        self.assertEqual(queried, receipt)
        code, receipt = self.request("POST", "/events", token=self.token(), raw=b"{")
        self.assertEqual(code, 400)
        self.denied(receipt)

    def test_T08_C_reject_http_client_credentials_confirmation(self):
        """7.5、9.2.4；OBJ-034/044；服务凭证不得确认。"""
        proposal = self.proposal()
        service_grant = fixture("AccessGrant")
        service_grant.update(object_id="https://example.edu/accessgrant/http-service", scopes=["grade.propose", "events.write"])
        self.ok(self.s.issue_grant(self.admin, service_grant))
        decision = fixture("GradeDecision")
        decision.pop("proposer_type")
        decision.update(object_id="https://example.edu/gradedecision/http-confirmation", decision_status="confirmed", decider_type="staff", decided_by=self.grant["subject_ref"], handles_proposal_ref=ref(proposal))
        code, result = self.request("POST", "/grades/confirmations", {"decision": decision}, self.token(service_grant))
        self.assertEqual(code, 200)
        self.denied(result)

    def test_openapi_routes_match_service(self):
        """8.11；OBJ-029；手写 OpenAPI 与全部 Service 路由一一对应。"""
        documented = set()
        path = None
        operation = None
        for line in (ROOT / "openapi.yaml").read_text().splitlines():
            if re.match(r"^  /.*:$", line):
                path = line.strip()[:-1]
            elif re.match(r"^    (get|post):$", line):
                operation = line.strip()[:-1].upper()
            elif line.startswith("      operationId:"):
                documented.add((operation, path, line.split(":", 1)[1].strip()))
        self.assertEqual(documented, {(verb, path, method) for verb, path, method, _ in ROUTES})
        public = {name for name, fn in inspect.getmembers(Service, inspect.isfunction) if not name.startswith("_")}
        self.assertEqual(public, {r[2] for r in ROUTES})
