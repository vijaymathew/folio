from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


MutationKind = Literal["append", "replace", "delete"]


@dataclass(slots=True)
class Directive:
    type: str
    id: str | None
    params: dict[str, str]
    body: list[str]
    start_line: int
    end_line: int
    header_line: str
    is_block: bool

    def key(self) -> str:
        return self.id or str(self.start_line)

    def instance_key(self) -> str:
        return f"{self.type}:{self.key()}"

    def title(self) -> str:
        ident = f"[{self.id}]" if self.id else ""
        return f"::{self.type}{ident}"

    def header_text(self) -> str:
        ident = f"[{self.id}]" if self.id else ""
        if not self.params:
            return f"::{self.type}{ident}"
        items = " ".join(f"{key}={value}" for key, value in self.params.items())
        return f"::{self.type}{ident}{{{items}}}"


@dataclass(slots=True)
class ProseBlock:
    lines: list[str]
    start_line: int
    end_line: int


@dataclass(slots=True)
class DirectiveIndex:
    ordered: list[Directive] = field(default_factory=list)
    by_id: dict[str, Directive] = field(default_factory=dict)
    by_key: dict[str, Directive] = field(default_factory=dict)
    by_type_and_key: dict[tuple[str, str], Directive] = field(default_factory=dict)
    by_type: dict[str, list[Directive]] = field(default_factory=dict)
    by_start_line: dict[int, list[Directive]] = field(default_factory=dict)

    @classmethod
    def build(cls, directives: list[Directive]) -> DirectiveIndex:
        by_id: dict[str, Directive] = {}
        by_key: dict[str, Directive] = {}
        by_type_and_key: dict[tuple[str, str], Directive] = {}
        by_type: dict[str, list[Directive]] = {}
        by_start_line: dict[int, list[Directive]] = {}

        for directive in directives:
            key = directive.key()
            by_key.setdefault(key, directive)
            by_type_and_key[(directive.type, key)] = directive
            if directive.id is not None:
                by_id.setdefault(directive.id, directive)
            by_type.setdefault(directive.type, []).append(directive)
            by_start_line.setdefault(directive.start_line, []).append(directive)

        return cls(
            ordered=directives,
            by_id=by_id,
            by_key=by_key,
            by_type_and_key=by_type_and_key,
            by_type=by_type,
            by_start_line=by_start_line,
        )

    def find(self, directive_type: str, target: str) -> Directive | None:
        return self.by_type_and_key.get((directive_type, target))

    def directives_of_type(self, directive_type: str) -> list[Directive]:
        return self.by_type.get(directive_type, [])

    def directives_starting_at(self, line_no: int) -> list[Directive]:
        return self.by_start_line.get(line_no, [])


@dataclass(slots=True)
class DocumentModel:
    text: str
    directives: list[Directive] = field(default_factory=list)
    prose: list[ProseBlock] = field(default_factory=list)
    directive_index: DirectiveIndex = field(default_factory=DirectiveIndex)


@dataclass(slots=True)
class TextMutation:
    kind: MutationKind
    start_line: int
    end_line: int
    new_text: str
    source: str


@dataclass(slots=True)
class PyBlockResult:
    key: str
    status: str
    stdout: list[str]
    error: str | None
    context: dict[str, object] = field(default_factory=dict)
    table: list[dict[str, object]] | None = None


@dataclass(slots=True)
class ShRunResult:
    key: str
    command: str
    cwd: str
    exit_code: int
    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: str = ""
    error: str | None = None


@dataclass(slots=True)
class WebLink:
    index: int
    text: str
    url: str


@dataclass(slots=True)
class WebPageResult:
    key: str
    status: str
    url: str
    title: str
    content: str
    error: str | None = None
    links: list[WebLink] = field(default_factory=list)
    content_type: str = "text/plain"
