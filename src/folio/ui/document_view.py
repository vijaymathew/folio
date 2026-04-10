from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from folio.core.models import DocumentModel
from folio.core.registry import CapabilityRegistry
from folio.renderers.base import RenderContext


class DocumentView(VerticalScroll):
    def render_document(
        self,
        model: DocumentModel,
        registry: CapabilityRegistry,
        ctx: RenderContext,
        *,
        title: str = "Rendered",
    ) -> None:
        self.remove_children()
        self.mount(Static(title, classes="pane-title"))

        for widget in self._build_widgets(model, registry, ctx):
            self.mount(widget)

        self.refresh(repaint=True, layout=True)

    def _build_widgets(
        self,
        model: DocumentModel,
        registry: CapabilityRegistry,
        ctx: RenderContext,
    ) -> list[Widget]:
        widgets: list[Widget] = []
        prose_index = 0

        for line_no, _line in enumerate(model.text.splitlines() or [""]):
            while prose_index < len(model.prose) and model.prose[prose_index].start_line == line_no:
                block = model.prose[prose_index]
                if any(part.strip() for part in block.lines):
                    widgets.append(Static("\n".join(block.lines), markup=False))
                prose_index += 1

            for directive in model.directive_index.directives_starting_at(line_no):
                renderer = registry.create(directive.type)
                widgets.append(
                    renderer.render(directive, ctx) if renderer else Static(directive.header_line, markup=False)
                )

        return widgets
