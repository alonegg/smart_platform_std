"""仅回环地址上的合成坏实现 HTTP 托管；不用于生产或真实数据。"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bad_impls import REGISTRY
from server import ReferenceHTTPServer


def make_server(name, port=0):
    service = REGISTRY[name]()
    try:
        return ReferenceHTTPServer(("127.0.0.1", port), service)
    except Exception:
        service.db.close()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=sorted(REGISTRY))
    parser.add_argument("--port", type=int, default=8701)
    parser.add_argument("--bootstrap", action="store_true", help="仅输出本次合成管理员凭证")
    args = parser.parse_args()
    server = make_server(args.name, args.port)
    if args.bootstrap:
        print(json.dumps({"admin_token": server.service.admin_token, "warning": "synthetic defective service only"}), flush=True)
    print(f"Deliberately defective {args.name}: http://127.0.0.1:{server.server_port} (synthetic only)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.service.db.close()


if __name__ == "__main__":
    main()
