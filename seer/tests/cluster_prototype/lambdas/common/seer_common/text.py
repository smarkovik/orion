"""Pure text and URL helpers shared by scrape and ingest."""

import re
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

DROP_PARAMS = ("utm_", "at_")
DROP_EXACT = {"fbclid", "gclid"}
BLOCK_TAGS = {"p", "br", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr", "figure"}
SKIP_TAGS = {"script", "style"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str, keep_breaks: bool = True) -> str:
    parser = _TextExtractor()
    parser.feed(html or "")
    parser.close()
    text = unescape("".join(parser.parts)).replace("\xa0", " ")
    if not keep_breaks:
        return re.sub(r"\s+", " ", text).strip()
    lines = (re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


def canonical_url(link: str) -> str:
    parts = urlsplit(link.strip())
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if parts.port:
        host = f"{host}:{parts.port}"
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k not in DROP_EXACT and not k.startswith(DROP_PARAMS)
    ]
    return urlunsplit((parts.scheme.lower(), host, parts.path, urlencode(query), ""))


def absolute_image(url: Any, base: str) -> str | None:
    if not isinstance(url, str) or not url.strip() or url.strip().startswith("data:"):
        return None
    full = urljoin(base, url.strip())
    return full if full.startswith(("http://", "https://")) else None


def parse_utc(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
