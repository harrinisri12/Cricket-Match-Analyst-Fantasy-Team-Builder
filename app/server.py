"""
Standard Library HTTP Server Adapter for Cricket Match Analyst & Fantasy Team Builder.
Serves the frontend/ static assets and provides the /api/analyze endpoint for web browsers.
Zero external dependencies (uses Python standard library http.server).
"""

import os
import sys
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import execute_query


class CricketAppHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler that serves the frontend and handles analysis API calls."""

    def __init__(self, *args, **kwargs):
        frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
        super().__init__(*args, directory=frontend_dir, **kwargs)

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        """Handle API requests."""
        if self.path == "/api/analyze":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                post_body = self.rfile.read(content_length).decode("utf-8")
                req_data = json.loads(post_body) if post_body else {}
                query = req_data.get("query", "").strip()

                if not query:
                    self.send_response(400)
                    self._send_cors_headers()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "message": "Query parameter cannot be empty."
                    }).encode("utf-8"))
                    return

                # Execute analysis query through LangGraph
                final_state = execute_query(query)

                response_payload = {
                    "status": "success",
                    "query": query,
                    "intent": final_state.get("intent", "ANALYSIS"),
                    "final_answer": final_state.get("final_answer", ""),
                    "candidate_team": final_state.get("candidate_team", {}),
                    "stats": final_state.get("stats", {}),
                    "news": final_state.get("news", []),
                    "validation_result": final_state.get("validation_result", ""),
                    "validation_errors": final_state.get("validation_errors", [])
                }

                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_payload).encode("utf-8"))

            except Exception as e:
                self.send_response(500)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error",
                    "message": f"Server encountered an issue: {str(e)}"
                }).encode("utf-8"))
        else:
            self.send_error(404, "Endpoint not found.")


def run_server(port: int = 8000, host: str = "0.0.0.0"):
    """Launch the Python standard library HTTP server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, CricketAppHandler)
    display_host = "localhost" if host == "0.0.0.0" else host
    print(f"\n=======================================================")
    print(f" CRICKET MATCH ANALYST & FANTASY BUILDER FRONTEND SERVER")
    print(f"=======================================================")
    print(f" URL: http://{display_host}:{port}")
    print(f" Serving frontend from: frontend/")
    print(f" API Endpoint: http://{display_host}:{port}/api/analyze")
    print(f" Press Ctrl+C to stop the server.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping frontend server. Goodbye!")
        httpd.server_close()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000
    run_server(port=port_arg)
