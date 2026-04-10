from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from folio.core.models import WebLink, WebPageResult


def resolve_web_url(raw_url: str) -> str:
    return raw_url.strip().strip('"')


class WebReaderError(RuntimeError):
    pass


@dataclass(slots=True)
class ReaderDocument:
    title: str
    content: str
    links: list[WebLink]


class _ReaderHTMLParser(HTMLParser):
    BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote"}
    IGNORE_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.links: list[WebLink] = []
        self._current: list[str] = []
        self._blocks: list[str] = []
        self._ignore_depth = 0
        self._in_title = False
        self._title_parts: list[str] = []
        self._current_href: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.IGNORE_TAGS:
            self._ignore_depth += 1
            return
        if self._ignore_depth:
            return
        if tag == "title":
            self._in_title = True
            return
        if tag in self.BLOCK_TAGS:
            self._flush_block()
            if tag == "li":
                self._current.append("• ")
        elif tag == "br":
            self._flush_block()
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._current_href = urljoin(self.base_url, href)
                self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self.IGNORE_TAGS:
            self._ignore_depth = max(0, self._ignore_depth - 1)
            return
        if self._ignore_depth:
            return
        if tag == "title":
            self._in_title = False
            self.title = " ".join(self._title_parts).strip()
            return
        if tag == "a" and self._current_href is not None:
            text = " ".join(self._current_link_text).strip()
            if text:
                index = len(self.links) + 1
                self.links.append(WebLink(index=index, text=text, url=self._current_href))
                self._current.append(f" [{index}]")
            self._current_href = None
            self._current_link_text = []
            return
        if tag in self.BLOCK_TAGS:
            self._flush_block()

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
            return
        if self._current and not self._current[-1].endswith((" ", "\n", "• ")):
            self._current.append(" ")
        self._current.append(text)
        if self._current_href is not None:
            self._current_link_text.append(text)

    def close(self) -> ReaderDocument:
        super().close()
        self._flush_block()
        title = self.title or "Untitled page"
        content = "\n\n".join(block for block in self._blocks if block).strip() or "(no readable text extracted)"
        return ReaderDocument(title=title, content=content, links=self.links)

    def _flush_block(self) -> None:
        text = "".join(self._current).strip()
        if text:
            self._blocks.append(text)
        self._current = []


class WebReader:
    DEFAULT_USER_AGENT = "FolioWebReader/0.1"

    def fetch(
        self,
        key: str,
        url: str,
        *,
        allowed_origins: list[str] | None = None,
        max_fetch_bytes: int = 262144,
        timeout_seconds: float = 5.0,
    ) -> WebPageResult:
        try:
            self._check_url(url, allowed_origins or [])
            request = Request(
                url,
                headers={
                    "User-Agent": self.DEFAULT_USER_AGENT,
                    "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
                },
            )
            with urlopen(request, timeout=timeout_seconds) as response:
                final_url = response.geturl()
                content_type = response.headers.get_content_type()
                charset = response.headers.get_content_charset() or "utf-8"
                raw = response.read(max_fetch_bytes + 1)
                truncated = len(raw) > max_fetch_bytes
                raw = raw[:max_fetch_bytes]
        except Exception as exc:
            return WebPageResult(
                key=key,
                status="error",
                url=url,
                title="Fetch failed",
                content="",
                error=str(exc),
            )

        text = raw.decode(charset, errors="replace")
        if content_type == "text/plain":
            content = text.strip() or "(empty response)"
            if truncated:
                content += "\n\n[truncated]"
            return WebPageResult(
                key=key,
                status="ok",
                url=final_url,
                title=urlparse(final_url).netloc or final_url,
                content=content,
                links=[],
                content_type=content_type,
            )

        document = self._reader_document(text, final_url)
        content = document.content
        if truncated:
            content += "\n\n[truncated]"
        return WebPageResult(
            key=key,
            status="ok",
            url=final_url,
            title=document.title,
            content=content,
            links=document.links,
            content_type=content_type,
        )

    def _reader_document(self, html: str, base_url: str) -> ReaderDocument:
        parser = _ReaderHTMLParser(base_url)
        parser.feed(html)
        return parser.close()

    def _check_url(self, url: str, allowed_origins: list[str]) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise WebReaderError("only http and https URLs are supported")
        host = (parsed.hostname or "").lower()
        if not host:
            raise WebReaderError("URL host is missing")
        if "*" in allowed_origins or not allowed_origins:
            return
        for origin in allowed_origins:
            normalized = origin.lower()
            if host == normalized or host.endswith(f".{normalized}"):
                return
        raise WebReaderError(f"origin '{host}' is not allowed by renderer manifest")
