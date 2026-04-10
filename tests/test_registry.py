from __future__ import annotations

from pathlib import Path

from folio.core.registry import CapabilityRegistry
from folio.renderers.base import RenderContext
from folio.renderers.file import FileRenderer
from folio.renderers.note import NoteRenderer
from folio.renderers.py import PyRenderer
from folio.renderers.table import TableRenderer
from folio.renderers.task import TaskRenderer


def _registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for renderer in (TaskRenderer, PyRenderer, TableRenderer, NoteRenderer, FileRenderer):
        registry.register(renderer)
    return registry


def test_registry_exposes_supported_types_and_manifests() -> None:
    registry = _registry()

    assert registry.supported_types() == ["file", "note", "py", "table", "task"]
    assert registry.manifest_for("task") is TaskRenderer.manifest
    assert registry.manifest_for("py") is PyRenderer.manifest
    assert registry.manifest_for("task").manifest_path == TaskRenderer.manifest_path
    assert '[renderer]\ndirective_type = "task"' in (registry.manifest_source_for("task") or "")
    assert [manifest.directive_type for manifest in registry.manifests()] == registry.supported_types()


def test_registry_creates_renderer_instances_from_registered_manifest() -> None:
    registry = _registry()

    task_renderer = registry.create("task")
    py_renderer = registry.create("py")

    assert isinstance(task_renderer, TaskRenderer)
    assert isinstance(py_renderer, PyRenderer)
    assert registry.renderer_for("table") is TableRenderer
    assert registry.create("missing") is None


def test_registry_rejects_duplicate_renderer_registration() -> None:
    registry = CapabilityRegistry()
    registry.register(TaskRenderer)

    class DuplicateTaskRenderer:
        manifest_path = TaskRenderer.manifest_path

        def render(self, directive, ctx):
            raise NotImplementedError

    try:
        registry.register(DuplicateTaskRenderer)
    except ValueError as exc:
        assert "renderer already registered" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected duplicate renderer registration to fail")


def test_registry_filters_render_context_by_declared_capabilities(tmp_path: Path) -> None:
    registry = _registry()
    base_ctx = RenderContext(
        events=object(),  # type: ignore[arg-type]
        py_results={"budget-check": object()},  # type: ignore[dict-item]
        document_path=tmp_path / "example.folio",
        source_text="hidden",
        directives_by_id={"call-finance": object()},  # type: ignore[dict-item]
    )

    task_ctx = registry.context_for("task", base_ctx)
    assert task_ctx.events is base_ctx.events
    assert task_ctx.directives_by_id is base_ctx.directives_by_id
    assert task_ctx.py_results is None
    assert task_ctx.file_access is None
    assert task_ctx.source_text is None

    file_ctx = registry.context_for("file", base_ctx)
    assert file_ctx.file_access is not None
    assert file_ctx.document_path == base_ctx.document_path
    assert file_ctx.events is None
    assert file_ctx.py_results is None
    assert file_ctx.directives_by_id is None
