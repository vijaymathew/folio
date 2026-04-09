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
class DocumentModel:
    text: str
    directives: list[Directive] = field(default_factory=list)
    prose: list[ProseBlock] = field(default_factory=list)


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
