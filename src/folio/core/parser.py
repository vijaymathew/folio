from __future__ import annotations

import re

from .models import Directive, DocumentModel, ProseBlock


DIRECTIVE_RE = re.compile(r"^::(?P<type>[a-zA-Z0-9:_-]+)(?:\[(?P<id>[^\]]+)\])?(?:\{(?P<params>.*)\})?$")
PARAM_RE = re.compile(r'([a-zA-Z0-9:_-]+)=(".*?"|\S+)')


class DirectiveParser:
    def parse(self, text: str) -> DocumentModel:
        lines = text.splitlines()
        directives: list[Directive] = []
        prose: list[ProseBlock] = []
        prose_buffer: list[str] = []
        prose_start = 0
        line_no = 0

        while line_no < len(lines):
            raw = lines[line_no]
            match = DIRECTIVE_RE.match(raw.strip())
            if not match or match.group("type") == "end":
                if not prose_buffer:
                    prose_start = line_no
                prose_buffer.append(raw)
                line_no += 1
                continue

            if prose_buffer:
                prose.append(
                    ProseBlock(
                        lines=prose_buffer[:],
                        start_line=prose_start,
                        end_line=line_no - 1,
                    )
                )
                prose_buffer.clear()

            params = self._parse_params(match.group("params") or "")
            directive_type = match.group("type")
            directive_id = match.group("id")
            start_line = line_no
            body: list[str] = []
            is_block = False

            if line_no + 1 < len(lines):
                probe = line_no + 1
                while probe < len(lines):
                    probe_raw = lines[probe].strip()
                    if DIRECTIVE_RE.match(probe_raw):
                        if probe_raw == "::end":
                            is_block = True
                            body = lines[line_no + 1 : probe]
                            line_no = probe
                        break
                    probe += 1

            directives.append(
                Directive(
                    type=directive_type,
                    id=directive_id,
                    params=params,
                    body=body,
                    start_line=start_line,
                    end_line=line_no,
                    header_line=raw,
                    is_block=is_block,
                )
            )
            line_no += 1

        if prose_buffer:
            prose.append(
                ProseBlock(
                    lines=prose_buffer,
                    start_line=prose_start,
                    end_line=len(lines) - 1,
                )
            )

        return DocumentModel(text=text, directives=directives, prose=prose)

    def _parse_params(self, raw: str) -> dict[str, str]:
        params: dict[str, str] = {}
        for key, value in PARAM_RE.findall(raw):
            params[key] = value
        return params
