"""Modal screens for the bico TUI: the help overlay and the path pickers.

``HelpScreen`` shows the help text; ``DirectoryPickerScreen`` and
``FilePickerScreen`` share ``_PickerScreen`` (an editable path field over a
``DirectoryTree``). All are split out of ``app.py`` and re-exported there.
"""
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Markdown, Static

from bico.tui.constants import HELP_MD


class HelpScreen(ModalScreen):
    """Scrollable help overlay explaining the TUI."""

    BINDINGS = [('escape', 'close', 'Close'), ('q', 'close', 'Close'), ('h', 'close', 'Close')]

    def compose(self) -> ComposeResult:
        with Vertical(id='help'):
            yield Static('bico — help   (esc to close)', classes='help-title')
            with VerticalScroll(id='help-body'):
                yield Markdown(HELP_MD)
            with Horizontal(id='help-actions'):
                close = Button('Close', id='help-close', variant='primary')
                close.tooltip = 'Close this help (or press Esc)'
                yield close

    @on(Button.Pressed, '#help-close')
    def _close(self) -> None:
        self.dismiss()

    @on(Markdown.LinkClicked)
    def _open_link(self, event: Markdown.LinkClicked) -> None:
        # Markdown does not follow links itself; open them in the browser.
        self.app.open_url(event.href)

    def action_close(self) -> None:
        self.dismiss()


class _PickerScreen(ModalScreen[str]):
    """Shared modal browser: an editable path field over a ``DirectoryTree``.

    Subclasses supply the title/labels (``compose``) and decide what counts as a
    valid pick (the tree-selection, path-submit and OK handlers). Dismisses with
    the chosen path string, or None if cancelled.

    Only the handlers common to every picker live here. Textual dispatches every
    ``@on`` handler found across the MRO (deduped by function, not by name), so an
    override in a subclass would *also* run the base version — the differing
    handlers must therefore stay in the subclasses, not here.
    """

    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, start_path: str):
        super().__init__()
        path = Path(start_path) if start_path else Path.home()
        # Fall back gracefully if the configured path no longer exists.
        while not path.is_dir() and path != path.parent:
            path = path.parent
        if not path.is_dir():
            path = Path.home()
        self._root = path
        self._selected = str(path)

    def _set_selected(self, path) -> None:
        """Update the selected path and reflect it in the editable path field."""
        self._selected = str(path)
        self.query_one('#picker-path', Input).value = self._selected

    def _goto(self, path) -> None:
        """Re-root the tree at path (if it is a directory) and select it."""
        path = Path(path)
        if path.is_dir():
            self.query_one('#picker-tree', DirectoryTree).path = str(path)
            self._set_selected(path)
            return True
        return False

    @on(Button.Pressed, '#picker-up')
    def _on_up(self) -> None:
        tree = self.query_one('#picker-tree', DirectoryTree)
        self._goto(Path(tree.path).parent)

    @on(Button.Pressed, '#picker-cancel')
    def _on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class DirectoryPickerScreen(_PickerScreen):
    """Modal folder browser. Dismisses with the chosen folder, or None if cancelled."""

    def compose(self) -> ComposeResult:
        with Vertical(id='picker'):
            yield Static('Select a folder (type or paste a path, then Enter)',
                         classes='picker-title')
            yield Input(self._selected, id='picker-path',
                        placeholder='Paste a folder path and press Enter')
            yield DirectoryTree(str(self._root), id='picker-tree')
            with Horizontal(id='picker-actions'):
                up = Button('Up', id='picker-up')
                up.tooltip = 'Go to the parent folder'
                yield up
                ok = Button('Select folder', id='picker-ok', variant='success')
                ok.tooltip = 'Use the folder in the path field above'
                yield ok
                cancel = Button('Cancel', id='picker-cancel')
                cancel.tooltip = 'Close without choosing'
                yield cancel

    @on(DirectoryTree.DirectorySelected)
    def _on_dir_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self._set_selected(event.path)

    @on(Input.Submitted, '#picker-path')
    def _on_path_submitted(self, event: Input.Submitted) -> None:
        # Jump the tree to a typed/pasted path.
        if not self._goto(event.value.strip()):
            self.notify(f'Not a folder: {event.value}', severity='warning')

    @on(Button.Pressed, '#picker-ok')
    def _on_ok(self) -> None:
        # The editable path field is the source of truth.
        self.dismiss(self.query_one('#picker-path', Input).value.strip())


class FilePickerScreen(_PickerScreen):
    """Modal file browser. Dismisses with the chosen file path, or None if cancelled.

    Clicking a folder expands it; clicking a file selects it; OK is gated on the
    path field naming an existing file. When the start path is a file, the tree
    opens at its folder with that file pre-selected.
    """

    def __init__(self, start_path: str, title: str = 'Select a file'):
        self._title = title
        start = Path(start_path) if start_path else None
        self._initial_file = str(start) if start and start.is_file() else ''
        # Root the tree at the file's folder when a file path is given.
        super().__init__(str(start.parent) if self._initial_file else start_path)
        if self._initial_file:
            self._selected = self._initial_file

    def compose(self) -> ComposeResult:
        with Vertical(id='picker'):
            yield Static(f'{self._title} (type or paste a path, then Enter)',
                         classes='picker-title')
            yield Input(self._selected, id='picker-path',
                        placeholder='Paste a file path and press Enter')
            yield DirectoryTree(str(self._root), id='picker-tree')
            with Horizontal(id='picker-actions'):
                up = Button('Up', id='picker-up')
                up.tooltip = 'Go to the parent folder'
                yield up
                ok = Button('Select file', id='picker-ok', variant='success')
                ok.tooltip = 'Use the file in the path field above'
                yield ok
                cancel = Button('Cancel', id='picker-cancel')
                cancel.tooltip = 'Close without choosing'
                yield cancel

    @on(DirectoryTree.FileSelected)
    def _on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self._set_selected(event.path)

    @on(Input.Submitted, '#picker-path')
    def _on_path_submitted(self, event: Input.Submitted) -> None:
        # A typed file path selects it (opening the tree at its folder); a folder
        # path re-roots the tree there.
        value = event.value.strip()
        path = Path(value)
        if path.is_file():
            self._goto(path.parent)
            self._set_selected(path)
        elif not self._goto(value):
            self.notify(f'Not a file or folder: {value}', severity='warning')

    @on(Button.Pressed, '#picker-ok')
    def _on_ok(self) -> None:
        value = self.query_one('#picker-path', Input).value.strip()
        if not Path(value).is_file():
            self.notify(f'Not a file: {value}', severity='warning')
            return
        self.dismiss(value)
