"""Serve the site folder and log every request in CloudFront standard-log format (standard library only)."""

import argparse
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlsplit

FIELDS = (
    "date time x-edge-location sc-bytes c-ip cs-method cs(Host) cs-uri-stem sc-status cs(Referer) cs(User-Agent) "
    "cs-uri-query cs(Cookie) x-edge-result-type x-edge-request-id x-host-header cs-protocol cs-bytes time-taken "
    "x-forwarded-for ssl-protocol ssl-cipher x-edge-response-result-type cs-protocol-version fle-status "
    "fle-encrypted-fields c-port time-to-first-byte x-edge-detailed-result-type sc-content-type sc-content-len "
    "sc-range-start sc-range-end"
).split()
_lock = threading.Lock()


def _v(value: str | None) -> str:
    return quote(value, safe="/:;=,+@&?%.-_~") if value else "-"


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".webmanifest": "application/manifest+json",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".xml": "application/xml",
        ".js": "text/javascript",
        ".json": "application/json",
    }
    protocol_version = "HTTP/1.1"
    logs: Path = Path(".")

    def end_headers(self) -> None:
        if urlsplit(self.path).path.endswith("/p.gif"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        now = datetime.now(timezone.utc)
        url = urlsplit(self.path)
        ctype = self.extensions_map.get(Path(url.path).suffix.lower(), "-")
        row = {
            "date": f"{now:%Y-%m-%d}",
            "time": f"{now:%H:%M:%S}",
            "x-edge-location": "PRV1-P1",
            "sc-bytes": str(size),
            "c-ip": "-",
            "cs-method": self.command,
            "cs(Host)": _v(self.headers.get("Host")),
            "cs-uri-stem": _v(url.path),
            "sc-status": str(code),
            "cs(Referer)": _v(self.headers.get("Referer")),
            "cs(User-Agent)": _v(self.headers.get("User-Agent")),
            "cs-uri-query": _v(url.query),
            "cs(Cookie)": "-",
            "x-edge-result-type": "Miss",
            "x-edge-request-id": "-",
            "x-host-header": _v(self.headers.get("Host")),
            "cs-protocol": "http",
            "cs-bytes": "-",
            "time-taken": "0.001",
            "x-forwarded-for": "-",
            "ssl-protocol": "-",
            "ssl-cipher": "-",
            "x-edge-response-result-type": "Miss",
            "cs-protocol-version": self.request_version,
            "fle-status": "-",
            "fle-encrypted-fields": "-",
            "c-port": "-",
            "time-to-first-byte": "0.001",
            "x-edge-detailed-result-type": "Miss",
            "sc-content-type": ctype,
            "sc-content-len": str(size),
            "sc-range-start": "-",
            "sc-range-end": "-",
        }
        path = self.logs / f"preview.{now:%Y-%m-%d-%H}.log"
        with _lock:
            fresh = not path.exists()
            with path.open("a", encoding="utf-8") as f:
                if fresh:
                    f.write("#Version: 1.0\n#Fields: " + " ".join(FIELDS) + "\n")
                f.write("\t".join(row[k] for k in FIELDS) + "\n")

    def log_message(self, fmt: str, *args: object) -> None:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--directory", default="data/s3/seer-site")
    ap.add_argument("--logs", default="data/logs/cloudfront")
    args = ap.parse_args()
    Handler.logs = Path(args.logs)
    Handler.logs.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("", args.port), partial(Handler, directory=args.directory))
    print(f"Serving {args.directory} on http://localhost:{args.port}/ ; logs in {args.logs}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
