from __future__ import annotations

from folio.core.registry import CapabilityRegistry
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
        manifest = TaskRenderer.manifest

        def render(self, directive, ctx):
            raise NotImplementedError

    try:
        registry.register(DuplicateTaskRenderer)
    except ValueError as exc:
        assert "renderer already registered" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected duplicate renderer registration to fail")
