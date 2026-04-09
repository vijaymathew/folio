from __future__ import annotations

from collections.abc import Callable

from folio.renderers.base import Renderer


RendererFactory = Callable[[], Renderer]


class CapabilityRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, RendererFactory] = {}

    def register(self, directive_type: str, factory: RendererFactory) -> None:
        self._factories[directive_type] = factory

    def create(self, directive_type: str) -> Renderer | None:
        factory = self._factories.get(directive_type)
        return factory() if factory else None
