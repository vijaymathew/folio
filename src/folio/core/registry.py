from __future__ import annotations

from typing import TypeAlias

from folio.renderers.base import Renderer, RendererManifest


RendererType: TypeAlias = type[Renderer]


class CapabilityRegistry:
    def __init__(self) -> None:
        self._renderers: dict[str, RendererType] = {}
        self._manifests: dict[str, RendererManifest] = {}

    def register(self, renderer_cls: RendererType) -> None:
        manifest = renderer_cls.manifest
        directive_type = manifest.directive_type
        existing = self._renderers.get(directive_type)
        if existing is not None and existing is not renderer_cls:
            raise ValueError(f"renderer already registered for directive type '{directive_type}'")
        self._renderers[directive_type] = renderer_cls
        self._manifests[directive_type] = manifest

    def create(self, directive_type: str) -> Renderer | None:
        renderer_cls = self._renderers.get(directive_type)
        return renderer_cls() if renderer_cls else None

    def renderer_for(self, directive_type: str) -> RendererType | None:
        return self._renderers.get(directive_type)

    def manifest_for(self, directive_type: str) -> RendererManifest | None:
        return self._manifests.get(directive_type)

    def manifests(self) -> list[RendererManifest]:
        return [self._manifests[key] for key in sorted(self._manifests)]

    def supported_types(self) -> list[str]:
        return sorted(self._renderers)
