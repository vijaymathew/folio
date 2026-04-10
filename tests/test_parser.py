from __future__ import annotations

from pathlib import Path

from folio.core.parser import DirectiveParser


def test_parser_builds_directive_index_for_example_document() -> None:
    text = Path("/home/vijay/Projects/folio/docs/example.folio").read_text()
    model = DirectiveParser().parse(text)

    assert len(model.directives) == 9
    assert model.directive_index.find("task", "call-finance") is not None
    assert model.directive_index.find("contact", "docs/sample/contacts") is not None
    assert model.directive_index.find("email", "docs/sample/email") is not None
    assert model.directive_index.find("py", "q3-data") is not None
    assert [directive.key() for directive in model.directive_index.directives_of_type("py")] == [
        "q3-data",
        "budget-check",
    ]


def test_parser_indexes_directives_by_start_line() -> None:
    text = """Intro

::task[first]{done="false"}
First task
::end

::py[calc]{run="manual"}
print(1)
::end
"""
    model = DirectiveParser().parse(text)

    task = model.directive_index.find("task", "first")
    py_block = model.directive_index.find("py", "calc")

    assert task is not None
    assert py_block is not None
    assert model.directive_index.directives_starting_at(task.start_line) == [task]
    assert model.directive_index.directives_starting_at(py_block.start_line) == [py_block]


def test_parser_distinguishes_same_id_across_different_directive_types() -> None:
    text = """::sh[check]{cmd="echo ok"}
::sh-output[check]{exit=0 duration="0.1s" ts="2026-04-10T12:00:00"}
[stdout]
ok
::end
"""
    model = DirectiveParser().parse(text)

    sh_block = model.directive_index.find("sh", "check")
    sh_output = model.directive_index.find("sh-output", "check")

    assert sh_block is not None
    assert sh_output is not None
    assert sh_block.type == "sh"
    assert sh_output.type == "sh-output"
