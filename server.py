#!/usr/bin/env python3
"""Minimal server for the PoC — serves poc.html on port 8888."""
import http.server
import os

PORT = int(os.environ.get("PORT", 10000))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)

httpd = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
print(f"PoC server on http://localhost:{PORT}/poc.html")
httpd.serve_forever()
