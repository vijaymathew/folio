from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TypeAlias

from folio.renderers.base import (
    ActionSpec,
    CapabilitySpec,
    ParamSpec,
    RenderContext,
    Renderer,
    RendererFileAccess,
    RendererManifest,
    SandboxSpec,
)


RendererType: TypeAlias = type[Renderer]


class CapabilityRegistry:
    def __init__(self) -> None:
        self._renderers: dict[str, RendererType] = {}
        self._manifests: dict[str, RendererManifest] = {}
        self._manifest_sources: dict[str, str] = {}

    def register(self, renderer_cls: RendererType) -> None:
        manifest_path = getattr(renderer_cls, "manifest_path", None)
        if manifest_path is None:
            raise ValueError(f"{renderer_cls.__name__} must declare manifest_path")
        manifest_source = Path(manifest_path).read_text(encoding="utf-8")
        manifest = self._load_manifest(Path(manifest_path), manifest_source)
        directive_type = manifest.directive_type
        existing = self._renderers.get(directive_type)
        if existing is not None and existing is not renderer_cls:
            raise ValueError(f"renderer already registered for directive type '{directive_type}'")
        self._renderers[directive_type] = renderer_cls
        self._manifests[directive_type] = manifest
        self._manifest_sources[directive_type] = manifest_source
        setattr(renderer_cls, "manifest", manifest)

    def create(self, directive_type: str) -> Renderer | None:
        renderer_cls = self._renderers.get(directive_type)
        return renderer_cls() if renderer_cls else None

    def renderer_for(self, directive_type: str) -> RendererType | None:
        return self._renderers.get(directive_type)

    def manifest_for(self, directive_type: str) -> RendererManifest | None:
        return self._manifests.get(directive_type)

    def manifests(self) -> list[RendererManifest]:
        return [self._manifests[key] for key in sorted(self._manifests)]

    def manifest_source_for(self, directive_type: str) -> str | None:
        return self._manifest_sources.get(directive_type)

    def context_for(self, directive_type: str, base_ctx: RenderContext) -> RenderContext:
        manifest = self._manifests.get(directive_type)
        if manifest is None:
            return RenderContext()

        caps = manifest.capabilities
        return RenderContext(
            events=base_ctx.events if caps.events else None,
            py_results=base_ctx.py_results if caps.py_results else None,
            web_results=base_ctx.web_results if caps.web_results else None,
            email_selection=base_ctx.email_selection if caps.email_selection else None,
            document_path=base_ctx.document_path if caps.document_path else None,
            file_access=RendererFileAccess(base_ctx.document_path) if (caps.filesystem_read or caps.filesystem_write) else None,
            source_text=base_ctx.source_text if caps.source_text else None,
            directives_by_id=base_ctx.directives_by_id if caps.directive_lookup else None,
            directive_find=base_ctx.directive_find if caps.directive_lookup else None,
            document_trusted=base_ctx.document_trusted if caps.trust_state else True,
            pending_shell_confirmations=(
                set(base_ctx.pending_shell_confirmations or set()) if caps.trust_state else None
            ),
        )

    def supported_types(self) -> list[str]:
        return sorted(self._renderers)

    def _load_manifest(self, manifest_path: Path, source: str) -> RendererManifest:
        data = tomllib.loads(source)
        renderer = data.get("renderer", {})
        capabilities = data.get("capabilities", {})
        sandbox = data.get("sandbox", {})
        params = [self._param_spec(item) for item in data.get("params", [])]
        actions = [self._action_spec(item) for item in data.get("actions", [])]

        return RendererManifest(
            directive_type=renderer["directive_type"],
            display_name=renderer["display_name"],
            description=renderer["description"],
            version=renderer.get("version", "1.0.0"),
            params=params,
            actions=actions,
            capabilities=CapabilitySpec(
                events=bool(capabilities.get("events", False)),
                py_results=bool(capabilities.get("py_results", False)),
                web_results=bool(capabilities.get("web_results", False)),
                email_selection=bool(capabilities.get("email_selection", False)),
                document_path=bool(capabilities.get("document_path", False)),
                source_text=bool(capabilities.get("source_text", False)),
                directive_lookup=bool(capabilities.get("directive_lookup", False)),
                filesystem_read=bool(capabilities.get("filesystem_read", False)),
                filesystem_write=bool(capabilities.get("filesystem_write", False)),
                trust_state=bool(capabilities.get("trust_state", False)),
            ),
            sandbox=SandboxSpec(
                execution_mode=str(sandbox.get("execution_mode", "in-process")),
                network=bool(sandbox.get("network", False)),
                storage=bool(sandbox.get("storage", False)),
                document_text=bool(sandbox.get("document_text", False)),
                allowed_origins=[str(item) for item in sandbox.get("allowed_origins", [])],
                max_fetch_bytes=int(sandbox.get("max_fetch_bytes", 262144)),
                timeout_seconds=float(sandbox.get("timeout_seconds", 5.0)),
                notes=str(sandbox.get("notes", "")),
            ),
            supports_inline_source=bool(renderer.get("supports_inline_source", False)),
            supports_editing=bool(renderer.get("supports_editing", False)),
            manifest_path=manifest_path,
        )

    def _param_spec(self, data: dict[str, object]) -> ParamSpec:
        return ParamSpec(
            name=str(data["name"]),
            required=bool(data.get("required", False)),
            default=str(data["default"]) if "default" in data else None,
            description=str(data.get("description", "")),
        )

    def _action_spec(self, data: dict[str, object]) -> ActionSpec:
        payload_schema = data.get("payload_schema", {})
        if not isinstance(payload_schema, dict):
            payload_schema = {}
        return ActionSpec(
            name=str(data["name"]),
            description=str(data.get("description", "")),
            payload_schema={str(key): str(value) for key, value in payload_schema.items()},
        )
