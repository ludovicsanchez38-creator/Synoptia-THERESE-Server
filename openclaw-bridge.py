"""Micro HTTP bridge pour appeler openclaw agent depuis Docker."""
import json
import logging
import subprocess
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("openclaw-bridge")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            agent = data.get("agent", "")
            message = data.get("message", "")
            timeout = data.get("timeout", 300)

            if not agent or not message:
                self._respond(400, {"error": "agent and message required"})
                return

            logger.info("Running agent=%s timeout=%ds", agent, timeout)
            result = subprocess.run(
                ["openclaw", "agent", "--agent", agent, "--message", message, "--json"],
                capture_output=True, text=True, timeout=timeout,
                env={**os.environ, "HOME": "/home/ubuntu"},
            )

            output = result.stdout
            # Extraire le texte des payloads
            try:
                parsed = json.loads(output)
                # Format: {"runId":..., "result": {"payloads": [{"text": "..."}]}}
                if isinstance(parsed, dict):
                    payloads = None
                    if "result" in parsed and isinstance(parsed["result"], dict):
                        payloads = parsed["result"].get("payloads", [])
                    elif "payloads" in parsed:
                        payloads = parsed["payloads"]
                    if payloads:
                        texts = [p.get("text", "") for p in payloads if p.get("text")]
                        if texts:
                            output = "\n\n".join(texts)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

            logger.info("Agent done, exit=%d, len=%d", result.returncode, len(output))
            self._respond(200, {"output": output, "exit_code": result.returncode})

        except subprocess.TimeoutExpired:
            logger.warning("Timeout after %ds", timeout)
            self._respond(200, {"output": "", "exit_code": -1, "error": "timeout"})
        except Exception as e:
            logger.error("Error: %s", e)
            self._respond(500, {"error": str(e)})

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18800
    server = HTTPServer(("0.0.0.0", port), Handler)
    logger.info("OpenClaw bridge on 0.0.0.0:%d", port)
    server.serve_forever()
