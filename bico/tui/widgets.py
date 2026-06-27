"""Custom Textual widgets for the bico TUI.

``PathDropInput`` is a path field that fills itself from a dragged-in file or
folder; ``SelectableRichLog`` is a ``RichLog`` whose text can be selected with
the mouse and copied. Both are split out of ``app.py`` and re-exported there.
"""
from rich.style import Style
from textual import events
from textual.strip import Strip
from textual.widgets import Input, RichLog

from bico.tui.constants import _dropped_folder


class PathDropInput(Input):
    """A path field that fills itself from a dragged-in file or folder.

    Most terminals paste a dropped file/folder as its path; when the pasted text
    is a real path this sets the field to the folder (a dropped file yields its
    parent folder), so source/output folders can be set by dropping instead of
    browsing. Any other paste behaves like a normal Input paste.

    A terminal routes a dropped path to the *focused* widget, so click (focus) the
    field before dropping onto it.
    """

    def _on_paste(self, event: events.Paste) -> None:
        folder = _dropped_folder(event.text)
        if folder is not None:
            self.value = folder
            self.cursor_position = len(folder)
            # Textual dispatches `_on_paste` for every class in the MRO; only
            # prevent_default() stops Input's own handler from then inserting the
            # raw path. stop() keeps it from bubbling to the app paste handler.
            event.prevent_default()
            event.stop()
        # Otherwise do nothing: Textual still calls Input._on_paste (normal paste).


class SelectableRichLog(RichLog):
    """A ``RichLog`` whose text can be selected with the mouse and copied.

    Plain ``RichLog`` (Textual 8.2) renders pre-styled strips and never attaches
    the per-cell content offsets the screen uses to map a mouse drag to text, nor
    does it draw the selection or expose the selected text — so dragging over it
    selects nothing. This subclass adds the three missing pieces: it stamps each
    rendered line with its content offset (so a drag forms a selection), paints
    the selection highlight, and returns the selected text for copy (Ctrl+C).
    """

    def _selection_style(self) -> Style:
        """Selection highlight: only a background colour, so the text keeps its own
        colour and stays readable. (The theme's ``screen--selection`` foreground is
        ``transparent`` = "keep existing", which, applied as a base style, would turn
        plain text invisible — so we take just its background.)"""
        comp = self.screen.get_component_rich_style('screen--selection')
        return Style(bgcolor=comp.bgcolor) if comp.bgcolor else Style(reverse=True)

    @staticmethod
    def _highlight_span(line: Strip, start: int, end: int, style: Style) -> Strip:
        """Return `line` with the background of cells [start, end) set to `style`."""
        start = max(0, start)
        end = min(end, line.cell_length)
        if end <= start:
            return line
        before, selected, after = line.divide([start, end, line.cell_length])
        return Strip.join([before, selected.apply_style(style), after])

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        content_y = scroll_y + y
        selection = self.text_selection
        if selection is None:
            # No selection: keep the base (cached) rendering, but stamp offsets so
            # a future drag can resolve the cell under the mouse to content text.
            return super().render_line(y).apply_offsets(scroll_x, content_y)
        width = self.scrollable_content_region.width
        if content_y >= len(self.lines):
            return Strip.blank(width, self.rich_style).apply_offsets(scroll_x, content_y)
        line = self.lines[content_y]
        span = selection.get_span(content_y)
        if span is not None:
            start, end = span
            if end == -1:
                end = line.cell_length
            line = self._highlight_span(line, start, end, self._selection_style())
        line = line.crop_extend(scroll_x, scroll_x + width, self.rich_style)
        line = line.apply_style(self.rich_style)
        return line.apply_offsets(scroll_x, content_y)

    def get_selection(self, selection):
        text = '\n'.join(strip.text for strip in self.lines)
        return selection.extract(text), '\n'

    def selection_updated(self, selection) -> None:
        self.refresh()
