from __future__ import annotations

from folio.core.web_reader import WebReader, WebReaderError


def test_web_reader_extracts_readable_text_and_links() -> None:
    html = """
    <html>
      <head><title>Example article</title></head>
      <body>
        <main>
          <h1>Launch Notes</h1>
          <p>This is the first paragraph.</p>
          <p>Read the <a href="/docs">documentation</a> next.</p>
        </main>
      </body>
    </html>
    """

    document = WebReader()._reader_document(html, "https://example.test/article")

    assert document.title == "Example article"
    assert "Launch Notes" in document.content
    assert "This is the first paragraph." in document.content
    assert len(document.links) == 1
    assert document.links[0].text == "documentation"
    assert document.links[0].url == "https://example.test/docs"


def test_web_reader_blocks_disallowed_origins_and_non_http_urls() -> None:
    reader = WebReader()

    try:
        reader._check_url("file:///tmp/example.html", ["*"])
    except WebReaderError as exc:
        assert "http and https" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected file URL to be rejected")

    try:
        reader._check_url("https://news.example.com/story", ["example.org"])
    except WebReaderError as exc:
        assert "not allowed" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected disallowed origin to be rejected")
