import logging

try:
    from rich.console import Console
    from rich.logging import RichHandler

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def get_logger(name: str = "task") -> logging.Logger:
    """Return a configured logger for this project."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    if HAS_RICH:
        # Force terminal styling so logs remain rich even in non-TTY contexts.
        handler = RichHandler(
            console=Console(force_terminal=True),
            show_time=True,
            show_level=True,
            show_path=False,
            markup=False,
            rich_tracebacks=True,
        )
        handler.setFormatter(logging.Formatter("%(name)s | %(message)s"))
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
