"""Textual terminal UI for bico.

Importing this subpackage pulls in Textual; the conversion modules and tests do
not import it, so the package core stays UI-free.
"""
from bico.tui.app import BicoApp, run_tui

__all__ = ['BicoApp', 'run_tui']
