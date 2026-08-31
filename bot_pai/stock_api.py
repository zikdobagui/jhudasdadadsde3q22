import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from stock_storage import add_access, reserve_first, stock_summary


class StockAPI:
    def __init__(self, api_key):
        self.api_key = api_key

    def handler(self):
        api_key = self.api_key

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/health":
                    self.send_json(200, {"status": "ok"})
                    return
                if path in ("/api/stock", "/api/stock/summary"):
                    if not self.authorized(api_key):
                        self.send_json(401, {"error": "unauthorized"})
                        return
                    self.send_json(200, {"stock": stock_summary()})
                    return
                self.send_json(404, {"error": "not_found"})

            def do_POST(self):
                path = urlparse(self.path).path
                if not self.authorized(api_key):
                    self.send_json(401, {"error": "unauthorized"})
                    return

                body = self.read_json()
                if body is None:
                    self.send_json(400, {"error": "invalid_json"})
                    return

                if path == "/api/stock/reserve":
                    access = reserve_first(
                        body.get("service"),
                        body.get("child_bot_id", ""),
                        body.get("buyer_id", ""),
                        body.get("sale_id", ""),
                    )
                    if not access:
                        self.send_json(404, {"error": "out_of_stock"})
                        return
                    self.send_json(200, {"access": access})
                    return

                if path == "/api/stock/add":
                    ok, result = add_access(body)
                    if not ok:
                        self.send_json(400, {"error": result})
                        return
                    self.send_json(201, {"access": result})
                    return

                self.send_json(404, {"error": "not_found"})

            def authorized(self, expected_key):
                received = self.headers.get("X-Stock-Key", "")
                return bool(expected_key) and received == expected_key

            def read_json(self):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw = self.rfile.read(length)
                    return json.loads(raw.decode("utf-8") or "{}")
                except Exception:
                    return None

            def send_json(self, status, payload):
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                pass

        return Handler


def run_stock_api(host, port, api_key):
    try:
        server = ThreadingHTTPServer((host, int(port)), StockAPI(api_key).handler())
    except PermissionError:
        if int(port) != 80:
            raise
        fallback_port = 8080
        print(f"[STOCK API] Sem permissao para porta 80. Usando porta local {fallback_port}.")
        server = ThreadingHTTPServer((host, fallback_port), StockAPI(api_key).handler())
        port = fallback_port
    print(f"[STOCK API] Rodando em {host}:{port}")
    server.serve_forever()
