"""Phone / browser front end and the JSON-over-TCP API server.

* `WebServer`: `GET /` serves a single-page touch UI (two virtual sticks, behaviour buttons, e-stop, status); `POST /api` takes one Command
  API v1 JSON message and returns the reply; `GET /api/status` returns the status snapshot. Stdlib only (http.server), no internet needed:
  the phone joins the robot's Wi-Fi hotspot and opens http://<robot-ip>:8080. Binds 127.0.0.1 unless told otherwise; an optional `token` is
  required in the `X-Token` header (the page reads it from the URL fragment, never sent to a third party).
* `JsonLineServer`: one JSON object per line over TCP, one reply line per request. This is the documented transport for an off-board LLM /
  MCP plugin (`docs/software.md`); the plugin's tools map 1:1 onto the Command API commands.
"""
from __future__ import annotations

import json
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..commands import CommandBus

PAGE = """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1,user-scalable=no">
<title>Adam control</title><style>
body{margin:0;font-family:system-ui,sans-serif;background:#111;color:#eee;touch-action:none;user-select:none}
#top{display:flex;gap:8px;padding:8px;flex-wrap:wrap}button{font-size:18px;padding:12px 16px;border-radius:10px;border:0;background:#2a6;color:#fff}
button.warn{background:#c33}button.alt{background:#456}#st{padding:6px 10px;font:13px monospace;white-space:pre-wrap}
#pads{display:flex;justify-content:space-around;margin-top:8px}canvas{background:#222;border-radius:50%;touch-action:none}
</style></head><body><div id=top>
<button onclick="b('stand')">Stand</button><button onclick="b('wave')">Wave</button><button onclick="b('dance')">Dance</button>
<button onclick="b('pickup')">Pick up</button><button class=alt onclick="s('stop',{})">Stop all</button>
<button class=warn onclick="s('estop',{reason:'phone'})">E-STOP</button><button class=alt onclick="s('reset_estop',{})">Reset e-stop</button></div>
<div id=pads><canvas id=L width=200 height=200></canvas><canvas id=R width=200 height=200></canvas></div><div id=st>connecting...</div>
<script>
const tok=(location.hash||'').slice(1);let vx=0,vy=0,wz=0;
function s(cmd,o){return fetch('/api',{method:'POST',headers:{'X-Token':tok,'Content-Type':'application/json'},body:JSON.stringify(Object.assign({v:1,cmd:cmd},o))}).then(r=>r.json())}
function b(n){s('behaviour',{name:n,params:{}})}
function pad(id,cb){const c=document.getElementById(id),x=c.getContext('2d');let a=false;
function draw(px,py){x.clearRect(0,0,200,200);x.strokeStyle='#666';x.beginPath();x.arc(100,100,90,0,7);x.stroke();x.fillStyle='#2a6';x.beginPath();x.arc(100+px*80,100+py*80,22,0,7);x.fill()}
function mv(e){if(!a)return;const r=c.getBoundingClientRect(),t=e.touches?e.touches[0]:e;let px=((t.clientX-r.left)/r.width-.5)*2,py=((t.clientY-r.top)/r.height-.5)*2;const n=Math.hypot(px,py);if(n>1){px/=n;py/=n}cb(px,py);draw(px,py);e.preventDefault()}
function up(){a=false;cb(0,0);draw(0,0)}c.addEventListener('touchstart',e=>{a=true;mv(e)});c.addEventListener('touchmove',mv);c.addEventListener('touchend',up);
c.addEventListener('mousedown',e=>{a=true;mv(e)});c.addEventListener('mousemove',mv);window.addEventListener('mouseup',up);draw(0,0)}
pad('L',(px,py)=>{vx=-py*0.15;vy=-px*0.07});pad('R',(px,py)=>{wz=-px*0.5});
setInterval(()=>{s('velocity',{vx:vx,vy:vy,wz:wz,ttl:0.4})},100);
setInterval(()=>{fetch('/api/status',{headers:{'X-Token':tok}}).then(r=>r.json()).then(j=>{document.getElementById('st').textContent=JSON.stringify(j.result||j,null,1)})},700);
</script></body></html>"""


def make_handler(bus: CommandBus, token: str | None):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):          # quiet
            pass

        def _ok(self) -> bool:
            if token and self.headers.get("X-Token") != token and not self.path == "/":
                self.send_response(401)
                self.end_headers()
                return False
            return True

        def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/status":
                if self._ok():
                    self._send(200, json.dumps(bus.submit({"v": 1, "cmd": "status"}, "web")).encode())
            else:
                self._send(404, b"{}")

        def do_POST(self):
            if self.path != "/api" or not self._ok():
                return
            n = int(self.headers.get("Content-Length", 0))
            try:
                msg = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError as e:
                self._send(400, json.dumps({"ok": False, "error": {"code": "bad_json", "message": str(e)}}).encode())
                return
            self._send(200, json.dumps(bus.submit(msg, "web")).encode())

    return H


class WebServer:
    def __init__(self, bus: CommandBus, host: str = "127.0.0.1", port: int = 8080, token: str | None = None):
        self.httpd = ThreadingHTTPServer((host, port), make_handler(bus, token))
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self) -> "WebServer":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class JsonLineServer:
    def __init__(self, bus: CommandBus, host: str = "127.0.0.1", port: int = 8765):
        class H(socketserver.StreamRequestHandler):
            def handle(inner):
                for line in inner.rfile:
                    line = line.strip()
                    if not line:
                        continue
                    inner.wfile.write(json.dumps(bus.submit(line.decode(), "tcp")).encode() + b"\n")

        class Srv(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True
            block_on_close = False             # open client connections must not block shutdown
        self.srv = Srv((host, port), H)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)

    def start(self) -> "JsonLineServer":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()
