"""Dev server: builds, serves dist/ on http://localhost:4173, and rebuilds when lang/, registry/ or site/ change.

    python scripts/serve.py            (PORT=8000 to change the port)

If a rebuild fails validation, the last good dist/ keeps being served and the errors are printed.
"""
import os
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from build_site import DIST_DIR, LANG_DIR, REGISTRY_DIR, SITE_DIR, build

PORT = int(os.environ.get("PORT", "4173"))
WATCHED = (LANG_DIR, REGISTRY_DIR, SITE_DIR)


class Handler(SimpleHTTPRequestHandler):
    # Windows' registry sometimes maps .js to text/plain, which breaks module scripts.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".json": "application/json",
        ".css": "text/css",
        ".html": "text/html",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def snapshot():
    files = [p for d in WATCHED for p in d.rglob("*") if p.is_file()]
    return len(files), max((p.stat().st_mtime_ns for p in files), default=0)


def watch():
    last = snapshot()
    while True:
        time.sleep(0.5)
        try:
            current = snapshot()
            if current != last:
                last = current
                print("\nChange detected, rebuilding...")
                build()
        except Exception as exc:  # keep the server alive through half-saved files
            print(f"rebuild error: {exc}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    if not build():
        sys.exit(1)
    threading.Thread(target=watch, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=str(DIST_DIR)))
    print(f"\nServing http://localhost:{PORT}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
