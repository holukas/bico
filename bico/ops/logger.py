import logging
import sys
from pathlib import Path

# Shared log formatting, used by the main logger and by the per-file workers
# (bico.ops.parallel) so that worker logs replayed into the main log are
# byte-consistent with lines written directly by the main logger.
LOG_FORMAT = '%(asctime)s | %(levelname)-7s | %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def get_formatter():
    """The shared log formatter (file output and replayed worker output)."""
    return logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)


def setup_logger(settings_dict, console: bool = True):
    """Create the main run logger writing to this run's log file.

    Parameters
    ----------
    settings_dict : dict
        Run settings; must contain 'run_id' and 'dir_out_run_log'.
    console : bool
        If True, also stream log output to stdout. The TUI sets this False
        (it routes the logger into an on-screen console widget instead, so a
        stdout stream would corrupt the terminal UI).
    """
    logfile_name = f"{settings_dict['run_id']}.log"
    logfile_path = settings_dict['dir_out_run_log'] / logfile_name
    logger = create_logger(logfile_path=logfile_path, name='main_logger', console=console)
    return logger


def create_logger(name: str, logfile_path: Path = None, console: bool = True):
    """
    Create a named logger that logs to a file (and optionally to stdout).

    Handlers are reset on every call so that each run gets a fresh file handler
    pointing at that run's log file. (The logger name is reused across runs in a
    long-lived process such as the TUI, so without a reset the first run's
    handlers would persist and keep writing to the first run's log file.)

    Parameters
    ----------
    name : str
        Logger name.
    logfile_path : Path
        Path to the log file to which the log output is saved.
    console : bool
        If True, attach a stdout stream handler in addition to the file handler.

    Returns
    -------
    logging.Logger
    """

    logger = logging.getLogger(name)

    # Reset any handlers from a previous run before attaching fresh ones (see
    # docstring): close file handlers so the previous run's log file is released.
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    logger.setLevel(logging.DEBUG)

    formatter = get_formatter()

    file_handler = logging.FileHandler(logfile_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if console:
        stream_handler = logging.StreamHandler(stream=sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger
