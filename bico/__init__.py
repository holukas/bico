"""bico - Binary Converter for ETH eddy covariance raw data.

Kept import-light on purpose: importing this package must not pull in Textual
(so the conversion modules and tests can be imported without the TUI). The TUI
lives in ``bico.tui`` and is imported lazily by the entry point. Use the console
entry point ``bico`` or ``python -m bico`` to run the application.
"""
