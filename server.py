"""HTTP API for the seller agent (standard library only).

    python server.py --port 8080
    docker build -t fairdeal . && docker run -p 8080:8080 fairdeal

Endpoints
    GET  /health                  -> {"ok": true}
    GET  /agent-card              -> agent_card.json
    POST /negotiate               body: {"session_id": "abc", "message": {...buyer JSON...}}
                                  -> the seller's reply (same JSON the harness gets)
    POST /reset                   body: {"session_id": "abc"}  (start a new negotiation)

Each session is its own negotiation with its own agent state. Sessions idle for
30 minutes are dropped. Requests for one session are handled one at a time.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from seller import SellerAgent

ROOT = Path(__file__).resolve().parent
CARD = json.loads((ROOT / "agent_card.json").read_text())
TTL = 30 * 60
MAX_BODY = 64 * 1024


class Sessions:
    def __init__(self):
        self.lock = threading.Lock()
        self.items: dict[str, tuple] = {}  # id -> (agent, lock, last_used)
        self.template = SellerAgent()      # loads store + policy once

    def get(self, sid: str):
        now = time.time()
        with self.lock:
            for k in [k for k, v in self.items.items() if now - v[2] > TTL]:
                del self.items[k]
            if sid not in self.items:
                self.items[sid] = (self.template.fork(), threading.Lock(), now)
            agent, lk, _ = self.items[sid]
            self.items[sid] = (agent, lk, now)
            return agent, lk

    def drop(self, sid: str):
        with self.lock:
            self.items.pop(sid, None)


SESSIONS = Sessions()


class Handler(BaseHTTPRequestHandler):
    server_version = "fairdeal/1.0"

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("body too large")
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw or b"{}")

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True})
        if self.path == "/agent-card":
            return self._send(200, CARD)
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = self._body()
        except Exception as e:  # bad JSON or oversized body
            return self._send(400, {"error": str(e)})
        sid = str(body.get("session_id") or "default")[:128]
        if self.path == "/reset":
            SESSIONS.drop(sid)
            return self._send(200, {"ok": True, "session_id": sid})
        if self.path == "/negotiate":
            agent, lk = SESSIONS.get(sid)
            with lk:
                reply = agent.respond(body.get("message", {}))
            return self._send(200, reply)
        return self._send(404, {"error": "not found"})

    def log_message(self, *args):  # keep stdout quiet under load
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()
    print(f"FairDeal AI seller agent on http://{a.host}:{a.port}")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
