from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Input, Static, TextArea

from folio.core.models import Directive, DocumentModel, ProseBlock
from folio.core.registry import CapabilityRegistry
from folio.renderers.base import AdvisoryAction, AdvisorySpec, RenderContext, widget_id_fragment


@dataclass(slots=True)
class RenderBlock:
    start_line: int
    end_line: int
    estimated_height: int
    build_widget: Callable[[], Widget]


class AdvisoryWidget(Vertical):
    def __init__(self, advisory: AdvisorySpec, ctx: RenderContext) -> None:
        super().__init__(classes=f"advisory-widget advisory-{advisory.level}")
        self.advisory = advisory
        self.ctx = ctx

    def compose(self) -> ComposeResult:
        yield Static(self.advisory.title, classes="advisory-title", markup=False)
        yield Static(self.advisory.message, classes="advisory-message", markup=False)
        if self.advisory.actions:
            with Horizontal(classes="advisory-actions"):
                for action in self.advisory.actions:
                    yield Button(
                        action.label,
                        id=f"advisory-action-{self.advisory.id}-{action.key}",
                        compact=True,
                    )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        prefix = f"advisory-action-{self.advisory.id}-"
        button_id = event.button.id or ""
        if not button_id.startswith(prefix) or self.ctx.events is None:
            return
        key = button_id[len(prefix) :]
        for action in self.advisory.actions:
            if action.key == key:
                payload = dict(action.payload)
                payload["advisory_id"] = self.advisory.id
                self.ctx.events.emit(action.event_name, **payload)
                event.stop()
                return


class DirectiveBlock(Vertical):
    can_focus = True

    def __init__(self, directive: Directive, inner: Widget, source_text: str, show_source: bool, ctx: RenderContext) -> None:
        super().__init__(
            id=f"directive-block-{widget_id_fragment(directive.instance_key())}",
            classes="directive-container",
        )
        self.directive = directive
        self.inner = inner
        self.source_text = source_text
        self.show_source = show_source
        self.ctx = ctx
        self.key_fragment = widget_id_fragment(directive.instance_key())

    def compose(self) -> ComposeResult:
        with Horizontal(classes="directive-toolbar"):
            yield Static(self.directive.title(), classes="directive-title", markup=False)
        if self.show_source:
            if "\n" in self.source_text:
                yield DirectiveSourceEditor(
                    self.directive,
                    self.source_text,
                    self.key_fragment,
                    self.ctx,
                )
            else:
                yield DirectiveSourceInput(
                    self.directive,
                    self.source_text,
                    self.key_fragment,
                    self.ctx,
                )
        else:
            yield self.inner

    def on_key(self, event: events.Key) -> None:
        if self.show_source or self.ctx.events is None:
            return
        if event.key in {"enter", "e"}:
            self.ctx.events.emit("directive.edit_open", directive=self.directive)
            event.stop()

    def on_click(self, event: events.Click) -> None:
        self.focus()
        if self.show_source or self.ctx.events is None:
            return
        if getattr(event, "chain", 1) >= 2:
            self.ctx.events.emit("directive.edit_open", directive=self.directive)
            event.stop()


class DirectiveSourceEditor(TextArea):
    COMPONENT_CLASSES = TextArea.COMPONENT_CLASSES

    def __init__(self, directive: Directive, source_text: str, key_fragment: str, ctx: RenderContext) -> None:
        super().__init__(
            source_text,
            id=f"directive-source-{key_fragment}",
            classes="directive-source",
            language="markdown",
            soft_wrap=False,
            show_line_numbers=False,
        )
        self.directive = directive
        self.ctx = ctx
        self._last_synced_text = source_text
        self._sync_height(source_text)

    def on_mount(self) -> None:
        self._sync_height(self.text)
        self.focus()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area is not self:
            return
        self._sync_height(self.text)
        if self.ctx.events is None or self.text == self._last_synced_text:
            return
        self._last_synced_text = self.text
        self.ctx.events.emit(
            "directive.edit_buffer",
            directive=self.directive,
            new_text=self.text,
        )

    def on_key(self, event: events.Key) -> None:
        if self.ctx.events is None:
            return
        if event.key == "ctrl+s":
            self.ctx.events.emit("directive.edit_save", directive=self.directive, new_text=self.text)
            event.stop()
            return
        if event.key == "escape":
            self.ctx.events.emit("directive.edit_cancel", directive=self.directive)
            event.stop()
            return

    def _sync_height(self, text: str) -> None:
        line_count = max(3, len(text.splitlines()) + 2)
        self.styles.height = line_count


class DirectiveSourceInput(Input):
    def __init__(self, directive: Directive, source_text: str, key_fragment: str, ctx: RenderContext) -> None:
        super().__init__(
            source_text,
            id=f"directive-source-{key_fragment}",
            classes="directive-source-input",
        )
        self.directive = directive
        self.ctx = ctx

    def on_mount(self) -> None:
        self.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input is not self or self.ctx.events is None:
            return
        self.ctx.events.emit(
            "directive.edit_buffer",
            directive=self.directive,
            new_text=self.value,
        )

    def on_key(self, event: events.Key) -> None:
        if self.ctx.events is None:
            return
        if event.key == "ctrl+s":
            self.ctx.events.emit("directive.edit_save", directive=self.directive, new_text=self.value)
            event.stop()
            return
        if event.key == "escape":
            self.ctx.events.emit("directive.edit_cancel", directive=self.directive)
            event.stop()
            return


class DocumentView(VerticalScroll):
    VIEWPORT_MARGIN = 12
    TITLE_HEIGHT = 2

    def __init__(self, *children: Widget, **kwargs) -> None:
        super().__init__(*children, **kwargs)
        self._blocks: list[RenderBlock] = []
        self._title = "Rendered"
        self._window_signature: tuple[int, int, int, int] | None = None
        self._rendering_window = False
        self._pending_force = False

    def render_document(
        self,
        model: DocumentModel,
        registry: CapabilityRegistry,
        ctx: RenderContext,
        *,
        title: str = "Rendered",
    ) -> None:
        self._title = title
        source_text = ctx.source_text if ctx.source_text is not None else model.text
        self._source_lines = source_text.splitlines()
        self._blocks = self._build_blocks(model, registry, ctx)
        self._schedule_render_visible_window(force=True)

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        if round(old_value) != round(new_value):
            self._schedule_render_visible_window()

    def on_resize(self, _event: events.Resize) -> None:
        self._schedule_render_visible_window(force=True)

    def _schedule_render_visible_window(self, *, force: bool = False) -> None:
        self._pending_force = self._pending_force or force
        self.call_next(self._render_visible_window)

    async def _render_visible_window(self) -> None:
        if self._rendering_window:
            return
        force = self._pending_force
        self._pending_force = False
        start_index, end_index, top_spacer, bottom_spacer = self._window_bounds()
        signature = (start_index, end_index, top_spacer, bottom_spacer)
        if not force and signature == self._window_signature:
            return

        self._rendering_window = True
        try:
            widgets: list[Widget] = [Static(self._title, classes="pane-title")]
            if top_spacer > 0:
                widgets.append(self._spacer(top_spacer))

            for block in self._blocks[start_index:end_index]:
                widgets.append(block.build_widget())

            if bottom_spacer > 0:
                widgets.append(self._spacer(bottom_spacer))

            async with self.batch():
                await self.remove_children()
                await self.mount_all(widgets)
            self._window_signature = signature
            self.refresh(repaint=True, layout=True)
        finally:
            self._rendering_window = False
            if self._pending_force:
                self.call_next(self._render_visible_window)

    def _window_bounds(self) -> tuple[int, int, int, int]:
        if not self._blocks:
            return (0, 0, 0, 0)

        viewport_height = max(1, self.container_size.height - self.TITLE_HEIGHT)
        visible_top = max(0, round(self.scroll_y) - self.TITLE_HEIGHT)
        target_top = max(0, visible_top - self.VIEWPORT_MARGIN)
        target_bottom = visible_top + viewport_height + self.VIEWPORT_MARGIN

        total_height = sum(block.estimated_height for block in self._blocks)
        top_spacer = 0
        start_index = 0

        while start_index < len(self._blocks):
            next_height = self._blocks[start_index].estimated_height
            if top_spacer + next_height > target_top:
                break
            top_spacer += next_height
            start_index += 1

        end_index = start_index
        consumed_height = top_spacer
        while end_index < len(self._blocks) and consumed_height < target_bottom:
            consumed_height += self._blocks[end_index].estimated_height
            end_index += 1

        bottom_spacer = max(0, total_height - consumed_height)
        return (start_index, end_index, top_spacer, bottom_spacer)

    def _build_blocks(
        self,
        model: DocumentModel,
        registry: CapabilityRegistry,
        ctx: RenderContext,
    ) -> list[RenderBlock]:
        blocks: list[RenderBlock] = []
        for advisory in ctx.advisories or []:
            blocks.append(
                RenderBlock(
                    start_line=-1,
                    end_line=-1,
                    estimated_height=self._estimate_advisory_height(advisory),
                    build_widget=lambda advisory=advisory, ctx=ctx: AdvisoryWidget(advisory, ctx),
                )
            )

        prose_index = 0

        for line_no, _line in enumerate(model.text.splitlines() or [""]):
            while prose_index < len(model.prose) and model.prose[prose_index].start_line == line_no:
                block = model.prose[prose_index]
                if any(part.strip() for part in block.lines):
                    blocks.append(
                        RenderBlock(
                            start_line=block.start_line,
                            end_line=block.end_line,
                            estimated_height=self._estimate_prose_height(block),
                            build_widget=lambda lines=tuple(block.lines): Static("\n".join(lines), markup=False),
                        )
                    )
                prose_index += 1

            for directive in model.directive_index.directives_starting_at(line_no):
                renderer = registry.create(directive.type)
                renderer_ctx = registry.context_for(directive.type, ctx) if renderer is not None else ctx
                blocks.append(
                    RenderBlock(
                        start_line=directive.start_line,
                        end_line=directive.end_line,
                        estimated_height=self._estimate_directive_height(directive, ctx),
                        build_widget=self._widget_factory(directive, renderer, renderer_ctx, ctx),
                    )
                )

        return blocks

    def _estimate_prose_height(self, block: ProseBlock) -> int:
        return max(1, len(block.lines))

    def _estimate_directive_height(self, directive: Directive, ctx: RenderContext) -> int:
        source_lines = max(1, len(self._directive_source_text(directive).splitlines()) or 1)
        if directive.instance_key() in (ctx.directive_source_view or set()):
            return source_lines + 3

        if directive.type == "task":
            return max(source_lines, 4 + max(0, len(directive.body) - 1)) + 1

        if directive.type == "py":
            code_lines = max(1, len(directive.body) or 1)
            run_mode = directive.params.get("run", '"manual"').strip('"')
            result = (ctx.py_results or {}).get(directive.key())
            if result is None:
                output_lines = 1
            elif result.status == "ok":
                output_lines = max(1, len(result.stdout) or 1)
                if result.table is not None:
                    output_lines += 1
            else:
                output_lines = max(1, len((result.error or "").splitlines()) or 1)
            return code_lines + output_lines + (1 if run_mode == "manual" else 0) + 4

        if directive.type == "sh":
            return 4

        if directive.type == "sh-output":
            body_lines = max(1, len(directive.body) or 1)
            return body_lines + 3

        if directive.type == "table":
            rows = self._table_row_count(directive, ctx)
            return max(source_lines, rows + 5)

        if directive.type == "file":
            return max(source_lines, self._preview_lines(directive) + 4)

        if directive.type == "contact":
            limit = self._limit_lines(directive, default=6)
            return max(source_lines, 4 + (limit * 5))

        if directive.type == "email":
            if directive.id == "draft":
                body_lines = max(6, len(directive.body) + 8)
                return max(source_lines, body_lines)
            limit = self._limit_lines(directive, default=20)
            return max(source_lines, 12 + limit + 12)

        if directive.type == "note":
            return max(source_lines, max(4, len(directive.body) + 4))

        return max(source_lines, 4)

    def _table_row_count(self, directive: Directive, ctx: RenderContext) -> int:
        if directive.body:
            return max(1, len([line for line in directive.body if line.strip()]))

        source = directive.params.get("source", '"inline"').strip('"')
        result = (ctx.py_results or {}).get(source)
        if result is not None and result.table is not None:
            return max(1, len(result.table))
        return 2

    def _preview_lines(self, directive: Directive) -> int:
        return self._limit_lines(directive, default=20, param_name="lines")

    def _limit_lines(self, directive: Directive, default: int, param_name: str = "limit") -> int:
        raw_lines = directive.params.get("lines")
        if param_name != "lines":
            raw_lines = directive.params.get(param_name)
        if raw_lines is None:
            return default
        try:
            return max(1, int(raw_lines.strip('"')))
        except ValueError:
            return default

    def _spacer(self, height: int) -> Static:
        spacer = Static("", classes="viewport-spacer")
        spacer.styles.height = height
        return spacer

    def _widget_factory(
        self,
        directive: Directive,
        renderer: object | None,
        renderer_ctx: RenderContext,
        display_ctx: RenderContext,
    ) -> Callable[[], Widget]:
        source_text = self._directive_source_text(directive)

        def build(
            directive: Directive = directive,
            renderer: object | None = renderer,
            renderer_ctx: RenderContext = renderer_ctx,
            display_ctx: RenderContext = display_ctx,
        ) -> Widget:
            inner = renderer.render(directive, renderer_ctx) if renderer is not None else Static(directive.header_line, markup=False)
            return DirectiveBlock(
                directive=directive,
                inner=inner,
                source_text=source_text,
                show_source=directive.instance_key() in (display_ctx.directive_source_view or set()),
                ctx=display_ctx,
            )

        return build

    def _directive_source_text(self, directive: Directive) -> str:
        edit_buffers = getattr(self, "_current_edit_buffers", None)
        if edit_buffers and directive.instance_key() in edit_buffers:
            return edit_buffers[directive.instance_key()]
        lines = getattr(self, "_source_lines", None)
        if lines is None:
            return directive.header_line
        return "\n".join(lines[directive.start_line : directive.end_line + 1])

    def _estimate_advisory_height(self, advisory: AdvisorySpec) -> int:
        action_rows = 1 if advisory.actions else 0
        return max(3, len(advisory.message.splitlines()) + action_rows + 2)
